"""Model initialization utilities and factory functions."""

from typing import Any

from langchain.chat_models import BaseChatModel, init_chat_model

from langchain_docker.core.config import validate_api_key
from langchain_docker.utils.errors import ModelInitializationError


def get_supported_providers() -> list[str]:
    """Get list of supported model providers.

    Returns:
        List of provider names
    """
    return ["openai", "anthropic", "google"]


def init_model(
    provider: str,
    model: str,
    temperature: float = 0.0,
    **kwargs: Any,
) -> BaseChatModel:
    """Initialize a chat model with the specified provider and configuration.

    Args:
        provider: Model provider (openai, anthropic, google)
        model: Model name/identifier
        temperature: Temperature for response generation (0.0-1.0)
        **kwargs: Additional provider-specific parameters

    Returns:
        Initialized chat model instance

    Raises:
        APIKeyMissingError: If API key for provider is not configured
        ModelInitializationError: If model initialization fails
    """
    validate_api_key(provider)

    try:
        chat_model = init_chat_model(
            model=model,
            model_provider=provider,
            temperature=temperature,
            **kwargs,
        )
        return chat_model
    except Exception as e:
        raise ModelInitializationError(provider, model, e)


def get_openai_model(
    model: str = "gpt-4o-mini",
    temperature: float = 0.0,
    **kwargs: Any,
) -> BaseChatModel:
    """Get a pre-configured OpenAI model.

    Args:
        model: OpenAI model name (default: gpt-4o-mini)
        temperature: Temperature for response generation
        **kwargs: Additional OpenAI-specific parameters

    Returns:
        Initialized OpenAI chat model

    Raises:
        APIKeyMissingError: If OPENAI_API_KEY is not configured
        ModelInitializationError: If model initialization fails
    """
    return init_model("openai", model, temperature, **kwargs)


def get_anthropic_model(
    model: str = "claude-3-5-sonnet-20241022",
    temperature: float = 0.0,
    **kwargs: Any,
) -> BaseChatModel:
    """Get a pre-configured Anthropic model.

    Args:
        model: Anthropic model name (default: claude-3-5-sonnet-20241022)
        temperature: Temperature for response generation
        **kwargs: Additional Anthropic-specific parameters

    Returns:
        Initialized Anthropic chat model

    Raises:
        APIKeyMissingError: If ANTHROPIC_API_KEY is not configured
        ModelInitializationError: If model initialization fails
    """
    return init_model("anthropic", model, temperature, **kwargs)


def get_google_model(
    model: str = "gemini-2.0-flash-exp",
    temperature: float = 0.0,
    **kwargs: Any,
) -> BaseChatModel:
    """Get a pre-configured Google model.

    Args:
        model: Google model name (default: gemini-2.0-flash-exp)
        temperature: Temperature for response generation
        **kwargs: Additional Google-specific parameters

    Returns:
        Initialized Google chat model

    Raises:
        APIKeyMissingError: If GOOGLE_API_KEY is not configured
        ModelInitializationError: If model initialization fails
    """
    return init_model("google", model, temperature, **kwargs)
