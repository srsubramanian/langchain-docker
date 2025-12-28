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
- **Memory Management**: Intelligent conversation summarization to prevent context overflow
- **CORS Support**: Ready for Chainlit and other frontend integrations

### Memory Management (NEW!)
- **Automatic Summarization**: Conversations are automatically summarized when they exceed configurable thresholds
- **Context Window Optimization**: Keep recent messages intact while summarizing older ones
- **Configurable Thresholds**: Control when summarization triggers and how many recent messages to preserve
- **LLM-Based Summaries**: Uses the same or a cheaper model to generate high-quality summaries
- **Transparent Operation**: Memory metadata included in API responses for observability
- **Graceful Fallback**: Simple text-based summaries if LLM summarization fails

### React Web UI (Recommended)
- **Modern Chat Interface**: Dark-themed UI inspired by LangSmith Agent Builder
- **Real-time Streaming**: SSE-based streaming with token-by-token display
- **Multi-Agent Workflows**: Visual React Flow diagrams showing agent coordination
- **Custom Agent Builder**: Single-page builder with live flow visualization
  - Inline agent name editing with Draft badge
  - Collapsible Instructions and Toolbox sections
  - Tool selection (blue nodes) and Skill selection (purple nodes)
  - Real-time Agent Flow diagram showing connected tools/skills
- **Skills Management**: Browse, create, and edit skills with progressive disclosure
- **Provider Selection**: Switch between OpenAI, Anthropic, Google, and Bedrock

### Chainlit UI (Legacy)
- **Interactive Chat Interface**: Web-based chat UI powered by Chainlit
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
- **React Web UI** (Recommended): http://localhost:8001
- **Chainlit UI** (Legacy): http://localhost:8002
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
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│  React Web UI   │   │  Chainlit UI    │   │  FastAPI API    │
│  (Recommended)  │   │  (Legacy)       │◄──┤  Container      │
│  Port: 8001     │◄──┤  Port: 8002     │   │  Port: 8000     │
└─────────────────┘   └─────────────────┘   └─────────────────┘
         │                    │                      │
         └────────────────────┴──────────────────────┘
                         Docker Network
                              │
                   ┌──────────▼──────────┐
                   │   LLM Providers     │
                   │  (OpenAI/Anthropic/ │
                   │   Google/Bedrock)   │
                   └─────────────────────┘
```

### Benefits of Docker

- **Consistent Environment**: Same setup across dev, staging, and production
- **Easy Deployment**: Single command to deploy the entire stack
- **Isolation**: Services run in isolated containers
- **Scalability**: Easy to scale services independently
- **No Local Setup**: No need to install Python, uv, or dependencies

## Tracing & Observability

Monitor, debug, and evaluate your LLM applications with your choice of tracing platform.

### Supported Platforms

| Platform | Type | Best For |
|----------|------|----------|
| **Phoenix** | Open source, self-hosted | Full control, no vendor lock-in |
| **LangSmith** | Hosted service | Zero-config with LangChain |

### Choosing a Platform

Set `TRACING_PROVIDER` in your `.env` file:

```bash
# Options: phoenix, langsmith, none
TRACING_PROVIDER=phoenix
```

---

## LangSmith (Hosted)

LangSmith is LangChain's hosted tracing solution with zero-config setup.

### Setup

1. Get your API key at https://smith.langchain.com/settings

2. Configure in `.env`:
```bash
TRACING_PROVIDER=langsmith
LANGCHAIN_API_KEY=lsv2_...
LANGCHAIN_PROJECT=langchain-docker  # optional
```

3. Run your application:
```bash
uv run langchain-docker serve
```

4. View traces at: https://smith.langchain.com

### LangSmith Features

- **Zero Configuration**: Just set API key and it works
- **Hosted Solution**: No infrastructure to manage
- **Deep LangChain Integration**: Auto-instrumentation of all LangChain operations
- **Playground**: Test prompts directly in the UI
- **Datasets & Evaluations**: Built-in evaluation tools

---

## Phoenix (Self-Hosted)

Phoenix from Arize is an open-source tracing platform with full self-hosting support.

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

### Phoenix Features

- **Open Source**: Full control, no vendor lock-in
- **Self-Hosted**: Your data stays on your infrastructure
- **Framework Agnostic**: Works with LangChain, LlamaIndex, and more
- **OpenTelemetry Native**: Integrates with existing observability stacks

### Accessing Phoenix UI

Open http://localhost:6006 in your browser to:
- View real-time traces of your LLM calls
- Analyze performance metrics
- Debug issues with detailed span information
- Export traces for analysis

### Phoenix Configuration

```bash
# Phoenix endpoint (default: http://localhost:6006/v1/traces)
PHOENIX_ENDPOINT=http://localhost:6006/v1/traces

