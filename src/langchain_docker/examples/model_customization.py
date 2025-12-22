"""Model customization examples showing parameter effects."""

from langchain.chat_models import init_chat_model

from langchain_docker.core.config import load_environment


def temperature_comparison(
    provider: str = "openai",
    model: str = "gpt-4o-mini",
) -> None:
    """Compare model responses with different temperature settings.

    Temperature controls randomness in responses:
    - 0.0: Deterministic, focused, consistent
    - 1.0: Creative, varied, exploratory

    Args:
        provider: Model provider to use
        model: Model name to use
    """
    load_environment()

    print(f"\n{'='*60}")
    print(f"Temperature Comparison Example")
    print(f"{'='*60}")
    print(f"Provider: {provider}")
    print(f"Model: {model}")
    print(f"{'='*60}\n")

    prompt = "Write a creative opening line for a sci-fi story."

    print(f"Prompt: {prompt}\n")
    print(f"{'-'*60}\n")

    # Low temperature - deterministic
    print("Temperature = 0.0 (Deterministic)")
    print("-" * 40)
    model_low = init_chat_model(
        model=model,
        model_provider=provider,
        temperature=0.0,
    )
    response_low = model_low.invoke(prompt)
    print(f"{response_low.content}\n")

    # High temperature - creative
    print("Temperature = 1.0 (Creative)")
    print("-" * 40)
    model_high = init_chat_model(
        model=model,
        model_provider=provider,
        temperature=1.0,
    )
    response_high = model_high.invoke(prompt)
    print(f"{response_high.content}\n")

    print("Note: Running this example multiple times will show that:")
    print("- Temperature 0.0 produces consistent outputs")
    print("- Temperature 1.0 produces varied, creative outputs")
    print()


def parameter_showcase(
    provider: str = "openai",
    model: str = "gpt-4o-mini",
) -> None:
    """Demonstrate various model parameters.

    Shows how different parameters affect model behavior.

    Args:
        provider: Model provider to use
        model: Model name to use
    """
    load_environment()

    print(f"\n{'='*60}")
    print(f"Model Parameters Showcase")
    print(f"{'='*60}")
    print(f"Provider: {provider}")
    print(f"Model: {model}")
    print(f"{'='*60}\n")

    # Example 1: max_tokens
    print("Example 1: Limiting Response Length with max_tokens")
    print("-" * 40)

    chat_model = init_chat_model(
        model=model,
        model_provider=provider,
        temperature=0.0,
        max_tokens=50,
    )

    response = chat_model.invoke("Explain quantum computing in detail.")
    print(f"Response (max 50 tokens): {response.content}\n")

    # Example 2: Default (no token limit)
    print("Example 2: Full Response (no token limit)")
    print("-" * 40)

    chat_model_full = init_chat_model(
        model=model,
        model_provider=provider,
        temperature=0.0,
    )

    response_full = chat_model_full.invoke("Explain quantum computing in one sentence.")
    print(f"Response: {response_full.content}\n")

    print("Parameter Summary:")
    print("- temperature: Controls randomness (0.0 = deterministic, 1.0 = creative)")
    print("- max_tokens: Limits response length")
    print("- Other parameters vary by provider (top_p, frequency_penalty, etc.)")
    print()


if __name__ == "__main__":
    temperature_comparison()
    print("\n" + "="*60 + "\n")
    parameter_showcase()
