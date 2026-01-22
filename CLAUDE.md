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
- OpenSearch: http://localhost:9200 (Knowledge Base)
- Neo4j: http://localhost:7474 (Graph RAG - Browser UI)

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
│   │   ├── approvals.py      # HITL approval endpoints
│   │   ├── mcp.py            # MCP server management
│   │   ├── skills.py         # Skills API
│   │   └── models.py         # Provider/model endpoints
│   ├── schemas/               # Pydantic request/response models
│   ├── services/
│   │   ├── agent_service.py      # Multi-agent orchestration (LangGraph)
│   │   ├── agent_serializer.py   # Agent serialization for Redis
│   │   ├── approval_service.py   # HITL approval request management
│   │   ├── hitl_tool_wrapper.py  # Tool wrapper for HITL approval
│   │   ├── redis_agent_store.py  # Redis-backed agent storage
│   │   ├── session_service.py    # Session storage (Redis or in-memory)
│   │   ├── redis_session_store.py # Redis session backend
│   │   ├── session_serializer.py  # Message serialization
│   │   ├── chat_service.py       # Chat orchestration with MCP tools + HITL
│   │   ├── mcp_server_manager.py # MCP server configuration management
│   │   ├── mcp_tool_service.py   # MCP tool discovery via langchain-mcp-adapters
│   │   ├── skill_registry.py     # Skills: built-in + custom, editable via API
│   │   ├── redis_skill_store.py  # Redis-backed skill versioning
│   │   ├── versioned_skill.py    # Skill version dataclasses
│   │   ├── tool_registry.py      # Tool registry (loads from providers)
│   │   ├── tools/                # Tool providers by domain
│   │   │   ├── base.py          # ToolProvider ABC, ToolTemplate, ToolParameter
│   │   │   ├── sql_tools.py     # SQLToolProvider (5 database tools)
│   │   │   ├── jira_tools.py    # JiraToolProvider (11 project management tools)
│   │   │   └── kb_tools.py      # KBToolProvider (5 knowledge base tools)
│   │   ├── embedding_service.py  # OpenAI embeddings for knowledge base
│   │   ├── opensearch_store.py   # OpenSearch vector store
│   │   ├── document_processor.py # PDF/MD/TXT parsing and chunking
│   │   ├── docling_processor.py  # Docling-based PDF processor (langchain-docling)
│   │   ├── knowledge_base_service.py # KB orchestration (upload, search, manage)
│   │   ├── graph_rag_service.py  # LlamaIndex GraphRAG with Neo4j
│   │   ├── memory_service.py     # Conversation summarization + RAG context
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
│   ├── knowledge_base/        # Knowledge Base skill (RAG)
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
│   │   ├── skills/           # SkillsPage
│   │   └── knowledge-base/   # KnowledgeBasePage - RAG document management
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
                           │            └─────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
       ┌───────────┐ ┌───────────┐ ┌───────────┐
       │ OpenSearch│ │   Neo4j   │ │ LLM APIs  │
       │ (vectors) │ │  (graph)  │ │ + MCP     │
       │ Port 9200 │ │ Port 7687 │ └───────────┘
       └───────────┘ └───────────┘