# Debug: print traces to console (default: false)
PHOENIX_CONSOLE_EXPORT=false
```

---

## Common Features

Both platforms support these features:

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

**Session Tracking:**
- All traces are automatically grouped by conversation session
- Each session (conversation thread) gets a unique identifier
- View multi-turn conversations as connected traces
- Includes both user chat messages and automatic memory summarization traces
- Makes debugging long conversations much easier

### Session Grouping

Traces are automatically organized by session ID, making it easy to:
- **Debug Conversations**: Follow the flow of a multi-turn conversation
- **Analyze Performance**: See how response times change over conversation length
- **Track Memory Operations**: View when summarization occurs and how it affects context
- **Compare Sessions**: Analyze different user conversations side-by-side

### Disabling Tracing

To disable all tracing:

```bash
# In .env file
TRACING_PROVIDER=none
```

### Docker Compose Architecture

When using Docker Compose, the stack includes:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Phoenix    │     │  FastAPI    │     │  React UI   │     │  Chainlit   │
│  Port: 6006 │◄────│  Port: 8000 │◄────│  Port: 8001 │     │  Port: 8002 │
│  (Tracing)  │     │  (Backend)  │     │ (Recommend) │     │  (Legacy)   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                    │                    │                  │
       └────────────────────┴────────────────────┴──────────────────┘
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

#### Multi-Agent Endpoints (NEW!)

**GET /api/v1/agents/builtin** - List available agents
```bash
curl http://localhost:8000/api/v1/agents/builtin
```

**POST /api/v1/agents/workflows** - Create a multi-agent workflow
```bash
curl -X POST http://localhost:8000/api/v1/agents/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "my-workflow",
    "agents": ["math_expert", "weather_expert"],
    "provider": "openai"
  }'
```

**POST /api/v1/agents/workflows/{workflow_id}/invoke** - Invoke workflow
```bash
curl -X POST http://localhost:8000/api/v1/agents/workflows/my-workflow/invoke \
  -H "Content-Type: application/json" \
  -d '{"message": "What is 15 times 7, and what is the weather in Tokyo?"}'
```

**GET /api/v1/agents/workflows** - List active workflows
```bash
curl http://localhost:8000/api/v1/agents/workflows
```

**DELETE /api/v1/agents/workflows/{workflow_id}** - Delete workflow
```bash
curl -X DELETE http://localhost:8000/api/v1/agents/workflows/my-workflow
```

#### Skills API Endpoints

**GET /api/v1/skills** - List all skills (metadata only)
```bash
curl http://localhost:8000/api/v1/skills
```

**GET /api/v1/skills/{skill_id}** - Get full skill details
```bash
curl http://localhost:8000/api/v1/skills/write_sql
```

**POST /api/v1/skills** - Create a custom skill
```bash
curl -X POST http://localhost:8000/api/v1/skills \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Custom Skill",
    "description": "A custom skill for specific tasks",
    "category": "custom",
    "core_content": "Skill instructions and context..."
  }'
