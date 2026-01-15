# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a comprehensive demonstration of LangChain foundational models, managed using `uv` (modern Python package manager). The project showcases examples for basic model invocation, customization, multi-provider support, agents, and streaming. It works as both a CLI tool and importable Python library.

Python version: 3.13+

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

### Running the React Web UI (Recommended)

**Note: The React Web UI requires the FastAPI backend to be running.**

```bash
# Terminal 1: Start FastAPI backend
uv run langchain-docker serve

# Terminal 2: Start React dev server
cd web_ui
npm install
npm run dev
```

Once running:
- React Web UI: http://localhost:3000 (dev) or http://localhost:8001 (Docker)
- FastAPI Backend: http://localhost:8000

**Features:**
- Streaming chat with provider/model selection
- Multi-agent workflow visualization with React Flow
- Custom agent builder with single-page layout (LangSmith-inspired)
- Skills management with progressive disclosure
- Multi-user support with user selector dropdown
- Dark theme with teal accents

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
- `phoenix`: Phoenix tracing server on port 6006
- `api`: FastAPI backend on port 8000
- `react-ui`: React Web UI on port 8001
- Shared network: `langchain-network`
- Health checks enabled for automatic dependency management

**Environment:**
- API keys loaded from `.env` file

### Running with Phoenix Tracing

**Phoenix is automatically included when using Docker Compose:**

```bash
docker-compose up
```

**Services running:**
- Phoenix UI: http://localhost:6006
- FastAPI Backend: http://localhost:8000
- React Web UI: http://localhost:8001

**For local development without Docker:**