```

## Key Features

### 1. Redis Persistence (5 layers)

| Layer | Store | Purpose |
|-------|-------|---------|
| Sessions | `RedisSessionStore` | Chat history, survives restarts |
| Custom Agents | `RedisAgentStore` | Agent configs with schedules |
| Checkpoints | `RedisSaver` | LangGraph state persistence |
| Skills | `RedisSkillStore` | Skill versions, custom content, usage metrics |
| Approvals | `ApprovalService` | HITL approval requests (pending, resolved) |

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
- SQL: `sql_query`, `sql_list_tables`, `sql_get_samples`, `sql_execute` (HITL)
- Jira: `jira_search`, `jira_get_issue`, `jira_list_projects`, `jira_get_sprints`, `jira_get_changelog`, `jira_get_comments`, `jira_get_boards`, `jira_get_worklogs`, `jira_get_sprint_issues`, `jira_jql_reference`

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

MCP integration uses the official `langchain-mcp-adapters` library for:
- Automatic subprocess lifecycle management (stateless by default)
- Built-in JSON-RPC communication
- Native LangChain tool conversion
- Support for both stdio and HTTP/SSE transports

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

**Architecture:**
```
MCPServerManager (config only)     MCPToolService
├── Load server configs      ──▶   ├── MultiServerMCPClient
├── Custom server CRUD             │   └── Automatic subprocess mgmt
└── Status tracking                └── Tool caching
```

Custom servers stored in: `~/.langchain-docker/custom_mcp_servers.json`

### 8. Human-in-the-Loop (HITL) Tool Approval

Tools can be configured to require human approval before execution. This is useful for dangerous operations like database writes, file deletions, or external API calls.

```
┌─────────────────────────────────────────────────────────────────┐
│                      HITL APPROVAL FLOW                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Agent calls HITL-enabled tool (e.g., sql_execute)           │
│     ↓                                                            │
│  2. Backend creates ApprovalRequest, emits SSE event            │
│     ↓                                                            │
│  3. React UI shows ApprovalCard inline in chat                  │
│     ↓                                                            │
│  4. User clicks Approve or Reject                               │
│     ↓                                                            │
│  5. Backend updates approval status                             │
│     ↓                                                            │
│  6. Agent receives result (approved → execute, rejected → skip) │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Configuring HITL on a tool:**
```python
from langchain_docker.api.services.hitl_tool_wrapper import HITLConfig

ToolTemplate(
    id="sql_execute",
    name="SQL Execute (Write)",
    description="Execute INSERT, UPDATE, DELETE statements",
    category="database",
    factory=lambda: self._create_sql_execute_tool(),
    requires_approval=HITLConfig(
        enabled=True,
        message="This will modify the database. Review before approving.",
        show_args=True,          # Show tool arguments in approval UI
        timeout_seconds=300,     # Auto-reject after 5 minutes
        require_reason_on_reject=False,
    ),
)
```

**Key components:**
- `ApprovalService` - Manages approval requests (Redis or in-memory)
- `HITLConfig` - Configuration for approval behavior
- `ApprovalCard` - React component for inline approval UI
- SSE event `approval_request` - Sent when approval is needed

**API endpoints:**
- `GET /api/v1/approvals/pending?session_id=...` - List pending approvals
- `GET /api/v1/approvals/{id}` - Get approval details
- `POST /api/v1/approvals/{id}/approve` - Approve action
- `POST /api/v1/approvals/{id}/reject` - Reject action (with optional reason)
- `POST /api/v1/approvals/{id}/cancel` - Cancel pending approval

**Built-in HITL tool:** `sql_execute` - Allows INSERT/UPDATE/DELETE with approval.

### 9. Tool Provider Pattern

Tools are organized by domain using the Tool Provider pattern for maintainability:

```
src/langchain_docker/api/services/
├── tool_registry.py (172 lines)     # Core registry, loads providers
└── tools/
    ├── base.py (133 lines)          # ToolProvider ABC, ToolTemplate, ToolParameter
    ├── sql_tools.py (195 lines)     # SQLToolProvider (5 tools)
    └── jira_tools.py (443 lines)    # JiraToolProvider (11 tools)
```

**Adding a new tool provider:**

```python
# tools/github_tools.py
from langchain_docker.api.services.tools.base import ToolProvider, ToolTemplate

class GithubToolProvider(ToolProvider):
    def get_skill_id(self) -> str:
        return "github"

    def get_templates(self) -> list[ToolTemplate]:
        return [
            ToolTemplate(
                id="github_list_repos",
                name="List GitHub Repos",
                description="List repositories for a user or org",
                category="version_control",
                factory=self._create_list_repos_tool,
            ),
            # ... more tools
        ]

    def _create_list_repos_tool(self) -> Callable[[], str]:
        skill = self.get_skill()
        def list_repos() -> str:
            return skill.list_repos()
        return list_repos

# Then register in tool_registry.py:
self._providers = [
    SQLToolProvider(skill_registry),
    JiraToolProvider(skill_registry),
    GithubToolProvider(skill_registry),  # Add here
]
```

