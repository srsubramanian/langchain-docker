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
11. [Built-in Skills Reference](#built-in-skills-reference)

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
- **Data-Driven Configuration**: Tools and resources defined in SKILL.md YAML frontmatter

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

Returns query examples, sample data, advanced patterns, anti-patterns, or dialect references.

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
│  Gated tools now available: sql_query, sql_list_tables, sql_describe_table│
│                             sql_explain_query, sql_validate_query          │
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
│   │   ├── SKILL.md                    # Level 2 content + YAML frontmatter (v2.0.0)
│   │   ├── examples.md                 # Level 3: Query examples
│   │   ├── patterns.md                 # Level 3: Join, CTE, window function patterns
│   │   ├── anti_patterns.md            # Level 3: 20 SQL anti-patterns to avoid
│   │   └── dialect_reference.md        # Level 3: SQLite/PostgreSQL/MySQL/SQL Server syntax
│   ├── jira/
│   │   ├── SKILL.md                    # Jira skill instructions
│   │   └── jql_reference.md            # JQL syntax guide
│   ├── xlsx/
│   │   ├── SKILL.md                    # XLSX skill instructions
│   │   ├── examples.md                 # Code examples
│   │   ├── formatting.md               # Formatting guide
│   │   └── recalc.md                   # Recalculation script
│   └── middleware/                      # State-aware skill system
│       ├── __init__.py
│       ├── registry.py                 # SkillDefinition, SkillRegistry (middleware)
│       ├── middleware.py               # SkillMiddleware (prompt injection)
│       ├── state.py                    # SkillAwareState (state schema)
│       ├── tools.py                    # load_skill, list_loaded_skills tools
│       └── gated_domain_tools.py       # Gated SQL/Jira tools + dynamic tool factory
│
├── api/services/
│   ├── skill_registry.py               # SQLSkill, JiraSkill, XLSXSkill classes
│   │                                   # SkillRegistry (main, with Redis support)
│   ├── tool_registry.py                # ToolRegistry (non-gated tool factories)
│   ├── versioned_skill.py              # SkillVersion, VersionedSkill, ToolConfig, ResourceConfig
│   ├── skill_serializer.py             # Redis serialization
│   └── redis_skill_store.py            # Redis persistence for skills
```

---

## Component Deep Dive

### 1. Skill Definition Files

**Location**: `src/langchain_docker/skills/{skill_name}/SKILL.md`

Each skill is defined as a markdown file with YAML frontmatter that includes tool and resource configurations:

```yaml
---
name: write_sql
description: "Write and execute SQL queries against the database with query optimization, validation, and dialect-aware syntax"
category: database
version: "2.0.0"

# Tool configurations - gated tools that require this skill
tool_configs:
  - name: sql_query
    description: "Execute a SQL query against the database. In read-only mode, only SELECT queries are allowed."
    method: execute_query
    args:
      - name: query
        type: string
        description: "The SQL query to execute"
        required: true

  - name: sql_describe_table
    description: "Get detailed schema information for a specific table including column names, types, constraints, and indexes."
    method: describe_table
    args:
      - name: table_name
        type: string
        description: "Name of the table to describe"
        required: true

  - name: sql_explain_query
    description: "Get the execution plan for a SQL query without running it."
    method: explain_query
    args:
      - name: query
        type: string
        required: true

  - name: sql_validate_query
    description: "Validate SQL syntax without executing the query."
    method: validate_query
    args:
      - name: query
        type: string
        required: true

  - name: sql_list_tables
    description: "List all available tables in the database."
    method: list_tables
    args: []

  - name: sql_get_samples
    description: "Get sample rows from database tables."
    method: load_details
    args:
      - name: resource
        type: string
        default: "samples"

# Resource configurations - Level 3 content
resource_configs:
  - name: samples
    description: "Sample rows from each database table (generated dynamically)"
    dynamic: true
    method: get_sample_rows

  - name: examples
    description: "SQL query examples for common operations"
    file: examples.md

  - name: patterns
    description: "Common SQL patterns including joins, subqueries, CTEs, and window functions"
    file: patterns.md

  - name: anti_patterns
    description: "SQL anti-patterns to avoid and their correct alternatives"
    file: anti_patterns.md

  - name: dialect_reference
    description: "Dialect-specific SQL syntax for SQLite, PostgreSQL, MySQL, and SQL Server"
    file: dialect_reference.md
---

# SQL Query Expert

## Core Purpose
You are an expert SQL developer with deep knowledge of relational databases...
```

**Key Points**:
- `name`: Skill ID used in `load_skill("write_sql")`
- `description`: Shown in Level 1 metadata
- `category`: Groups skills (database, project_management, data)
- `version`: Semantic version for tracking updates
- `tool_configs`: Define gated tools with their method mappings and arguments
- `resource_configs`: Define Level 3 resources (static files or dynamic methods)
- Body content: Level 2 instructions loaded on-demand

### 2. Skill Classes

**Location**: `src/langchain_docker/api/services/skill_registry.py`

#### SQLSkill (v2.0.0)

```python
class SQLSkill(Skill):
    """SQL skill with database schema progressive disclosure."""

    def __init__(self, db_url: Optional[str] = None, read_only: Optional[bool] = None):
        self.id = "write_sql"
        self.name = "SQL Query Expert"
        self.description = "Write and execute SQL queries against the database"
        self.category = "database"
        self.is_builtin = True
        self.version = "2.0.0"  # Added in latest update
        self.db_url = db_url or get_database_url()
        self.read_only = read_only if read_only is not None else is_sql_read_only()
        self._db: Optional[SQLDatabase] = None
        self._skill_dir = SKILLS_DIR / "sql"
        self._tool_configs = []
        self._resource_configs = []
        self._load_configs_from_frontmatter()  # Load from YAML

    def _load_configs_from_frontmatter(self):
        """Load tool and resource configs from SKILL.md YAML frontmatter."""
        skill_md = self._skill_dir / "SKILL.md"
        if skill_md.exists():
            content = skill_md.read_text()
            if content.startswith("---"):
                # Parse YAML frontmatter
                import yaml
                end_idx = content.find("---", 3)
                if end_idx > 0:
                    frontmatter = yaml.safe_load(content[3:end_idx])
                    self._tool_configs = frontmatter.get("tool_configs", [])
                    self._resource_configs = frontmatter.get("resource_configs", [])

    def get_tool_configs(self) -> list[dict]:
        """Get tool configurations from frontmatter."""
        return self._tool_configs

    def get_resource_configs(self) -> list[dict]:
        """Get resource configurations from frontmatter."""
        return self._resource_configs

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
        resource_map = {
            "examples": "examples.md",
            "patterns": "patterns.md",
            "anti_patterns": "anti_patterns.md",
            "dialect_reference": "dialect_reference.md",
        }
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

    def describe_table(self, table_name: str) -> str:
        """Get detailed schema information for a specific table."""
        db = self._get_db()
        try:
            schema_info = db.get_table_info([table_name])
            # Add index information for supported dialects
            if "sqlite" in str(db.dialect).lower():
                index_info = db.run(f"PRAGMA index_list('{table_name}')")
                if index_info:
                    schema_info += f"\n\n## Indexes\n{index_info}"
            return schema_info
        except Exception as e:
            return f"Error describing table {table_name}: {str(e)}"

    def explain_query(self, query: str) -> str:
        """Get the execution plan for a SQL query."""
        db = self._get_db()
        try:
            dialect = str(db.dialect).lower()
            if "sqlite" in dialect:
                explain_query = f"EXPLAIN QUERY PLAN {query}"
            elif "postgresql" in dialect:
                explain_query = f"EXPLAIN (ANALYZE false, COSTS true, FORMAT TEXT) {query}"
            else:
                explain_query = f"EXPLAIN {query}"
            result = db.run(explain_query)
            return f"## Query Execution Plan\n\n{result}"
        except Exception as e:
            return f"Error explaining query: {str(e)}"

    def validate_query(self, query: str) -> str:
        """Validate SQL syntax without executing the query."""
        db = self._get_db()
        try:
            dialect = str(db.dialect).lower()
            if "sqlite" in dialect:
                validate_query = f"EXPLAIN {query}"
            else:
                validate_query = f"EXPLAIN {query}"
            db.run(validate_query)
            return "✓ Query syntax is valid.\n\nThe query is syntactically correct and can be executed."
        except Exception as e:
            return f"✗ Query syntax error:\n\n{str(e)}\n\nPlease fix the syntax and try again."

    def list_tables(self) -> str:
        """List all available tables."""
        return ", ".join(self._get_db().get_usable_table_names())
```

**Key Methods**:
| Method | Progressive Level | Description |
|--------|------------------|-------------|
| `id`, `name`, `description`, `version` | Level 1 | Metadata always in prompt |
| `load_core()` | Level 2 | Dynamic schema + static guidelines |
| `load_details(resource)` | Level 3 | Examples, patterns, anti-patterns, dialect reference |
| `execute_query(query)` | Execution | Run SQL with safety checks |
| `describe_table(table_name)` | Execution | Get detailed table schema |
| `explain_query(query)` | Execution | Get query execution plan |
| `validate_query(query)` | Execution | Validate SQL syntax |
| `get_tool_configs()` | Configuration | Return tool definitions from YAML |
| `get_resource_configs()` | Configuration | Return resource definitions from YAML |

### 3. Skill Registry

**Location**: `src/langchain_docker/api/services/skill_registry.py`

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

    def get_skill_full(self, skill_id: str) -> Optional[dict]:
        """Get complete skill information including tool and resource configs."""
        skill = self.get_skill(skill_id)
        if not skill:
            return None

        return {
            "id": skill.id,
            "name": skill.name,
            "description": skill.description,
            "category": skill.category,
            "version": getattr(skill, "version", "1.0.0"),
            "is_builtin": getattr(skill, "is_builtin", False),
            "tool_configs": skill.get_tool_configs() if hasattr(skill, "get_tool_configs") else [],
            "resource_configs": skill.get_resource_configs() if hasattr(skill, "get_resource_configs") else [],
        }
```

### 4. Tool Registry (Non-Gated)

**Location**: `src/langchain_docker/api/services/tool_registry.py`

Creates tool factories that wrap skill methods.

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


# Dynamic tool creation from SKILL.md frontmatter
def create_dynamic_tool_from_config(
    skill: Any,
    tool_config: dict,
    skill_id: str
) -> Any:
    """Create a LangChain tool from a tool config dictionary."""
    tool_name = tool_config.get("name", "")
    description = tool_config.get("description", "")
    method_name = tool_config.get("method", "")
    args_config = tool_config.get("args", [])

    method = getattr(skill, method_name, None)
    if not method:
        return None

    # Build Pydantic model for arguments
    if args_config:
        fields = {}
        for arg in args_config:
            arg_name = arg.get("name")
            arg_type = arg.get("type", "string")
            required = arg.get("required", False)
            default = arg.get("default", ...)

            python_type = {"string": str, "integer": int, "boolean": bool}.get(arg_type, str)

            if required:
                fields[arg_name] = (python_type, Field(description=arg.get("description", "")))
            else:
                fields[arg_name] = (Optional[python_type], Field(default=default, description=arg.get("description", "")))

        ArgsModel = create_model(f"{tool_name}Args", **fields)

        return StructuredTool.from_function(
            func=method,
            name=tool_name,
            description=description,
            args_schema=ArgsModel,
        )
    else:
        # No-args tool
        return StructuredTool.from_function(
            func=method,
            name=tool_name,
            description=description,
        )


def create_gated_tools_from_configs(skill: Any, skill_id: str) -> list:
    """Create gated tools from skill's tool_configs."""
    tools = []
    if hasattr(skill, "get_tool_configs"):
        for config in skill.get_tool_configs():
            tool = create_dynamic_tool_from_config(skill, config, skill_id)
            if tool:
                tools.append(tool)
    return tools
```

**Gated Tools for SQL (v2.0.0)**:
| Tool | Required Skill | Description |
|------|----------------|-------------|
| `sql_query` | write_sql | Execute SQL query |
| `sql_list_tables` | write_sql | List database tables |
| `sql_describe_table` | write_sql | Get detailed table schema with indexes |
| `sql_explain_query` | write_sql | Get query execution plan |
| `sql_validate_query` | write_sql | Validate SQL syntax |
| `sql_get_samples` | write_sql | Get sample data from tables |

**Gated Tools for Jira**:
| Tool | Required Skill | Description |
|------|----------------|-------------|
| `jira_search` | jira | Search issues with JQL |
| `jira_get_issue` | jira | Get issue details |
| `jira_list_projects` | jira | List projects |
| `jira_get_sprints` | jira | Get board sprints |
| `jira_get_changelog` | jira | Get issue history |
| `jira_jql_reference` | jira | Load JQL syntax guide |

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

### 7. Middleware

**Location**: `src/langchain_docker/skills/middleware/middleware.py`

The middleware injects skill metadata into the system prompt and manages skill loading state.

---

## Execution Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. APPLICATION STARTUP                                          │
│    SkillRegistry._register_builtin_skills()                     │
│    → SQLSkill (v2.0.0), XLSXSkill (v1.0.0), JiraSkill (v1.0.0) │
│    → Tool configs loaded from SKILL.md frontmatter             │
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
│    Gated tools unlocked: sql_query, sql_describe_table, etc.   │
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
│    Calls: sql_get_samples("patterns") or ("anti_patterns")     │
│    → Returns patterns, anti-patterns, or dialect reference     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 8. AGENT RESPONDS TO USER                                       │
│    "You have 42 customers in the database."                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tool-to-Skill Mapping

### SQL Skill (write_sql) - v2.0.0

| Tool | Method | Description |
|------|--------|-------------|
| `sql_query` | `execute_query` | Execute SQL query with read-only enforcement |
| `sql_list_tables` | `list_tables` | List all database tables |
| `sql_describe_table` | `describe_table` | Get table schema with indexes |
| `sql_explain_query` | `explain_query` | Get query execution plan |
| `sql_validate_query` | `validate_query` | Validate SQL syntax |
| `sql_get_samples` | `load_details` | Get sample data or load resources |

### Jira Skill (jira) - v1.0.0

| Tool | Method | Description |
|------|--------|-------------|
| `jira_search` | `search_issues` | Search issues with JQL |
| `jira_get_issue` | `get_issue` | Get issue details |
| `jira_list_projects` | `list_projects` | List all projects |
| `jira_get_sprints` | `get_sprints` | Get board sprints |
| `jira_get_changelog` | `get_changelog` | Get issue history |
| `jira_jql_reference` | `load_details` | Load JQL reference |

### XLSX Skill (xlsx) - v1.0.0

| Tool | Method | Description |
|------|--------|-------------|
| `xlsx_get_examples` | `load_details` | Get code examples |
| `xlsx_get_formatting` | `load_details` | Get formatting guide |
| `xlsx_get_recalc` | `load_details` | Get recalc script |

---

## Adding a New Skill

### Step 1: Create Skill Files

```bash
mkdir -p src/langchain_docker/skills/my_skill
```

Create `SKILL.md` with YAML frontmatter:

```yaml
---
name: my_skill
description: "Description shown in Level 1 metadata"
category: custom
version: "1.0.0"

tool_configs:
  - name: my_tool
    description: "Tool description"
    method: do_something
    args:
      - name: input
        type: string
        description: "Input parameter"
        required: true

resource_configs:
  - name: examples
    description: "Example usage"
    file: examples.md

  - name: dynamic_data
    description: "Dynamic data"
    dynamic: true
    method: get_dynamic_data
---

# My Custom Skill

## Core Purpose
What this skill does...

## Guidelines
- Guideline 1
- Guideline 2
```

### Step 2: Create Skill Class

In `skill_registry.py`:

```python
class MySkill(Skill):
    """My custom skill description."""

    def __init__(self):
        self.id = "my_skill"
        self.name = "My Custom Skill"
        self.description = "Description for Level 1 metadata"
        self.category = "custom"
        self.is_builtin = True
        self.version = "1.0.0"
        self._skill_dir = SKILLS_DIR / "my_skill"
        self._tool_configs = []
        self._resource_configs = []
        self._load_configs_from_frontmatter()

    def load_core(self) -> str:
        """Level 2: Load core content."""
        static_content = self._read_md_file("SKILL.md")
        return f"## My Skill Activated\n\n{static_content}"

    def load_details(self, resource: str) -> str:
        """Level 3: Load detailed resources."""
        resource_map = {"examples": "examples.md"}
        if resource in resource_map:
            return self._read_md_file(resource_map[resource])
        return f"Unknown resource: {resource}"

    def do_something(self, input: str) -> str:
        """Custom method mapped to my_tool."""
        return f"Processed: {input}"

    def get_tool_configs(self) -> list[dict]:
        return self._tool_configs

    def get_resource_configs(self) -> list[dict]:
        return self._resource_configs
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

---

## API Integration

### Skills Endpoints

```bash
# List all skills (Level 1 metadata)
GET /api/v1/skills

# Get full skill details including tool_configs and resource_configs
GET /api/v1/skills/{skill_id}

# Load skill (triggers Level 2)
POST /api/v1/skills/{skill_id}/load

# Create custom skill
POST /api/v1/skills
{
  "name": "My Skill",
  "description": "...",
  "category": "custom",
  "core_content": "...",
  "tool_configs": [...],
  "resource_configs": [...]
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
  tool_configs: list[ToolConfig]       # NEW: Tool definitions
  resource_configs: list[ResourceConfig] # NEW: Resource definitions
  created_at: datetime
  change_summary: Optional[str]
```

---

## Built-in Skills Reference

### SQL Skill (write_sql) - v2.0.0

| Aspect | Details |
|--------|---------|
| **Purpose** | Write and execute SQL queries with optimization and validation |
| **Category** | database |
| **Version** | 2.0.0 |
| **Tools** | sql_query, sql_list_tables, sql_describe_table, sql_explain_query, sql_validate_query, sql_get_samples |
| **Resources** | samples (dynamic), examples, patterns, anti_patterns, dialect_reference |
| **Dynamic Content** | Database schema, available tables, dialect info |

### Jira Skill (jira) - v1.0.0

| Aspect | Details |
|--------|---------|
| **Purpose** | Query Jira issues, sprints, projects (read-only) |
| **Category** | project_management |
| **Version** | 1.0.0 |
| **Tools** | jira_search, jira_get_issue, jira_list_projects, jira_get_sprints, jira_get_changelog, jira_jql_reference |
| **Resources** | jql_reference |
| **Dynamic Content** | Jira configuration status, project list |

### XLSX Skill (xlsx) - v1.0.0

| Aspect | Details |
|--------|---------|
| **Purpose** | Spreadsheet creation, editing, and analysis |
| **Category** | data |
| **Version** | 1.0.0 |
| **Tools** | (via load_details) |
| **Resources** | examples, formatting, recalc |
| **Dynamic Content** | None |

---

## Key Files Summary

| File | Purpose |
|------|---------|
| `skills/sql/SKILL.md` | SQL skill v2.0.0 with tool/resource configs |
| `skills/sql/examples.md` | SQL query examples (Level 3) |
| `skills/sql/patterns.md` | Join, CTE, window function patterns (Level 3) |
| `skills/sql/anti_patterns.md` | 20 SQL anti-patterns to avoid (Level 3) |
| `skills/sql/dialect_reference.md` | SQLite/PostgreSQL/MySQL/SQL Server syntax (Level 3) |
| `api/services/skill_registry.py` | Skill classes with tool/resource config support |
| `api/services/versioned_skill.py` | ToolConfig, ResourceConfig dataclasses |
| `skills/middleware/gated_domain_tools.py` | Dynamic tool factory from configs |
| `skills/middleware/registry.py` | Middleware SkillDefinition |

---

## Related Documentation

- [Anthropic Agent Skills Blog Post](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangChain Tools](https://python.langchain.com/docs/modules/tools/)
