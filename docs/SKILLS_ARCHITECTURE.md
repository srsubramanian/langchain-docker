# Skills Architecture: Progressive Disclosure Pattern

This document provides a comprehensive guide to the Skills system implementation, based on Anthropic's **Progressive Disclosure Pattern** for agent context management.

**Reference**: [Anthropic - Equipping Agents for the Real World with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)

---

## Table of Contents

1. [Overview](#overview)
2. [Progressive Disclosure Levels](#progressive-disclosure-levels)
3. [Architecture Diagram](#architecture-diagram)
4. [File Structure](#file-structure)
5. [Component Deep Dive](#component-deep-dive)
   - [Skill Definition Files](#1-skill-definition-files)
   - [Skill Classes](#2-skill-classes)
   - [Skill Registry](#3-skill-registry)
   - [Tool Registry](#4-tool-registry-non-gated)
   - [Gated Tools](#5-gated-tools-state-aware)
   - [State Tracking](#6-state-tracking)
   - [Middleware](#7-middleware)
6. [Execution Flow](#execution-flow)
7. [Tool-to-Skill Mapping](#tool-to-skill-mapping)
8. [Adding a New Skill](#adding-a-new-skill)
9. [API Integration](#api-integration)
10. [Redis Versioning](#redis-versioning)

---

## Overview

The Skills system implements a three-level progressive disclosure pattern that keeps agent context lightweight while enabling full capabilities on-demand:

| Level | Content | When Loaded | Token Cost |
|-------|---------|-------------|------------|
| **Level 1** (Metadata) | Skill ID, name, description | Always in system prompt | ~50 tokens/skill |
| **Level 2** (Core) | Full instructions, schema, guidelines | On `load_skill()` call | ~2000 tokens |
| **Level 3** (Details) | Examples, patterns, samples | On specific request | Variable |

**Benefits**:
- **Lightweight Initial Context**: Agent only sees skill metadata until needed
- **On-Demand Loading**: Full content loaded only when the agent decides to use a skill
- **State Tracking**: Prevents duplicate loading, tracks what's active
- **Gated Execution**: Tools fail gracefully if required skill not loaded
- **Dynamic Content**: Database schema, API status injected at runtime

---

## Progressive Disclosure Levels

### Level 1: Metadata (Always Present)

Shown in the agent's system prompt at all times:

```
## Available Skills
- write_sql: SQL Query Expert - Write and execute SQL queries against the database
- jira: Jira Query Expert - Query Jira issues, sprints, projects, and users (read-only)
- xlsx: Spreadsheet Expert - Comprehensive spreadsheet creation and analysis
```

**Source**: `SkillMiddleware._build_skill_prompt_section()` in `middleware.py`

### Level 2: Core Content (On-Demand)

Loaded when agent calls `load_skill("write_sql")`:

```markdown
## SQL Skill Activated

### Database Information
- Dialect: sqlite
- Available Tables: customers, orders, products

### Database Schema
CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT,
    email TEXT,
    city TEXT
);
...

## Guidelines
### Query Best Practices
- Always use explicit column names
- Use appropriate JOINs
...
```

**Source**: `SQLSkill.load_core()` in `skill_registry.py`

### Level 3: Details (Specific Request)

Loaded when agent needs examples or patterns:

```python
# Agent calls sql_get_samples() or load_skill_detail("write_sql", "examples")
```

Returns query examples, sample data, or advanced patterns.

**Source**: `SQLSkill.load_details(resource)` in `skill_registry.py`

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AGENT SYSTEM PROMPT                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Level 1: Skill Metadata (always present)                            │   │
│  │ - write_sql: SQL Query Expert - Write and execute SQL queries...   │   │
│  │ - jira: Jira Query Expert - Query Jira issues...                   │   │
│  │ - xlsx: Spreadsheet Expert - Comprehensive spreadsheet...          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  Tools available: load_skill, list_loaded_skills                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
               Agent decides: "I need to query the database"
                                    │
                                    ▼
                    Agent calls: load_skill("write_sql")
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LEVEL 2 CONTENT LOADED                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ ## SQL Skill Activated                                              │   │
│  │ - Dialect: sqlite                                                   │   │
│  │ - Available Tables: customers, orders, products                     │   │
│  │ ### Database Schema                                                 │   │
│  │ CREATE TABLE customers (...);                                       │   │
│  │ CREATE TABLE orders (...);                                          │   │
│  │ ### Guidelines                                                      │   │
│  │ - Query Best Practices                                              │   │
│  │ - Safety Considerations                                             │   │
│  │ - Performance Tips                                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  State updated: skills_loaded = ["write_sql"]                              │
│  Gated tools now available: sql_query, sql_list_tables, sql_get_samples   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
           Agent calls: sql_query("SELECT * FROM customers LIMIT 10")
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          GATED TOOL EXECUTION                               │
│  1. Check: "write_sql" in state["skills_loaded"]? → YES                    │
│  2. Execute: sql_skill.execute_query(query)                                │
│  3. Return: Query results                                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
src/langchain_docker/
├── skills/                              # Skill content files
│   ├── sql/
│   │   ├── SKILL.md                    # Level 2 static content (YAML frontmatter)
│   │   ├── examples.md                 # Level 3: Query examples
│   │   └── patterns.md                 # Level 3: Advanced patterns
│   ├── jira/
│   │   ├── SKILL.md                    # Jira skill instructions
│   │   └── jql_reference.md            # JQL syntax guide
│   ├── xlsx/
│   │   ├── SKILL.md                    # XLSX skill instructions
│   │   ├── examples.md                 # Code examples
│   │   └── formatting.md               # Formatting guide
│   └── middleware/                      # State-aware skill system
│       ├── __init__.py
│       ├── registry.py                 # SkillDefinition, SkillRegistry (middleware)
│       ├── middleware.py               # SkillMiddleware (prompt injection)
│       ├── state.py                    # SkillAwareState (state schema)
│       ├── tools.py                    # load_skill, list_loaded_skills tools
│       └── gated_domain_tools.py       # Gated SQL/Jira tools
│
├── api/services/
│   ├── skill_registry.py               # SQLSkill, JiraSkill, XLSXSkill classes
│   │                                   # SkillRegistry (main, with Redis support)
│   ├── tool_registry.py                # ToolRegistry (non-gated tool factories)
│   ├── versioned_skill.py              # SkillVersion, VersionedSkill dataclasses
│   ├── skill_serializer.py             # Redis serialization
│   └── redis_skill_store.py            # Redis persistence for skills
```

---

## Component Deep Dive

### 1. Skill Definition Files

**Location**: `src/langchain_docker/skills/{skill_name}/SKILL.md`

Each skill is defined as a markdown file with YAML frontmatter:

```yaml
---
name: write_sql
description: "Write and execute SQL queries against the database"
category: database
---

# SQL Skill

## Core Purpose
Write and execute SQL queries to retrieve, analyze, and manipulate data...

## Guidelines
### Query Best Practices
- Always use explicit column names
- Use appropriate JOINs
- Use LIMIT to prevent large result sets
...
```

**Key Points**:
- `name`: Skill ID used in `load_skill("write_sql")`
- `description`: Shown in Level 1 metadata
- `category`: Groups skills (database, project_management, data)
- Body content: Level 2 instructions loaded on-demand

### 2. Skill Classes

**Location**: `src/langchain_docker/api/services/skill_registry.py`

#### SQLSkill (lines 184-374)

```python
class SQLSkill(Skill):
    """SQL skill with database schema progressive disclosure."""

    id = "write_sql"
    name = "SQL Query Expert"
    description = "Write and execute SQL queries against the database"
    category = "database"

    def __init__(self, db_url: Optional[str] = None, read_only: Optional[bool] = None):
        self.db_url = db_url or get_database_url()
        self.read_only = read_only if read_only is not None else is_sql_read_only()
        self._db: Optional[SQLDatabase] = None
        self._skill_dir = SKILLS_DIR / "sql"

    def _get_db(self) -> SQLDatabase:
        """Lazy database connection initialization."""
        if self._db is None:
            if self.db_url.startswith("sqlite:///"):
                ensure_demo_database(self.db_url)
            self._db = SQLDatabase.from_uri(self.db_url)
        return self._db

    def load_core(self) -> str:
        """Level 2: Load database schema and SQL guidelines."""
        db = self._get_db()
        tables = db.get_usable_table_names()
        schema = db.get_table_info()
        dialect = db.dialect

        static_content = self._read_md_file("SKILL.md")

        return f"""## SQL Skill Activated

### Database Information
- Dialect: {dialect}
- Available Tables: {', '.join(tables)}

### Database Schema
{schema}

{static_content}
"""

    def load_details(self, resource: str) -> str:
        """Level 3: Load sample rows or query examples."""
        if resource == "samples":
            # Dynamic: Query actual sample data
            db = self._get_db()
            tables = db.get_usable_table_names()
            samples = ["## Sample Data\n"]
            for table in tables[:5]:
                result = db.run(f"SELECT * FROM {table} LIMIT 3")
                samples.append(f"### {table}\n```\n{result}\n```")
            return "\n\n".join(samples)

        # Static: Load from .md files
        resource_map = {"examples": "examples.md", "patterns": "patterns.md"}
        return self._read_md_file(resource_map.get(resource, ""))

    def execute_query(self, query: str) -> str:
        """Execute SQL with read-only enforcement."""
        db = self._get_db()

        if self.read_only:
            query_upper = query.strip().upper()
            write_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER"]
            for keyword in write_keywords:
                if query_upper.startswith(keyword):
                    return f"Error: {keyword} operations not allowed in read-only mode."

        return db.run(query)

    def list_tables(self) -> str:
        """List all available tables."""
        return ", ".join(self._get_db().get_usable_table_names())
```

**Key Methods**:
| Method | Progressive Level | Description |
|--------|------------------|-------------|
| `id`, `name`, `description` | Level 1 | Metadata always in prompt |
| `load_core()` | Level 2 | Dynamic schema + static guidelines |
| `load_details(resource)` | Level 3 | Examples, patterns, samples |
| `execute_query(query)` | Execution | Run SQL with safety checks |

### 3. Skill Registry

**Location**: `src/langchain_docker/api/services/skill_registry.py` (lines 1066-1860)

```python
class SkillRegistry:
    """Registry of available skills with optional Redis versioning."""

    def __init__(self, redis_url: Optional[str] = None):
        self._skills: dict[str, Skill] = {}
        self._custom_skills: dict[str, CustomSkill] = {}
        self._redis_url = redis_url
        self._redis_store: Optional[RedisSkillStore] = None

        # Initialize Redis if available
        if redis_url:
            self._redis_store = RedisSkillStore(redis_url)

        # Register built-in skills on startup
        self._register_builtin_skills()

    def _register_builtin_skills(self) -> None:
        """Register SQLSkill, XLSXSkill, JiraSkill."""
        sql_skill = SQLSkill()
        sql_skill.is_builtin = True
        self.register(sql_skill)

        xlsx_skill = XLSXSkill()
        self.register(xlsx_skill)

        jira_skill = JiraSkill()
        self.register(jira_skill)

    def load_skill(self, skill_id: str, session_id: Optional[str] = None) -> str:
        """Load a skill's core content (Level 2)."""
        skill = self.get_skill(skill_id)
        if not skill:
            return f"Unknown skill: {skill_id}"

        # Track metrics in Redis
        if self._redis_store:
            self._redis_store.record_skill_load(skill_id, session_id)

        return skill.load_core()
```

**Key Features**:
- Built-in skill registration on startup
- Custom skill CRUD operations
- Redis versioning support (immutable version history)
- Usage metrics tracking

### 4. Tool Registry (Non-Gated)

**Location**: `src/langchain_docker/api/services/tool_registry.py`

Creates tool factories that wrap skill methods:

```python
class ToolRegistry:
    """Registry of available tool templates."""

    def __init__(self):
        self._tools: dict[str, ToolTemplate] = {}
        self._register_builtin_tools()

    def _register_builtin_tools(self) -> None:
        """Register SQL and Jira tools."""
        self.register(ToolTemplate(
            id="load_sql_skill",
            name="Load SQL Skill",
            description="Load SQL skill with database schema",
            category="database",
            factory=lambda: self._create_load_sql_skill_tool(),
        ))

        self.register(ToolTemplate(
            id="sql_query",
            name="SQL Query",
            description="Execute a SQL query",
            category="database",
            factory=lambda: self._create_sql_query_tool(),
        ))
        # ... more tools

    def _get_sql_skill(self):
        """Lazy skill instantiation."""
        if not hasattr(self, "_skill_registry"):
            from langchain_docker.api.services.skill_registry import SkillRegistry
            self._skill_registry = SkillRegistry()
        return self._skill_registry.get_skill("write_sql")

    def _create_sql_query_tool(self) -> Callable[[str], str]:
        """Create SQL query execution tool."""
        sql_skill = self._get_sql_skill()

        def sql_query(query: str) -> str:
            """Execute a SQL query against the database."""
            return sql_skill.execute_query(query)

        return sql_query
```

**Tools Created**:
| Tool ID | Description | Skill Method |
|---------|-------------|--------------|
| `load_sql_skill` | Load SQL skill | `SQLSkill.load_core()` |
| `sql_query` | Execute SQL | `SQLSkill.execute_query()` |
| `sql_list_tables` | List tables | `SQLSkill.list_tables()` |
| `sql_get_samples` | Get sample data | `SQLSkill.load_details("samples")` |
| `load_jira_skill` | Load Jira skill | `JiraSkill.load_core()` |
| `jira_search` | Search issues | `JiraSkill.search_issues()` |
| `jira_get_issue` | Get issue details | `JiraSkill.get_issue()` |

### 5. Gated Tools (State-Aware)

**Location**: `src/langchain_docker/skills/middleware/gated_domain_tools.py`

Gated tools check if the required skill is loaded before execution:

```python
def is_skill_loaded(state: SkillAwareState, skill_id: str) -> bool:
    """Check if a skill is loaded in the current state."""
    return skill_id in state.get("skills_loaded", [])


def skill_required_error(skill_id: str, tool_call_id: str, tool_name: str) -> Command:
    """Create an error Command when required skill is not loaded."""
    error_msg = (
        f"The '{tool_name}' tool requires the '{skill_id}' skill to be loaded first.\n"
        f"Please use load_skill('{skill_id}') before using this tool."
    )
    return Command(
        update={
            "messages": [ToolMessage(content=error_msg, tool_call_id=tool_call_id)]
        }
    )


def create_gated_sql_query_tool(sql_skill):
    """Create a gated SQL query tool that requires write_sql skill."""

    @tool
    def sql_query(query: str, runtime: ToolRuntime) -> str | Command:
        """Execute a SQL query. Requires 'write_sql' skill to be loaded."""
        state: SkillAwareState = runtime.state

        # CHECK: Is skill loaded?
        if not is_skill_loaded(state, "write_sql"):
            return skill_required_error("write_sql", runtime.tool_call_id, "sql_query")

        # EXECUTE: Skill is loaded
        return sql_skill.execute_query(query)

    return sql_query
```

**Gated Tools**:
| Tool | Required Skill |
|------|----------------|
| `sql_query` | write_sql |
| `sql_list_tables` | write_sql |
| `sql_get_samples` | write_sql |
| `jira_search` | jira |
| `jira_get_issue` | jira |
| `jira_list_projects` | jira |
| `jira_get_sprints` | jira |
| `jira_get_changelog` | jira |
| `jira_jql_reference` | jira |

### 6. State Tracking

**Location**: `src/langchain_docker/skills/middleware/state.py`

```python
class SkillAwareState(AgentState):
    """Extended agent state that tracks skill loading."""

    # List of skill IDs loaded in this conversation
    skills_loaded: NotRequired[list[str]]

    # Track load counts to prevent duplicate loading
    skill_load_count: NotRequired[dict[str, int]]

    # Track which version of each skill was loaded
    skills_version_loaded: NotRequired[dict[str, int]]

    # Optional skill-specific context
    skill_context: NotRequired[dict[str, Any]]
```

**State Evolution**:
```python
# Initial state
state = {
    "messages": [],
    "skills_loaded": [],
    "skill_load_count": {},
}

# After load_skill("write_sql")
state = {
    "messages": [...],
    "skills_loaded": ["write_sql"],
    "skill_load_count": {"write_sql": 1},
}

# After loading another skill
state = {
    "messages": [...],
    "skills_loaded": ["write_sql", "jira"],
    "skill_load_count": {"write_sql": 1, "jira": 1},
}
```

### 7. Middleware

#### Load Skill Tool

**Location**: `src/langchain_docker/skills/middleware/tools.py`

```python
def create_load_skill_tool(registry: SkillRegistry):
    """Create a load_skill tool bound to a specific registry."""

    @tool
    def load_skill(skill_id: str, runtime: ToolRuntime) -> Command:
        """Load a skill to get specialized knowledge and capabilities."""
        state: SkillAwareState = runtime.state
        skills_loaded = list(state.get("skills_loaded", []))
        skill_load_count = dict(state.get("skill_load_count", {}))

        # Check if skill exists
        skill = registry.get(skill_id)
        if not skill:
            return Command(update={
                "messages": [ToolMessage(content=f"Unknown skill: {skill_id}", ...)]
            })

        # Check if already loaded (prevent duplicates)
        if skill_id in skills_loaded:
            return Command(update={
                "messages": [ToolMessage(content=f"Skill '{skill_id}' already loaded", ...)]
            })

        # Load the skill content (Level 2)
        content = skill.get_core_content()

        # Update state
        skills_loaded.append(skill_id)
        skill_load_count[skill_id] = skill_load_count.get(skill_id, 0) + 1

        return Command(update={
            "messages": [ToolMessage(content=f"## Skill Loaded: {skill.name}\n\n{content}", ...)],
            "skills_loaded": skills_loaded,
            "skill_load_count": skill_load_count,
        })

    return load_skill
```

#### Skill Middleware

**Location**: `src/langchain_docker/skills/middleware/middleware.py`

```python
class SkillMiddleware(AgentMiddleware[SkillAwareState]):
    """Middleware that manages skills for an agent."""

    state_schema = SkillAwareState

    def __init__(self, registry: SkillRegistry, ...):
        self.registry = registry
        self.tools = [
            create_load_skill_tool(registry),
            create_list_loaded_skills_tool(),
        ]

    def before_agent(self, state: SkillAwareState, runtime) -> dict | None:
        """Initialize skill-aware state fields."""
        updates = {}
        if "skills_loaded" not in state:
            updates["skills_loaded"] = []
        if "skill_load_count" not in state:
            updates["skill_load_count"] = {}
        return updates if updates else None

    def wrap_model_call(self, request: ModelRequest, handler) -> ModelResponse:
        """Inject skill descriptions into system prompt."""
        messages = list(request.messages)

        # Build skill descriptions
        skill_section = self._build_skill_prompt_section()

        # Add currently loaded skills info
        loaded_skills = getattr(self, "_current_loaded_skills", [])
        if loaded_skills:
            skill_section += f"\n\n**Currently loaded**: {', '.join(loaded_skills)}"

        # Inject into system message
        for i, msg in enumerate(messages):
            if isinstance(msg, SystemMessage):
                messages[i] = SystemMessage(content=f"{msg.content}\n\n{skill_section}")
                break

        return handler(request.override(messages=messages))

    def before_model(self, state: SkillAwareState, runtime):
        """Cache loaded skills for wrap_model_call."""
        self._current_loaded_skills = state.get("skills_loaded", [])
```

---

## Execution Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. APPLICATION STARTUP                                          │
│    SkillRegistry._register_builtin_skills()                     │
│    → SQLSkill, XLSXSkill, JiraSkill registered                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. AGENT INITIALIZATION                                         │
│    SkillMiddleware attached to agent                            │
│    → load_skill, list_loaded_skills tools added                │
│    → State initialized with skills_loaded=[]                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. AGENT SEES LEVEL 1 (Metadata in System Prompt)              │
│    "## Available Skills                                         │
│     - write_sql: SQL Query Expert - Write and execute SQL..."  │
│    Tools available: load_skill, list_loaded_skills             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. USER: "How many customers do we have?"                       │
│    Agent decides: I need SQL to answer this                     │
│    Agent calls: load_skill("write_sql")                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. LEVEL 2 CONTENT LOADED                                       │
│    - Database dialect detected (SQLite, PostgreSQL, etc.)       │
│    - Available tables listed (customers, orders, products)      │
│    - Full schema returned                                       │
│    - Guidelines from SKILL.md injected                          │
│    State updated: skills_loaded = ["write_sql"]                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 6. AGENT USES GATED TOOLS                                       │
│    Agent calls: sql_query("SELECT COUNT(*) FROM customers")     │
│    → Gated tool checks: "write_sql" in skills_loaded? YES      │
│    → Executes: sql_skill.execute_query(query)                   │
│    → Returns: "[(42,)]" (42 customers)                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 7. OPTIONAL: LEVEL 3 DETAILS                                    │
│    Agent needs examples for complex query:                      │
│    Calls: sql_get_samples() or load_skill_detail("examples")   │
│    → Returns sample data or example queries                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 8. AGENT RESPONDS TO USER                                       │
│    "You have 42 customers in the database."                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tool-to-Skill Mapping

| Tool | Required Skill | Gated? | Description |
|------|----------------|--------|-------------|
| `load_sql_skill` | - | No | Loads write_sql skill |
| `sql_query` | write_sql | Yes | Execute SQL query |
| `sql_list_tables` | write_sql | Yes | List database tables |
| `sql_get_samples` | write_sql | Yes | Get sample data |
| `load_jira_skill` | - | No | Loads jira skill |
| `jira_search` | jira | Yes | Search issues with JQL |
| `jira_get_issue` | jira | Yes | Get issue details |
| `jira_list_projects` | jira | Yes | List projects |
| `jira_get_sprints` | jira | Yes | Get board sprints |
| `jira_get_changelog` | jira | Yes | Get issue history |
| `jira_jql_reference` | jira | Yes | Load JQL syntax guide |

---

## Adding a New Skill

### Step 1: Create Skill Files

```bash
mkdir -p src/langchain_docker/skills/my_skill
```

Create `SKILL.md`:
```yaml
---
name: my_skill
description: "Description shown in Level 1 metadata"
category: custom
---

# My Custom Skill

## Core Purpose
What this skill does...

## Guidelines
- Guideline 1
- Guideline 2
```

Create additional resources for Level 3:
```bash
touch src/langchain_docker/skills/my_skill/examples.md
touch src/langchain_docker/skills/my_skill/reference.md
```

### Step 2: Create Skill Class

In `skill_registry.py`:

```python
class MySkill(Skill):
    """My custom skill description."""

    id = "my_skill"
    name = "My Custom Skill"
    description = "Description for Level 1 metadata"
    category = "custom"
    is_builtin = True

    def __init__(self):
        self._skill_dir = SKILLS_DIR / "my_skill"

    def load_core(self) -> str:
        """Level 2: Load core content."""
        static_content = self._read_md_file("SKILL.md")
        # Add any dynamic content
        return f"## My Skill Activated\n\n{static_content}"

    def load_details(self, resource: str) -> str:
        """Level 3: Load detailed resources."""
        resource_map = {
            "examples": "examples.md",
            "reference": "reference.md",
        }
        if resource in resource_map:
            return self._read_md_file(resource_map[resource])
        return f"Unknown resource: {resource}"
```

### Step 3: Register the Skill

In `SkillRegistry._register_builtin_skills()`:

```python
def _register_builtin_skills(self) -> None:
    # ... existing skills ...

    my_skill = MySkill()
    my_skill.is_builtin = True
    self.register(my_skill)
```

### Step 4: Create Tools (Optional)

In `tool_registry.py`:

```python
def _register_builtin_tools(self) -> None:
    # ... existing tools ...

    self.register(ToolTemplate(
        id="load_my_skill",
        name="Load My Skill",
        description="Load my custom skill",
        category="custom",
        factory=lambda: self._create_load_my_skill_tool(),
    ))

def _create_load_my_skill_tool(self) -> Callable[[], str]:
    my_skill = self._get_my_skill()

    def load_my_skill() -> str:
        """Load my custom skill."""
        return my_skill.load_core()

    return load_my_skill
```

### Step 5: Create Gated Tools (Optional)

In `gated_domain_tools.py`:

```python
def create_gated_my_skill_tool(my_skill):
    @tool
    def my_skill_action(param: str, runtime: ToolRuntime) -> str | Command:
        """Action that requires my_skill to be loaded."""
        state: SkillAwareState = runtime.state

        if not is_skill_loaded(state, "my_skill"):
            return skill_required_error("my_skill", runtime.tool_call_id, "my_skill_action")

        return my_skill.do_something(param)

    return my_skill_action
```

---

## API Integration

### Skills Endpoints

```bash
# List all skills (Level 1 metadata)
GET /api/v1/skills

# Get full skill details
GET /api/v1/skills/{skill_id}

# Load skill (triggers Level 2)
POST /api/v1/skills/{skill_id}/load

# Create custom skill
POST /api/v1/skills
{
  "name": "My Skill",
  "description": "...",
  "category": "custom",
  "core_content": "..."
}

# Update custom skill
PUT /api/v1/skills/{skill_id}

# Delete custom skill
DELETE /api/v1/skills/{skill_id}
```

### Versioning Endpoints (requires Redis)

```bash
# List skill versions
GET /api/v1/skills/{skill_id}/versions

# Get specific version
GET /api/v1/skills/{skill_id}/versions/{version_number}

# Set active version (rollback)
POST /api/v1/skills/{skill_id}/versions/{version_number}/activate

# Get usage metrics
GET /api/v1/skills/{skill_id}/metrics
```

---

## Redis Versioning

When Redis is configured, skills support immutable versioning:

```python
# VersionedSkill structure
VersionedSkill:
  skill_id: str
  is_builtin: bool
  created_at: datetime
  updated_at: datetime
  active_version: int
  versions: list[SkillVersion]

# Each version is immutable
SkillVersion:
  version_number: int          # 1, 2, 3...
  semantic_version: str        # "1.0.0", "1.1.0"
  name: str
  description: str
  category: str
  author: Optional[str]
  core_content: str
  resources: list[SkillVersionResource]
  scripts: list[SkillVersionScript]
  created_at: datetime
  change_summary: Optional[str]
```

**Benefits**:
- **Immutable History**: Every update creates a new version
- **Rollback Support**: Activate any previous version
- **Usage Metrics**: Track skill loads per version and session
- **Audit Trail**: See who changed what and when

---

## Key Files Summary

| File | Lines | Purpose |
|------|-------|---------|
| `skills/sql/SKILL.md` | ~118 | SQL skill instructions (Level 2 static) |
| `skills/sql/examples.md` | ~191 | SQL query examples (Level 3) |
| `skills/sql/patterns.md` | ~198 | Advanced SQL patterns (Level 3) |
| `api/services/skill_registry.py` | ~1860 | Skill classes, SkillRegistry |
| `api/services/tool_registry.py` | ~559 | Non-gated tool factories |
| `skills/middleware/gated_domain_tools.py` | ~464 | State-aware gated tools |
| `skills/middleware/state.py` | ~94 | SkillAwareState schema |
| `skills/middleware/tools.py` | ~332 | load_skill tool |
| `skills/middleware/middleware.py` | ~296 | SkillMiddleware |
| `skills/middleware/registry.py` | ~380 | Middleware SkillDefinition |

---

## Related Documentation

- [Anthropic Agent Skills Blog Post](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangChain Tools](https://python.langchain.com/docs/modules/tools/)