```bash
# Terminal 1: Start Phoenix server
python -m phoenix.server.main serve

# Terminal 2: Start FastAPI
uv run langchain-docker serve

# Terminal 3: Start React Web UI
cd web_ui && npm run dev
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
│   │   ├── sessions.py       # Session/conversation history endpoints
│   │   └── skills.py         # Skills CRUD and loading endpoints
│   ├── schemas/               # Pydantic models for request/response
│   │   ├── __init__.py
│   │   ├── agents.py         # Multi-agent workflow schemas
│   │   ├── chat.py           # Chat request/response schemas
│   │   ├── models.py         # Model schemas
│   │   ├── sessions.py       # Session schemas
│   │   └── skills.py         # Skill request/response schemas
│   └── services/              # Business logic layer
│       ├── __init__.py
│       ├── agent_service.py  # Multi-agent workflow orchestration (LangGraph)
│       ├── chat_service.py   # Chat orchestration
│       ├── demo_database.py  # Demo SQLite database with sample data
│       ├── memory_service.py # Conversation memory and summarization
│       ├── model_service.py  # Model instance caching (LRU)
│       ├── scheduler_service.py # APScheduler-based agent scheduling
│       ├── session_service.py # Session storage & retrieval (in-memory)
│       ├── skill_registry.py # Skills with progressive disclosure pattern
│       └── tool_registry.py  # Tool templates for custom agents
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
├── skills/                     # Skill content files (markdown)
│   ├── __init__.py            # Skills package documentation
│   ├── sql/                   # SQL skill content
│   │   ├── __init__.py        # Skill module documentation
│   │   ├── SKILL.md           # Core skill instructions + guidelines
│   │   ├── examples.md        # SQL query examples
│   │   └── patterns.md        # Advanced SQL patterns
│   └── xlsx/                  # XLSX skill content
│       ├── __init__.py        # Skill module documentation
│       ├── SKILL.md           # Core skill instructions (Level 2)
│       ├── recalc.md          # Recalculation script docs
│       ├── examples.md        # Code examples
│       └── formatting.md      # Formatting guide
└── utils/
    ├── __init__.py            # Utility exports
    └── errors.py              # Custom exception classes

web_ui/                         # React Web UI (port 8001)
├── src/
│   ├── api/                   # API client modules (chat, sessions, models, agents)
│   ├── components/
│   │   ├── ui/               # shadcn/ui components
│   │   └── layout/           # Header with navigation
│   ├── features/
│   │   ├── chat/             # ChatPage - streaming chat
│   │   ├── multiagent/       # MultiAgentPage - React Flow visualization
│   │   └── builder/          # BuilderPage - 4-step agent wizard
│   ├── stores/               # Zustand stores (session, settings, user)
│   ├── types/                # TypeScript types
│   ├── lib/                  # Utilities (cn.ts)
│   ├── App.tsx               # Router configuration
│   ├── main.tsx              # Entry point
│   └── index.css             # Tailwind + dark theme
├── Dockerfile                 # Multi-stage build (Node → nginx)
├── nginx.conf                 # SPA routing + API proxy
├── package.json               # Dependencies
├── vite.config.ts             # Vite configuration
└── tailwind.config.js         # Theme configuration

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
- `validate_bedrock_access()`: Validate AWS Bedrock access using boto3 credentials
- `get_api_key(provider)`: Get API key without raising error
- `get_bedrock_models()`: Get list of Bedrock model ARNs from environment
- `get_bedrock_region()`: Get AWS region for Bedrock (defaults to us-east-1)
- `get_bedrock_profile()`: Get AWS profile for Bedrock authentication
- `Config` dataclass: Store default settings

**models.py** (`src/langchain_docker/core/models.py`):
- `init_model(provider, model, **kwargs)`: Factory function using `init_chat_model()`
- `get_openai_model()`: Pre-configured OpenAI model
- `get_anthropic_model()`: Pre-configured Anthropic model
- `get_google_model()`: Pre-configured Google model
- `get_bedrock_model()`: Pre-configured AWS Bedrock model using ChatBedrockConverse
- `get_supported_providers()`: List available providers (openai, anthropic, google, bedrock)

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
- `skills.py`: SkillMetadata, SkillInfo, SkillCreateRequest, SkillUpdateRequest, SkillResource, SkillScript

**Services** (`src/langchain_docker/api/services/`):
- Business logic layer, reuses 100% of existing core functionality
- `agent_service.py`: Multi-agent workflow orchestration
  - LangGraph supervisor pattern for agent coordination
  - Static agents: math_expert, weather_expert, research_expert, finance_expert
  - Dynamic agents: sql_expert (created from SkillRegistry)
  - Methods: `create_workflow()`, `invoke_workflow()`, `list_workflows()`, `delete_workflow()`
  - Uses `create_agent()` and `create_supervisor()` from langgraph
- `skill_registry.py`: Skills with progressive disclosure pattern
  - `Skill` base class with `load_core()` and `load_details()` methods
  - `SQLSkill`: Database querying with on-demand schema loading
  - `SkillRegistry`: Central registry for all skills (singleton via dependencies.py)
  - Progressive disclosure: Level 1 (metadata) → Level 2 (schema) → Level 3 (samples)
- `demo_database.py`: Demo SQLite database
  - Auto-creates `demo.db` with sample data on first use
  - Tables: customers, orders, products
  - Used by SQLSkill for testing and demos
- `tool_registry.py`: Tool templates for custom agents
  - Categories: math, weather, research, finance, database
  - SQL tools: load_sql_skill, sql_query, sql_list_tables, sql_get_samples
  - Methods: `register()`, `list_tools()`, `create_tool_instance()`
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
- `scheduler_service.py`: Automated agent execution scheduler
  - APScheduler-based background scheduler with cron support
  - Methods: `add_schedule()`, `remove_schedule()`, `enable_schedule()`, `disable_schedule()`
  - Methods: `get_schedule()`, `list_schedules()`, `get_next_run_time()`
  - Supports timezone configuration and execution callbacks

**Routers** (`src/langchain_docker/api/routers/`):
- FastAPI route handlers using dependency injection
- `agents.py`: Multi-agent workflow endpoints (GET builtin, POST workflows, POST invoke, DELETE)
- `chat.py`: POST /api/v1/chat, POST /api/v1/chat/stream (SSE)
- `models.py`: GET /api/v1/models/providers, GET /api/v1/models/providers/{provider}, POST /api/v1/models/validate
- `sessions.py`: Full CRUD for sessions (POST, GET, LIST, DELETE)
- `skills.py`: Skills API endpoints
  - GET /api/v1/skills - List all skills (metadata only)
  - GET /api/v1/skills/{skill_id} - Get full skill details with core content
  - POST /api/v1/skills - Create custom skill
  - PUT /api/v1/skills/{skill_id} - Update skill
  - DELETE /api/v1/skills/{skill_id} - Delete custom skill
  - POST /api/v1/skills/{skill_id}/load - Load skill into agent context

**Middleware** (`src/langchain_docker/api/middleware.py`):
- Maps custom exceptions to HTTP responses
- `APIKeyMissingError` → 503 Service Unavailable
- `ModelInitializationError` → 500 Internal Server Error
- `SessionNotFoundError` → 404 Not Found
- `InvalidProviderError` → 400 Bad Request

**Dependencies** (`src/langchain_docker/api/dependencies.py`):
- Singleton instances via `@lru_cache` for services
- `get_session_service()`, `get_model_service()`, `get_chat_service()`, `get_memory_service()`
- `get_skill_registry()`: Singleton SkillRegistry for progressive disclosure skills
- `get_agent_service()`: Receives SkillRegistry to create dynamic skill-based agents
- `get_current_user_id()`: Extracts user ID from `X-User-ID` header (defaults to "default")

**App Factory** (`src/langchain_docker/api/app.py`):
- `create_app()`: Configures FastAPI with CORS, routers, exception handlers
- CORS enabled for React Web UI integration (localhost:3000, 8000, 8001)
- Health check at `/health`, detailed status at `/api/v1/status`

### React Web UI (web_ui/)

A modern React-based web UI inspired by LangSmith Agent Builder, featuring React Flow for workflow visualization.

**Tech Stack:**
- React 18 + Vite + TypeScript
- shadcn/ui (Radix UI primitives)
- Tailwind CSS (dark theme with teal accents)
- Zustand (state management with localStorage persistence)
- React Flow (workflow/graph visualization)
- React Router v6 (client-side routing)

**Project Structure:**
```
web_ui/
├── src/
│   ├── api/                  # API client modules
│   │   ├── index.ts         # Barrel exports
│   │   ├── client.ts        # Centralized axios client with user ID interceptor
│   │   ├── chat.ts          # Chat API with SSE streaming
│   │   ├── sessions.ts      # Session CRUD operations
│   │   ├── models.ts        # Provider/model endpoints
│   │   ├── agents.ts        # Multi-agent workflow API
│   │   └── skills.ts        # Skills API (list, get, create, update, delete)
│   ├── components/
│   │   ├── ui/              # shadcn/ui components (Button, Input, Card, Collapsible, etc.)
│   │   └── layout/          # Header with navigation, MainLayout
│   ├── features/
│   │   ├── chat/            # ChatPage - streaming chat with ThreadList sidebar
│   │   │   ├── ChatPage.tsx # Main chat interface with model selection
│   │   │   └── ThreadList.tsx # Collapsible thread sidebar with search/delete
│   │   ├── multiagent/      # MultiAgentPage - React Flow + chat
│   │   ├── builder/         # BuilderPage - single-page agent builder
│   │   │   ├── BuilderPage.tsx # Agent configuration wizard
│   │   │   ├── templates.ts    # Predefined agent templates
│   │   │   └── TemplateSelector.tsx # Template selection grid
│   │   ├── skills/          # SkillsPage - skills management
│   │   └── agents/          # AgentsPage - agent management
│   ├── stores/
│   │   ├── index.ts         # Barrel exports for stores
│   │   ├── sessionStore.ts  # Chat state (messages, streaming)
│   │   ├── settingsStore.ts # Persisted settings (provider, model, temp)
│   │   └── userStore.ts     # Multi-user state (current user, user list)
│   ├── types/
│   │   └── api.ts           # TypeScript types matching backend schemas
│   ├── lib/
│   │   └── cn.ts            # Tailwind class merge utility
│   ├── App.tsx              # Router configuration
│   ├── main.tsx             # React entry point
│   └── index.css            # Tailwind + dark theme CSS variables
├── Dockerfile               # Multi-stage build (Node → nginx)
├── nginx.conf               # SPA routing + API proxy
├── package.json             # Dependencies
├── vite.config.ts           # Vite + path aliases + dev proxy
├── tailwind.config.js       # Theme configuration
└── tsconfig.json            # TypeScript configuration
```

**Routes:**
| Route | Component | Description |
|-------|-----------|-------------|
| `/chat` | ChatPage | Standard streaming chat with provider/model selection |
| `/agents` | MultiAgentPage | Split-panel: chat left, React Flow graph right |
| `/builder` | BuilderPage | Single-page agent builder (LangSmith-inspired) |
| `/skills` | SkillsPage | Skills management with editor |

**Key Features:**

1. **ChatPage** (`src/features/chat/ChatPage.tsx`):
   - SSE streaming with real-time token display
   - Provider/model/temperature settings panel with dynamic model loading
   - Message history with user/assistant bubbles
   - Session persistence across page reloads
   - ThreadList sidebar with search, delete, and collapse functionality
   - Automatic thread refresh after message exchange

2. **MultiAgentPage** (`src/features/multiagent/MultiAgentPage.tsx`):
   - Split-panel layout (resizable)
   - React Flow graph showing: User Input → Supervisor → Agents → Response
   - Agent preset selector (all, math_weather, research_finance, math_only)
   - Bidirectional edges between supervisor and agents

3. **BuilderPage** (`src/features/builder/BuilderPage.tsx`):
   - Single-page layout inspired by LangSmith Agent Builder
   - Template selector with predefined agent configurations:
     - Research Assistant, Math Tutor, Weather Assistant
     - Data Analyst, Finance Advisor, General Assistant
     - Category filtering (Productivity, Analysis, Communication, Development)
   - Header bar with inline agent name input, Draft badge, and Create Agent button
   - Collapsible Instructions section (system prompt with character counter)
   - Collapsible Toolbox section with Tools and Skills tabs
   - Tool/Skill selection via "Add" buttons with category-filtered popover
   - Selected items shown as removable badges with X buttons
   - Real-time Agent Flow visualization showing:
     - User Input → Agent → Response flow
     - Connected tool nodes (blue) and skill nodes (purple)
     - Dynamic count badge on agent showing total tools + skills
   - Validation summary at bottom with inline error display
   - Random avatar color generation for new agents

4. **SkillsPage** (`src/features/skills/SkillsPage.tsx`):
   - Skills listing with category-based organization
   - Inline skill editor with code preview
   - Progressive disclosure pattern for skill content

**Centralized API Client Pattern:**
```typescript
// src/api/client.ts - Axios client with user ID interceptor
import axios from 'axios';
import { useUserStore } from '@/stores/userStore';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 60000,
});

