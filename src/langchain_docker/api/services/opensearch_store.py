"""OpenSearch vector store for knowledge base."""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from opensearchpy import OpenSearch
from opensearchpy.exceptions import NotFoundError, RequestError

from langchain_docker.api.services.embedding_service import EmbeddingService
from langchain_docker.core.config import get_opensearch_index, get_opensearch_url

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """A chunk of a document with its embedding."""

    id: str
    document_id: str
    content: str
    embedding: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)
    chunk_index: int = 0


@dataclass
class SearchResult:
    """A search result from the vector store."""

    document_id: str
    chunk_id: str
    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class OpenSearchStore:
    """OpenSearch-based vector store for knowledge base.

    Provides vector similarity search using OpenSearch's k-NN plugin.
    Stores document chunks with their embeddings for semantic search.
    """

    def __init__(
        self,
        embedding_service: EmbeddingService,
        opensearch_url: str | None = None,
        index_name: str | None = None,
    ):
        """Initialize the OpenSearch store.

        Args:
            embedding_service: Service for generating embeddings
            opensearch_url: OpenSearch URL (defaults to env)
            index_name: Index name (defaults to env)
        """
        self._embedding_service = embedding_service
        self._opensearch_url = opensearch_url or get_opensearch_url()
        self._index_name = index_name or get_opensearch_index()
        self._client: OpenSearch | None = None
        self._initialized = False

        if self._opensearch_url:
            self._connect()

    def _connect(self) -> None:
        """Connect to OpenSearch and initialize index."""
        if not self._opensearch_url:
            logger.warning("OpenSearch URL not configured, vector store disabled")
            return

        try:
            # Parse URL to get host and port
            url = self._opensearch_url.replace("http://", "").replace("https://", "")
            host, port = url.split(":") if ":" in url else (url, "9200")

            self._client = OpenSearch(
                hosts=[{"host": host, "port": int(port)}],
                http_compress=True,
                use_ssl=self._opensearch_url.startswith("https"),
                verify_certs=False,
                ssl_show_warn=False,
            )

            # Test connection
            info = self._client.info()
            logger.info(f"Connected to OpenSearch: {info.get('version', {}).get('number', 'unknown')}")

            # Ensure index exists
            self._ensure_index()
            self._initialized = True

        except Exception as e:
            logger.error(f"Failed to connect to OpenSearch: {e}")
            self._client = None

    def _ensure_index(self) -> None:
        """Create the index if it doesn't exist."""
        if not self._client:
            return

        try:
            if self._client.indices.exists(index=self._index_name):
                logger.info(f"Index '{self._index_name}' already exists")
                return

            # Create index with k-NN settings
            dimensions = self._embedding_service.dimensions
            index_body = {
                "settings": {
                    "index": {
                        "knn": True,
                        "knn.algo_param.ef_search": 100,
                    },
                    "number_of_shards": 1,
                    "number_of_replicas": 0,
                },
                "mappings": {
                    "properties": {
                        "document_id": {"type": "keyword"},
                        "chunk_id": {"type": "keyword"},
                        "content": {"type": "text"},
                        "embedding": {
                            "type": "knn_vector",
                            "dimension": dimensions,
                            "method": {
                                "name": "hnsw",
                                "space_type": "l2",
                                "engine": "lucene",
                                "parameters": {
                                    "ef_construction": 128,
                                    "m": 24,
                                },
                            },
                        },
                        "metadata": {"type": "object", "enabled": True},
                        "chunk_index": {"type": "integer"},
                        "filename": {"type": "keyword"},
                        "content_type": {"type": "keyword"},
                        "collection": {"type": "keyword"},
                        "created_at": {"type": "date"},
                    }
                },
            }

            self._client.indices.create(index=self._index_name, body=index_body)
            logger.info(f"Created index '{self._index_name}' with {dimensions} dimensions")

        except RequestError as e:
            if "resource_already_exists_exception" in str(e):
                logger.info(f"Index '{self._index_name}' already exists")
            else:
                raise

    @property
    def is_available(self) -> bool:
        """Check if the store is available and connected.

        Returns:
            True if connected and initialized
        """
        return self._initialized and self._client is not None

    def add_chunks(self, chunks: list[DocumentChunk]) -> list[str]:
        """Add document chunks to the store.

        Args:
            chunks: List of document chunks to add

        Returns:
            List of chunk IDs that were added

        Raises:
            RuntimeError: If store is not available
        """
        if not self.is_available:
            raise RuntimeError("OpenSearch store is not available")

        chunk_ids = []
        for chunk in chunks:
            doc = {
                "document_id": chunk.document_id,
                "chunk_id": chunk.id,
                "content": chunk.content,
                "embedding": chunk.embedding,
                "metadata": chunk.metadata,
                "chunk_index": chunk.chunk_index,
                "filename": chunk.metadata.get("filename", ""),
                "content_type": chunk.metadata.get("content_type", ""),
                "collection": chunk.metadata.get("collection", ""),
                "created_at": chunk.metadata.get("created_at", datetime.utcnow().isoformat()),
            }

            self._client.index(
                index=self._index_name,
                id=chunk.id,
                body=doc,
                refresh=True,
            )
            chunk_ids.append(chunk.id)

        logger.info(f"Added {len(chunk_ids)} chunks to index '{self._index_name}'")
        return chunk_ids

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
        collection: str | None = None,
    ) -> list[SearchResult]:
        """Search for similar documents.

        Args:
            query: Search query text
            top_k: Number of results to return
            min_score: Minimum similarity score (0-1)
            collection: Optional collection filter

        Returns:
            List of search results sorted by relevance

        Raises:
            RuntimeError: If store is not available
        """
        if not self.is_available:
            raise RuntimeError("OpenSearch store is not available")

        # Generate query embedding
        query_embedding = self._embedding_service.embed_query(query)

        # Build k-NN query
        knn_query = {
            "size": top_k,
            "query": {
                "knn": {
                    "embedding": {
                        "vector": query_embedding,
                        "k": top_k,
                    }
                }
            },
        }

        # Add collection filter if specified
        if collection:
            knn_query["query"] = {
                "bool": {
                    "must": [
                        {
                            "knn": {
                                "embedding": {
                                    "vector": query_embedding,
                                    "k": top_k,
                                }
                            }
                        }
                    ],
                    "filter": [{"term": {"collection": collection}}],
                }
            }

        response = self._client.search(index=self._index_name, body=knn_query)

        results = []
        for hit in response.get("hits", {}).get("hits", []):
            # OpenSearch k-NN returns L2 distance, convert to similarity score
            # Lower distance = higher similarity
            distance = hit.get("_score", 0)
            # Normalize score to 0-1 range (approximate)
            score = 1 / (1 + distance) if distance > 0 else 1.0

            if score >= min_score:
                source = hit.get("_source", {})
                results.append(
                    SearchResult(
                        document_id=source.get("document_id", ""),
                        chunk_id=source.get("chunk_id", ""),
                        content=source.get("content", ""),
                        score=score,
                        metadata=source.get("metadata", {}),
                    )
                )

        return results

    def delete_document(self, document_id: str) -> int:
        """Delete all chunks for a document.

        Args:
            document_id: Document ID to delete

        Returns:
            Number of chunks deleted

        Raises:
            RuntimeError: If store is not available
        """
        if not self.is_available:
            raise RuntimeError("OpenSearch store is not available")

        query = {"query": {"term": {"document_id": document_id}}}
        response = self._client.delete_by_query(
            index=self._index_name,
            body=query,
            refresh=True,
        )

        deleted = response.get("deleted", 0)
        logger.info(f"Deleted {deleted} chunks for document '{document_id}'")
        return deleted

    def get_document_chunks(self, document_id: str) -> list[dict[str, Any]]:
        """Get all chunks for a document.

        Args:
            document_id: Document ID

        Returns:
            List of chunk documents
        """
        if not self.is_available:
            return []

        query = {
            "query": {"term": {"document_id": document_id}},
            "sort": [{"chunk_index": "asc"}],
            "size": 10000,
        }

        response = self._client.search(index=self._index_name, body=query)
        return [hit.get("_source", {}) for hit in response.get("hits", {}).get("hits", [])]

    def get_stats(self) -> dict[str, Any]:
        """Get index statistics.

        Returns:
            Dictionary with index stats
        """
        if not self.is_available:
            return {
                "available": False,
                "total_chunks": 0,
                "total_documents": 0,
                "index_size": "0b",
            }

        try:
            stats = self._client.indices.stats(index=self._index_name)
            index_stats = stats.get("indices", {}).get(self._index_name, {})

            # Get unique document count
            doc_count_query = {
                "size": 0,
                "aggs": {"unique_documents": {"cardinality": {"field": "document_id"}}},
            }
            doc_response = self._client.search(index=self._index_name, body=doc_count_query)

            return {
                "available": True,
                "total_chunks": index_stats.get("primaries", {}).get("docs", {}).get("count", 0),
                "total_documents": doc_response.get("aggregations", {})
                .get("unique_documents", {})
                .get("value", 0),
                "index_size": index_stats.get("primaries", {}).get("store", {}).get("size", "0b"),
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {
                "available": False,
                "total_chunks": 0,
                "total_documents": 0,
                "index_size": "0b",
                "error": str(e),
            }

    def list_documents(
        self,
        collection: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List unique documents in the store.

        Args:
            collection: Optional collection filter
            limit: Maximum documents to return
            offset: Offset for pagination

        Returns:
            List of document info dictionaries
        """
        if not self.is_available:
            return []

        # Use aggregation to get unique documents
        agg_query: dict[str, Any] = {
            "size": 0,
            "aggs": {
                "documents": {
                    "composite": {
                        "size": limit,
                        "sources": [{"document_id": {"terms": {"field": "document_id"}}}],
                    },
                    "aggs": {
                        "doc_info": {
                            "top_hits": {
                                "size": 1,
                                "_source": [
                                    "document_id",
                                    "filename",
                                    "content_type",
                                    "collection",
                                    "created_at",
                                    "metadata",
                                ],
                            }
                        },
                        "chunk_count": {"value_count": {"field": "chunk_id"}},
                    },
                }
            },
        }

        if collection:
            agg_query["query"] = {"term": {"collection": collection}}

        response = self._client.search(index=self._index_name, body=agg_query)

        documents = []
        for bucket in response.get("aggregations", {}).get("documents", {}).get("buckets", []):
            hits = bucket.get("doc_info", {}).get("hits", {}).get("hits", [])
            if hits:
                source = hits[0].get("_source", {})
                documents.append(
                    {
                        "id": source.get("document_id", ""),
                        "filename": source.get("filename", ""),
                        "content_type": source.get("content_type", ""),
                        "collection": source.get("collection", ""),
                        "chunk_count": bucket.get("chunk_count", {}).get("value", 0),
                        "created_at": source.get("created_at", ""),
                        "metadata": source.get("metadata", {}),
                    }
                )

        return documents

    def list_collections(self) -> list[dict[str, Any]]:
        """List all collections with document counts.

        Returns:
            List of collection info dictionaries
        """
        if not self.is_available:
            return []

        agg_query = {
            "size": 0,
            "aggs": {
                "collections": {
                    "terms": {"field": "collection", "size": 1000},
                    "aggs": {"unique_docs": {"cardinality": {"field": "document_id"}}},
                }
            },
        }

        response = self._client.search(index=self._index_name, body=agg_query)

        collections = []
        for bucket in response.get("aggregations", {}).get("collections", {}).get("buckets", []):
            name = bucket.get("key", "")
            if name:  # Skip empty collection names
                collections.append(
                    {
                        "id": name,
                        "name": name,
                        "document_count": bucket.get("unique_docs", {}).get("value", 0),
                    }
                )

        return collections
