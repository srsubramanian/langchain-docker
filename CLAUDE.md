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

### Running the Chainlit UI

**Note: The Chainlit UI requires the FastAPI backend to be running.**

```bash
# Terminal 1: Start FastAPI backend
uv run langchain-docker serve

# Terminal 2: Start Chainlit UI on port 8001
uv run chainlit run chainlit_app/app.py --port 8001

# With watch mode (auto-reload on file changes)
uv run chainlit run chainlit_app/app.py --port 8001 -w
```

Once running:
- Chainlit UI: http://localhost:8001
- FastAPI Backend: http://localhost:8000

### Running with Docker

**For production deployments or consistent environments:**

```bash
# Build and start all services
docker-compose up --build

# Run in detached mode (background)
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

**Docker Compose Services:**
- `api`: FastAPI backend on port 8000
- `ui`: Chainlit UI on port 8001
- Shared network: `langchain-network`
- Health checks enabled for automatic dependency management

**Environment:**
- API keys loaded from `.env` file
- Chainlit automatically connects to API via `http://api:8000` (internal network)

### Running with Phoenix Tracing

**Phoenix is automatically included when using Docker Compose:**

```bash
docker-compose up
```

**Services running:**
- Phoenix UI: http://localhost:6006
- FastAPI Backend: http://localhost:8000
- Chainlit UI: http://localhost:8001

**For local development without Docker:**