// Request interceptor for adding user ID header
apiClient.interceptors.request.use((config) => {
  const userId = useUserStore.getState().currentUserId;
  if (userId) {
    config.headers['X-User-ID'] = userId;
  }
  return config;
});
```

**SSE Streaming Pattern:**
```typescript
// src/api/chat.ts - SSE streaming
async *streamMessage(request: ChatRequest): AsyncGenerator<StreamEvent> {
  const response = await fetch(`${API_BASE_URL}/api/v1/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...request, stream: true }),
  });

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    // Parse SSE events (event: type, data: json)
    // yield parsed StreamEvent objects
  }
}
```

**Zustand Store Pattern:**
```typescript
// src/stores/settingsStore.ts - Persisted settings
export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      provider: 'openai',
      model: null,
      temperature: 0.7,
      setProvider: (provider) => set({ provider }),
      setModel: (model) => set({ model }),
      setTemperature: (temperature) => set({ temperature }),
    }),
    { name: 'settings-storage' }  // localStorage key
  )
);
```

**Dynamic Model Loading Pattern:**
```typescript
// ChatPage.tsx - Load models when provider changes
const [availableModels, setAvailableModels] = useState<ModelInfo[]>([]);

// Fetch available models when provider changes
useEffect(() => {
  if (provider) {
    modelsApi
      .getProviderDetails(provider)
      .then((details) => {
        setAvailableModels(details.available_models);
      })
      .catch(console.error);
  }
}, [provider]);

// Render model selector
<Select value={model || 'default'} onValueChange={(v) => setModel(v === 'default' ? null : v)}>
  <SelectContent>
    <SelectItem value="default">Default ({provider?.default_model})</SelectItem>
    {availableModels.map((m) => (
      <SelectItem key={m.name} value={m.name}>{m.name}</SelectItem>
    ))}
  </SelectContent>
</Select>
```

**Docker Configuration:**
```dockerfile
# web_ui/Dockerfile - Multi-stage build
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

```nginx
# web_ui/nginx.conf - SPA routing + API proxy
server {
    listen 80;
    root /usr/share/nginx/html;

    # SPA routing
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API proxy
    location /api {
        proxy_pass http://api:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
    }
}
```

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

### Adding a New Skill (Progressive Disclosure)

Skills support two approaches: **file-based** (recommended for content-heavy skills) and **inline** (for simpler skills).

#### Option A: File-Based Skill (Recommended)

1. Create skill directory `src/langchain_docker/skills/my_skill/`:
   ```
   skills/my_skill/
   ├── __init__.py        # Module documentation
   ├── SKILL.md           # Core instructions (Level 2)
   ├── examples.md        # Code examples (Level 3)
   └── advanced.md        # Advanced topics (Level 3)
   ```

2. Create `SKILL.md` with YAML frontmatter:
   ```markdown
   ---
   name: my_skill
   description: "Description of what the skill does"
   category: my_category
   ---

   # My Skill

   ## Core Purpose
   Explain what this skill does...

   ## Guidelines
   - Guideline 1
   - Guideline 2
   ```

3. Create skill class in `skill_registry.py`:
   ```python
   class MyNewSkill(Skill):
       def __init__(self):
           self.id = "my_skill"
           self.name = "My Skill Expert"
           self.description = "Does something useful"
           self.category = "my_category"
           self.is_builtin = True
           self._skill_dir = SKILLS_DIR / "my_skill"

       def _read_md_file(self, filename: str) -> str:
           file_path = self._skill_dir / filename
           if file_path.exists():
               return file_path.read_text(encoding="utf-8")
           return f"Error: File {filename} not found"

       def load_core(self) -> str:
           content = self._read_md_file("SKILL.md")
           # Strip YAML frontmatter if present
           if content.startswith("---"):
               lines = content.split("\n")
               for i, line in enumerate(lines[1:], 1):
                   if line.strip() == "---":
                       content = "\n".join(lines[i+1:]).strip()
                       break
           return f"## My Skill Activated\n\n{content}"

       def load_details(self, resource: str) -> str:
           resource_map = {"examples": "examples.md", "advanced": "advanced.md"}
           if resource in resource_map:
               return self._read_md_file(resource_map[resource])
           return f"Unknown resource: {resource}"
   ```

#### Option B: Inline Skill (Simple Skills)

   ```python
   class SimpleSkill(Skill):
       def __init__(self):
           self.id = "simple_skill"
           self.name = "Simple Skill"
           self.description = "A simpler skill"
           self.category = "general"

       def load_core(self) -> str:
           return "Skill context and guidelines..."

       def load_details(self, resource: str) -> str:
           if resource == "examples":
               return "Example usage..."
           return f"Unknown resource: {resource}"
   ```

#### Registering the Skill

Register in `SkillRegistry._register_builtin_skills()`:
   ```python
   def _register_builtin_skills(self):
       self.register(SQLSkill())
       self.register(XLSXSkill())
       self.register(MyNewSkill())  # Add here
   ```

Add tools in `tool_registry.py` (optional, for custom agents):
   ```python
   self.register(ToolTemplate(
       id="load_my_skill",
       name="Load My Skill",
       description="Load my skill context",
       category="my_category",
       factory=lambda: self._create_my_skill_tool(),
   ))
   ```

AgentService automatically creates `my_skill_expert` agent from the skill.

Test via API:
   ```bash
   curl http://localhost:8000/api/v1/agents/builtin  # Should show my_skill_expert
   ```

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

### Developing the React Web UI

1. **Start services for development**:
   ```bash
   # Terminal 1: FastAPI backend with reload
   uv run langchain-docker serve --reload

   # Terminal 2: React dev server with hot reload
   cd web_ui
   npm install
   npm run dev
   ```
   - React dev server runs on http://localhost:3000
   - API requests proxy to http://localhost:8000

2. **Project setup (if starting fresh)**:
   ```bash
   cd web_ui
   npm install
   # or with cache issues:
   npm install --cache /tmp/npm-cache
   ```

3. **Key files to modify**:
   - `src/features/chat/ChatPage.tsx` - Chat interface and streaming logic
   - `src/features/multiagent/MultiAgentPage.tsx` - React Flow workflow visualization
   - `src/features/builder/BuilderPage.tsx` - Single-page agent builder with flow visualization
   - `src/features/skills/SkillsPage.tsx` - Skills management interface
   - `src/components/ui/collapsible.tsx` - Reusable collapsible section component
   - `src/api/*.ts` - API client methods
   - `src/stores/*.ts` - Zustand state management
   - `src/types/api.ts` - TypeScript types (keep in sync with backend schemas)
   - `src/index.css` - Theme CSS variables

4. **Adding a new shadcn/ui component**:
   ```bash
   # Components are manually added from shadcn/ui docs
   # Copy component code to src/components/ui/
   # Example components already included:
   # - Button, Input, Card, Badge, Select, Slider, ScrollArea, Checkbox
   # - Collapsible (custom), Popover, Tabs, Textarea
   ```

5. **Building for production**:
   ```bash
   cd web_ui
   npm run build
   # Output in dist/ folder
   ```

6. **Docker build**:
   ```bash
   # Build just the React UI
   docker build -t langchain-react-ui ./web_ui

   # Or rebuild all services
   docker-compose up --build
   ```

7. **Adding new routes**:
   - Create feature folder in `src/features/<feature-name>/`
   - Create `<Feature>Page.tsx` component
   - Add route in `src/App.tsx`
   - Add navigation link in `src/components/layout/Header.tsx`

8. **Adding new API endpoints**:
   - Add TypeScript types in `src/types/api.ts`
   - Create or update API client in `src/api/`
   - Export from `src/api/index.ts`

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

**Tracing Configuration:**
- `TRACING_PROVIDER` (default: phoenix) - Tracing platform: "langsmith", "phoenix", or "none"

**LangSmith (if TRACING_PROVIDER=langsmith):**
- `LANGCHAIN_API_KEY` - LangSmith API key (required)
- `LANGCHAIN_PROJECT` (default: langchain-docker) - Project name in LangSmith
- `LANGCHAIN_ENDPOINT` (optional) - LangSmith API endpoint

**Phoenix (if TRACING_PROVIDER=phoenix):**
- `PHOENIX_ENDPOINT` (default: http://localhost:6006/v1/traces) - Phoenix collector endpoint
- `PHOENIX_CONSOLE_EXPORT` (default: false) - Export traces to console for debugging

**AWS Bedrock Configuration:**
- `AWS_PROFILE` or `BEDROCK_PROFILE` - AWS profile for authentication (optional, uses default credential chain)
- `AWS_DEFAULT_REGION` or `AWS_REGION` (default: us-east-1) - AWS region for Bedrock
- `BEDROCK_MODEL_ARNS` - Comma-separated list of model ARNs or inference profile ARNs
  - Default: `anthropic.claude-3-5-sonnet-20241022-v2:0,anthropic.claude-3-5-haiku-20241022-v1:0`
  - Example: `arn:aws:bedrock:us-east-1:123456789:inference-profile/my-profile`

**Database Configuration (for SQL Skill):**
- `DATABASE_URL` (default: sqlite:///demo.db) - Database connection string
- `SQL_READ_ONLY` (default: true) - Enforce read-only mode (only SELECT allowed)

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

### Multi-Agent Workflow Pattern (LangGraph Supervisor)
```python
# In agent_service.py
from langchain.agents import create_agent  # New location (moved from langgraph.prebuilt)
from langgraph_supervisor import create_supervisor

# Define tools for agents
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Sunny, 68°F in {city}"

# Create specialized agents using create_agent (replaces deprecated create_react_agent)
math_agent = create_agent(
    model=llm,
    tools=[add, subtract, multiply, divide],
    name="math_expert",
    system_prompt="You are a math expert. Use tools to perform calculations."
)

weather_agent = create_agent(
    model=llm,
    tools=[get_weather],
    name="weather_expert",
    system_prompt="You are a weather expert. Provide weather information."
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

### Scheduler Service Pattern

The scheduler service enables automated agent execution using APScheduler with cron expressions.

**Adding a Schedule:**
```python
# In scheduler_service.py
from langchain_docker.api.services.scheduler_service import SchedulerService

scheduler = SchedulerService()
scheduler.start()

# Add a schedule with cron expression (5 parts: min hour day month weekday)
schedule = scheduler.add_schedule(
    agent_id="my-agent-123",
    cron_expression="0 9 * * 1-5",  # 9 AM on weekdays
    trigger_prompt="Generate the daily report",
    timezone="America/New_York",
    enabled=True,
)
# Returns: {"agent_id": "...", "next_run": "2025-01-16T09:00:00-05:00", ...}
```

**Managing Schedules:**
```python
# Disable without removing
scheduler.disable_schedule("my-agent-123")

# Re-enable
scheduler.enable_schedule("my-agent-123")

# Get schedule info
info = scheduler.get_schedule("my-agent-123")
# Returns: {"cron_expression": "0 9 * * 1-5", "enabled": True, "next_run": "..."}

# List all schedules
all_schedules = scheduler.list_schedules()

# Remove schedule completely
scheduler.remove_schedule("my-agent-123")
```

**Setting Execution Callback:**
```python
# Set callback for when schedules trigger
def execute_agent(agent_id: str, prompt: str):
    # Execute the agent with the trigger prompt
    workflow = agent_service.get_workflow(agent_id)
    result = workflow.invoke({"messages": [HumanMessage(content=prompt)]})
    return result

scheduler.set_execution_callback(execute_agent)
```

### Skills with Progressive Disclosure Pattern

The skills architecture enables specialized capabilities as invokable "skills" that load context on-demand, keeping the base agent lightweight. Reference: [LangChain Skills Documentation](https://docs.langchain.com/oss/python/langchain/multi-agent/skills)

**Architecture:**
```
┌─────────────────────────────────────────────────────────────┐
│  Level 1: Skill Metadata (always in agent prompt)          │
│  - "write_sql: SQL query writing expert"                   │
└─────────────────────────────────────────────────────────────┘
                        ↓ Agent calls load_sql_skill()
┌─────────────────────────────────────────────────────────────┐
│  Level 2: Core Content (loaded on-demand)                   │
│  - Database schema, table definitions                       │
│  - SQL dialect-specific guidelines                          │
└─────────────────────────────────────────────────────────────┘
                        ↓ Agent calls sql_get_samples()
┌─────────────────────────────────────────────────────────────┐
│  Level 3: Detailed Resources (loaded as needed)             │
│  - Sample rows from tables                                  │
│  - Complex query examples                                   │
└─────────────────────────────────────────────────────────────┘
```

**Skill Definition:**
```python
# In skill_registry.py
class SQLSkill(Skill):
    def __init__(self, db_url=None, read_only=None):
        self.id = "write_sql"
        self.name = "SQL Query Expert"
        self.db_url = db_url or get_database_url()  # From env var
        self.read_only = read_only if read_only is not None else is_sql_read_only()
        self._db = None  # Lazy-loaded database connection

    def load_core(self) -> str:
        """Level 2: Load database schema on-demand."""
        db = self._get_db()
        return f"""
## SQL Skill Activated
### Available Tables: {', '.join(db.get_usable_table_names())}
### Schema: {db.get_table_info()}
"""

    def execute_query(self, query: str) -> str:
        """Execute SQL with read-only enforcement."""
        if self.read_only and not query.strip().upper().startswith("SELECT"):
            return "Error: Only SELECT queries allowed in read-only mode"
        return self._get_db().run(query)
```

**SkillRegistry Integration:**
```python
# In dependencies.py - Singleton registry
def get_skill_registry() -> SkillRegistry:
    global _skill_registry
    if _skill_registry is None:
        _skill_registry = SkillRegistry()  # Registers SQLSkill automatically
    return _skill_registry

# In agent_service.py - Dynamic agent creation
def _create_skill_based_agents(self):
    sql_skill = self._skill_registry.get_skill("write_sql")
    if sql_skill:
        # Create tools from skill methods
        def load_sql_skill() -> str:
            return sql_skill.load_core()

        def sql_query(query: str) -> str:
            return sql_skill.execute_query(query)

        return {
            "sql_expert": {
                "name": "sql_expert",
                "tools": [load_sql_skill, sql_query, ...],
                "prompt": "You are a SQL expert..."
            }
        }
```

**Using the SQL Expert Agent:**
```bash
# Create workflow with sql_expert
curl -X POST http://localhost:8000/api/v1/agents/workflows \
  -H "Content-Type: application/json" \
  -d '{"agents": ["sql_expert"], "workflow_id": "sql-demo"}'

# Query the database (agent uses progressive disclosure)
curl -X POST http://localhost:8000/api/v1/agents/workflows/sql-demo/invoke \
  -H "Content-Type: application/json" \
  -d '{"message": "What are the top 5 customers by order total?"}'
```

**Agent Flow (Explicit Tool Calls):**
```
User: "Show me top customers"
         │
         ▼
Agent: "I need database schema first"
         │
         ▼
Agent calls: load_sql_skill()     ← Explicit, visible in traces
         │
         ▼
Agent receives: table schemas, guidelines
         │
         ▼
Agent calls: sql_query("SELECT c.name, SUM(o.total)...")
         │
         ▼
Returns formatted results
```

**Adding New Skills:**
```python
# 1. Create skill class in skill_registry.py
class LegalDocSkill(Skill):
    def __init__(self):
        self.id = "legal_doc"
        self.name = "Legal Document Expert"
        ...

    def load_core(self) -> str:
        return "Legal review guidelines..."

# 2. Register in SkillRegistry._register_builtin_skills()
def _register_builtin_skills(self):
    self.register(SQLSkill())
    self.register(LegalDocSkill())  # New skill

# 3. AgentService automatically creates legal_doc_expert agent
```

### Multi-User Support

The application supports multiple users with isolated sessions and conversation history.

**Architecture:**
```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (React)                                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  User Selector (Header dropdown)                     │   │
│  │  - Alice, Bob, Charlie (default users)               │   │
│  │  - Add custom users                                  │   │
│  │  - Persisted in localStorage                         │   │
│  └─────────────────────────────────────────────────────┘   │
│                         │                                   │
│                         ▼ X-User-ID header                  │
└─────────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────────────┐
│  Backend (FastAPI)                                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  get_current_user_id() dependency                    │   │
│  │  - Extracts X-User-ID from request header            │   │
│  │  - Defaults to "default" if not provided             │   │
│  └─────────────────────────────────────────────────────┘   │
│                         │                                   │
│                         ▼                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Session Service                                     │   │
│  │  - Sessions scoped by user_id                        │   │
│  │  - list(user_id=...) filters by user                 │   │
│  │  - Each user sees only their conversations           │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**Frontend User Store** (`web_ui/src/stores/userStore.ts`):
```typescript
// Zustand store with localStorage persistence
export const useUserStore = create<UserState>()(
  persist(
    (set, get) => ({
      currentUserId: 'alice',
      currentUserName: 'Alice',
      users: [
        { id: 'alice', name: 'Alice', color: 'bg-violet-500' },
        { id: 'bob', name: 'Bob', color: 'bg-blue-500' },
        { id: 'charlie', name: 'Charlie', color: 'bg-teal-500' },
      ],
      setCurrentUser: (userId) => { /* switch user */ },
      addUser: (name) => { /* add new user */ },
    }),
    { name: 'user-storage' }
  )
);
```

**API Client with User Header** (`web_ui/src/api/client.ts`):
```typescript
// Axios interceptor adds X-User-ID to all requests
apiClient.interceptors.request.use((config) => {
  const userId = useUserStore.getState().currentUserId;
  if (userId) {
    config.headers['X-User-ID'] = userId;
  }
  return config;
});
```

**Backend User Extraction** (`src/langchain_docker/api/dependencies.py`):
```python
def get_current_user_id(
    x_user_id: str | None = Header(None, alias="X-User-ID"),
) -> str:
    """Extract current user ID from request header."""
    return x_user_id or "default"