**Current tool providers:**
| Provider | Category | Tools |
|----------|----------|-------|
| `SQLToolProvider` | database | `load_sql_skill`, `sql_query`, `sql_list_tables`, `sql_get_samples`, `sql_execute` |
| `JiraToolProvider` | project_management | `load_jira_skill`, `jira_search`, `jira_get_issue`, `jira_list_projects`, `jira_get_sprints`, `jira_get_changelog`, `jira_get_comments`, `jira_get_boards`, `jira_get_worklogs`, `jira_get_sprint_issues`, `jira_jql_reference` |
| `KBToolProvider` | knowledge | `load_kb_skill`, `kb_search`, `kb_list_documents`, `kb_list_collections`, `kb_get_stats` |

### 10. Knowledge Base / RAG

The knowledge base provides Retrieval-Augmented Generation (RAG) capabilities using OpenSearch as a vector store.

```
┌─────────────────────────────────────────────────────────────────┐
│  KNOWLEDGE BASE ARCHITECTURE                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  INGESTION:                                                      │
│  Upload → DocumentProcessor → Docling/Chunking → Embeddings → OS│
│         (PDF/MD/TXT)         (structure-aware)   (OpenAI)  (k-NN)│
│                                                                  │
│  RETRIEVAL:                                                      │
│  Query → Embeddings → Vector Search → Context → MemoryService   │
│                       (top-k)         (chunks)  (RAG injection) │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Key Services:**
- `EmbeddingService` - OpenAI text-embedding-3-small (1536 dims)
- `DocumentProcessor` - PDF (via Docling), Markdown, Text parsing
- `DoclingProcessor` - Structure-aware PDF extraction via `langchain-docling`
- `OpenSearchStore` - Vector store with k-NN search (HNSW algorithm, L2 space)
- `KnowledgeBaseService` - High-level orchestration (upload, search, manage)

### 11. Docling PDF Processing

PDFs are processed using [Docling](https://github.com/DS4SD/docling) via the `langchain-docling` integration for structure-aware extraction.

**Features:**
- Preserves document hierarchy (headings, sections)
- Extracts tables as markdown
- Provides rich metadata per chunk (page number, bounding box, element type)
- Uses `HybridChunker` for tokenizer-aligned chunking

**Chunk Metadata:**
```python
{
    "headings": ["3. Configuration", "3.1 Environment Variables"],
    "page": 2,
    "element_type": "text",  # or "table", "paragraph", etc.
    "heading_context": "3. Configuration > 3.1 Environment Variables",
    "processor": "docling",  # "text" for non-PDFs
}
```

**Configuration (Environment Variables):**
| Variable | Default | Description |
|----------|---------|-------------|
| `DOCLING_MAX_TOKENS` | `512` | Max tokens per chunk |
| `DOCLING_TOKENIZER` | `sentence-transformers/all-MiniLM-L6-v2` | Tokenizer for chunking |
| `DOCLING_ENABLE_OCR` | `false` | Enable OCR for scanned PDFs |
| `DOCLING_ENABLE_TABLES` | `true` | Enable table structure extraction |

**System Dependencies:**

Docling requires OpenGL libraries for image processing. These are handled automatically in Docker but may need manual installation on Linux:

| Platform | Required? | Installation |
|----------|-----------|--------------|
| **macOS** | No | Built into macOS |
| **Windows** | No | Provided by graphics drivers |
| **Linux** | Yes | `sudo apt install libgl1 libglib2.0-0` |
| **Docker** | Yes | Already in Dockerfile |

For RHEL/CentOS Linux:
```bash
sudo yum install mesa-libGL glib2
```

**Two Integration Modes:**

1. **Automatic RAG in Chat** - Add `enable_rag: true` to ChatRequest:
   ```python
   # ChatRequest fields for RAG
   enable_rag: bool = False      # Enable automatic context injection
   rag_top_k: int = 5           # Documents to retrieve
   rag_min_score: float = 0.0   # Minimum similarity score
   rag_collection: str | None   # Optional collection filter
   ```

2. **Agent-Controlled via Skill** - Use KB tools for explicit control:
   - `load_kb_skill` - Load skill with status and instructions
   - `kb_search` - Semantic search with query
   - `kb_list_documents` - List uploaded documents
   - `kb_list_collections` - List document collections
   - `kb_get_stats` - Get KB statistics

**Docker Setup:**
```yaml
# docker-compose.yml includes:
opensearch:
  image: opensearchproject/opensearch:2.11.0
  ports:
    - "9200:9200"
  environment:
    - discovery.type=single-node
    - DISABLE_SECURITY_PLUGIN=true
