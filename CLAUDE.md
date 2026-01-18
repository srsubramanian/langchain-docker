# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

A comprehensive LangChain orchestration platform with multi-provider LLM support, managed using `uv`. Features include multi-agent workflows with LangGraph, MCP server integration, middleware-based skills with progressive disclosure, Redis persistence, and agent scheduling.

**Python version:** 3.13+

## Quick Start

```bash
# Setup
uv sync
cp .env.example .env  # Add API keys

# Docker (preferred - includes Redis, Phoenix tracing)
docker-compose up --build

# Or run locally without Docker:
# uv run langchain-docker serve  # API only (no Redis)
# cd web_ui && npm install && npm run dev  # React UI
```

**Development Note:** Always use `docker-compose up --build` for testing features that require Redis (skills versioning, session persistence, agent storage). Local `uv run` mode falls back to in-memory storage.

**Service URLs:**
- React Web UI: http://localhost:3000 (dev) / http://localhost:8001 (Docker)
- FastAPI API: http://localhost:8000/docs
- Phoenix Tracing: http://localhost:6006
- Redis: localhost:6379

## Project Structure

```
src/langchain_docker/
├── cli.py                      # CLI - only 'serve' command
├── api/
│   ├── app.py                 # FastAPI app factory
│   ├── dependencies.py        # Singleton services via @lru_cache
│   ├── routers/               # API endpoints
│   │   ├── chat.py           # Chat streaming endpoints
│   │   ├── sessions.py       # Session CRUD
│   │   ├── agents.py         # Custom agent CRUD, workflow invocation
│   │   ├── mcp.py            # MCP server management
│   │   ├── skills.py         # Skills API
│   │   └── models.py         # Provider/model endpoints
│   ├── schemas/               # Pydantic request/response models
│   ├── services/
│   │   ├── agent_service.py      # Multi-agent orchestration (LangGraph)
│   │   ├── agent_serializer.py   # Agent serialization for Redis
│   │   ├── redis_agent_store.py  # Redis-backed agent storage
│   │   ├── session_service.py    # Session storage (Redis or in-memory)
│   │   ├── redis_session_store.py # Redis session backend
│   │   ├── session_serializer.py  # Message serialization
│   │   ├── chat_service.py       # Chat orchestration with MCP tools
│   │   ├── mcp_server_manager.py # MCP subprocess lifecycle
│   │   ├── mcp_tool_service.py   # MCP tool discovery/execution
│   │   ├── skill_registry.py     # Skills: built-in + custom, editable via API
│   │   ├── redis_skill_store.py  # Redis-backed skill versioning
│   │   ├── versioned_skill.py    # Skill version dataclasses
│   │   ├── tool_registry.py      # Tool templates for agents
│   │   ├── memory_service.py     # Conversation summarization
│   │   ├── model_service.py      # Model LRU cache
│   │   └── scheduler_service.py  # APScheduler for agent scheduling
│   └── mcp_servers.json       # MCP server configuration
├── core/
│   ├── config.py              # Environment config, Redis/Bedrock helpers
│   ├── models.py              # Model factory (OpenAI, Anthropic, Google, Bedrock)
│   └── tracing.py             # Phoenix/LangSmith tracing
├── skills/
│   ├── sql/                   # SQL skill (SKILL.md, examples.md)
│   ├── xlsx/                  # XLSX skill
│   ├── jira/                  # Jira skill (read-only)
│   └── middleware/            # Middleware-based skills system
│       ├── registry.py        # SkillRegistry, SkillDefinition
│       ├── middleware.py      # SkillMiddleware for LangChain
│       ├── state.py           # SkillAwareState for tracking
│       ├── tools.py           # Tool factories
│       └── gated_domain_tools.py # Gated SQL/Jira tools

web_ui/                         # React Web UI
├── src/
│   ├── api/                   # API clients
│   ├── features/
│   │   ├── chat/             # ChatPage - streaming chat
│   │   ├── multiagent/       # MultiAgentPage - React Flow
│   │   ├── agents/           # AgentsPage - custom agent management
│   │   ├── builder/          # BuilderPage - agent wizard
│   │   └── skills/           # SkillsPage
│   └── stores/                # Zustand (session, settings, user, mcp)
```

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  React UI   │────▶│  FastAPI    │────▶│    Redis    │     │   Phoenix   │
│  Port 8001  │     │  Port 8000  │     │  Port 6379  │     │  Port 6006  │
└─────────────┘     └──────┬──────┘     │ - Sessions  │     │  (Tracing)  │
                           │            │ - Agents    │     └─────────────┘
                           │            │ - Checkpts  │
                           ▼            └─────────────┘
                    ┌─────────────┐
                    │ LLM APIs    │
                    │ + MCP Srvrs │
                    └─────────────┘
