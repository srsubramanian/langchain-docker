"""Knowledge base Pydantic schemas."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class DocumentUploadRequest(BaseModel):
    """Request schema for uploading text content."""

    content: str = Field(..., min_length=1, description="Text content to upload")
    filename: str = Field(..., min_length=1, description="Filename for the document")
    collection: str | None = Field(None, description="Optional collection name")
    metadata: dict[str, Any] | None = Field(None, description="Additional metadata")


class DocumentResponse(BaseModel):
    """Response schema for document operations."""

    id: str = Field(..., description="Document ID")
    filename: str = Field(..., description="Original filename")
    content_type: Literal["pdf", "markdown", "text"] = Field(..., description="Document type")
    chunk_count: int = Field(..., description="Number of chunks created")
    size: int = Field(..., description="Original file size in bytes")
    collection: str | None = Field(None, description="Collection name")
    created_at: str = Field(..., description="Creation timestamp (ISO format)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Document metadata")


class DocumentListResponse(BaseModel):
    """Response schema for listing documents."""

    documents: list[DocumentResponse] = Field(default_factory=list, description="List of documents")
    total: int = Field(..., description="Total number of documents")


class CollectionResponse(BaseModel):
    """Response schema for a collection."""

    id: str = Field(..., description="Collection ID")
    name: str = Field(..., description="Collection name")
    document_count: int = Field(..., description="Number of documents in collection")
    color: str | None = Field(None, description="Optional color for UI")


class CollectionListResponse(BaseModel):
    """Response schema for listing collections."""

    collections: list[CollectionResponse] = Field(default_factory=list, description="List of collections")
    total: int = Field(..., description="Total number of collections")


class SearchRequest(BaseModel):
    """Request schema for semantic search."""

    query: str = Field(..., min_length=1, description="Search query")
    top_k: int = Field(5, ge=1, le=50, description="Number of results to return")
    min_score: float = Field(0.0, ge=0.0, le=1.0, description="Minimum similarity score")
    collection: str | None = Field(None, description="Optional collection filter")
    use_graph: bool | None = Field(
        None,
        description="Use graph-aware retrieval (defaults to env GRAPH_RAG_ENABLED). "
        "Combines entity-aware graph search with vector similarity."
    )


class SearchResultItem(BaseModel):
    """Schema for a single search result."""

    document_id: str = Field(..., description="Document ID")
    chunk_id: str = Field(..., description="Chunk ID")
    content: str = Field(..., description="Chunk content")
    score: float = Field(..., description="Similarity score (0-1)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Chunk metadata")


class SearchResponse(BaseModel):
    """Response schema for search results."""

    query: str = Field(..., description="Original query")
    results: list[SearchResultItem] = Field(default_factory=list, description="Search results")
    total: int = Field(..., description="Total number of results")


class KBStatsResponse(BaseModel):
    """Response schema for knowledge base statistics."""

    total_documents: int = Field(..., description="Total number of documents")
    total_chunks: int = Field(..., description="Total number of chunks")
    total_collections: int = Field(..., description="Total number of collections")
    index_size: str = Field(..., description="Index size on disk")
    last_updated: str = Field(..., description="Last update timestamp (ISO format)")
    available: bool = Field(..., description="Whether the knowledge base is available")


class FileUploadResponse(BaseModel):
    """Response schema for file upload."""

    document: DocumentResponse = Field(..., description="Uploaded document info")
    message: str = Field(..., description="Success message")


class DeleteResponse(BaseModel):
    """Response schema for delete operations."""

    success: bool = Field(..., description="Whether the operation succeeded")
    message: str = Field(..., description="Result message")


class GraphStatsResponse(BaseModel):
    """Response schema for knowledge graph statistics."""

    available: bool = Field(..., description="Whether Graph RAG is available")
    node_count: int = Field(0, description="Total number of nodes (entities)")
    relationship_count: int = Field(0, description="Total number of relationships")
    entity_types: dict[str, int] = Field(default_factory=dict, description="Entity type distribution")
    neo4j_url: str | None = Field(None, description="Neo4j connection URL")
    llm_provider: str | None = Field(None, description="LLM provider (openai or bedrock)")
    llm_model: str | None = Field(None, description="LLM model for entity extraction")
    embed_provider: str | None = Field(None, description="Embedding provider (openai or bedrock)")
    embed_model: str | None = Field(None, description="Embedding model for vector search")
    error: str | None = Field(None, description="Error message if unavailable")


class EntityConnection(BaseModel):
    """Schema for an entity connection in the graph."""

    source: str = Field(..., description="Source entity name")
    target: str = Field(..., description="Target entity name")
    relationships: list[Any] = Field(default_factory=list, description="Relationships between entities")


class EntityContextResponse(BaseModel):
    """Response schema for entity context lookup."""

    entity: str = Field(..., description="Queried entity name")
    depth: int = Field(2, description="Traversal depth used")
    connections: list[EntityConnection] = Field(default_factory=list, description="Connected entities")
    total_nodes: int = Field(0, description="Total nodes found")
    error: str | None = Field(None, description="Error message if failed")


class SchemaSuggestion(BaseModel):
    """Schema suggestion from insights analysis."""

    type: str = Field(..., description="Suggested entity or relation type")
    occurrences: int = Field(..., description="Number of times discovered")


class SchemaInsightsResponse(BaseModel):
    """Response schema for schema insights analysis."""

    analyzed_documents: int = Field(..., description="Number of documents analyzed")
    configured_entities: list[str] = Field(default_factory=list, description="Currently configured entity types")
    configured_relations: list[str] = Field(default_factory=list, description="Currently configured relation types")
    suggested_entities: list[SchemaSuggestion] = Field(
        default_factory=list, description="Entity types discovered not in schema"
    )
    suggested_relations: list[SchemaSuggestion] = Field(
        default_factory=list, description="Relation types discovered not in schema"
    )
    env_update: dict[str, str] | None = Field(
        None, description="Suggested .env updates if new types found"
    )
