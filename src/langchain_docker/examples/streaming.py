"""Streaming output examples for real-time responses."""

from langchain_core.messages import HumanMessage

from langchain_docker.core.config import load_environment
from langchain_docker.core.models import get_openai_model


def basic_streaming(
    provider: str = "openai",
    model: str = "gpt-4o-mini",
) -> None:
    """Demonstrate basic token-by-token streaming.

    Streaming allows you to display responses as they're generated
    rather than waiting for the complete response.

    Args:
        provider: Model provider to use
        model: Model name
    """
    load_environment()

    print(f"\n{'='*60}")
    print(f"Basic Streaming Example")
    print(f"{'='*60}")
    print(f"Provider: {provider}")
    print(f"Model: {model}")
    print(f"{'='*60}\n")

    if provider == "openai":
        chat_model = get_openai_model(model=model)
    else:
        from langchain_docker.core.models import init_model

        chat_model = init_model(provider, model)

    prompt = "Tell me a short story about a robot learning to paint."

    print(f"Prompt: {prompt}\n")
    print("Streaming response:")
    print("-" * 40)

    for chunk in chat_model.stream(prompt):
        print(chunk.content, end="", flush=True)

    print("\n" + "-" * 40)
    print("\n✓ Streaming complete\n")


def streaming_with_messages(
    provider: str = "openai",
    model: str = "gpt-4o-mini",
) -> None:
    """Demonstrate streaming with message history.

    Shows how to use streaming in a conversation context
    with message objects.

    Args:
        provider: Model provider to use
        model: Model name
    """
    load_environment()

    print(f"\n{'='*60}")
    print(f"Streaming with Message History")
    print(f"{'='*60}")
    print(f"Provider: {provider}")
    print(f"Model: {model}")
    print(f"{'='*60}\n")

    if provider == "openai":
        chat_model = get_openai_model(model=model)
    else:
        from langchain_docker.core.models import init_model

        chat_model = init_model(provider, model)

    messages = [
        HumanMessage(content="I'm interested in space exploration"),
        HumanMessage(content="Tell me an interesting fact about Mars"),
    ]

    print("User: I'm interested in space exploration")
    print("User: Tell me an interesting fact about Mars\n")
    print("Assistant (streaming): ", end="", flush=True)

    for chunk in chat_model.stream(messages):
        print(chunk.content, end="", flush=True)

    print("\n\n✓ Streaming complete\n")


def compare_streaming_vs_invoke(
    provider: str = "openai",
    model: str = "gpt-4o-mini",
) -> None:
    """Compare streaming vs non-streaming responses.

    Demonstrates the difference in user experience between
    waiting for a complete response vs seeing tokens as they arrive.

    Args:
        provider: Model provider to use
        model: Model name
    """
    load_environment()

    print(f"\n{'='*60}")
    print(f"Streaming vs Non-Streaming Comparison")
    print(f"{'='*60}")
    print(f"Provider: {provider}")
    print(f"Model: {model}")
    print(f"{'='*60}\n")

    if provider == "openai":
        chat_model = get_openai_model(model=model)
    else:
        from langchain_docker.core.models import init_model

        chat_model = init_model(provider, model)

    prompt = "Explain what streaming is in three sentences."

    # Non-streaming approach
    print("Method 1: invoke() - Wait for complete response")
    print("-" * 40)
    print("(waiting...)", end="", flush=True)

    response = chat_model.invoke(prompt)
    print(f"\r{response.content}\n")

    # Streaming approach
    print("Method 2: stream() - Display tokens as they arrive")
    print("-" * 40)

    for chunk in chat_model.stream(prompt):
        print(chunk.content, end="", flush=True)

    print("\n" + "-" * 40)
    print("\nKey Differences:")
    print("- invoke(): Waits for full response, then displays all at once")
    print("- stream(): Shows tokens immediately as they're generated")
    print("- stream() provides better UX for long responses")
    print("- Both methods produce the same content")
    print()


if __name__ == "__main__":
    basic_streaming()
    print("\n" + "="*60 + "\n")
    streaming_with_messages()
    print("\n" + "="*60 + "\n")
    compare_streaming_vs_invoke()
