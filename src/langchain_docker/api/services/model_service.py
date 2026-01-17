"""Model caching and management service."""

import threading
from collections import OrderedDict
from typing import Any

from langchain.chat_models import BaseChatModel

from langchain_docker.api.schemas.models import ModelInfo, ProviderDetails, ProviderInfo
from langchain_docker.core.config import get_api_key
from langchain_docker.core.models import get_supported_providers, init_model, create_bedrock_client
from langchain_docker.utils.errors import InvalidProviderError


class ModelService:
    """Service for model instance caching and provider management.

    Implements LRU cache for model instances to avoid repeated initialization.
    """

    def __init__(self, max_cache_size: int = 10):
        """Initialize model service.

        Args:
            max_cache_size: Maximum number of models to cache
        """
        self._cache: OrderedDict[tuple, BaseChatModel] = OrderedDict()
        self._lock = threading.Lock()
        self._max_cache_size = max_cache_size

    def get_or_create(
        self,
        provider: str,
        model: str | None = None,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> BaseChatModel:
        """Get cached model or create new one.

        Args:
            provider: Model provider name
            model: Model name (uses provider default if None)
            temperature: Temperature setting
            **kwargs: Additional model parameters

        Returns:
            Chat model instance

        Raises:
            InvalidProviderError: If provider is invalid
            APIKeyMissingError: If API key not configured
            ModelInitializationError: If initialization fails
        """
        # Validate provider
        valid_providers = get_supported_providers()
        if provider not in valid_providers:
            raise InvalidProviderError(provider, valid_providers)

        # Get default model if not specified
        if model is None:
            model = self._get_default_model(provider)

        # Create cache key
        cache_key = (provider, model, temperature)

        with self._lock:
            # Check cache
            if cache_key in self._cache:
                # Move to end (most recently used)
                self._cache.move_to_end(cache_key)
                return self._cache[cache_key]

            # For Bedrock, use ChatBedrockConverse directly (handles ARNs better)
            if provider == "bedrock":
                from langchain_aws import ChatBedrockConverse

                bedrock_kwargs = {
                    "model": model,
                    "provider": "anthropic",
                    "temperature": temperature,
                    "client": create_bedrock_client(),
                }
                bedrock_kwargs.update(kwargs)

                model_instance = ChatBedrockConverse(**bedrock_kwargs)
            else:
                # Create new model instance for other providers
                model_instance = init_model(provider, model, temperature, **kwargs)

            # Add to cache
            self._cache[cache_key] = model_instance

            # Evict oldest if over limit
            if len(self._cache) > self._max_cache_size:
                self._cache.popitem(last=False)

            return model_instance

    def _get_default_model(self, provider: str) -> str:
        """Get default model for provider.

        Args:
            provider: Provider name

        Returns:
            Default model name
        """
        from langchain_docker.core.config import get_bedrock_models

        defaults = {
            "openai": "gpt-4o-mini",
            "anthropic": "claude-sonnet-4-20250514",
            "google": "gemini-2.0-flash-exp",
        }

        # For Bedrock, use first configured model
        if provider == "bedrock":
            bedrock_models = get_bedrock_models()
            return bedrock_models[0] if bedrock_models else "anthropic.claude-3-5-sonnet-20241022-v2:0"

        return defaults.get(provider, "gpt-4o-mini")

    def get_provider_info(self, provider: str) -> ProviderInfo:
        """Get information about a provider.

        Args:
            provider: Provider name

        Returns:
            Provider information

        Raises:
            InvalidProviderError: If provider is invalid
        """
        valid_providers = get_supported_providers()
        if provider not in valid_providers:
            raise InvalidProviderError(provider, valid_providers)

        api_key = get_api_key(provider)
        configured = api_key is not None

        return ProviderInfo(
            name=provider,
            available=True,
            configured=configured,
            default_model=self._get_default_model(provider),
        )

    def list_providers(self) -> list[ProviderInfo]:
        """List all available providers.

        Returns:
            List of provider information
        """
        providers = get_supported_providers()
        return [self.get_provider_info(p) for p in providers]

    def get_provider_details(self, provider: str) -> ProviderDetails:
        """Get detailed information about a provider.

        Args:
            provider: Provider name

        Returns:
            Provider details

        Raises:
            InvalidProviderError: If provider is invalid
        """
        from langchain_docker.core.config import get_bedrock_models

        valid_providers = get_supported_providers()
        if provider not in valid_providers:
            raise InvalidProviderError(provider, valid_providers)

        # Special handling for Bedrock
        if provider == "bedrock":
            bedrock_arns = get_bedrock_models()
            available_models = []

            for arn in bedrock_arns:
                # Extract readable name from ARN
                model_name = arn.split("/")[-1] if "/" in arn else arn
                description = self._generate_bedrock_description(model_name)

                available_models.append(
                    ModelInfo(name=arn, description=description)
                )

            return ProviderDetails(
                name="bedrock",
                configured=self._is_bedrock_configured(),
                available_models=available_models,
                default_model=bedrock_arns[0] if bedrock_arns else "",
            )

        # Standard providers
        api_key = get_api_key(provider)
        configured = api_key is not None

        # Define available models for each provider
        models_map = {
            "openai": [
                ModelInfo(name="gpt-4o-mini", description="Fast and cost-effective"),
                ModelInfo(name="gpt-4o", description="Advanced reasoning"),
                ModelInfo(name="gpt-4-turbo", description="Balanced performance"),
            ],
            "anthropic": [
                ModelInfo(name="claude-sonnet-4-20250514", description="Most balanced, recommended for most use cases"),
                ModelInfo(name="claude-opus-4-20250514", description="Most capable, for complex tasks"),
                ModelInfo(name="claude-haiku-4-20250110", description="Fastest, most cost-effective"),
            ],
            "google": [
                ModelInfo(name="gemini-2.0-flash-exp", description="Experimental, fast"),
                ModelInfo(name="gemini-1.5-pro", description="Production ready"),
                ModelInfo(name="gemini-1.5-flash", description="Fast responses"),
            ],
        }

        return ProviderDetails(
            name=provider,
            configured=configured,
            available_models=models_map.get(provider, []),
            default_model=self._get_default_model(provider),
        )

    def _generate_bedrock_description(self, model_id: str) -> str:
        """Generate human-readable description from Bedrock model ID.

        Args:
            model_id: Bedrock model ID or ARN

        Returns:
            Description string
        """
        # Simple mapping - can be enhanced
        if "claude-sonnet-4" in model_id:
            return "Claude Sonnet 4 - Most balanced"
        elif "claude-opus-4" in model_id:
            return "Claude Opus 4 - Most capable"
        elif "claude-haiku-4" in model_id:
            return "Claude Haiku 4 - Fastest"
        elif "claude-3-5-sonnet" in model_id:
            return "Claude 3.5 Sonnet - Balanced performance"
        elif "claude-3-5-haiku" in model_id:
            return "Claude 3.5 Haiku - Fast and efficient"
        elif "claude-3-opus" in model_id:
            return "Claude 3 Opus - Most capable"
        elif "llama3" in model_id.lower():
            return "Meta Llama 3 - Open source"
        elif "titan" in model_id.lower():
            return "Amazon Titan - AWS native"
        else:
            return "AWS Bedrock model"

    def _is_bedrock_configured(self) -> bool:
        """Check if Bedrock is properly configured.

        Returns:
            True if Bedrock credentials are configured
        """
        try:
            from langchain_docker.core.config import validate_bedrock_access
            validate_bedrock_access()
            return True
        except:
            return False

    def clear_cache(self) -> int:
        """Clear the model cache.

        Returns:
            Number of models evicted from cache
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count

    def get_cache_size(self) -> int:
        """Get current cache size.

        Returns:
            Number of models in cache
        """
        with self._lock:
            return len(self._cache)
