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

### Chainlit UI
- **Interactive Chat Interface**: Modern web-based chat UI powered by Chainlit
- **Real-time Streaming**: See AI responses as they're being generated
- **Provider Selection**: Switch between OpenAI, Anthropic, and Google models on the fly
- **Temperature Control**: Adjust response creativity with a simple slider
- **Persistent Sessions**: Conversation history automatically maintained
- **Settings Panel**: Easy configuration without restarting the app

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

## Docker Setup (Recommended for Production)

Run the entire stack with Docker Compose:

### Prerequisites
- Docker and Docker Compose installed
- API keys configured in `.env` file

### Quick Start

```bash
# 1. Copy and configure environment file
cp .env.example .env
# Edit .env and add your API keys

# 2. Build and start all services
docker-compose up --build

# Or run in detached mode
docker-compose up -d --build
```

Once running:
- **Chainlit UI**: http://localhost:8001
- **FastAPI Backend**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Phoenix Tracing**: http://localhost:6006

### Docker Commands

```bash
# Start services
docker-compose up

# Start in background
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f

# View logs for specific service
docker-compose logs -f api
docker-compose logs -f ui

# Rebuild after code changes
docker-compose up --build

# Remove containers and volumes
docker-compose down -v
```

### Architecture

```
┌─────────────────┐         ┌─────────────────┐
│  Chainlit UI    │         │  FastAPI API    │
│  Container      │◄────────┤  Container      │
│  Port: 8001     │         │  Port: 8000     │
└─────────────────┘         └─────────────────┘
         │                           │
         │    Docker Network         │
         └───────────────────────────┘
                    │
         ┌──────────▼──────────┐
         │   LLM Providers     │
         │  (OpenAI/Anthropic/ │
         │      Google)        │
         └─────────────────────┘
```

### Benefits of Docker

- **Consistent Environment**: Same setup across dev, staging, and production
- **Easy Deployment**: Single command to deploy the entire stack
- **Isolation**: Services run in isolated containers
- **Scalability**: Easy to scale services independently
- **No Local Setup**: No need to install Python, uv, or dependencies

## Phoenix Tracing & Observability

Monitor, debug, and evaluate your LLM applications with Phoenix from Arize.

### What is Phoenix?

Phoenix provides:
- **LLM Tracing**: Track every LLM call with detailed spans
- **Performance Monitoring**: Latency, token usage, and cost tracking
- **Debugging Tools**: Inspect inputs, outputs, and intermediate steps
- **Evaluation Framework**: Test and evaluate LLM responses
- **Visualization**: Beautiful UI to explore your traces

### Running with Phoenix

**With Docker Compose** (Recommended):

Phoenix is included automatically when using Docker:

```bash
docker-compose up
```

Access Phoenix at: http://localhost:6006

**Without Docker** (Local Development):

1. Install and start Phoenix:
```bash
# Install Phoenix
pip install arize-phoenix

# Start Phoenix server
python -m phoenix.server.main serve
```

2. Phoenix will start on http://localhost:6006

3. Run your application:
```bash
# FastAPI backend
uv run langchain-docker serve

# Chainlit UI
uv run chainlit run chainlit_app/app.py --port 8001
```

### Accessing Phoenix UI

Open http://localhost:6006 in your browser to:
- View real-time traces of your LLM calls
- Analyze performance metrics
- Debug issues with detailed span information
- Export traces for analysis

### Features Available

**Automatic Instrumentation:**
- All LangChain operations are automatically traced
- Model invocations (invoke, stream)
- Agent executions
- Tool calls
- Message history

**Trace Information:**
- Model name and parameters
- Input prompts and output responses
- Token counts and costs
- Execution time
- Error details

### Configuration

Control Phoenix tracing via environment variables:

```bash
# Enable/disable tracing (default: true)
PHOENIX_ENABLED=true

# Phoenix endpoint (default: http://localhost:6006/v1/traces)
PHOENIX_ENDPOINT=http://localhost:6006/v1/traces

# Debug: print traces to console (default: false)
PHOENIX_CONSOLE_EXPORT=false
```

### Disabling Tracing

To disable Phoenix tracing:

```bash
# In .env file
PHOENIX_ENABLED=false
```

Or temporarily:

```bash
PHOENIX_ENABLED=false uv run langchain-docker serve
```

### Docker Compose Architecture

When using Docker Compose, the stack includes:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Phoenix    │     │  FastAPI    │     │  Chainlit   │
│  Port: 6006 │◄────│  Port: 8000 │◄────│  Port: 8001 │
│  (Tracing)  │     │  (Backend)  │     │  (Frontend) │
└─────────────┘     └─────────────┘     └─────────────┘
       │                    │                    │
       └────────────────────┴────────────────────┘
                   Docker Network
```

Phoenix traces are automatically sent from the API backend and visualized in the Phoenix UI.

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

## Chainlit UI

The project includes a fully-featured chat interface built with Chainlit.

### Starting the Chainlit UI

**You need to run both the FastAPI backend and Chainlit UI:**

```bash
# Terminal 1: Start the FastAPI backend
uv run langchain-docker serve

# Terminal 2: Start the Chainlit UI on port 8001
uv run chainlit run chainlit_app/app.py --port 8001

# Or with watch mode (auto-reload on changes)
uv run chainlit run chainlit_app/app.py --port 8001 -w
```

Once running:
- **Chainlit UI**: http://localhost:8001
- **API Backend**: http://localhost:8000

### Using the Chat Interface

1. **Welcome Screen**: When you first open the app, you'll see a welcome message with available providers
2. **Settings Panel**: Click the settings icon to:
   - Select your provider (OpenAI, Anthropic, or Google)
   - Adjust temperature (0.0 = focused, 2.0 = creative)
3. **Start Chatting**: Type your message and press Enter
4. **Streaming Responses**: Watch the AI response appear in real-time
5. **Session Persistence**: Your conversation history is automatically saved

### Features

- **Multiple Providers**: Switch between OpenAI, Anthropic, and Google models
- **Real-time Streaming**: See responses as they're generated
- **Temperature Control**: Adjust creativity with a slider (0.0 - 2.0)
- **Persistent Sessions**: Conversations are automatically maintained
- **Error Handling**: Clear error messages if the backend is unavailable

### Architecture

The Chainlit UI communicates with the FastAPI backend via HTTP:

```
┌─────────────┐      HTTP/SSE      ┌──────────────┐      LangChain      ┌─────────────┐
│  Chainlit   │ ◄─────────────────► │   FastAPI    │ ◄──────────────────► │  LLM APIs   │
│     UI      │   (localhost:8001)  │   Backend    │  (OpenAI/Anthropic)  │  (OpenAI/   │
│             │                     │              │                      │  Anthropic/ │
│ (Frontend)  │                     │ (Backend)    │                      │   Google)   │
└─────────────┘                     └──────────────┘                      └─────────────┘
```

### Configuration

The Chainlit app uses environment variables:

```bash
# Optional: Override default API backend URL
FASTAPI_BASE_URL=http://localhost:8000
```

All other configuration (API keys, models) is handled by the FastAPI backend through the shared `.env` file.

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
