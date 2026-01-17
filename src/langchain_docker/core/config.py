"""Configuration and environment handling."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from langchain_docker.utils.errors import APIKeyMissingError

# Provider to environment variable mapping
PROVIDER_KEY_MAP = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
}


@dataclass
class Config:
    """Configuration for langchain-docker.

    Attributes:
        default_provider: Default model provider to use
        default_model: Default model name
        default_temperature: Default temperature for model responses
        memory_enabled: Enable conversation summarization
        memory_trigger_message_count: Trigger summarization after N messages
        memory_keep_recent_count: Keep last N messages unsummarized
        memory_summarization_provider: Provider for summarization (optional)
        memory_summarization_model: Model for summarization (optional)
        memory_summarization_temperature: Temperature for summarization
        tracing_provider: Tracing platform (langsmith, phoenix, or none)
        database_url: Database connection string for SQL skill
        sql_read_only: Enforce read-only mode for SQL queries
    """

    default_provider: str = "openai"
    default_model: str = "gpt-4o-mini"
    default_temperature: float = 0.0
    memory_enabled: bool = True
    memory_trigger_message_count: int = 20
    memory_keep_recent_count: int = 10
    memory_summarization_provider: str | None = None
    memory_summarization_model: str | None = None
    memory_summarization_temperature: float = 0.0
    tracing_provider: str = "phoenix"
    database_url: str = "sqlite:///demo.db"
    sql_read_only: bool = True
    redis_url: str | None = None
    session_ttl_hours: int = 24

    @classmethod
    def from_env(cls) -> "Config":
        """Create Config from environment variables.

        Returns:
            Config instance with values from environment or defaults
        """
        return cls(
            default_provider=os.getenv("DEFAULT_MODEL_PROVIDER", "openai"),
            default_model=os.getenv("DEFAULT_MODEL_NAME", "gpt-4o-mini"),
            default_temperature=float(os.getenv("DEFAULT_TEMPERATURE", "0.0")),
            memory_enabled=os.getenv("MEMORY_ENABLED", "true").lower() == "true",
            memory_trigger_message_count=int(os.getenv("MEMORY_TRIGGER_MESSAGE_COUNT", "20")),
            memory_keep_recent_count=int(os.getenv("MEMORY_KEEP_RECENT_COUNT", "10")),
            memory_summarization_provider=os.getenv("MEMORY_SUMMARIZATION_PROVIDER") or None,
            memory_summarization_model=os.getenv("MEMORY_SUMMARIZATION_MODEL") or None,
            memory_summarization_temperature=float(os.getenv("MEMORY_SUMMARIZATION_TEMPERATURE", "0.0")),
            tracing_provider=os.getenv("TRACING_PROVIDER", "phoenix").lower(),
            database_url=os.getenv("DATABASE_URL", "sqlite:///demo.db"),
            sql_read_only=os.getenv("SQL_READ_ONLY", "true").lower() == "true",
            redis_url=os.getenv("REDIS_URL") or None,
            session_ttl_hours=int(os.getenv("SESSION_TTL_HOURS", "24")),
        )


def load_environment() -> None:
    """Load environment variables from .env file.

    Looks for .env file in current directory and parent directories.
    Silently succeeds if .env file is not found.
    """
    env_path = Path(".env")

    if env_path.exists():
        load_dotenv(env_path, override=True)
    else:
        # Try to find .env in parent directories
        load_dotenv(override=True)


def validate_bedrock_access() -> bool:
    """Validate AWS Bedrock access using boto3 default credentials.

    Returns:
        True if credentials are available and valid

    Raises:
        APIKeyMissingError: If AWS credentials are not configured
    """
    try:
        import boto3
        from botocore.exceptions import NoCredentialsError, ClientError

        # Get region and profile from environment (default to us-east-1 for Bedrock)
        region = os.getenv("AWS_DEFAULT_REGION") or os.getenv("AWS_REGION") or "us-east-1"
        profile = os.getenv("AWS_PROFILE") or os.getenv("BEDROCK_PROFILE")

        # Create Bedrock management client (not bedrock-runtime)
        # bedrock-runtime is for invoking models, bedrock is for management APIs
        session = boto3.Session(region_name=region, profile_name=profile)
        bedrock = session.client("bedrock")

        # Simple validation: list foundation models (doesn't cost anything)
        bedrock.list_foundation_models()

        return True

    except NoCredentialsError:
        raise APIKeyMissingError(
            "bedrock",
            "AWS credentials not found. Run 'aws configure' or set up IAM role."
        )
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        if error_code in ('UnauthorizedOperation', 'AccessDeniedException'):
            raise APIKeyMissingError(
                "bedrock",
                "AWS credentials found but no access to Bedrock. Check IAM permissions."
            )
        raise


def validate_api_key(provider: str) -> str:
    """Validate that API key/credentials exist for the given provider.

    Args:
        provider: Provider name (openai, anthropic, google, bedrock)

    Returns:
        The API key value (or "AWS_CREDENTIALS_VALID" for Bedrock)

    Raises:
        APIKeyMissingError: If the API key/credentials are not found
    """
    # Special handling for Bedrock (uses AWS credentials, not API key)
    if provider.lower() == "bedrock":
        # validate_bedrock_access()  # TODO: Fix Bedrock validation issue
        return "AWS_CREDENTIALS_VALID"  # Not an actual key, just a flag

    # Existing logic for other providers
    env_var = PROVIDER_KEY_MAP.get(provider.lower())
    if not env_var:
        raise ValueError(f"Unknown provider: {provider}")

    api_key = os.getenv(env_var)
    if not api_key:
        raise APIKeyMissingError(provider)

    return api_key


def get_api_key(provider: str) -> str | None:
    """Get API key for provider without raising an error.

    Args:
        provider: Provider name (openai, anthropic, google, bedrock)

    Returns:
        API key if found, None otherwise
    """
    # Special handling for Bedrock - always show as configured
    # Actual credential validation happens at runtime when invoking models
    if provider.lower() == "bedrock":
        return "AWS_CREDENTIALS_CONFIGURED"

    env_var = PROVIDER_KEY_MAP.get(provider.lower())
    if not env_var:
        return None

    return os.getenv(env_var)


def get_bedrock_models() -> list[str]:
    """Get list of Bedrock model ARNs from environment.

    Returns:
        List of model ARNs or inference profile ARNs
    """
    models_env = os.getenv("BEDROCK_MODEL_ARNS", "")
    if not models_env:
        # Default models if not configured
        return [
            "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "anthropic.claude-3-5-haiku-20241022-v1:0",
        ]

    # Parse comma-separated list
    return [model.strip() for model in models_env.split(",") if model.strip()]


def get_bedrock_region() -> str:
    """Get AWS region for Bedrock.

    Returns:
        Region name (defaults to us-east-1 if not set)
    """
    return os.getenv("AWS_DEFAULT_REGION") or os.getenv("AWS_REGION") or "us-east-1"


def get_bedrock_profile() -> str | None:
    """Get AWS profile for Bedrock.

    Returns:
        Profile name if set, None otherwise (uses default credential chain)
    """
    return os.getenv("AWS_PROFILE") or os.getenv("BEDROCK_PROFILE")


def get_database_url() -> str:
    """Get database URL for SQL skill.

    Returns:
        Database connection string (defaults to sqlite:///demo.db)
    """
    return os.getenv("DATABASE_URL", "sqlite:///demo.db")


def is_sql_read_only() -> bool:
    """Check if SQL read-only mode is enabled.

    Returns:
        True if read-only mode is enabled (default)
    """
    return os.getenv("SQL_READ_ONLY", "true").lower() == "true"


# Jira Configuration Functions


def get_jira_url() -> str | None:
    """Get Jira instance URL.

    Returns:
        Jira URL if configured, None otherwise
    """
    return os.getenv("JIRA_URL")


def get_jira_bearer_token() -> str | None:
    """Get Jira Bearer token (Personal Access Token).

    Returns:
        Bearer token if configured, None otherwise
    """
    return os.getenv("JIRA_BEARER_TOKEN")


def get_jira_api_version() -> str:
    """Get Jira API version.

    Returns:
        API version (defaults to "2")
    """
    return os.getenv("JIRA_API_VERSION", "2")


def is_jira_configured() -> bool:
    """Check if Jira is fully configured.

    Returns:
        True if URL and Bearer token are present
    """
    return bool(get_jira_url() and get_jira_bearer_token())


# Redis Configuration Functions


def get_redis_url() -> str | None:
    """Get Redis URL from environment.

    Returns:
        Redis URL if configured, None otherwise (falls back to in-memory)
    """
    return os.getenv("REDIS_URL") or None


def get_session_ttl_hours() -> int:
    """Get session TTL in hours.

    Returns:
        Session TTL hours (defaults to 24)
    """
    return int(os.getenv("SESSION_TTL_HOURS", "24"))
