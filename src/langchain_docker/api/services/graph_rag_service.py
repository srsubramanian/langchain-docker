"""LlamaIndex GraphRAG service for entity-aware retrieval.

This service provides graph-based RAG capabilities using LlamaIndex
PropertyGraphIndex with Neo4j as the graph store. It enables:
- Entity extraction during document ingestion
- Graph-aware retrieval that leverages relationships
- Hybrid search combining graph and vector approaches
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from langchain_docker.core.config import (
    get_graph_rag_entities,
    get_graph_rag_relations,
    get_neo4j_password,
    get_neo4j_url,
    get_neo4j_username,
)

logger = logging.getLogger(__name__)


@dataclass
class GraphSearchResult:
    """Result from graph-enhanced search.

    Attributes:
        content: The text content of the result
        score: Relevance score (0-1)
        entities: List of entities found in this result
        relationships: List of relationships involving these entities
        source_chunks: IDs of source chunks
        metadata: Additional metadata
    """

    content: str
    score: float
    entities: list[str] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    source_chunks: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionResult:
    """Result from entity extraction.

    Attributes:
        document_id: Source document ID
        chunks_processed: Number of chunks processed
        entities_extracted: Number of entities extracted
        relationships_extracted: Number of relationships extracted
        status: Status of extraction (success, partial, failed)
        error: Error message if failed
    """

    document_id: str
    chunks_processed: int
    entities_extracted: int = 0
    relationships_extracted: int = 0
    status: str = "success"
    error: str | None = None


class GraphRAGService:
    """Service for graph-based RAG using LlamaIndex PropertyGraphIndex.

    Provides:
    - Entity extraction during document ingestion
    - Graph-aware retrieval using Neo4j
    - Hybrid search combining graph traversal and vector similarity

    The service uses LlamaIndex's PropertyGraphIndex with Neo4jPropertyGraphStore
    for persistent graph storage. Entity extraction is performed using
    SchemaLLMPathExtractor with configurable entity and relationship types.

    Example:
        ```python
        service = GraphRAGService()
        if service.is_available:
            # Extract entities from document chunks
            result = service.extract_and_store(
                document_id="doc123",
                chunks=[{"content": "John works at Acme Corp", "metadata": {}}],
            )

            # Search using graph-aware retrieval
            results = service.search("Who works at Acme Corp?")
        ```
    """

    def __init__(
        self,
        neo4j_url: str | None = None,
        neo4j_username: str | None = None,
        neo4j_password: str | None = None,
        llm_model: str = "gpt-4o-mini",
        embed_model: str = "text-embedding-3-small",
    ):
        """Initialize GraphRAG service.

        Args:
            neo4j_url: Neo4j Bolt URL (defaults to env NEO4J_URL)
            neo4j_username: Neo4j username (defaults to env NEO4J_USERNAME)
            neo4j_password: Neo4j password (defaults to env NEO4J_PASSWORD)
            llm_model: OpenAI model for entity extraction
            embed_model: OpenAI model for embeddings
        """
        self._neo4j_url = neo4j_url or get_neo4j_url()
        self._neo4j_username = neo4j_username or get_neo4j_username()
        self._neo4j_password = neo4j_password or get_neo4j_password()
        self._llm_model = llm_model
        self._embed_model = embed_model

        self._graph_store = None
        self._index = None
        self._initialized = False
        self._initialization_error: str | None = None

        # Attempt initialization if configuration is present
        if self._neo4j_url and self._neo4j_password:
            self._initialize()
        else:
            logger.info(
                "GraphRAGService: Neo4j not configured, service disabled. "
                "Set NEO4J_URL and NEO4J_PASSWORD to enable."
            )

    def _initialize(self) -> None:
        """Initialize LlamaIndex components.

        Sets up:
        - LlamaIndex Settings with OpenAI LLM and embeddings
        - Neo4jPropertyGraphStore connection
        - PropertyGraphIndex for entity-aware retrieval
        """
        try:
            from llama_index.core import PropertyGraphIndex, Settings
            from llama_index.embeddings.openai import OpenAIEmbedding
            from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
            from llama_index.llms.openai import OpenAI

            # Configure LlamaIndex global settings
            Settings.llm = OpenAI(model=self._llm_model, temperature=0)
            Settings.embed_model = OpenAIEmbedding(model=self._embed_model)

            # Connect to Neo4j
            self._graph_store = Neo4jPropertyGraphStore(
                url=self._neo4j_url,
                username=self._neo4j_username,
                password=self._neo4j_password,
            )

            # Create index from existing graph store
            # This loads any existing entities/relationships
            self._index = PropertyGraphIndex.from_existing(
                property_graph_store=self._graph_store,
            )

            self._initialized = True
            logger.info(
                f"GraphRAGService initialized successfully: "
                f"neo4j_url={self._neo4j_url}, llm={self._llm_model}"
            )

        except ImportError as e:
            self._initialization_error = f"Missing LlamaIndex dependencies: {e}"
            logger.error(f"GraphRAGService initialization failed: {self._initialization_error}")
            self._initialized = False

        except Exception as e:
            self._initialization_error = str(e)
            logger.error(f"GraphRAGService initialization failed: {e}")
            self._initialized = False

    @property
    def is_available(self) -> bool:
        """Check if service is available and ready.

        Returns:
            True if Neo4j connection is established and index is ready
        """
        return self._initialized

    @property
    def initialization_error(self) -> str | None:
        """Get initialization error message if any.

        Returns:
            Error message if initialization failed, None otherwise
        """
        return self._initialization_error

    def extract_and_store(
        self,
        document_id: str,
        chunks: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> ExtractionResult:
        """Extract entities from chunks and store in graph.

        Uses LlamaIndex SchemaLLMPathExtractor to identify entities and
        relationships in the document chunks, then stores them in Neo4j.

        Args:
            document_id: Source document ID for tracking
            chunks: List of chunk dicts with 'content' and optional 'metadata'
            metadata: Document-level metadata to attach to entities

        Returns:
            ExtractionResult with entity/relationship counts and status

        Example:
            ```python
            result = service.extract_and_store(
                document_id="doc123",
                chunks=[
                    {"content": "John leads the AI project at Acme.", "metadata": {"page": 1}},
                    {"content": "The AI project uses Python and TensorFlow.", "metadata": {"page": 2}},
                ],
                metadata={"filename": "report.pdf"},
            )
            print(f"Extracted {result.entities_extracted} entities")
            ```
        """
        if not self.is_available:
            return ExtractionResult(
                document_id=document_id,
                chunks_processed=0,
                status="failed",
                error="GraphRAG service not available",
            )

        try:
            from llama_index.core import Document, Settings
            from llama_index.core.indices.property_graph import SchemaLLMPathExtractor

            # Convert chunks to LlamaIndex Documents
            documents = []
            for i, chunk in enumerate(chunks):
                chunk_metadata = chunk.get("metadata", {}).copy()
                chunk_metadata["document_id"] = document_id
                chunk_metadata["chunk_id"] = chunk.get("id", f"chunk_{i}")
                if metadata:
                    chunk_metadata.update(metadata)

                documents.append(
                    Document(
                        text=chunk["content"],
                        metadata=chunk_metadata,
                    )
                )

            # Create schema-guided extractor
            extractor = SchemaLLMPathExtractor(
                llm=Settings.llm,
                possible_entities=get_graph_rag_entities(),
                possible_relations=get_graph_rag_relations(),
                strict=False,  # Allow entities outside schema for flexibility
            )

            # Insert documents with entity extraction
            # This adds nodes to the index and extracts entities/relationships
            self._index.insert_nodes(documents, kg_extractors=[extractor])

            # Get extraction stats from graph store
            stats = self._get_extraction_stats(document_id)

            logger.info(
                f"Extracted entities for document '{document_id}': "
                f"{len(chunks)} chunks, {stats['entities']} entities, "
                f"{stats['relationships']} relationships"
            )

            return ExtractionResult(
                document_id=document_id,
                chunks_processed=len(chunks),
                entities_extracted=stats["entities"],
                relationships_extracted=stats["relationships"],
                status="success",
            )

        except Exception as e:
            logger.error(f"Entity extraction failed for document '{document_id}': {e}")
            return ExtractionResult(
                document_id=document_id,
                chunks_processed=0,
                status="failed",
                error=str(e),
            )

    def _get_extraction_stats(self, document_id: str) -> dict[str, int]:
        """Get extraction statistics for a document.

        Args:
            document_id: Document ID to get stats for

        Returns:
            Dict with 'entities' and 'relationships' counts
        """
        try:
            # Query Neo4j for document-specific stats
            query = """
            MATCH (n)
            WHERE n.document_id = $document_id OR n.metadata_document_id = $document_id
            WITH count(n) as entity_count
            OPTIONAL MATCH ()-[r]->()
            WHERE r.document_id = $document_id
            RETURN entity_count, count(r) as relationship_count
            """
            result = self._graph_store.structured_query(
                query,
                param_map={"document_id": document_id},
            )
            if result:
                return {
                    "entities": result[0].get("entity_count", 0) if result else 0,
                    "relationships": result[0].get("relationship_count", 0) if result else 0,
                }
        except Exception as e:
            logger.warning(f"Failed to get extraction stats: {e}")

        return {"entities": 0, "relationships": 0}

    def search(
        self,
        query: str,
        top_k: int = 5,
        include_text: bool = True,
        retriever_mode: str = "hybrid",
    ) -> list[GraphSearchResult]:
        """Search using graph-aware retrieval.

        Performs retrieval using LlamaIndex's PropertyGraphIndex retriever,
        which combines entity matching with vector similarity.

        Args:
            query: Natural language search query
            top_k: Maximum number of results to return
            include_text: Include source text chunks in results
            retriever_mode: Retrieval mode - "keyword", "embedding", or "hybrid"

        Returns:
            List of GraphSearchResult with content, scores, and entities

        Example:
            ```python
            results = service.search(
                "How does X relate to Y?",
                top_k=5,
                retriever_mode="hybrid",
            )
            for r in results:
                print(f"Score: {r.score}, Entities: {r.entities}")
                print(f"Content: {r.content[:100]}...")
            ```
        """
        if not self.is_available:
            logger.warning("GraphRAG search called but service not available")
            return []

        try:
            # Create retriever with specified mode
            retriever = self._index.as_retriever(
                include_text=include_text,
                retriever_mode=retriever_mode,
                similarity_top_k=top_k,
            )

            # Execute retrieval
            nodes = retriever.retrieve(query)

            # Convert to GraphSearchResult
            results = []
            for node in nodes:
                # Extract entities from node metadata
                entities = node.metadata.get("entities", [])
                if isinstance(entities, str):
                    entities = [entities]

                # Extract relationships
                relationships = node.metadata.get("relationships", [])
                if isinstance(relationships, str):
                    relationships = [{"type": relationships}]

                results.append(
                    GraphSearchResult(
                        content=node.text if hasattr(node, "text") else str(node),
                        score=node.score if hasattr(node, "score") and node.score else 0.0,
                        entities=entities,
                        relationships=relationships,
                        source_chunks=node.metadata.get("source_chunks", []),
                        metadata=node.metadata,
                    )
                )

            logger.debug(f"Graph search for '{query}': {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Graph search failed for query '{query}': {e}")
            return []

    def get_entity_context(
        self,
        entity: str,
        depth: int = 2,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Get context around a specific entity.

        Traverses the graph to find related entities and relationships
        within the specified depth from the target entity.

        Args:
            entity: Entity name to explore
            depth: Maximum traversal depth (hops)
            limit: Maximum number of results

        Returns:
            Dict with entity info, connections, and related content

        Example:
            ```python
            context = service.get_entity_context("Acme Corp", depth=2)
            print(f"Entity: {context['entity']}")
            for conn in context['connections']:
                print(f"  -> {conn['relationship']} -> {conn['target']}")
            ```
        """
        if not self.is_available:
            return {"error": "GraphRAG service not available"}

        try:
            # Query Neo4j for entity neighborhood
            query = f"""
            MATCH (n)-[r*1..{depth}]-(m)
            WHERE toLower(n.name) CONTAINS toLower($entity)
               OR toLower(n.id) CONTAINS toLower($entity)
            RETURN n, r, m
            LIMIT {limit}
            """

            result = self._graph_store.structured_query(
                query,
                param_map={"entity": entity},
            )

            # Process results into structured format
            connections = []
            seen_nodes = set()

            for record in result or []:
                if isinstance(record, dict):
                    # Extract node and relationship info
                    n = record.get("n", {})
                    m = record.get("m", {})
                    r = record.get("r", [])

                    node_id = n.get("id") or n.get("name", "")
                    if node_id and node_id not in seen_nodes:
                        seen_nodes.add(node_id)

                    target_id = m.get("id") or m.get("name", "")
                    if target_id and target_id != node_id:
                        connections.append({
                            "source": node_id,
                            "target": target_id,
                            "relationships": r if isinstance(r, list) else [r],
                        })

            return {
                "entity": entity,
                "depth": depth,
                "connections": connections,
                "total_nodes": len(seen_nodes),
            }

        except Exception as e:
            logger.error(f"Failed to get entity context for '{entity}': {e}")
            return {"entity": entity, "error": str(e)}

    def get_stats(self) -> dict[str, Any]:
        """Get graph statistics.

        Returns counts of nodes, relationships, and entity types
        in the knowledge graph.

        Returns:
            Dict with graph statistics
        """
        if not self.is_available:
            return {
                "available": False,
                "error": self._initialization_error or "Service not initialized",
            }

        try:
            # Query for overall stats
            stats_query = """
            MATCH (n)
            WITH count(n) as node_count
            MATCH ()-[r]->()
            WITH node_count, count(r) as relationship_count
            RETURN node_count, relationship_count
            """

            result = self._graph_store.structured_query(stats_query)

            node_count = 0
            relationship_count = 0

            if result and len(result) > 0:
                if isinstance(result[0], dict):
                    node_count = result[0].get("node_count", 0)
                    relationship_count = result[0].get("relationship_count", 0)

            # Get entity type distribution
            type_query = """
            MATCH (n)
            WHERE n.type IS NOT NULL
            RETURN n.type as entity_type, count(*) as count
            ORDER BY count DESC
            LIMIT 10
            """
            type_result = self._graph_store.structured_query(type_query)

            entity_types = {}
            for record in type_result or []:
                if isinstance(record, dict):
                    entity_types[record.get("entity_type", "unknown")] = record.get("count", 0)

            return {
                "available": True,
                "node_count": node_count,
                "relationship_count": relationship_count,
                "entity_types": entity_types,
                "neo4j_url": self._neo4j_url,
            }

        except Exception as e:
            logger.error(f"Failed to get graph stats: {e}")
            return {
                "available": True,
                "error": str(e),
            }

    def delete_document_entities(self, document_id: str) -> int:
        """Delete all entities and relationships for a document.

        Removes all nodes and relationships that were extracted from
        the specified document.

        Args:
            document_id: Document ID to delete entities for

        Returns:
            Number of nodes deleted
        """
        if not self.is_available:
            return 0

        try:
            # Delete nodes and their relationships for this document
            delete_query = """
            MATCH (n)
            WHERE n.document_id = $document_id
               OR n.metadata_document_id = $document_id
            DETACH DELETE n
            RETURN count(n) as deleted_count
            """

            result = self._graph_store.structured_query(
                delete_query,
                param_map={"document_id": document_id},
            )

            deleted = 0
            if result and len(result) > 0:
                if isinstance(result[0], dict):
                    deleted = result[0].get("deleted_count", 0)

            logger.info(f"Deleted {deleted} entities for document '{document_id}'")
            return deleted

        except Exception as e:
            logger.error(f"Failed to delete entities for document '{document_id}': {e}")
            return 0