```bash
# Terminal 1: Start Phoenix server
python -m phoenix.server.main serve

# Terminal 2: Start FastAPI
uv run langchain-docker serve

# Terminal 3: Start Chainlit
uv run chainlit run chainlit_app/app.py --port 8001
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
├── api/                        # FastAPI backend
│   ├── __init__.py            # API package initialization
│   ├── app.py                 # FastAPI app factory and configuration
│   ├── dependencies.py        # Dependency injection for services
│   ├── middleware.py          # Error handling middleware
│   ├── routers/               # API route modules
│   │   ├── __init__.py
│   │   ├── agents.py         # Multi-agent workflow endpoints
│   │   ├── chat.py           # Chat endpoints (streaming & non-streaming)
│   │   ├── models.py         # Model management endpoints
│   │   └── sessions.py       # Session/conversation history endpoints
│   ├── schemas/               # Pydantic models for request/response
│   │   ├── __init__.py
│   │   ├── agents.py         # Multi-agent workflow schemas
│   │   ├── chat.py           # Chat request/response schemas
│   │   ├── models.py         # Model schemas
│   │   └── sessions.py       # Session schemas
│   └── services/              # Business logic layer
│       ├── __init__.py
│       ├── agent_service.py  # Multi-agent workflow orchestration (LangGraph)
│       ├── chat_service.py   # Chat orchestration
│       ├── memory_service.py # Conversation memory and summarization
│       ├── model_service.py  # Model instance caching (LRU)
│       └── session_service.py # Session storage & retrieval (in-memory)
├── core/
│   ├── __init__.py            # Core module exports
│   ├── config.py              # Environment variable handling and configuration
│   ├── models.py              # Model initialization utilities and factory functions
│   └── tracing.py             # Phoenix tracing configuration and setup
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

chainlit_app/                   # Chainlit UI application
├── app.py                     # Main Chainlit application
├── utils.py                   # API client for FastAPI communication
├── chainlit.md                # Welcome page markdown
├── .chainlit/                 # Chainlit configuration
│   └── config.toml           # UI and app settings
└── public/                    # Static assets (optional)

.env.example                    # Template for environment variables
.env                           # User's API keys (git-ignored)
pyproject.toml                 # Project metadata and dependencies
uv.lock                        # Locked dependency versions
Dockerfile                     # Docker image definition
docker-compose.yml             # Multi-container orchestration
.dockerignore                  # Files to exclude from Docker build
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
- `agents.py`: WorkflowCreateRequest, WorkflowInvokeRequest, WorkflowInvokeResponse, BuiltinAgentInfo
- `chat.py`: MessageSchema, ChatRequest, ChatResponse, StreamEvent, MemoryMetadata
- `sessions.py`: SessionCreate, SessionResponse, SessionList, DeleteResponse
- `models.py`: ProviderInfo, ProviderDetails, ValidateRequest, ValidateResponse

**Services** (`src/langchain_docker/api/services/`):
- Business logic layer, reuses 100% of existing core functionality
- `agent_service.py`: Multi-agent workflow orchestration
  - LangGraph supervisor pattern for agent coordination
  - Built-in agents: math_expert, weather_expert, research_expert, finance_expert
  - Methods: `create_workflow()`, `invoke_workflow()`, `list_workflows()`, `delete_workflow()`
  - Uses `create_react_agent()` and `create_supervisor()` from langgraph
- `session_service.py`: Thread-safe in-memory session storage with TTL cleanup
  - OrderedDict-based LRU storage with max 1000 sessions
  - Background thread removes expired sessions (24h default TTL)
  - Methods: `create()`, `get()`, `get_or_create()`, `list()`, `delete()`, `clear()`
- `model_service.py`: LRU cache for model instances
  - Caches up to 10 models by (provider, model, temperature) key
  - Thread-safe with Lock for concurrent access
  - Reuses `init_model()` from core/models.py
  - Methods: `get_or_create()`, `list_providers()`, `get_provider_models()`
- `memory_service.py`: Conversation memory and summarization
  - Automatic summarization when conversations exceed thresholds
  - Methods: `process_conversation()`, `_should_summarize()`, `_summarize_messages()`
- `chat_service.py`: Orchestrates chat interactions
  - Converts Pydantic schemas to LangChain messages
  - Integrates with MemoryService for context optimization
  - Methods: `process_message()` (non-streaming), `stream_message()` (async generator)

**Routers** (`src/langchain_docker/api/routers/`):
- FastAPI route handlers using dependency injection
- `agents.py`: Multi-agent workflow endpoints (GET builtin, POST workflows, POST invoke, DELETE)
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
- `get_session_service()`, `get_model_service()`, `get_chat_service()`, `get_memory_service()`, `get_agent_service()`

**App Factory** (`src/langchain_docker/api/app.py`):
- `create_app()`: Configures FastAPI with CORS, routers, exception handlers
- CORS enabled for Chainlit integration (localhost:3000, 8000, 8001)
- Health check at `/health`, detailed status at `/api/v1/status`

### Chainlit UI Modules

The Chainlit UI provides a web-based chat interface that communicates with the FastAPI backend.

**app.py** (`chainlit_app/app.py`):
- Main Chainlit application with chat lifecycle handlers
- `@cl.on_chat_start`: Initialize session, check API health, fetch providers
- `@cl.on_message`: Handle incoming user messages, stream responses
- `@cl.on_settings_update`: Handle provider/temperature changes
- Uses Chainlit's `ChatSettings` for provider selection and temperature control

**utils.py** (`chainlit_app/utils.py`):
- `APIClient` class: HTTP client for FastAPI communication
- Methods: `chat()`, `chat_stream()`, `create_session()`, `get_session()`, `list_providers()`
- Handles SSE streaming by parsing "data: " prefixed lines
- Configurable via `FASTAPI_BASE_URL` environment variable

**chainlit.md** (`chainlit_app/chainlit.md`):
- Welcome page displayed when chat starts
- Provides usage instructions and feature documentation

**config.toml** (`chainlit_app/.chainlit/config.toml`):
- Chainlit configuration: UI theme, features, telemetry
- Project name: "LangChain Docker Chat"
- Shows README as default, session timeout: 3600s

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

### Developing the Chainlit UI

1. **Start both services during development**:
   ```bash
   # Terminal 1: FastAPI with reload
   uv run langchain-docker serve --reload

   # Terminal 2: Chainlit with watch mode on port 8001
   uv run chainlit run chainlit_app/app.py --port 8001 -w
   ```

2. **Modify the UI**:
   - Edit `chainlit_app/app.py` for chat logic and handlers
   - Edit `chainlit_app/utils.py` for API client changes
   - Edit `chainlit_app/chainlit.md` for welcome page content
   - Edit `chainlit_app/.chainlit/config.toml` for UI theme/settings

3. **Test UI changes**:
   - Chainlit auto-reloads when files change (with `-w` flag)
   - Check browser console for JavaScript errors
   - Check terminal for Python errors

4. **Add new Chainlit features**:
   - Use `@cl.on_chat_start` for initialization logic
   - Use `@cl.on_message` for message handling
   - Use `@cl.on_settings_update` for settings changes
   - Use `@cl.action_callback` for custom button actions
   - Use `cl.user_session.set/get` for state management

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
- `FASTAPI_BASE_URL` (default: http://localhost:8000) - For Chainlit UI to connect to backend

**Tracing Configuration:**
- `TRACING_PROVIDER` (default: phoenix) - Tracing platform: "langsmith", "phoenix", or "none"

**LangSmith (if TRACING_PROVIDER=langsmith):**
- `LANGCHAIN_API_KEY` - LangSmith API key (required)
- `LANGCHAIN_PROJECT` (default: langchain-docker) - Project name in LangSmith
- `LANGCHAIN_ENDPOINT` (optional) - LangSmith API endpoint

**Phoenix (if TRACING_PROVIDER=phoenix):**
- `PHOENIX_ENDPOINT` (default: http://localhost:6006/v1/traces) - Phoenix collector endpoint
- `PHOENIX_CONSOLE_EXPORT` (default: false) - Export traces to console for debugging

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

### Chainlit Chat Handler Pattern
```python
# In chainlit_app/app.py
import chainlit as cl