```

**POST /api/v1/skills/{skill_id}/load** - Load skill into agent context
```bash
curl -X POST http://localhost:8000/api/v1/skills/write_sql/load
```

#### Custom Agent Endpoints

**GET /api/v1/agents/tools** - List available tool templates
```bash
curl http://localhost:8000/api/v1/agents/tools
```

**POST /api/v1/agents/custom** - Create a custom agent
```bash
curl -X POST http://localhost:8000/api/v1/agents/custom \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Assistant",
    "system_prompt": "You are a helpful assistant...",
    "tools": [{"tool_id": "calculator", "config": {}}],
    "skills": ["write_sql"]
  }'
```

**GET /api/v1/agents/custom** - List custom agents
```bash
curl http://localhost:8000/api/v1/agents/custom
```

### Multi-Agent Workflows

The API supports LangGraph-based multi-agent workflows where a supervisor agent delegates tasks to specialized worker agents.

#### Architecture

```
                    ┌─────────────────┐
                    │   Supervisor    │
                    │     Agent       │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  Math Expert    │ │ Weather Expert  │ │ Research Expert │
│   (tools:       │ │   (tools:       │ │   (tools:       │
│  add,subtract,  │ │ get_weather)    │ │  search_web)    │
│  multiply,div)  │ │                 │ │                 │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

#### Built-in Agents

| Agent | Description | Tools |
|-------|-------------|-------|
| `math_expert` | Performs arithmetic calculations | add, subtract, multiply, divide |
| `weather_expert` | Gets weather information | get_current_weather |
| `research_expert` | Searches for information online | search_web |
| `finance_expert` | Gets stock prices and financial data | get_stock_price |

#### How It Works

1. **Create a Workflow**: Combine multiple agents into a workflow with a supervisor
2. **Invoke the Workflow**: Send a message that may require multiple agents
3. **Supervisor Delegation**: The supervisor analyzes the request and delegates to appropriate agents
4. **Aggregated Response**: Results from all agents are combined into a final response

#### Example: Complex Query

```bash
# 1. Create a workflow with math and weather agents
curl -X POST http://localhost:8000/api/v1/agents/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "assistant",
    "agents": ["math_expert", "weather_expert"],
    "provider": "openai"
  }'

# 2. Ask a question requiring both agents
curl -X POST http://localhost:8000/api/v1/agents/workflows/assistant/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is 15 times 7, and what is the weather in San Francisco?"
  }'

# Response:
# {
#   "response": "15 times 7 is 105. The weather in San Francisco is sunny, 68°F (20°C).",
#   "workflow_id": "assistant",
#   "message_count": 12
# }
```

#### Custom Supervisor Prompt

Customize how the supervisor delegates tasks:

```bash
curl -X POST http://localhost:8000/api/v1/agents/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "concise-assistant",
    "agents": ["math_expert", "weather_expert", "research_expert"],
    "provider": "openai",
    "supervisor_prompt": "You are a helpful assistant. Always be concise and direct. Delegate tasks to the appropriate specialist agents."
  }'
```

#### Session Tracking

Workflow invocations support session IDs for tracing in Phoenix or LangSmith:

```bash
curl -X POST http://localhost:8000/api/v1/agents/workflows/assistant/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Calculate 100 divided by 5",
    "session_id": "user-123-session"
  }'
```

### Memory Management

The API automatically manages conversation memory through intelligent summarization. When conversations exceed a configurable threshold, older messages are summarized to prevent context window overflow while preserving recent context.

#### How It Works

1. **Automatic Triggering**: When a conversation reaches 20 messages (default), summarization is triggered
2. **LLM-Based Summary**: Older messages are summarized using the same or a cheaper model
3. **Context Optimization**: Summary + recent 10 messages (default) are sent to the model
4. **Full History Preserved**: Complete message history is kept in the session for auditing

#### Configuration

Control memory management via environment variables in `.env`:

```bash
# Enable/disable memory management (default: true)
MEMORY_ENABLED=true

# Trigger summarization after N messages (default: 20)
MEMORY_TRIGGER_MESSAGE_COUNT=20

# Keep last N messages unsummarized (default: 10)
MEMORY_KEEP_RECENT_COUNT=10

# Optional: Use specific provider for summarization
MEMORY_SUMMARIZATION_PROVIDER=openai

# Optional: Use cheaper model for summarization (default: gpt-4o-mini)
MEMORY_SUMMARIZATION_MODEL=gpt-4o-mini

# Temperature for summarization (default: 0.0 for consistency)
MEMORY_SUMMARIZATION_TEMPERATURE=0.0
```

#### Per-Request Control

Override memory settings for individual requests:

```bash
# Custom trigger and keep-recent counts
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Continue our discussion",
    "session_id": "my-session",
    "provider": "openai",
    "memory_trigger_count": 30,
    "memory_keep_recent": 15
  }'
```

```bash
# Disable memory for specific request
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is the weather?",
    "session_id": "my-session",
    "provider": "openai",
    "enable_memory": false
  }'
```

#### Memory Metadata

Each response includes memory metadata for observability:

```json
{
  "session_id": "my-session",
  "message": {...},
  "conversation_length": 25,
  "memory_metadata": {
    "summarized": true,
    "summary_triggered": true,
    "total_messages": 25,
    "summarized_message_count": 15,
    "recent_message_count": 10,
    "summary_content": "The user asked about..."
  }
}
```

#### Benefits

- **Prevent Token Limit Errors**: Automatic context management prevents hitting model limits
- **Cost Optimization**: Reduce token usage in long conversations
- **Maintain Context**: Important information is preserved in summaries
- **Improved Performance**: Smaller context windows mean faster responses

## React Web UI (Recommended)

The project includes a modern React-based web UI inspired by LangSmith Agent Builder.

### Starting the React Web UI

**You need to run both the FastAPI backend and React dev server:**

```bash
# Terminal 1: Start the FastAPI backend
uv run langchain-docker serve

# Terminal 2: Start the React dev server
cd web_ui
npm install
npm run dev
```

Once running:
- **React Web UI**: http://localhost:3000 (dev) or http://localhost:8001 (Docker)
- **API Backend**: http://localhost:8000

### Features

| Route | Feature | Description |
|-------|---------|-------------|
| `/chat` | Streaming Chat | Real-time SSE streaming with provider/model selection |
| `/agents` | Multi-Agent Workflows | React Flow visualization of supervisor + agent coordination |
| `/builder` | Custom Agent Builder | Single-page builder with live flow diagram |
| `/skills` | Skills Management | Browse, create, and edit skills |

### Custom Agent Builder

The Builder page provides a LangSmith-inspired single-page layout:

1. **Header Bar**: Inline agent name input, Draft badge, Create Agent button
2. **Instructions Section** (Collapsible): System prompt with character counter
3. **Toolbox Section** (Collapsible):
   - **Tools Tab**: Select from available tools (shown as blue nodes in flow)
   - **Skills Tab**: Select skills for progressive disclosure (shown as purple nodes)
4. **Agent Flow Visualization**: Real-time diagram showing:
   - User Input → Agent → Response flow
   - Connected tools and skills with count badge
5. **Validation Summary**: Inline error display at bottom

### Tech Stack

- React 18 + Vite + TypeScript
- shadcn/ui (Radix UI primitives)
- Tailwind CSS (dark theme with teal accents)
- Zustand (state management with localStorage)
- React Flow (workflow visualization)
- React Router v6

---

## Chainlit UI (Legacy)

The project also includes a chat interface built with Chainlit.

### Starting the Chainlit UI

**You need to run both the FastAPI backend and Chainlit UI:**

```bash
# Terminal 1: Start the FastAPI backend
uv run langchain-docker serve

# Terminal 2: Start the Chainlit UI on port 8002
uv run chainlit run chainlit_app/app.py --port 8002

# Or with watch mode (auto-reload on changes)
uv run chainlit run chainlit_app/app.py --port 8002 -w
```