```

**React UI:** Navigate to `/knowledge-base` for document management dashboard.

### 12. Graph RAG (LlamaIndex + Neo4j)

Graph RAG provides entity-aware retrieval using LlamaIndex PropertyGraphIndex with Neo4j as the knowledge graph store. It enables relationship-based queries like "How does X relate to Y?".

```
┌─────────────────────────────────────────────────────────────────┐
│  GRAPH RAG ARCHITECTURE                                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  INGESTION (parallel with vector RAG):                          │
│  Document → Chunks → SchemaLLMPathExtractor → Neo4j (entities)  │
│                      (LlamaIndex)             (relationships)   │
│                                                                  │
│  RETRIEVAL (hybrid):                                            │
│  Query → PropertyGraphIndex → Graph Traversal ─┐                │
│       → OpenSearch          → Vector Search  ──┼→ Merged Results│
│                                               ─┘                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Key Services:**
- `GraphRAGService` - LlamaIndex PropertyGraphIndex with Neo4j backend
- `SchemaLLMPathExtractor` - Entity/relationship extraction with schema guidance
- `KnowledgeBaseService` - Orchestrates both vector and graph stores

**When to Use:**
| Query Type | Best Approach |
|------------|---------------|
| "What is X?" | Vector RAG (similarity search) |
| "How does X relate to Y?" | Graph RAG (relationship traversal) |
| "Who works on project Z?" | Graph RAG (entity connections) |
| General Q&A | Hybrid (both combined) |

**Configuration:**
```bash
# Enable Graph RAG (default: false)
GRAPH_RAG_ENABLED=true

# Neo4j Connection
NEO4J_URL=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password

# Entity types for extraction (automatically converted to UPPER_SNAKE_CASE)
GRAPH_RAG_ENTITIES=Person,Organization,PaymentNetwork,API,BIN

# Relationship types for extraction
GRAPH_RAG_RELATIONS=works_on,leads,member_of,uses,related_to,part_of,contains
```

**Entity Type → Neo4j Label Conversion:**

Entity types in `.env` are automatically converted to UPPER_SNAKE_CASE for Neo4j node labels. Acronyms are preserved:

| Input (`.env`) | Neo4j Label |
|----------------|-------------|
| `PaymentNetwork` | `PAYMENT_NETWORK` |
| `API` | `API` |
| `BIN` | `BIN` |
| `PaymentFacilitator` | `PAYMENT_FACILITATOR` |

This ensures proper entity categorization in Neo4j. Without UPPERCASE conversion, entities would be stored with generic `__Node__` labels instead of typed labels.

> **Schema Evolution Guide**: See [docs/GRAPH_RAG_SCHEMA.md](docs/GRAPH_RAG_SCHEMA.md) for domain-specific schema configuration, entity/relation naming conventions, and evolution strategies.

**API Usage:**
```python
# Search with graph-aware retrieval
POST /api/v1/kb/search
{
    "query": "How does John relate to the AI project?",
    "use_graph": true,  # Enable graph search
    "top_k": 5
}

# Get entity context
GET /api/v1/kb/graph/entity/John?depth=2

# Get graph statistics
GET /api/v1/kb/graph/stats
```

**ChatRequest Integration:**
```python
# Enable graph-aware RAG in chat
{
    "message": "How do these teams collaborate?",
    "enable_rag": true,
    "rag_use_graph": true  # Use graph-aware retrieval
}
```

**Cost Considerations:**
- Ingestion: ~1 LLM call per chunk for entity extraction
- Storage: Neo4j community edition (free)
- Query: Same as vector RAG (1 LLM call for response)

