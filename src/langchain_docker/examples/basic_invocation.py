"""Basic model initialization and invocation examples."""

from pprint import pprint

from langchain.chat_models import init_chat_model
from langchain_core.messages import BaseMessage

from langchain_docker.core.config import load_environment


def basic_invoke_example(
    provider: str = "openai",
    model: str = "gpt-4o-mini",
    temperature: float = 0.0,
) -> BaseMessage:
    """Demonstrate basic model initialization and invocation.

    This example shows:
    1. How to initialize a chat model using init_chat_model()
    2. How to invoke the model with a simple prompt
    3. How to access the response content and metadata

    Args:
        provider: Model provider (openai, anthropic, google)
        model: Model name to use
        temperature: Temperature for response generation

    Returns:
        The model's response message
    """
    load_environment()

    print(f"\n{'='*60}")
    print(f"Basic Model Invocation Example")
    print(f"{'='*60}")
    print(f"Provider: {provider}")
    print(f"Model: {model}")
    print(f"Temperature: {temperature}")
    print(f"{'='*60}\n")

    chat_model = init_chat_model(
        model=model,
        model_provider=provider,
        temperature=temperature,
    )

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
