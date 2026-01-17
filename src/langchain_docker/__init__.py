"""LangChain Docker - Multi-provider LLM API Server

A comprehensive LangChain demonstration with multi-provider LLM support.
Features include basic model invocation, agents, streaming, MCP server
integration, and skills with progressive disclosure.
"""

__version__ = "0.1.0"

# Import core functionality
from langchain_docker.core.config import Config, load_environment, validate_api_key
from langchain_docker.core.models import (
    get_anthropic_model,
    get_bedrock_model,
    get_google_model,
    get_openai_model,
    get_supported_providers,
    init_model,
    create_bedrock_client,
)

# Import CLI entry point
from langchain_docker.cli import main

__all__ = [
    "__version__",
    "Config",
    "load_environment",
    "validate_api_key",
    "init_model",
    "get_openai_model",
    "get_anthropic_model",
    "get_google_model",
    "get_bedrock_model",
    "get_supported_providers",
    "create_bedrock_client",
    "main",
]