For 1000 chunks with GPT-4o-mini: ~$0.50-1.00 one-time ingestion cost.

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/chat/stream` | SSE streaming with tool/approval events |
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
| `GET /api/v1/approvals/pending` | List pending HITL approvals for session |
| `POST /api/v1/approvals/{id}/approve` | Approve pending action |
| `POST /api/v1/approvals/{id}/reject` | Reject pending action |
| `GET /api/v1/models/providers` | List LLM providers |
| `POST /api/v1/kb/documents` | Upload document to knowledge base |
| `GET /api/v1/kb/documents` | List documents in knowledge base |
| `GET /api/v1/kb/documents/{id}` | Get document metadata |
| `DELETE /api/v1/kb/documents/{id}` | Delete document |
| `POST /api/v1/kb/search` | Semantic search (with optional `use_graph`) |
| `GET /api/v1/kb/collections` | List collections |
| `GET /api/v1/kb/stats` | Get knowledge base statistics |
| `GET /api/v1/kb/graph/stats` | Get knowledge graph statistics |
| `GET /api/v1/kb/graph/entity/{entity}` | Get entity context and connections |

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
- See `/docs/BEDROCK.md` for detailed Bedrock configuration and troubleshooting

**Skills:**
- `DATABASE_URL` - SQL skill (default: `sqlite:///demo.db`)
- `JIRA_URL`, `JIRA_BEARER_TOKEN` - Jira skill (see `/docs/JIRA_TOOLS.md` for tools reference)

**Knowledge Base (RAG):**
- `OPENSEARCH_URL` - OpenSearch URL (e.g., `http://localhost:9200`)
- `OPENSEARCH_INDEX` - Index name (default: `knowledge_base`)
- `EMBEDDING_MODEL` - OpenAI embedding model (default: `text-embedding-3-small`)
- `RAG_CHUNK_SIZE` - Document chunk size for text/md (default: `500`)
- `RAG_CHUNK_OVERLAP` - Chunk overlap for text/md (default: `50`)
- `RAG_DEFAULT_TOP_K` - Default search results (default: `5`)

**Docling (PDF Processing):**
- `DOCLING_MAX_TOKENS` - Max tokens per PDF chunk (default: `512`)
- `DOCLING_TOKENIZER` - Tokenizer for chunking (default: `sentence-transformers/all-MiniLM-L6-v2`)
- `DOCLING_ENABLE_OCR` - Enable OCR for scanned PDFs (default: `false`)
- `DOCLING_ENABLE_TABLES` - Enable table extraction (default: `true`)

**Graph RAG (LlamaIndex + Neo4j):**
- `GRAPH_RAG_ENABLED` - Enable graph-aware retrieval (default: `false`)
- `NEO4J_URL` - Neo4j Bolt URL (e.g., `bolt://localhost:7687`)
- `NEO4J_USERNAME` - Neo4j username (default: `neo4j`)
- `NEO4J_PASSWORD` - Neo4j password (required if enabled)
- `GRAPH_RAG_ENTITIES` - Entity types for extraction (comma-separated, auto-converted to UPPER_SNAKE_CASE)
- `GRAPH_RAG_RELATIONS` - Relationship types for extraction (comma-separated, auto-converted to UPPER_SNAKE_CASE)

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
# mcp_tool_service.py - uses langchain-mcp-adapters internally
tools = await mcp_tool_service.get_langchain_tools(["filesystem", "chrome-devtools"])
model_with_tools = model.bind_tools(tools)

# Tools are LangChain BaseTool instances with:
# - Automatic subprocess management (starts on first call)
# - Built-in argument validation from MCP schemas
# - Async execution via tool.ainvoke(args)
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

### Adding New Tools to an Existing Provider

1. Add backend method to the skill class in `skill_registry.py`:
   ```python
   def my_new_method(self, arg: str) -> str:
       result = self._api_get(f"/rest/api/endpoint/{arg}")
       return self._format_result(result)
   ```

2. Add `tool_configs` entry in `skills/{skill}/SKILL.md` frontmatter:
   ```yaml
   tool_configs:
     - name: my_new_tool
       description: "Does something useful"
       method: my_new_method
       args:
         - name: arg
           type: string
           required: true
   ```

3. Add `ToolTemplate` in the provider (e.g., `tools/jira_tools.py`):
   ```python
   ToolTemplate(
       id="my_new_tool",
       name="My New Tool",
       description="Does something useful",
       category="my_category",
       factory=self._create_my_new_tool,
   )
   ```