@cl.on_message
async def main(message: cl.Message):
    # Get settings from user session
    provider = cl.user_session.get("provider")
    session_id = cl.user_session.get("session_id")

    # Create streaming message
    msg = cl.Message(content="", author="Assistant")
    await msg.send()

    # Stream from API
    async for event in api_client.chat_stream(
        message=message.content,
        session_id=session_id,
        provider=provider,
    ):
        if event.get("event") == "token":
            await msg.stream_token(event.get("content", ""))

    await msg.update()
```

### Chainlit Settings Pattern
```python
# In chainlit_app/app.py
from chainlit.input_widget import Select, Slider

@cl.on_chat_start
async def start():
    # Configure settings panel
    settings = await cl.ChatSettings([
        Select(
            id="provider",
            label="Model Provider",
            values=["openai", "anthropic", "google"],
            initial_value="openai",
        ),
        Slider(
            id="temperature",
            label="Temperature",
            initial=0.7,
            min=0.0,
            max=2.0,
            step=0.1,
        ),
    ]).send()

@cl.on_settings_update
async def settings_update(settings):
    # Save to user session
    cl.user_session.set("provider", settings["provider"])
    cl.user_session.set("temperature", settings["temperature"])
```

### Chainlit API Client Pattern
```python
# In chainlit_app/utils.py
class APIClient:
    async def chat_stream(self, message: str, **kwargs) -> AsyncGenerator:
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", f"{self.base_url}/api/v1/chat/stream", json=payload) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])  # Parse SSE format
                        yield data
```

### Multi-Agent Workflow Pattern (LangGraph Supervisor)
```python
# In agent_service.py
from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor
from langchain_core.tools import tool

# Define tools for agents
@tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

@tool
def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Sunny, 68°F in {city}"

# Create specialized agents
math_agent = create_react_agent(
    model=llm,
    tools=[add, subtract, multiply, divide],
    name="math_expert",
    prompt="You are a math expert. Use tools to perform calculations."
)

weather_agent = create_react_agent(
    model=llm,
    tools=[get_weather],
    name="weather_expert",
    prompt="You are a weather expert. Provide weather information."
)

# Create supervisor workflow
workflow = create_supervisor(
    agents=[math_agent, weather_agent],
    model=llm,
    prompt="Delegate tasks to the appropriate specialist agent."
)

# Compile and invoke
app = workflow.compile()
result = app.invoke({"messages": [HumanMessage(content="What is 5+5 and weather in NYC?")]})
```

### Tracing Session Pattern
```python
# In tracing.py - wrap operations in session context for trace grouping
from langchain_docker.core.tracing import trace_session

# All LLM calls within this context will be grouped by session_id
with trace_session(session_id="user-123"):
    result = model.invoke(messages)
    # Traces appear grouped in Phoenix/LangSmith UI
```

## Build System

This project uses `uv_build` as the build backend (specified in `pyproject.toml`). The CLI entry point is defined in `[project.scripts]` as `langchain-docker = "langchain_docker:main"`.
