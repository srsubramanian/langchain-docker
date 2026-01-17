# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A comprehensive LangChain demonstration with multi-provider LLM support, managed using `uv`. Features include basic model invocation, agents, streaming, MCP server integration, and skills with progressive disclosure. Works as both CLI tool and importable Python library.

**Python version:** 3.13+

## Quick Start

```bash
# Setup
uv sync
cp .env.example .env  # Add API keys

# Run API server
uv run langchain-docker serve

# Run React UI (in another terminal)
cd web_ui && npm install && npm run dev

# Docker (includes Redis, Phoenix tracing)
docker-compose up --build
```

**Service URLs:**
- React Web UI: http://localhost:3000 (dev) / http://localhost:8001 (Docker)
- FastAPI API: http://localhost:8000/docs
- Phoenix Tracing: http://localhost:6006
- Redis: localhost:6379

## Project Structure (Key Files)

```
src/langchain_docker/
├── cli.py                      # CLI with argparse subcommands
├── api/
│   ├── app.py                 # FastAPI app factory
│   ├── dependencies.py        # Singleton services via @lru_cache
│   ├── routers/               # API endpoints (chat, sessions, agents, mcp, skills, models)
│   ├── schemas/               # Pydantic request/response models
│   ├── services/
│   │   ├── session_service.py    # Session storage (Redis or in-memory)
│   │   ├── redis_session_store.py # Redis-backed storage with TTL
│   │   ├── session_serializer.py  # LangChain message serialization
│   │   ├── chat_service.py       # Chat orchestration with MCP tools
│   │   ├── agent_service.py      # Multi-agent workflows (LangGraph)
│   │   ├── mcp_server_manager.py # MCP subprocess lifecycle
│   │   ├── mcp_tool_service.py   # MCP tool discovery/execution
│   │   ├── skill_registry.py     # Skills with progressive disclosure
│   │   ├── memory_service.py     # Conversation summarization
│   │   └── model_service.py      # Model instance LRU cache
│   └── mcp_servers.json       # MCP server configuration
├── core/
│   ├── config.py              # Environment config, Redis URL helpers
│   ├── models.py              # Model factory (OpenAI, Anthropic, Google, Bedrock)
│   └── tracing.py             # Phoenix/LangSmith tracing setup
├── skills/                     # Skill markdown files (sql/, xlsx/, jira/)
└── examples/                   # CLI example modules

web_ui/                         # React Web UI (Vite + shadcn/ui + React Flow)
├── src/
│   ├── api/                   # API clients (chat, sessions, models, agents, mcp)
│   ├── features/              # Pages (chat, multiagent, builder, skills)
│   └── stores/                # Zustand stores (session, settings, user, mcp)
```

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  React UI   │────▶│  FastAPI    │────▶│    Redis    │     │   Phoenix   │
│  Port 8001  │     │  Port 8000  │     │  Port 6379  │     │  Port 6006  │
└─────────────┘     └──────┬──────┘     │  (Sessions) │     │  (Tracing)  │
                           │            └─────────────┘     └─────────────┘
                           ▼
                    ┌─────────────┐
                    │ LLM APIs    │
                    │ OpenAI etc  │
                    └─────────────┘
```

## Session Storage

Sessions support two storage backends controlled by `REDIS_URL` environment variable:

**In-Memory (default):** No config needed, sessions lost on restart
```python
# dependencies.py - No REDIS_URL set
session_service = SessionService(ttl_hours=24)  # Uses OrderedDict
```

**Redis (persistent):** Sessions survive restarts, support horizontal scaling
```bash
# Start Redis
docker run -d --name langchain-redis -p 6379:6379 redis:7-alpine redis-server --appendonly yes

# Set in .env
REDIS_URL=redis://localhost:6379/0
```

**Key files:**
- `session_service.py`: Storage abstraction, delegates to Redis or in-memory
- `redis_session_store.py`: Redis operations with TTL and user indexing
- `session_serializer.py`: LangChain message ↔ JSON conversion

**Redis data structure:**
```
session:{id}           → JSON session data (with SETEX TTL)
user:{user_id}:sessions → Set of session IDs for user
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/chat` | Non-streaming chat |
| `POST /api/v1/chat/stream` | SSE streaming with tool events |
| `GET/POST/DELETE /api/v1/sessions` | Session CRUD |
| `GET /api/v1/models/providers` | List LLM providers |
| `GET /api/v1/mcp/servers` | List MCP servers |
| `POST /api/v1/mcp/servers/{id}/start` | Start MCP server |
| `GET /api/v1/skills` | List skills |
| `POST /api/v1/agents/workflows` | Create multi-agent workflow |

## Environment Variables

**Required (at least one):**
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`

