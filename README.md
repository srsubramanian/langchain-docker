# LangChain Docker

A comprehensive demonstration of LangChain foundational models with examples for basic invocation, model customization, multiple providers, agents, and streaming responses.

## Features

### CLI Examples
- **Basic Model Invocation**: Initialize and use language models from different providers
- **Model Customization**: Control model behavior with parameters like temperature
- **Multi-Provider Support**: Work with OpenAI, Anthropic, and Google models
- **Agent Creation**: Build conversational agents with message history
- **Streaming Responses**: Display model outputs in real-time

### FastAPI Backend
- **REST API**: Full-featured REST API for chat, model management, and sessions
- **Chat Endpoints**: Non-streaming and Server-Sent Events (SSE) streaming support
- **Model Management**: List providers, get model details, validate configurations
- **Session Management**: Create, retrieve, list, and delete conversation sessions
- **CORS Support**: Ready for Chainlit and other frontend integrations

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd langchain-docker

# Install dependencies using uv
uv sync
```

## Configuration

Before running the examples, you need to configure your API keys:

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your API keys
# You need at least one provider configured
```

Get your API keys from:
- **OpenAI**: https://platform.openai.com/api-keys
- **Anthropic**: https://console.anthropic.com/
- **Google**: https://aistudio.google.com/app/apikey

## Usage

### Command Line Interface

Run examples using the `langchain-docker` command:

```bash
# Run all examples
uv run langchain-docker all

# Run specific examples
uv run langchain-docker basic
uv run langchain-docker customize
uv run langchain-docker providers
uv run langchain-docker agent
uv run langchain-docker stream

# Customize provider and model
uv run langchain-docker basic --provider anthropic
uv run langchain-docker basic --model gpt-4o --temperature 0.7
uv run langchain-docker stream --provider google
```

### As a Python Library

Import and use the examples in your own code:

```python
from langchain_docker import basic_invocation, load_environment

# Load API keys from .env
load_environment()

# Run an example
response = basic_invocation.basic_invoke_example(
    provider="openai",
    model="gpt-4o-mini",
    temperature=0.0
)

print(response.content)
```

### Using Core Utilities

```python
from langchain_docker import get_openai_model, init_model

# Get a pre-configured model
model = get_openai_model(model="gpt-4o-mini", temperature=0.5)
response = model.invoke("Hello!")

# Or initialize a custom model
model = init_model(
    provider="anthropic",
    model="claude-3-5-sonnet-20241022",
    temperature=0.0
)
```

## FastAPI Backend

The project includes a full REST API built with FastAPI.

### Starting the API Server

```bash
# Start the server
uv run langchain-docker serve

# With custom host and port
uv run langchain-docker serve --host 0.0.0.0 --port 8000

# With auto-reload for development
uv run langchain-docker serve --reload
```

Once running:
- **API Documentation**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

### API Endpoints

#### Chat Endpoints

**POST /api/v1/chat** - Non-streaming chat
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is FastAPI?",
    "provider": "openai",
    "model": "gpt-4o-mini",
    "temperature": 0.7
  }'
```

**POST /api/v1/chat/stream** - Streaming chat with SSE
```bash
curl -N -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Tell me a story",
    "provider": "openai",
    "stream": true
  }'
```

#### Model Management Endpoints

**GET /api/v1/models/providers** - List all providers
```bash
curl http://localhost:8000/api/v1/models/providers
```

**GET /api/v1/models/providers/{provider}** - Get provider details
```bash
curl http://localhost:8000/api/v1/models/providers/openai
```

**POST /api/v1/models/validate** - Validate model configuration
```bash
curl -X POST http://localhost:8000/api/v1/models/validate \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "model": "gpt-4o-mini",
    "temperature": 0.5
  }'
```

#### Session Management Endpoints

**POST /api/v1/sessions** - Create new session
```bash
curl -X POST http://localhost:8000/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"metadata": {"user_id": "user123"}}'
```

**GET /api/v1/sessions/{session_id}** - Get session details
```bash
curl http://localhost:8000/api/v1/sessions/{session_id}
```

**GET /api/v1/sessions** - List all sessions
```bash
curl "http://localhost:8000/api/v1/sessions?limit=10&offset=0"
```

**DELETE /api/v1/sessions/{session_id}** - Delete session
```bash
curl -X DELETE http://localhost:8000/api/v1/sessions/{session_id}
```

### Chainlit Integration

The API is ready for Chainlit integration:

```python
# In your Chainlit app
import httpx

async def send_message(message: str, session_id: str = None):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/chat",
            json={
                "message": message,
                "session_id": session_id,
                "provider": "openai"
            }
        )
        return response.json()
```

## Available Examples

### 1. Basic Invocation
Demonstrates how to initialize and invoke a language model:
```bash
uv run langchain-docker basic
```

### 2. Model Customization
Shows how different parameters affect model behavior:
```bash
uv run langchain-docker customize
```

### 3. Multi-Provider Comparison
Compares responses from OpenAI, Anthropic, and Google:
```bash
uv run langchain-docker providers
```

### 4. Agent and Conversations
Demonstrates multi-turn conversations with context:
```bash
uv run langchain-docker agent
```

### 5. Streaming Responses
Shows real-time token-by-token output:
```bash
uv run langchain-docker stream
```

## Supported Providers and Models

### OpenAI
- `gpt-4o-mini` (default) - Fast and cost-effective
- `gpt-4o` - Advanced reasoning
- `gpt-4-turbo` - Balanced performance

### Anthropic
- `claude-3-5-sonnet-20241022` (default) - Balanced
- `claude-3-5-haiku-20241022` - Fast
- `claude-3-opus-20240229` - Most capable

### Google
- `gemini-2.0-flash-exp` (default) - Experimental
- `gemini-1.5-pro` - Production
- `gemini-1.5-flash` - Fast

## Project Structure

```
src/langchain_docker/
├── __init__.py           # Package initialization and public API
├── __main__.py           # CLI entry point
├── cli.py                # Command-line interface
├── core/
│   ├── config.py        # Configuration and environment handling
│   └── models.py        # Model initialization utilities
├── examples/
│   ├── basic_invocation.py     # Basic model usage
│   ├── model_customization.py  # Parameter customization
│   ├── multi_provider.py       # Provider comparison
│   ├── agent_basics.py         # Agent creation
│   └── streaming.py            # Streaming output
└── utils/
    └── errors.py        # Custom exceptions
```

## Development

```bash
# Install development dependencies
uv add --dev pytest black ruff

# Run the package in development mode
uv run python -m langchain_docker basic

# Run a specific example directly
uv run python -m langchain_docker.examples.basic_invocation
```

## License

[Add your license information here]