```

## Key Features

### 1. Redis Persistence (4 layers)

| Layer | Store | Purpose |
|-------|-------|---------|
| Sessions | `RedisSessionStore` | Chat history, survives restarts |
| Custom Agents | `RedisAgentStore` | Agent configs with schedules |
| Checkpoints | `RedisSaver` | LangGraph state persistence |
| Skills | `RedisSkillStore` | Skill versions, custom content, usage metrics |

All fall back to in-memory when `REDIS_URL` not set. Skills versioning requires Redis.

### 2. Custom Agents

```python
# CustomAgent dataclass
@dataclass
class CustomAgent:
    id: str
    name: str
    system_prompt: str
    tool_configs: list[ToolConfig]  # Tool IDs resolved at runtime
    skill_ids: list[str]            # Skills to load
    schedule: ScheduleConfig | None # Cron scheduling
    provider: str
    model: str | None
    temperature: float
```

### 3. LangGraph Checkpointing

```python
# In dependencies.py
def get_checkpointer() -> BaseCheckpointSaver:
    redis_url = get_redis_url()
    if redis_url:
        return RedisSaver(redis_url)
    return InMemorySaver()
```

### 4. Middleware-Based Skills

```
┌────────────────────────────────────────────────────────┐
│  Level 1: Metadata (always in system prompt)           │
│  - "write_sql: SQL query expert"                       │
└────────────────────────────────────────────────────────┘
                    ↓ Agent calls load_skill()
┌────────────────────────────────────────────────────────┐
│  Level 2: Core Content (on-demand)                     │
│  - Database schema, guidelines                         │
└────────────────────────────────────────────────────────┘
                    ↓ Gated tools unlocked
┌────────────────────────────────────────────────────────┐
│  Level 3: Tool Execution                               │
│  - sql_query(), jira_search(), etc.                    │
└────────────────────────────────────────────────────────┘
```

**Gated tools require skill loading first:**
- SQL: `sql_query`, `sql_list_tables`, `sql_get_samples`
- Jira: `jira_search`, `jira_get_issue`, `jira_list_projects`, `jira_get_sprints`

### 5. Editable Built-in Skills (Redis Required)

Built-in skills (SQL, Jira, XLSX) can be customized via the API while preserving dynamic content generation:

```
┌─────────────────────────────────────────────────────────────────┐
│                     SKILL CONTENT FLOW                           │
├─────────────────────────────────────────────────────────────────┤
│  load_core() for SQLSkill:                                      │
│  ├── Dynamic content (always fresh from database)              │
│  │   └── Schema, tables, dialect, read-only status             │
│  ├── Static content (editable)                                  │
│  │   ├── Redis custom content (if edited via API)              │
│  │   └── OR SKILL.md file content (default)                    │
│  └── Combined: dynamic + static                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Key components:**
- `Skill._custom_content` - Redis-loaded content override
- `Skill.has_custom_content()` - Check if skill has been customized
- `Skill.get_file_content()` - Get original SKILL.md content
- `SkillRegistry.update_builtin_skill()` - Update with versioning
- `SkillRegistry.reset_builtin_skill()` - Revert to file defaults

**API endpoints:**
- `PUT /api/v1/skills/{id}` - Update skill (creates new version)
- `POST /api/v1/skills/{id}/reset` - Reset to file defaults
- `GET /api/v1/skills/{id}/versions` - List version history
- `POST /api/v1/skills/{id}/versions/{num}/activate` - Rollback

**Response includes `has_custom_content: bool` to indicate if skill has been edited.**

### 6. Agent Scheduling

```python
# ScheduleConfig
schedule = ScheduleConfig(
    enabled=True,
    cron_expression="0 9 * * 1-5",  # 9 AM weekdays
    trigger_prompt="Generate daily report",
    timezone="America/New_York"
)
```

### 7. MCP Server Integration

```json
// mcp_servers.json
{
  "filesystem": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
    "enabled": true
  }
}
```

Custom servers stored in: `~/.langchain-docker/custom_mcp_servers.json`

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/chat/stream` | SSE streaming with tool events |
| `GET/POST/DELETE /api/v1/sessions` | Session CRUD |
| `GET/POST/DELETE /api/v1/agents` | Custom agent CRUD |
| `POST /api/v1/agents/{id}/invoke` | Invoke agent |
| `GET /api/v1/mcp/servers` | List MCP servers |
| `POST /api/v1/mcp/servers/{id}/start` | Start MCP server |
| `GET /api/v1/skills` | List skills |
| `GET /api/v1/skills/{id}` | Get skill with full content |
| `PUT /api/v1/skills/{id}` | Update skill (built-in or custom) |
| `POST /api/v1/skills/{id}/reset` | Reset built-in skill to file defaults |
| `GET /api/v1/skills/{id}/versions` | List skill version history |
| `GET /api/v1/models/providers` | List LLM providers |

## Environment Variables

**Required (at least one):**
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`

