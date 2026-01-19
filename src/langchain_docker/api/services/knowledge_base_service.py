"""Knowledge base service for RAG functionality.

This service provides high-level operations for document ingestion,
search, and management. It orchestrates:
- Document processor for parsing (PDF via Docling, MD, TXT)
- Embedding service for vector embeddings
- OpenSearch store for vector similarity search
- Graph RAG service (optional) for entity-aware retrieval
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from itertools import zip_longest
from typing import TYPE_CHECKING, Any

from langchain_docker.api.services.document_processor import DocumentProcessor, ProcessedDocument
from langchain_docker.api.services.embedding_service import EmbeddingService
from langchain_docker.api.services.opensearch_store import OpenSearchStore, SearchResult
from langchain_docker.core.config import get_rag_default_top_k, is_graph_rag_enabled

if TYPE_CHECKING:
    from langchain_docker.api.services.graph_rag_service import GraphRAGService

logger = logging.getLogger(__name__)


@dataclass
class KBDocument:
    """Knowledge base document metadata."""

    id: str
    filename: str
    content_type: str
    chunk_count: int
    size: int
    collection: str | None
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class KBCollection:
    """Knowledge base collection."""

    id: str
    name: str
    document_count: int
    color: str | None = None


@dataclass
class KBStats:
    """Knowledge base statistics."""

    total_documents: int
    total_chunks: int
    total_collections: int
    index_size: str
    last_updated: str
    available: bool


class KnowledgeBaseService:
    """Service for managing the knowledge base.

    Provides high-level operations for document ingestion, search,
    and management. Orchestrates the document processor, embedding
    service, vector store, and optional graph RAG service.

    The service supports two retrieval modes:
    - Vector RAG (default): k-NN similarity search in OpenSearch
    - Graph RAG (optional): Entity-aware retrieval using Neo4j knowledge graph

    When both are enabled, hybrid search combines results from both
    approaches for improved retrieval quality on relationship queries.
    """

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        opensearch_store: OpenSearchStore | None = None,
        document_processor: DocumentProcessor | None = None,
        graph_rag_service: GraphRAGService | None = None,
    ):
        """Initialize the knowledge base service.

        Args:
            embedding_service: Service for embeddings (creates default if None)
            opensearch_store: Vector store (creates default if None)
            document_processor: Document processor (creates default if None)
            graph_rag_service: Graph RAG service for entity-aware retrieval (optional)
        """
        # Initialize embedding service first (needed by others)
        self._embedding_service = embedding_service or EmbeddingService()

        # Initialize vector store
        self._store = opensearch_store or OpenSearchStore(self._embedding_service)

        # Initialize document processor
        self._processor = document_processor or DocumentProcessor(self._embedding_service)

        # Initialize graph RAG service (optional)
        self._graph_rag = graph_rag_service

        graph_status = "disabled"
        if self._graph_rag:
            graph_status = "available" if self._graph_rag.is_available else "unavailable"

        logger.info(
            f"KnowledgeBaseService initialized: "
            f"store_available={self._store.is_available}, "
            f"graph_rag={graph_status}"
        )

    @property
    def is_available(self) -> bool:
        """Check if the knowledge base is available.

        Returns:
            True if the vector store is connected
        """
        return self._store.is_available

    def upload_document(
        self,
        content: bytes | str,
        filename: str,
        content_type: str | None = None,
        collection: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> KBDocument:
        """Upload and process a document.

        Args:
            content: Document content (bytes or string)
            filename: Original filename
            content_type: MIME type (optional)
            collection: Optional collection name
            metadata: Additional metadata

        Returns:
            KBDocument with document info

        Raises:
            RuntimeError: If store is not available
            ValueError: If document type is not supported
        """
        if not self.is_available:
            raise RuntimeError("Knowledge base is not available")

        # Process document (parse, chunk, embed)
        processed = self._processor.process(
            content=content,
            filename=filename,
            content_type=content_type,
            collection=collection,
            metadata=metadata,
        )

        # Store chunks in vector store
        self._store.add_chunks(processed.chunks)

        # Extract entities and store in graph (if GraphRAG is available)
        graph_extraction_result = None
        if self._graph_rag and self._graph_rag.is_available:
            try:
                chunks_for_graph = [
                    {
                        "content": chunk.content,
                        "metadata": chunk.metadata,
                        "id": chunk.id,
                    }
                    for chunk in processed.chunks
                ]
                graph_extraction_result = self._graph_rag.extract_and_store(
                    document_id=processed.id,
                    chunks=chunks_for_graph,
                    metadata={"filename": filename, "collection": collection},
                )
                logger.info(
                    f"Graph extraction for '{filename}': "
                    f"{graph_extraction_result.entities_extracted} entities, "
                    f"{graph_extraction_result.relationships_extracted} relationships"
                )
            except Exception as e:
                logger.warning(f"Graph extraction failed for '{filename}': {e}")

        logger.info(
            f"Uploaded document '{filename}' with {len(processed.chunks)} chunks "
            f"to collection '{collection or 'default'}'"
        )

        # Include graph extraction info in metadata
        doc_metadata = processed.metadata.copy()
        if graph_extraction_result:
            doc_metadata["graph_entities"] = graph_extraction_result.entities_extracted
            doc_metadata["graph_relationships"] = graph_extraction_result.relationships_extracted

        return KBDocument(
            id=processed.id,
            filename=processed.filename,
            content_type=processed.content_type,
            chunk_count=len(processed.chunks),
            size=processed.metadata.get("original_size", 0),
            collection=collection,
            created_at=processed.created_at,
            metadata=doc_metadata,
        )

    def upload_text(
        self,
        text: str,
        title: str = "Untitled",
        collection: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> KBDocument:
        """Upload plain text content directly.

        Args:
            text: Plain text content
            title: Document title
            collection: Optional collection name
            metadata: Additional metadata

        Returns:
            KBDocument with document info
        """
        return self.upload_document(
            content=text,
            filename=f"{title}.txt",
            content_type="text/plain",
            collection=collection,
            metadata=metadata,
        )

    def search(
        self,
        query: str,
        top_k: int | None = None,
        min_score: float = 0.0,
        collection: str | None = None,
        use_graph: bool | None = None,
    ) -> list[SearchResult]:
        """Search the knowledge base with optional graph-aware retrieval.

        When use_graph is enabled and GraphRAG is available, performs
        hybrid search combining vector similarity with graph traversal
        for improved results on relationship queries.

        Args:
            query: Search query
            top_k: Number of results (defaults to config)
            min_score: Minimum similarity score (0-1)
            collection: Optional collection filter
            use_graph: Enable graph-aware retrieval (defaults to GRAPH_RAG_ENABLED env)

        Returns:
            List of search results

        Raises:
            RuntimeError: If store is not available
        """
        if not self.is_available:
            raise RuntimeError("Knowledge base is not available")

        k = top_k or get_rag_default_top_k()

        # Determine if we should use graph-aware retrieval
        should_use_graph = use_graph if use_graph is not None else is_graph_rag_enabled()

        if should_use_graph and self._graph_rag and self._graph_rag.is_available:
            # Hybrid search: Graph + Vector
            logger.debug(f"Performing hybrid search (graph + vector) for: {query}")
            graph_results = self._graph_rag.search(query, top_k=k)
            vector_results = self._store.search(
                query=query,
                top_k=k,
                min_score=min_score,
                collection=collection,
            )
            return self._merge_results(graph_results, vector_results, k)
        else:
            # Vector-only search (existing behavior)
            return self._store.search(
                query=query,
                top_k=k,
                min_score=min_score,
                collection=collection,
            )

    def _merge_results(
        self,
        graph_results: list,
        vector_results: list[SearchResult],
        top_k: int,
    ) -> list[SearchResult]:
        """Merge graph and vector search results with deduplication.

        Interleaves results from both sources, prioritizing graph results
        for relationship-aware queries while preserving unique content.

        Args:
            graph_results: Results from GraphRAGService.search()
            vector_results: Results from OpenSearchStore.search()
            top_k: Maximum total results to return

        Returns:
            Merged and deduplicated list of SearchResult
        """
        seen_content = set()
        merged = []

        # Interleave results, prioritizing graph for relationship queries
        for g, v in zip_longest(graph_results, vector_results):
            # Process graph result
            if g is not None:
                content_key = g.content[:200] if hasattr(g, "content") else str(g)[:200]
                if content_key not in seen_content:
                    seen_content.add(content_key)
                    # Convert GraphSearchResult to SearchResult
                    merged.append(
                        SearchResult(
                            document_id=g.metadata.get("document_id", ""),
                            chunk_id=g.metadata.get("chunk_id", ""),
                            content=g.content,
                            score=g.score,
                            metadata={
                                **g.metadata,
                                "source": "graph",
                                "entities": g.entities,
                                "relationships": g.relationships,
                            },
                        )
                    )

            # Process vector result
            if v is not None:
                content_key = v.content[:200]
                if content_key not in seen_content:
                    seen_content.add(content_key)
                    # Mark source as vector
                    v_metadata = v.metadata.copy()
                    v_metadata["source"] = "vector"
                    merged.append(
                        SearchResult(
                            document_id=v.document_id,
                            chunk_id=v.chunk_id,
                            content=v.content,
                            score=v.score,
                            metadata=v_metadata,
                        )
                    )

            if len(merged) >= top_k:
                break

        return merged[:top_k]

    def get_context_for_query(
        self,
        query: str,
        top_k: int | None = None,
        min_score: float = 0.0,
        collection: str | None = None,
    ) -> str:
        """Get formatted context for RAG.

        Args:
            query: Search query
            top_k: Number of results
            min_score: Minimum similarity score
            collection: Optional collection filter

        Returns:
            Formatted context string for LLM
        """
        if not self.is_available:
            return ""

        results = self.search(
            query=query,
            top_k=top_k,
            min_score=min_score,
            collection=collection,
        )

        if not results:
            return ""

        # Format results as context
        context_parts = []
        for i, result in enumerate(results, 1):
            source = result.metadata.get("filename", "Unknown")
            context_parts.append(
                f"[Source {i}: {source}]\n{result.content}"
            )

        return "\n\n---\n\n".join(context_parts)

    def delete_document(self, document_id: str) -> bool:
        """Delete a document from the knowledge base.

        Removes document chunks from vector store and, if GraphRAG is
        enabled, also removes extracted entities and relationships.

        Args:
            document_id: Document ID to delete

        Returns:
            True if deleted successfully

        Raises:
            RuntimeError: If store is not available
        """
        if not self.is_available:
            raise RuntimeError("Knowledge base is not available")

        # Delete from vector store
        deleted = self._store.delete_document(document_id)

        # Delete from graph store if available
        if self._graph_rag and self._graph_rag.is_available:
            try:
                graph_deleted = self._graph_rag.delete_document_entities(document_id)
                logger.info(f"Deleted {graph_deleted} graph entities for document '{document_id}'")
            except Exception as e:
                logger.warning(f"Failed to delete graph entities for '{document_id}': {e}")

        return deleted > 0

    def get_document(self, document_id: str) -> KBDocument | None:
        """Get document metadata by ID.

        Args:
            document_id: Document ID

        Returns:
            KBDocument if found, None otherwise
        """
        if not self.is_available:
            return None

        chunks = self._store.get_document_chunks(document_id)
        if not chunks:
            return None

        # Get metadata from first chunk
        first_chunk = chunks[0]
        return KBDocument(
            id=document_id,
            filename=first_chunk.get("filename", ""),
            content_type=first_chunk.get("content_type", ""),
            chunk_count=len(chunks),
            size=first_chunk.get("metadata", {}).get("original_size", 0),
            collection=first_chunk.get("collection"),
            created_at=first_chunk.get("created_at", ""),
            metadata=first_chunk.get("metadata", {}),
        )

    def list_documents(
        self,
        collection: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[KBDocument]:
        """List documents in the knowledge base.

        Args:
            collection: Optional collection filter
            limit: Maximum documents to return
            offset: Pagination offset

        Returns:
            List of KBDocument objects
        """
        if not self.is_available:
            return []

        docs = self._store.list_documents(
            collection=collection,
            limit=limit,
            offset=offset,
        )

        return [
            KBDocument(
                id=doc.get("id", ""),
                filename=doc.get("filename", ""),
                content_type=doc.get("content_type", ""),
                chunk_count=doc.get("chunk_count", 0),
                size=doc.get("metadata", {}).get("original_size", 0),
                collection=doc.get("collection"),
                created_at=doc.get("created_at", ""),
                metadata=doc.get("metadata", {}),
            )
            for doc in docs
        ]

    def list_collections(self) -> list[KBCollection]:
        """List all collections.

        Returns:
            List of KBCollection objects
        """
        if not self.is_available:
            return []

        collections = self._store.list_collections()
        return [
            KBCollection(
                id=col.get("id", ""),
                name=col.get("name", ""),
                document_count=col.get("document_count", 0),
            )
            for col in collections
        ]

    def get_stats(self) -> KBStats:
        """Get knowledge base statistics.

        Returns:
            KBStats object with statistics
        """
        stats = self._store.get_stats()
        collections = self.list_collections() if self.is_available else []

        return KBStats(
            total_documents=stats.get("total_documents", 0),
            total_chunks=stats.get("total_chunks", 0),
            total_collections=len(collections),
            index_size=stats.get("index_size", "0b"),
            last_updated=datetime.utcnow().isoformat(),
            available=stats.get("available", False),
        )

    @property
    def graph_rag_available(self) -> bool:
        """Check if Graph RAG is available.

        Returns:
            True if GraphRAG service is configured and connected
        """
        return self._graph_rag is not None and self._graph_rag.is_available

    def get_graph_stats(self) -> dict[str, Any]:
        """Get knowledge graph statistics.

        Returns:
            Dict with graph statistics (node count, relationship count, etc.)
            or availability status if not configured
        """
        if not self._graph_rag:
            return {"available": False, "message": "GraphRAG not configured"}
        return self._graph_rag.get_stats()

    def get_entity_context(self, entity: str, depth: int = 2) -> dict[str, Any]:
        """Get context around a specific entity from the knowledge graph.

        Args:
            entity: Entity name to explore
            depth: Maximum traversal depth (hops)

        Returns:
            Dict with entity info and connected nodes/relationships
        """
        if not self._graph_rag:
            return {"error": "GraphRAG not configured"}
        if not self._graph_rag.is_available:
            return {"error": "GraphRAG not available"}
        return self._graph_rag.get_entity_context(entity, depth)
