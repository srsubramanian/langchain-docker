"""Basic model initialization and invocation examples."""

from pprint import pprint

from langchain.chat_models import init_chat_model
from langchain_core.messages import BaseMessage

from langchain_docker.core.config import load_environment


def _get_default_model(provider: str) -> str:
    """Get the default model for a provider.

    Args:
        provider: Model provider name

    Returns:
        Default model name/ID for the provider
    """
    if provider == "bedrock":
        from langchain_docker.core.config import get_bedrock_models
        models = get_bedrock_models()
        return models[0] if models else "anthropic.claude-3-5-sonnet-20241022-v2:0"

    defaults = {
        "openai": "gpt-4o-mini",
        "anthropic": "claude-3-5-sonnet-20241022",
        "google": "gemini-2.0-flash-exp",
    }
    return defaults.get(provider, "gpt-4o-mini")


def basic_invoke_example(
    provider: str = "openai",
    model: str | None = None,
    temperature: float = 0.0,
) -> BaseMessage:
    """Demonstrate basic model initialization and invocation.

    This example shows:
    1. How to initialize a chat model using init_chat_model()
    2. How to invoke the model with a simple prompt
    3. How to access the response content and metadata

    Args:
        provider: Model provider (openai, anthropic, google, bedrock)
        model: Model name to use (uses provider default if None)
        temperature: Temperature for response generation

    Returns:
        The model's response message
    """
    load_environment()

    # Use provider-specific default if model not specified
    if model is None:
        model = _get_default_model(provider)

    print(f"\n{'='*60}")
    print(f"Basic Model Invocation Example")
    print(f"{'='*60}")
    print(f"Provider: {provider}")
    print(f"Model: {model}")
    print(f"Temperature: {temperature}")
    print(f"{'='*60}\n")

    # Build kwargs for model initialization
    model_kwargs = {
        "model": model,
        "model_provider": provider,
        "temperature": temperature,
    }

    # Add Bedrock-specific parameters
    if provider == "bedrock":
        from langchain_docker.core.config import get_bedrock_region, get_bedrock_profile
        model_kwargs["region_name"] = get_bedrock_region()
        profile = get_bedrock_profile()
        if profile:
            model_kwargs["credentials_profile_name"] = profile

    chat_model = init_chat_model(**model_kwargs)

    prompt = "What is the capital of the Moon?"
    print(f"Prompt: {prompt}\n")

    response = chat_model.invoke(prompt)

    print(f"Response: {response.content}\n")
    print("Response Metadata:")
    pprint(response.response_metadata)
    print()

    return response


if __name__ == "__main__":
    basic_invoke_example()