```

**User-Scoped Sessions** (`src/langchain_docker/api/services/session_service.py`):
```python
@dataclass
class Session:
    session_id: str
    user_id: str = "default"  # Sessions are scoped to users
    messages: list[BaseMessage] = field(default_factory=list)
    # ...

def list(self, user_id: Optional[str] = None) -> tuple[list[Session], int]:
    """List sessions, optionally filtered by user."""
    sessions = list(self._sessions.values())
    if user_id:
        sessions = [s for s in sessions if s.user_id == user_id]
    return sessions, len(sessions)
```

**Testing Multi-User Isolation:**
```bash
# Create session for Alice
curl -X POST http://localhost:8000/api/v1/sessions \
  -H "Content-Type: application/json" \
  -H "X-User-ID: alice" \
  -d '{}'

# Create session for Bob
curl -X POST http://localhost:8000/api/v1/sessions \
  -H "Content-Type: application/json" \
  -H "X-User-ID: bob" \
  -d '{}'

# List Alice's sessions (only sees her sessions)
curl http://localhost:8000/api/v1/sessions -H "X-User-ID: alice"

# List Bob's sessions (only sees his sessions)
curl http://localhost:8000/api/v1/sessions -H "X-User-ID: bob"
```

## Build System

This project uses `uv_build` as the build backend (specified in `pyproject.toml`). The CLI entry point is defined in `[project.scripts]` as `langchain-docker = "langchain_docker:main"`.