Once running:
- **Chainlit UI**: http://localhost:8002
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
│     UI      │   (localhost:8002)  │   Backend    │  (OpenAI/Anthropic)  │  (OpenAI/   │
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

### AWS Bedrock

#### Prerequisites
- AWS account with Bedrock access enabled
- AWS CLI configured (`aws configure` or `aws sso login`)
- IAM permissions for Bedrock model invocation

#### Setup

1. **Configure AWS credentials** (choose one method):
   ```bash
   # Option A: AWS CLI
   aws configure

   # Option B: AWS SSO
   aws sso login --profile your-profile

   # Option C: Environment variables
   export AWS_ACCESS_KEY_ID=your-key
   export AWS_SECRET_ACCESS_KEY=your-secret
   ```

2. **Enable Bedrock models**:
   - Visit https://console.aws.amazon.com/bedrock/
   - Navigate to "Model access"
   - Request access to desired models (Claude, Llama, Titan, etc.)

3. **Configure model ARNs** in `.env`:
   ```bash
   AWS_DEFAULT_REGION=us-east-1
   BEDROCK_MODEL_ARNS=anthropic.claude-3-5-sonnet-20241022-v2:0,anthropic.claude-3-5-haiku-20241022-v1:0
   ```

4. **Test Bedrock access**:
   ```bash
   # Run a simple test
   uv run langchain-docker basic --provider bedrock
   ```

#### Supported Models
Configure any Bedrock foundation model or inference profile ARN:
- **Anthropic Claude**: `anthropic.claude-3-5-sonnet-20241022-v2:0`
- **Meta Llama**: `meta.llama3-1-70b-instruct-v1:0`
- **Amazon Titan**: `amazon.titan-text-premier-v1:0`
- **Custom Inference Profiles**: Your own inference profile ARNs

#### IAM Permissions Required
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream",
        "bedrock:ListFoundationModels"
      ],
      "Resource": "*"
    }
  ]
}
```

#### Using with Docker

To use AWS Bedrock with Docker, mount your AWS credentials:

```yaml
# Add to docker-compose.yml
api:
  environment:
    - AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION}
    - BEDROCK_MODEL_ARNS=${BEDROCK_MODEL_ARNS}
  volumes:
    - ~/.aws:/root/.aws:ro  # Mount AWS credentials (read-only)
```

Or pass credentials as environment variables:
```yaml
api:
  environment:
    - AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION}
    - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
    - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
    - BEDROCK_MODEL_ARNS=${BEDROCK_MODEL_ARNS}
```

## Project Structure

```
src/langchain_docker/
├── __init__.py           # Package initialization and public API
├── __main__.py           # CLI entry point
├── cli.py                # Command-line interface
├── api/                  # FastAPI backend
│   ├── routers/         # API route handlers
│   │   ├── agents.py    # Multi-agent workflow endpoints
│   │   ├── chat.py      # Chat endpoints (streaming & non-streaming)
│   │   ├── skills.py    # Skills CRUD endpoints
│   │   └── sessions.py  # Session management
│   ├── schemas/         # Pydantic request/response models
│   └── services/        # Business logic layer
│       ├── agent_service.py   # Multi-agent orchestration
│       ├── skill_registry.py  # Progressive disclosure skills
│       └── tool_registry.py   # Tool templates for custom agents
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

web_ui/                   # React Web UI (recommended)
├── src/
│   ├── api/             # API client modules
│   ├── components/ui/   # shadcn/ui components (Button, Card, Collapsible, etc.)
│   ├── features/
│   │   ├── chat/        # ChatPage - streaming chat
│   │   ├── multiagent/  # MultiAgentPage - React Flow visualization
│   │   ├── builder/     # BuilderPage - single-page agent builder
│   │   └── skills/      # SkillsPage - skills management
│   └── stores/          # Zustand state management
├── Dockerfile           # Multi-stage build (Node → nginx)
└── nginx.conf           # SPA routing + API proxy

chainlit_app/            # Chainlit UI (legacy)
├── app.py               # Main Chainlit application
└── utils.py             # API client for FastAPI
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
