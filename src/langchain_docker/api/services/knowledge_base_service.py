"""Knowledge base service for RAG functionality."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from langchain_docker.api.services.document_processor import DocumentProcessor, ProcessedDocument
from langchain_docker.api.services.embedding_service import EmbeddingService
from langchain_docker.api.services.opensearch_store import OpenSearchStore, SearchResult
from langchain_docker.core.config import get_rag_default_top_k

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
    service, and vector store.
    """

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        opensearch_store: OpenSearchStore | None = None,
        document_processor: DocumentProcessor | None = None,
    ):
        """Initialize the knowledge base service.

        Args:
            embedding_service: Service for embeddings (creates default if None)
            opensearch_store: Vector store (creates default if None)
            document_processor: Document processor (creates default if None)
        """
        # Initialize embedding service first (needed by others)
        self._embedding_service = embedding_service or EmbeddingService()

        # Initialize vector store
        self._store = opensearch_store or OpenSearchStore(self._embedding_service)

        # Initialize document processor
        self._processor = document_processor or DocumentProcessor(self._embedding_service)

        logger.info(
            f"KnowledgeBaseService initialized: "
            f"store_available={self._store.is_available}"
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

        logger.info(
            f"Uploaded document '{filename}' with {len(processed.chunks)} chunks "
            f"to collection '{collection or 'default'}'"
        )

        return KBDocument(
            id=processed.id,
            filename=processed.filename,
            content_type=processed.content_type,
            chunk_count=len(processed.chunks),
            size=processed.metadata.get("original_size", 0),
            collection=collection,
            created_at=processed.created_at,
            metadata=processed.metadata,
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
    ) -> list[SearchResult]:
        """Search the knowledge base.

        Args:
            query: Search query
            top_k: Number of results (defaults to config)
            min_score: Minimum similarity score (0-1)
            collection: Optional collection filter

        Returns:
            List of search results

        Raises:
            RuntimeError: If store is not available
        """
        if not self.is_available:
            raise RuntimeError("Knowledge base is not available")

        k = top_k or get_rag_default_top_k()
        return self._store.search(
            query=query,
            top_k=k,
            min_score=min_score,
            collection=collection,
        )

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

        Args:
            document_id: Document ID to delete

        Returns:
            True if deleted successfully

        Raises:
            RuntimeError: If store is not available
        """
        if not self.is_available:
            raise RuntimeError("Knowledge base is not available")

        deleted = self._store.delete_document(document_id)
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