**Redis (enables persistence):**
- `REDIS_URL` - e.g., `redis://localhost:6379/0`
- `SESSION_TTL_HOURS` - Session expiry (default: 24)

**Tracing:**
- `TRACING_PROVIDER` - `langsmith`, `phoenix`, or `none`
- `LANGCHAIN_API_KEY` / `PHOENIX_ENDPOINT`

**AWS Bedrock:**
- `AWS_PROFILE`, `AWS_DEFAULT_REGION`, `BEDROCK_MODEL_ARNS`

**Skills:**
- `DATABASE_URL` - SQL skill (default: `sqlite:///demo.db`)
- `JIRA_URL`, `JIRA_BEARER_TOKEN` - Jira skill

## Key Patterns

### Dependency Injection

```python
# dependencies.py - Singletons with @lru_cache
@lru_cache
def get_agent_service() -> AgentService:
    return AgentService(
        checkpointer=get_checkpointer(),
        redis_url=get_redis_url(),
        skill_registry=get_skill_registry()
    )
```

### Dual Skill Systems

```python
# Legacy (file-based)
skill_registry = SkillRegistry()  # Loads from skills/sql/, skills/jira/

# Middleware (state-aware for LangGraph)
from skills.middleware.registry import SkillRegistry as MiddlewareRegistry
mw_registry = MiddlewareRegistry()
mw_registry.load_from_legacy(skill_registry)  # Bridge
```

### MCP Tool Discovery

```python
# mcp_tool_service.py
tools = await mcp_tool_service.get_langchain_tools(["filesystem"])
model_with_tools = model.bind_tools(tools)
```

### Agent with Checkpointing

```python
# agent_service.py
workflow = create_supervisor(
    agents=[math_agent, weather_agent],
    model=llm,
    checkpointer=self._checkpointer  # Redis or in-memory
)
```

## Development Workflows

### Adding a New Skill

1. Create `skills/my_skill/SKILL.md` with YAML frontmatter
2. Add skill class to `skill_registry.py`
3. Add gated tools to `skills/middleware/gated_domain_tools.py`
4. Register in `SkillRegistry._register_builtin_skills()`

### Adding a New MCP Server

1. Add to `mcp_servers.json`:
   ```json
   "my-server": {
     "command": "npx",
     "args": ["-y", "my-mcp-package"],
     "enabled": true
   }
   ```
2. Restart backend

### Testing API

```bash
# Health
curl http://localhost:8000/health

# Streaming chat
curl -N -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello", "provider": "openai"}'

# Create custom agent
curl -X POST http://localhost:8000/api/v1/agents \
  -H "Content-Type: application/json" \
  -d '{"name": "My Agent", "system_prompt": "You help with math", "tool_ids": ["add", "multiply"]}'
```

### Redis CLI

```bash
docker exec -it langchain-redis redis-cli
KEYS session:*      # Sessions
KEYS agent:*        # Custom agents
KEYS checkpoint:*   # LangGraph state
```

## React Web UI

**Tech:** React 18 + Vite + TypeScript + shadcn/ui + Tailwind + Zustand + React Flow

**Routes:**
- `/chat` - Streaming chat with MCP toggle
- `/agents` - Custom agent management (NEW)
- `/multiagent` - Multi-agent workflow with React Flow
- `/builder` - Agent builder wizard
- `/skills` - Skills management

## Docker Compose Services

| Service | Port | Description |
|---------|------|-------------|
| `api` | 8000 | FastAPI backend |
| `react-ui` | 8001 | React Web UI |
| `redis` | 6379 | Persistence (sessions, agents, checkpoints) |
| `phoenix` | 6006 | Tracing UI |

## Major Files by Size

| File | Size | Purpose |
|------|------|---------|
| `skill_registry.py` | 75KB | Skills system: built-in + custom, versioning, Redis persistence |
| `agent_service.py` | 46KB | LangGraph orchestration, scheduling |
| `tool_registry.py` | 24KB | Tool templates, factories |
| `mcp_server_manager.py` | 22KB | MCP subprocess management |
| `redis_skill_store.py` | 15KB | Redis-backed skill versioning and metrics |
| `versioned_skill.py` | 12KB | Skill version dataclasses, tool/resource configs |

## What Was Removed

- CLI example commands (`basic`, `customize`, `providers`, `agent`, `stream`, `all`)
- `src/langchain_docker/examples/` package
- Chainlit UI (replaced by React web_ui)
