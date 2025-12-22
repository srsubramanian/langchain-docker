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

### Running the API Server
```bash
# Start the FastAPI server
uv run langchain-docker serve

# With custom host and port
uv run langchain-docker serve --host 0.0.0.0 --port 8000

# With auto-reload for development
uv run langchain-docker serve --reload

# Direct uvicorn command
uv run uvicorn langchain_docker.api.app:app --reload --port 8000
```

Once running:
- API Documentation: http://localhost:8000/docs
- Alternative Docs: http://localhost:8000/redoc
- Health Check: http://localhost:8000/health
- Status: http://localhost:8000/api/v1/status

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
├── api/                        # FastAPI backend
│   ├── __init__.py            # API package initialization
│   ├── app.py                 # FastAPI app factory and configuration
│   ├── dependencies.py        # Dependency injection for services
│   ├── middleware.py          # Error handling middleware
│   ├── routers/               # API route modules
│   │   ├── __init__.py
│   │   ├── chat.py           # Chat endpoints (streaming & non-streaming)
│   │   ├── models.py         # Model management endpoints
│   │   └── sessions.py       # Session/conversation history endpoints
│   ├── schemas/               # Pydantic models for request/response
│   │   ├── __init__.py
│   │   ├── chat.py           # Chat request/response schemas
│   │   ├── models.py         # Model schemas
│   │   └── sessions.py       # Session schemas
│   └── services/              # Business logic layer
│       ├── __init__.py
│       ├── chat_service.py   # Chat orchestration
│       ├── model_service.py  # Model instance caching (LRU)
│       └── session_service.py # Session storage & retrieval (in-memory)
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
- `SessionNotFoundError`: Raised when session ID not found
- `InvalidProviderError`: Raised when invalid provider specified

### API Modules

The API follows a layered architecture: **Routers → Services → Core**

**Schemas** (`src/langchain_docker/api/schemas/`):
- Pydantic models for request/response validation
- `chat.py`: MessageSchema, ChatRequest, ChatResponse, StreamEvent
- `sessions.py`: SessionCreate, SessionResponse, SessionList, DeleteResponse
- `models.py`: ProviderInfo, ProviderDetails, ValidateRequest, ValidateResponse

**Services** (`src/langchain_docker/api/services/`):
- Business logic layer, reuses 100% of existing core functionality
- `session_service.py`: Thread-safe in-memory session storage with TTL cleanup
  - OrderedDict-based LRU storage with max 1000 sessions
  - Background thread removes expired sessions (24h default TTL)
  - Methods: `create()`, `get()`, `get_or_create()`, `list()`, `delete()`, `clear()`
- `model_service.py`: LRU cache for model instances
  - Caches up to 10 models by (provider, model, temperature) key
  - Thread-safe with Lock for concurrent access
  - Reuses `init_model()` from core/models.py
  - Methods: `get_or_create()`, `list_providers()`, `get_provider_models()`
- `chat_service.py`: Orchestrates chat interactions
  - Converts Pydantic schemas to LangChain messages
  - Methods: `process_message()` (non-streaming), `stream_message()` (async generator)

**Routers** (`src/langchain_docker/api/routers/`):
- FastAPI route handlers using dependency injection
- `chat.py`: POST /api/v1/chat, POST /api/v1/chat/stream (SSE)
- `models.py`: GET /api/v1/models/providers, GET /api/v1/models/providers/{provider}, POST /api/v1/models/validate
- `sessions.py`: Full CRUD for sessions (POST, GET, LIST, DELETE)

**Middleware** (`src/langchain_docker/api/middleware.py`):
- Maps custom exceptions to HTTP responses
- `APIKeyMissingError` → 503 Service Unavailable
- `ModelInitializationError` → 500 Internal Server Error
- `SessionNotFoundError` → 404 Not Found
- `InvalidProviderError` → 400 Bad Request

**Dependencies** (`src/langchain_docker/api/dependencies.py`):
- Singleton instances via `@lru_cache` for services
- `get_session_service()`, `get_model_service()`, `get_chat_service()`

