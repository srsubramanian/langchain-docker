"""LangChain Docker - Foundational Models Examples

A comprehensive demonstration of LangChain foundational models
with examples for basic invocation, model customization, multiple
providers, agents, and streaming.
"""

__version__ = "0.1.0"

# Import core functionality
from langchain_docker.core.config import Config, load_environment, validate_api_key
from langchain_docker.core.models import (
    get_anthropic_model,
    get_google_model,
    get_openai_model,
    get_supported_providers,
    init_model,
)

# Import example modules for library usage
from langchain_docker.examples import (
    agent_basics,
    basic_invocation,
    model_customization,
    multi_provider,
    streaming,
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
    "get_supported_providers",
    "basic_invocation",
    "model_customization",
    "multi_provider",
    "agent_basics",
    "streaming",
    "main",
]
