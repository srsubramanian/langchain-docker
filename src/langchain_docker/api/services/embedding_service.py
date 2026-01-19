"""Embedding service for generating vector embeddings."""

import logging
import os
from functools import lru_cache

from langchain_openai import OpenAIEmbeddings

from langchain_docker.core.config import get_embedding_model, get_embedding_provider

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating text embeddings.

    Supports multiple embedding providers with OpenAI as the default.
    Uses text-embedding-3-small (1536 dimensions) by default for
    good balance of quality and cost.
    """

    # Embedding dimension sizes for supported models
    MODEL_DIMENSIONS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
    ):
        """Initialize the embedding service.

        Args:
            provider: Embedding provider (defaults to env EMBEDDING_PROVIDER)
            model: Model name (defaults to env EMBEDDING_MODEL)
        """
        self._provider = provider or get_embedding_provider()
        self._model = model or get_embedding_model()
        self._embeddings = self._create_embeddings()
        logger.info(f"EmbeddingService initialized with {self._provider}/{self._model}")

    def _create_embeddings(self):
        """Create the embeddings instance based on provider.

        Returns:
            LangChain embeddings instance

        Raises:
            ValueError: If provider is not supported
        """
        if self._provider.lower() == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY is required for OpenAI embeddings")
            return OpenAIEmbeddings(
                model=self._model,
                openai_api_key=api_key,
            )
        else:
            raise ValueError(f"Unsupported embedding provider: {self._provider}")

    @property
    def dimensions(self) -> int:
        """Get the embedding dimension size.

        Returns:
            Number of dimensions in the embedding vector
        """
        return self.MODEL_DIMENSIONS.get(self._model, 1536)

    @property
    def model(self) -> str:
        """Get the model name.

        Returns:
            Model name string
        """
        return self._model

    @property
    def provider(self) -> str:
        """Get the provider name.

        Returns:
            Provider name string
        """
        return self._provider

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query text.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        return self._embeddings.embed_query(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple documents.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        return self._embeddings.embed_documents(texts)

    def get_langchain_embeddings(self):
        """Get the underlying LangChain embeddings instance.

        Returns:
            LangChain Embeddings instance for use with vector stores
        """
        return self._embeddings


@lru_cache
def get_embedding_service() -> EmbeddingService:
    """Get singleton embedding service instance.

    Returns:
        EmbeddingService instance
    """
    return EmbeddingService()
