"""Examples demonstrating multiple model providers."""

from langchain_docker.core.config import get_api_key, load_environment
from langchain_docker.core.models import (
    get_anthropic_model,
    get_google_model,
    get_openai_model,
)
from langchain_docker.utils.errors import APIKeyMissingError


def compare_providers() -> None:
    """Compare responses from different model providers.

    Sends the same prompt to OpenAI, Anthropic, and Google models
    and displays their responses side-by-side.

    Gracefully handles missing API keys for providers.
    """
    load_environment()

    print(f"\n{'='*60}")
    print(f"Multi-Provider Comparison")
    print(f"{'='*60}\n")

    prompt = "In one sentence, what makes you unique as an AI?"

    print(f"Prompt: {prompt}\n")
    print(f"{'-'*60}\n")

    providers = [
        ("openai", "gpt-4o-mini", get_openai_model),
        ("anthropic", "claude-sonnet-4-20250514", get_anthropic_model),
        ("google", "gemini-2.0-flash-exp", get_google_model),
    ]

    results = {}

    for provider_name, model_name, get_model_func in providers:
        print(f"{provider_name.upper()}: {model_name}")
        print("-" * 40)

        if not get_api_key(provider_name):
            message = f"API key not configured. Set {provider_name.upper()}_API_KEY in .env"
            print(f"⚠️  {message}\n")
            results[provider_name] = None
            continue

        try:
            model = get_model_func()
            response = model.invoke(prompt)
            print(f"{response.content}\n")
            results[provider_name] = response.content
        except APIKeyMissingError as e:
            print(f"⚠️  {str(e)}\n")
            results[provider_name] = None
        except Exception as e:
            print(f"❌ Error: {str(e)}\n")
            results[provider_name] = None

    configured_count = sum(1 for v in results.values() if v is not None)
    print(f"{'='*60}")
    print(f"Summary: {configured_count}/{len(providers)} providers configured")
    print(f"{'='*60}\n")


def provider_specific_features() -> None:
    """Demonstrate provider-specific features and model naming.

    Shows the different model naming conventions and available
    models for each provider.
    """
    load_environment()

    print(f"\n{'='*60}")
    print(f"Provider-Specific Features")
    print(f"{'='*60}\n")

    print("OpenAI Models:")
    print("-" * 40)
    print("- gpt-4o-mini (fast, cost-effective)")
    print("- gpt-4o (advanced reasoning)")
    print("- gpt-4-turbo (balanced performance)")
    print()

    print("Anthropic Models:")
    print("-" * 40)
    print("- claude-sonnet-4-20250514 (most balanced, recommended)")
    print("- claude-opus-4-20250514 (most capable)")
    print("- claude-haiku-4-20250110 (fastest, cost-effective)")
    print()

    print("Google Models:")
    print("-" * 40)
    print("- gemini-2.0-flash-exp (experimental)")
    print("- gemini-1.5-pro (production)")
    print("- gemini-1.5-flash (fast)")
    print()

    print("Usage Examples:")
    print("-" * 40)
    print('from langchain_docker.core.models import get_openai_model')
    print()
    print('# Use specific model')
    print('model = get_openai_model(model="gpt-4o")')
    print()
    print('# Custom temperature')
    print('model = get_openai_model(temperature=0.7)')
    print()


if __name__ == "__main__":
    compare_providers()
    provider_specific_features()
