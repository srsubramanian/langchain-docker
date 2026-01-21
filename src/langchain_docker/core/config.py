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
        opensearch_url: OpenSearch URL for vector knowledge base
        opensearch_index: OpenSearch index name for knowledge base
        embedding_provider: Provider for embeddings (openai, etc.)
        embedding_model: Model name for embeddings
        rag_chunk_size: Chunk size for document splitting
        rag_chunk_overlap: Overlap between chunks
        rag_default_top_k: Default number of documents to retrieve
        graph_rag_enabled: Enable Graph RAG with Neo4j (default: false)
        neo4j_url: Neo4j Bolt URL for graph storage
        neo4j_username: Neo4j username
        neo4j_password: Neo4j password
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
    # Knowledge Base / RAG settings
    opensearch_url: str | None = None
    opensearch_index: str = "knowledge_base"
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    rag_chunk_size: int = 500
    rag_chunk_overlap: int = 50
    rag_default_top_k: int = 5
    # Graph RAG settings
    graph_rag_enabled: bool = False
    neo4j_url: str | None = None
    neo4j_username: str = "neo4j"
    neo4j_password: str | None = None

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
            opensearch_url=os.getenv("OPENSEARCH_URL") or None,
            opensearch_index=os.getenv("OPENSEARCH_INDEX", "knowledge_base"),
            embedding_provider=os.getenv("EMBEDDING_PROVIDER", "openai"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
            rag_chunk_size=int(os.getenv("RAG_CHUNK_SIZE", "500")),
            rag_chunk_overlap=int(os.getenv("RAG_CHUNK_OVERLAP", "50")),
            rag_default_top_k=int(os.getenv("RAG_DEFAULT_TOP_K", "5")),
            graph_rag_enabled=os.getenv("GRAPH_RAG_ENABLED", "false").lower() == "true",
            neo4j_url=os.getenv("NEO4J_URL") or None,
            neo4j_username=os.getenv("NEO4J_USERNAME", "neo4j"),
            neo4j_password=os.getenv("NEO4J_PASSWORD") or None,
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


# Knowledge Base / RAG Configuration Functions


def get_opensearch_url() -> str | None:
    """Get OpenSearch URL from environment.

    Returns:
        OpenSearch URL if configured, None otherwise
    """
    return os.getenv("OPENSEARCH_URL") or None


def get_opensearch_index() -> str:
    """Get OpenSearch index name.

    Returns:
        Index name (defaults to knowledge_base)
    """
    return os.getenv("OPENSEARCH_INDEX", "knowledge_base")


def get_embedding_provider() -> str:
    """Get embedding provider name.

    Returns:
        Provider name (defaults to openai)
    """
    return os.getenv("EMBEDDING_PROVIDER", "openai")


def get_embedding_model() -> str:
    """Get embedding model name.

    Returns:
        Model name (defaults to text-embedding-3-small)
    """
    return os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")


def get_rag_chunk_size() -> int:
    """Get chunk size for document splitting.

    Returns:
        Chunk size in characters (defaults to 500)
    """
    return int(os.getenv("RAG_CHUNK_SIZE", "500"))


def get_rag_chunk_overlap() -> int:
    """Get chunk overlap for document splitting.

    Returns:
        Overlap in characters (defaults to 50)
    """
    return int(os.getenv("RAG_CHUNK_OVERLAP", "50"))


def get_rag_default_top_k() -> int:
    """Get default number of documents to retrieve.

    Returns:
        Top K value (defaults to 5)
    """
    return int(os.getenv("RAG_DEFAULT_TOP_K", "5"))


def is_opensearch_configured() -> bool:
    """Check if OpenSearch is configured.

    Returns:
        True if OPENSEARCH_URL is set
    """
    return bool(get_opensearch_url())


# Docling Configuration Functions


def get_docling_max_tokens() -> int:
    """Get max tokens per chunk for Docling HybridChunker.

    Returns:
        Max tokens per chunk (default: 512)
    """
    return int(os.getenv("DOCLING_MAX_TOKENS", "512"))


def is_docling_ocr_enabled() -> bool:
    """Check if OCR should be enabled for scanned PDFs.

    Note: OCR requires tesseract-ocr system dependency.

    Returns:
        True if OCR is enabled (default: false)
    """
    return os.getenv("DOCLING_ENABLE_OCR", "false").lower() == "true"


def get_docling_tokenizer() -> str:
    """Get tokenizer for Docling HybridChunker.

    The tokenizer should approximate the embedding model's tokenization
    for optimal chunk sizing.

    Returns:
        Tokenizer name (default: sentence-transformers/all-MiniLM-L6-v2)
    """
    return os.getenv("DOCLING_TOKENIZER", "sentence-transformers/all-MiniLM-L6-v2")


def is_docling_table_extraction_enabled() -> bool:
    """Check if table extraction should be enabled.

    Returns:
        True if table extraction is enabled (default: true)
    """
    return os.getenv("DOCLING_ENABLE_TABLES", "true").lower() == "true"


# ============================================================
# Graph RAG Configuration (LlamaIndex + Neo4j)
# ============================================================


def is_graph_rag_enabled() -> bool:
    """Check if Graph RAG is enabled.

    Graph RAG provides entity-aware retrieval using LlamaIndex
    PropertyGraphIndex and Neo4j for knowledge graph storage.

    Returns:
        True if GRAPH_RAG_ENABLED is set to "true"
    """
    return os.getenv("GRAPH_RAG_ENABLED", "false").lower() == "true"


def get_neo4j_url() -> str | None:
    """Get Neo4j Bolt URL.

    Returns:
        Neo4j Bolt URL if configured (e.g., bolt://localhost:7687)
    """
    return os.getenv("NEO4J_URL") or None


def get_neo4j_username() -> str:
    """Get Neo4j username.

    Returns:
        Neo4j username (default: neo4j)
    """
    return os.getenv("NEO4J_USERNAME", "neo4j")


def get_neo4j_password() -> str | None:
    """Get Neo4j password.

    Returns:
        Neo4j password if configured
    """
    return os.getenv("NEO4J_PASSWORD") or None


def _to_upper_snake_case(s: str) -> str:
    """Convert a string to UPPER_SNAKE_CASE.

    Handles PascalCase, camelCase, and existing snake_case.
    Preserves consecutive uppercase letters (acronyms like API, BIN, MCC).

    Examples:
        PaymentNetwork -> PAYMENT_NETWORK
        API -> API
        cardNetwork -> CARD_NETWORK
        already_snake -> ALREADY_SNAKE
    """
    import re
    # Insert underscore before uppercase letters that follow lowercase letters
    # But NOT between consecutive uppercase letters (preserves acronyms)
    s = re.sub(r'([a-z])([A-Z])', r'\1_\2', s)
    # Handle transition from acronym to word: APIKey -> API_KEY
    s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', s)
    return s.upper().replace(' ', '_').replace('__', '_')


def get_graph_rag_entities() -> list[str]:
    """Get entity types for knowledge graph extraction.

    These entity types are used by LlamaIndex SchemaLLMPathExtractor
    to guide entity extraction from documents.

    Entity types are normalized to UPPERCASE for LlamaIndex compatibility,
    which uses entity types as Neo4j node labels.

    Returns:
        List of entity type names (UPPERCASE)
    """
    default = "PERSON,ORGANIZATION,PROJECT,TECHNOLOGY,CONCEPT,DOCUMENT"
    entities = os.getenv("GRAPH_RAG_ENTITIES", default).split(",")
    normalized = []
    for e in entities:
        e = e.strip()
        if e:
            normalized.append(_to_upper_snake_case(e))
    return normalized


def get_graph_rag_relations() -> list[str]:
    """Get relationship types for knowledge graph extraction.

    These relationship types are used by LlamaIndex SchemaLLMPathExtractor
    to guide relationship extraction between entities.

    Relation types are normalized to UPPERCASE with underscores for
    LlamaIndex/Neo4j compatibility.

    Returns:
        List of relationship type names (UPPERCASE)
    """
    default = "WORKS_ON,LEADS,MEMBER_OF,USES,RELATED_TO,PART_OF,CONTAINS"
    relations = os.getenv("GRAPH_RAG_RELATIONS", default).split(",")
    normalized = []
    for r in relations:
        r = r.strip()
        if r:
            normalized.append(_to_upper_snake_case(r))
    return normalized


def is_neo4j_configured() -> bool:
    """Check if Neo4j is fully configured.

    Returns:
        True if NEO4J_URL and NEO4J_PASSWORD are set
    """
    return bool(get_neo4j_url() and get_neo4j_password())


def get_graph_rag_llm_provider() -> str:
    """Get the LLM provider for GraphRAG entity extraction.

    Supported providers:
    - "openai": Uses OpenAI models (default)
    - "bedrock": Uses AWS Bedrock models (e.g., Claude Sonnet)

    Returns:
        Provider name (lowercase)
    """
    return os.getenv("GRAPH_RAG_LLM_PROVIDER", "openai").lower()


def get_graph_rag_llm_model() -> str:
    """Get the LLM model for GraphRAG entity extraction.

    Default depends on the provider:
    - OpenAI: gpt-4o-mini
    - Bedrock: anthropic.claude-3-5-sonnet-20241022-v2:0

    Returns:
        Model identifier string
    """
    provider = get_graph_rag_llm_provider()
    if provider == "bedrock":
        default = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    else:
        default = "gpt-4o-mini"
    return os.getenv("GRAPH_RAG_LLM_MODEL", default)


def get_graph_rag_embed_provider() -> str:
    """Get the embedding provider for GraphRAG.

    Supported providers:
    - "openai": Uses OpenAI embeddings (default)
    - "bedrock": Uses AWS Bedrock embeddings (Titan)

    Returns:
        Provider name (lowercase)
    """
    return os.getenv("GRAPH_RAG_EMBED_PROVIDER", "openai").lower()


def get_graph_rag_embed_model() -> str:
    """Get the embedding model for GraphRAG.

    Default depends on the provider:
    - OpenAI: text-embedding-3-small
    - Bedrock: amazon.titan-embed-text-v2:0

    Returns:
        Model identifier string
    """
    provider = get_graph_rag_embed_provider()
    if provider == "bedrock":
        default = "amazon.titan-embed-text-v2:0"
    else:
        default = "text-embedding-3-small"
    return os.getenv("GRAPH_RAG_EMBED_MODEL", default)


def get_graph_rag_aws_region() -> str:
    """Get AWS region for Bedrock GraphRAG.

    Falls back to AWS_DEFAULT_REGION if GRAPH_RAG_AWS_REGION not set.

    Returns:
        AWS region string
    """
    return os.getenv("GRAPH_RAG_AWS_REGION") or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
