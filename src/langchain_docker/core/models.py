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
    return ["openai", "anthropic", "google", "bedrock"]


def init_model(
    provider: str,
    model: str,
    temperature: float = 0.0,
    **kwargs: Any,
) -> BaseChatModel:
    """Initialize a chat model with the specified provider and configuration.

    Args:
        provider: Model provider (openai, anthropic, google, bedrock)
        model: Model name/identifier
        temperature: Temperature for response generation (0.0-2.0)
        **kwargs: Additional provider-specific parameters
            - For bedrock: region_name, credentials_profile_name, etc.

    Returns:
        Initialized chat model instance

    Raises:
        APIKeyMissingError: If API key/credentials for provider are not configured
        ModelInitializationError: If model initialization fails
    """
    validate_api_key(provider)

    try:
        # For Bedrock, LangChain expects model_provider="bedrock"
        # and boto3 will automatically use default credential chain
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


def get_bedrock_model(
    model: str | None = None,
    temperature: float = 0.0,
    **kwargs: Any,
) -> BaseChatModel:
    """Get a pre-configured AWS Bedrock model.

    Args:
        model: Bedrock model ID or ARN. If None, uses first configured model.
        temperature: Sampling temperature (0.0-1.0)
        **kwargs: Additional arguments for ChatBedrockConverse

    Returns:
        Configured ChatBedrockConverse instance

    Raises:
        APIKeyMissingError: If AWS credentials are not configured
        ModelInitializationError: If model initialization fails
    """
    import boto3
    from langchain_aws import ChatBedrockConverse
    from langchain_docker.core.config import get_bedrock_models, get_bedrock_region, get_bedrock_profile

    validate_api_key("bedrock")

    # Get default model if not specified
    if model is None:
        available_models = get_bedrock_models()
        model = available_models[0] if available_models else "anthropic.claude-3-5-sonnet-20241022-v2:0"

    # Create boto3 session and bedrock-runtime client with profile
    boto_session = boto3.Session(
        region_name=get_bedrock_region(),
        profile_name=get_bedrock_profile(),
    )
    bedrock_client = boto_session.client("bedrock-runtime")

    # Build kwargs for ChatBedrockConverse
    bedrock_kwargs = {
        "model": model,
        "provider": "anthropic",
        "temperature": temperature,
        "client": bedrock_client,
    }

    bedrock_kwargs.update(kwargs)

    try:
        return ChatBedrockConverse(**bedrock_kwargs)
    except Exception as e:
        raise ModelInitializationError("bedrock", model, e)
