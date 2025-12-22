# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a comprehensive demonstration of LangChain foundational models, managed using `uv` (modern Python package manager). The project showcases examples for basic model invocation, customization, multi-provider support, agents, and streaming. It works as both a CLI tool and importable Python library.

Python version: 3.11+

## Development Commands

### Environment Setup
```bash
# Install dependencies (uv automatically creates/uses .venv)
uv sync

# Activate virtual environment (optional, uv run handles this)
source .venv/bin/activate

# Configure API keys
cp .env.example .env
# Edit .env and add your API keys for OpenAI, Anthropic, and/or Google
```

### Running Examples
```bash
# Run all examples
uv run langchain-docker all

# Run specific examples
uv run langchain-docker basic
uv run langchain-docker customize
uv run langchain-docker providers
uv run langchain-docker agent
uv run langchain-docker stream

# Run with custom options
uv run langchain-docker basic --provider anthropic
uv run langchain-docker basic --model gpt-4o --temperature 0.7
uv run langchain-docker stream --provider google

# Run as Python module
uv run python -m langchain_docker basic

# Run individual example files directly
uv run python -m langchain_docker.examples.basic_invocation
```

### Package Management
```bash
# Add a dependency
uv add <package-name>

# Add a dev dependency
uv add --dev <package-name>

# Update dependencies
uv sync
```

## Project Structure

```
src/langchain_docker/
├── __init__.py                 # Package initialization and public API exports
├── __main__.py                 # CLI entry point for `python -m langchain_docker`
├── cli.py                      # Command-line interface with argparse
├── core/
│   ├── __init__.py            # Core module exports
│   ├── config.py              # Environment variable handling and configuration
│   └── models.py              # Model initialization utilities and factory functions
├── examples/
│   ├── __init__.py            # Example module exports
│   ├── basic_invocation.py   # Basic model initialization and invocation
│   ├── model_customization.py # Temperature and parameter customization
│   ├── multi_provider.py     # Multiple provider comparison (OpenAI, Anthropic, Google)
│   ├── agent_basics.py       # Agent creation and multi-turn conversations
│   └── streaming.py          # Streaming output demonstrations
└── utils/
    ├── __init__.py            # Utility exports
    └── errors.py              # Custom exception classes

.env.example                    # Template for environment variables
.env                           # User's API keys (git-ignored)
pyproject.toml                 # Project metadata and dependencies
uv.lock                        # Locked dependency versions
CLAUDE.md                      # This file
README.md                      # User-facing documentation
```

## Architecture

### Core Modules

**config.py** (`src/langchain_docker/core/config.py`):
- `load_environment()`: Load .env file
- `validate_api_key(provider)`: Check if API key exists, raise error if missing
- `get_api_key(provider)`: Get API key without raising error
- `Config` dataclass: Store default settings

**models.py** (`src/langchain_docker/core/models.py`):
- `init_model(provider, model, **kwargs)`: Factory function using `init_chat_model()`
- `get_openai_model()`: Pre-configured OpenAI model
- `get_anthropic_model()`: Pre-configured Anthropic model
- `get_google_model()`: Pre-configured Google model
- `get_supported_providers()`: List available providers

**errors.py** (`src/langchain_docker/utils/errors.py`):
- `LangChainDockerError`: Base exception
- `APIKeyMissingError`: Raised when API keys missing (includes helpful setup instructions)
- `ModelInitializationError`: Raised when model initialization fails

### Example Modules

All example modules follow this pattern:
- Standalone, callable functions
- Clear docstrings
- Return values for testing
- Optional `if __name__ == "__main__"` blocks for direct execution

### CLI Design

The CLI uses argparse with subcommands:
- `basic`: Run basic invocation example
- `customize`: Model customization examples
- `providers`: Compare providers
- `agent`: Agent and conversations
- `stream`: Streaming output
- `all`: Run all examples in sequence

Each command supports `--provider`, `--model`, and `--temperature` flags where applicable.

## Development Workflow

### Adding a New Example

1. Create new file in `src/langchain_docker/examples/`
2. Implement standalone functions with docstrings
3. Add imports to `src/langchain_docker/examples/__init__.py`
4. Add subcommand to `cli.py` in `create_parser()`
5. Add handler function in `cli.py`
6. Update `__all__` in `src/langchain_docker/__init__.py`
7. Update README.md with new example

### Adding a New Provider

1. Add provider-specific package: `uv add langchain-<provider>`
2. Add API key environment variable to `.env.example`
3. Update `validate_api_key()` in `core/config.py`
4. Add `get_<provider>_model()` function in `core/models.py`
5. Update `get_supported_providers()` in `core/models.py`
6. Update documentation in README.md and CLAUDE.md

## Important Patterns

### Error Handling
- Fail fast for missing API keys with helpful error messages
- Graceful degradation for optional providers in multi-provider examples
- Custom exceptions include setup instructions

### Environment Variables
All API keys are loaded from `.env` file:
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GOOGLE_API_KEY`
- Optional: `DEFAULT_MODEL_PROVIDER`, `DEFAULT_MODEL_NAME`, `DEFAULT_TEMPERATURE`

### Model Initialization
```python
from langchain_core.language_models import init_chat_model

model = init_chat_model(
    model="gpt-4o-mini",
    model_provider="openai",
    temperature=0.0
)
```

### Streaming Pattern
```python
for chunk in model.stream("Your prompt"):
    print(chunk.content, end="", flush=True)
print()  # Newline at end
```

### Multi-turn Conversations
```python
from langchain_core.messages import HumanMessage, AIMessage

messages = [HumanMessage(content="Hi, I'm Alice")]
response1 = model.invoke(messages)
messages.append(response1)
messages.append(HumanMessage(content="What's my name?"))
response2 = model.invoke(messages)
```

## Build System

This project uses `uv_build` as the build backend (specified in `pyproject.toml`). The CLI entry point is defined in `[project.scripts]` as `langchain-docker = "langchain_docker:main"`.