4. Add factory method in the provider:
   ```python
   def _create_my_new_tool(self) -> Callable[[str], str]:
       skill = self.get_skill()
       def my_new_tool(arg: str) -> str:
           return skill.my_new_method(arg)
       return my_new_tool
   ```

### Adding a New Tool Provider

1. Create `tools/my_tools.py` extending `ToolProvider`
2. Implement `get_skill_id()` and `get_templates()`
3. Add factory methods for each tool
4. Register in `tool_registry.py._load_providers()`

See "Tool Provider Pattern" section above for full example.

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
- `/knowledge-base` - Knowledge base document management (RAG)

## Docker Compose Services

| Service | Port | Description |
|---------|------|-------------|
| `api` | 8000 | FastAPI backend |
| `react-ui` | 8001 | React Web UI |
| `redis` | 6379 | Persistence (sessions, agents, checkpoints) |
| `phoenix` | 6006 | Tracing UI |
| `opensearch` | 9200 | Vector store for knowledge base (RAG) |
| `neo4j` | 7474, 7687 | Knowledge graph for Graph RAG (optional) |

## Major Files by Size

| File | Size | Purpose |
|------|------|---------|
| `skill_registry.py` | 75KB | Skills system: built-in + custom, versioning, Redis persistence |
| `agent_service.py` | 46KB | LangGraph orchestration, scheduling |
| `tool_registry.py` | 26KB | Tool templates, factories, HITL config support |
| `graph_rag_service.py` | 15KB | LlamaIndex GraphRAG with Neo4j |
| `redis_skill_store.py` | 15KB | Redis-backed skill versioning and metrics |
| `chat_service.py` | 14KB | Chat orchestration with MCP tools + HITL + RAG |
| `knowledge_base_service.py` | 12KB | KB orchestration (upload, search, manage, graph) |
| `versioned_skill.py` | 12KB | Skill version dataclasses, tool/resource configs |
| `approval_service.py` | 12KB | HITL approval request management |
| `mcp_server_manager.py` | 10KB | MCP server configuration (uses langchain-mcp-adapters) |
| `opensearch_store.py` | 10KB | OpenSearch vector store with k-NN search |
| `mcp_tool_service.py` | 7KB | MCP tool discovery via MultiServerMCPClient |

## Provider-Specific Streaming Behavior

When debugging empty responses or streaming issues, note these critical differences between LLM providers:

| Provider | Streaming Events | Fallback Event |
|----------|-----------------|----------------|
| OpenAI | `on_chat_model_stream` (multiple tokens) | `on_chat_model_end` |
| Anthropic | `on_chat_model_stream` (multiple tokens) | `on_chat_model_end` |
| Google | `on_chat_model_stream` (multiple tokens) | `on_chat_model_end` |
| **Bedrock** | **Does NOT emit** | **`on_chat_model_end` (required)** |

**Key insight:** AWS Bedrock's `ChatBedrockConverse` does not emit `on_chat_model_stream` events during streaming. The complete response only arrives via `on_chat_model_end`.

**Implementation in `agent_service.py`:**
1. **Primary path**: Capture streaming tokens from `on_chat_model_stream` events (works for OpenAI, Anthropic, Google)
2. **Fallback path**: Capture complete response from `on_chat_model_end` events (required for Bedrock)

**Tool calling flows** generate multiple LLM calls:
1. First call: LLM decides to use tools (e.g., "Let me load the SQL skill...")
2. Tool execution: Tools run and return results
3. Second call: LLM processes tool results and generates final response

Each LLM call triggers separate `on_chat_model_end` events - all must be captured for complete responses.

**Debugging checklist:**
- Phoenix traces show valid response but UI empty? → Check `on_chat_model_end` fallback
- Only first part of response shows? → Check multi-call handling for tool flows
- `on_chain_end` not triggering? → Check event name matches agent name, not just "LangGraph"

See `/docs/BEDROCK.md` for comprehensive Bedrock documentation.

## What Was Removed

- CLI example commands (`basic`, `customize`, `providers`, `agent`, `stream`, `all`)
- `src/langchain_docker/examples/` package
- Chainlit UI (replaced by React web_ui)