**Session Storage:**
- `REDIS_URL` - Redis connection (e.g., `redis://localhost:6379/0`)
- `SESSION_TTL_HOURS` - Session expiry (default: 24)

**Tracing:**
- `TRACING_PROVIDER` - `langsmith`, `phoenix`, or `none`
- `LANGCHAIN_API_KEY` - For LangSmith
- `PHOENIX_ENDPOINT` - For Phoenix (default: `http://localhost:6006/v1/traces`)

**AWS Bedrock:**
- `AWS_PROFILE`, `AWS_DEFAULT_REGION`, `BEDROCK_MODEL_ARNS`

**Skills:**
- `DATABASE_URL` - For SQL skill (default: `sqlite:///demo.db`)
- `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN` - For Jira skill

## Key Patterns

### Model Initialization
```python
from langchain_docker.core.models import init_model
model = init_model(provider="openai", model="gpt-4o-mini", temperature=0.7)
```

### Session with Redis
```python
# In dependencies.py
from langchain_docker.core.config import get_redis_url, get_session_ttl_hours

@lru_cache
def get_session_service() -> SessionService:
    return SessionService(
        ttl_hours=get_session_ttl_hours(),
        redis_url=get_redis_url()  # None = in-memory
    )
```

### SSE Streaming
```python
async def stream_events():
    yield {"event": "start", "data": json.dumps({"session_id": sid})}
    for chunk in model.stream(messages):
        yield {"event": "token", "data": json.dumps({"content": chunk.content})}
    yield {"event": "done", "data": json.dumps({})}
return EventSourceResponse(stream_events())
```

### Multi-User Sessions
```python
# Sessions scoped by X-User-ID header
def get_current_user_id(x_user_id: str | None = Header(None, alias="X-User-ID")) -> str:
    return x_user_id or "default"

# Filtering
sessions = session_service.list(user_id=current_user_id)
```

### MCP Tool Integration
```python
# In chat_service.py
mcp_tools = await mcp_tool_service.get_langchain_tools(server_ids)
model_with_tools = model.bind_tools(mcp_tools)
response = await model_with_tools.ainvoke(messages)
```

### Skills Progressive Disclosure
```python
class SQLSkill(Skill):
    def load_core(self) -> str:
        """Level 2: Load schema on-demand."""
        return f"Tables: {self._db.get_usable_table_names()}"

    def execute_query(self, query: str) -> str:
        if self.read_only and not query.upper().startswith("SELECT"):
            return "Error: Read-only mode"
        return self._db.run(query)
```

## Development Workflows

### Adding a New Provider
1. `uv add langchain-<provider>`
2. Add API key to `.env.example`
3. Add `get_<provider>_model()` to `core/models.py`
4. Update `get_supported_providers()`

### Adding a New Skill
1. Create `skills/my_skill/SKILL.md` with YAML frontmatter
2. Create skill class in `skill_registry.py`
3. Register in `SkillRegistry._register_builtin_skills()`
4. AgentService auto-creates `my_skill_expert` agent

### Adding a New MCP Server
1. Add to `mcp_servers.json`:
   ```json
   "my-server": {
     "name": "My Server",
     "command": "npx",
     "args": ["-y", "my-mcp-package"],
     "enabled": true
   }
   ```
2. Restart backend

### Testing API
```bash
# Health check
curl http://localhost:8000/health

# Streaming chat
curl -N -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello", "provider": "openai"}'

# With MCP tools
curl -N -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "List /tmp files", "provider": "openai", "mcp_servers": ["filesystem"]}'
```

### Redis CLI
```bash
# Connect
docker exec -it langchain-redis redis-cli

# View sessions
KEYS session:*
GET session:<id>
TTL session:<id>

# View user sessions
SMEMBERS user:<user_id>:sessions
```

## React Web UI

**Tech:** React 18 + Vite + TypeScript + shadcn/ui + Tailwind + Zustand + React Flow

**Routes:**
- `/chat` - Streaming chat with MCP toggle, thread sidebar
- `/agents` - Multi-agent workflow with React Flow graph
- `/builder` - Agent builder wizard with templates
- `/skills` - Skills management

**Key stores:**
- `sessionStore` - Chat messages, streaming state
- `settingsStore` - Provider, model, temperature (persisted)
- `userStore` - Multi-user support (persisted)
- `mcpStore` - MCP server toggle state (persisted)

## Docker Compose Services

| Service | Port | Description |
|---------|------|-------------|
| `api` | 8000 | FastAPI backend |
| `react-ui` | 8001 | React Web UI (nginx) |
| `redis` | 6379 | Session storage |
| `phoenix` | 6006 | Tracing UI |

All services on `langchain-network`. Redis uses `redis-data` volume for persistence.

## Build System

Uses `uv_build` backend. CLI entry point: `langchain-docker = "langchain_docker:main"`