**App Factory** (`src/langchain_docker/api/app.py`):
- `create_app()`: Configures FastAPI with CORS, routers, exception handlers
- CORS enabled for Chainlit integration (localhost:3000, 8000, 8001)
- Health check at `/health`, detailed status at `/api/v1/status`

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
- `serve`: Start FastAPI server (supports `--host`, `--port`, `--reload` flags)

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

### Adding a New API Endpoint

1. Define Pydantic schemas in `src/langchain_docker/api/schemas/`
2. Add business logic to appropriate service in `src/langchain_docker/api/services/`
3. Create route handler in `src/langchain_docker/api/routers/`
4. Register router in `api/app.py` if it's a new router module
5. Add error handling to `api/middleware.py` if needed
6. Update OpenAPI documentation (FastAPI auto-generates from docstrings)
7. Test endpoint via `/docs` or curl
8. Update README.md with endpoint examples

### Testing API Endpoints

```bash
# Start the server with reload
uv run langchain-docker serve --reload

# In another terminal, test endpoints

# Health check
curl http://localhost:8000/health

# List providers
curl http://localhost:8000/api/v1/models/providers

# Non-streaming chat
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello", "provider": "openai"}'

# Streaming chat with SSE
curl -N -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "Tell me a story", "provider": "openai", "stream": true}'

# Create session
curl -X POST http://localhost:8000/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"metadata": {"user_id": "test123"}}'

# Get session
curl http://localhost:8000/api/v1/sessions/{session_id}
```

## Important Patterns

### Error Handling
- Fail fast for missing API keys with helpful error messages
- Graceful degradation for optional providers in multi-provider examples
- Custom exceptions include setup instructions

### Environment Variables
All API keys and configuration are loaded from `.env` file:

**Required (at least one provider):**
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GOOGLE_API_KEY`

**Optional:**
- `DEFAULT_MODEL_PROVIDER`, `DEFAULT_MODEL_NAME`, `DEFAULT_TEMPERATURE`
- `API_HOST` (default: 0.0.0.0)
- `API_PORT` (default: 8000)
- `API_RELOAD` (default: false)
- `API_LOG_LEVEL` (default: info)
- `SESSION_TTL_HOURS` (default: 24)
- `MODEL_CACHE_SIZE` (default: 10)

### Model Initialization
```python
from langchain.chat_models import init_chat_model

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

### API SSE Streaming Pattern
```python
from sse_starlette.sse import EventSourceResponse

async def stream_events():
    # Start event
    yield {"event": "start", "data": json.dumps({"session_id": session_id})}

    # Stream tokens
    for chunk in model.stream(messages):
        yield {"event": "token", "data": json.dumps({"content": chunk.content})}

    # Done event
    yield {"event": "done", "data": json.dumps({"message_count": len(session.messages)})}

return EventSourceResponse(stream_events())
```

### API Session Management Pattern
```python
# In chat_service.py - get or create session
session = self.session_service.get_or_create(request.session_id)

# Convert Pydantic schema to LangChain message
user_message = HumanMessage(content=request.message)
session.messages.append(user_message)

# Invoke model with full conversation history
model = self.model_service.get_or_create(request.provider, request.model, request.temperature)
response = model.invoke(session.messages)

# Save response to session
session.messages.append(response)
```

### API Dependency Injection Pattern
```python
# In dependencies.py
from functools import lru_cache
from fastapi import Depends

@lru_cache
def get_session_service() -> SessionService:
    return SessionService()

# In routers
def chat_endpoint(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service)
):
    return chat_service.process_message(request)
```

### API Error Handling Pattern
```python
# In middleware.py - map exceptions to HTTP responses
@app.exception_handler(APIKeyMissingError)
async def api_key_missing_handler(request: Request, exc: APIKeyMissingError):
    return JSONResponse(
        status_code=503,
        content={
            "error": "Service Unavailable",
            "message": str(exc),
            "provider": exc.provider,
            "setup_url": get_setup_url(exc.provider),
        }
    )
```

## Build System

This project uses `uv_build` as the build backend (specified in `pyproject.toml`). The CLI entry point is defined in `[project.scripts]` as `langchain-docker = "langchain_docker:main"`.
