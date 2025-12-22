"""Custom exception classes and error handling utilities."""


class LangChainDockerError(Exception):
    """Base exception for langchain-docker."""

    pass


class APIKeyMissingError(LangChainDockerError):
    """Raised when required API key is not configured."""

    def __init__(self, provider: str, message: str | None = None):
        self.provider = provider
        if message is None:
            message = self._get_default_message()
        super().__init__(message)

    def _get_default_message(self) -> str:
        """Generate helpful error message for missing API key."""
        instructions = get_setup_instructions(self.provider)
        return (
            f"{self.provider.upper()}_API_KEY not found in environment.\n\n"
            f"{instructions}\n\n"
            f"After obtaining your API key:\n"
            f"1. Create a .env file in the project root (copy from .env.example)\n"
            f"2. Add: {self.provider.upper()}_API_KEY=your-key-here\n"
            f"3. Restart your application"
        )


class ModelInitializationError(LangChainDockerError):
    """Raised when model initialization fails."""

    def __init__(self, provider: str, model: str, original_error: Exception):
        self.provider = provider
        self.model = model
        self.original_error = original_error
        message = (
            f"Failed to initialize {provider} model '{model}'.\n"
            f"Error: {str(original_error)}\n\n"
            f"Please check:\n"
            f"1. Your API key is correct\n"
            f"2. The model name is valid for {provider}\n"
            f"3. Your account has access to this model"
        )
        super().__init__(message)


def get_setup_instructions(provider: str) -> str:
    """Get setup instructions for a specific provider.

    Args:
        provider: Model provider name (openai, anthropic, google)

    Returns:
        Setup instructions string
    """
    instructions = {
        "openai": (
            "Get your OpenAI API key:\n"
            "1. Visit https://platform.openai.com/api-keys\n"
            "2. Sign in or create an account\n"
            "3. Create a new API key"
        ),
        "anthropic": (
            "Get your Anthropic API key:\n"
            "1. Visit https://console.anthropic.com/\n"
            "2. Sign in or create an account\n"
            "3. Navigate to API Keys section\n"
            "4. Create a new API key"
        ),
        "google": (
            "Get your Google API key:\n"
            "1. Visit https://aistudio.google.com/app/apikey\n"
            "2. Sign in with your Google account\n"
            "3. Create a new API key"
        ),
    }

    return instructions.get(
        provider.lower(),
        f"Please obtain an API key for {provider} and set {provider.upper()}_API_KEY in your .env file.",
    )
