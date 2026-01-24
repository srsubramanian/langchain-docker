"""Skill registry service implementing progressive disclosure pattern.

Based on Anthropic's Agent Skills architecture for on-demand context loading.
Reference: https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills

Progressive Disclosure Levels:
- Level 1 (Metadata): name, description - always in agent system prompt
- Level 2 (Core): SKILL.md body - loaded when skill is triggered
- Level 3 (Details): Additional files - loaded only as needed
"""

import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from langchain_community.utilities import SQLDatabase

# Skills directory path (relative to this file)
SKILLS_DIR = Path(__file__).parent.parent.parent / "skills"

from langchain_docker.api.services.demo_database import ensure_demo_database
from langchain_docker.core.config import (
    get_database_url,
    get_jira_api_version,
    get_jira_bearer_token,
    get_jira_url,
    is_jira_configured,
    is_sql_read_only,
)
from langchain_docker.core.tracing import get_tracer

logger = logging.getLogger(__name__)


class SkillResource:
    """Additional resource file bundled with a skill."""

    def __init__(self, name: str, description: str, content: str = ""):
        self.name = name
        self.description = description
        self.content = content


class SkillScript:
    """Executable script bundled with a skill."""

    def __init__(
        self, name: str, description: str, language: str = "python", content: str = ""
    ):
        self.name = name
        self.description = description
        self.language = language
        self.content = content


class Skill(ABC):
    """Base class for skills with progressive disclosure levels.

    Progressive disclosure architecture:
    - Level 1 (Metadata): Skill id, name, description - always visible in agent prompt
    - Level 2 (Core): Main skill content - loaded on-demand via load_core()
    - Level 3 (Details): Specific resources - loaded as needed via load_details()

    Built-in skills can be customized via Redis. Custom content overrides
    the file-based content while preserving dynamic content generation.
    """

    id: str
    name: str
    description: str
    category: str
    is_builtin: bool = False

    # Redis-loaded content override (for built-in skills)
    _custom_content: Optional[str] = None
    _custom_resources: Optional[list] = None

    # Tool and resource configurations (loaded from SKILL.md frontmatter or Redis)
    _tool_configs: list = []
    _resource_configs: list = []

    def has_custom_content(self) -> bool:
        """Check if skill has Redis-customized content.

        Returns:
            True if custom content from Redis is set
        """
        return self._custom_content is not None

    def set_custom_content(
        self,
        content: str,
        resources: Optional[list] = None,
        tool_configs: Optional[list] = None,
        resource_configs: Optional[list] = None,
    ) -> None:
        """Set custom content from Redis.

        Args:
            content: Custom core content to use instead of file-based
            resources: Optional custom resources
            tool_configs: Optional tool configurations
            resource_configs: Optional resource configurations
        """
        self._custom_content = content
        self._custom_resources = resources or []
        if tool_configs is not None:
            self._tool_configs = tool_configs
        if resource_configs is not None:
            self._resource_configs = resource_configs

    def clear_custom_content(self) -> None:
        """Clear custom content, reverting to file-based defaults."""
        self._custom_content = None
        self._custom_resources = None
        # Note: We don't clear _tool_configs and _resource_configs as they
        # should reload from file when content is cleared

    def get_file_content(self) -> str:
        """Get the original file-based content for this skill.

        Override in subclasses to return the static content from SKILL.md.
        Used when resetting a skill to its default state.

        Returns:
            Original file-based content
        """
        return ""

    def get_tool_configs(self) -> list:
        """Get tool configurations for this skill.

        Returns:
            List of SkillToolConfig-like dicts or objects
        """
        return self._tool_configs

    def get_resource_configs(self) -> list:
        """Get resource configurations for this skill.

        Returns:
            List of SkillResourceConfig-like dicts or objects
        """
        return self._resource_configs

    @abstractmethod
    def load_core(self) -> str:
        """Level 2: Load core content on-demand.

        Returns:
            Core skill content including context, guidelines, and capabilities
        """
        pass

    @abstractmethod
    def load_details(self, resource: str) -> str:
        """Level 3: Load specific detailed resources.

        Args:
            resource: Resource identifier (e.g., "samples", "examples")

        Returns:
            Detailed resource content
        """
        pass


class XLSXSkill(Skill):
    """XLSX skill for spreadsheet creation, editing, and analysis.

    Based on Anthropic's xlsx skill from https://github.com/anthropics/skills
    Provides comprehensive spreadsheet capabilities with formulas, formatting,
    data analysis, and visualization support.

    Content is loaded from .md files in src/langchain_docker/skills/xlsx/
    """

    def __init__(self):
        """Initialize XLSX skill."""
        self.id = "xlsx"
        self.name = "Spreadsheet Expert"
        self.description = (
            "Comprehensive spreadsheet creation, editing, and analysis with support "
            "for formulas, formatting, data analysis, and visualization"
        )
        self.category = "data"
        self.is_builtin = True
        self.version = "1.0.0"
        self._skill_dir = SKILLS_DIR / "xlsx"
        self._custom_content = None
        self._custom_resources = None
        self._tool_configs = []
        self._resource_configs = []
        self._load_configs_from_frontmatter()

    def _read_md_file(self, filename: str) -> str:
        """Read content from a markdown file in the skill directory.

        Args:
            filename: Name of the .md file to read

        Returns:
            File content or error message if file not found
        """
        file_path = self._skill_dir / filename
        try:
            if file_path.exists():
                return file_path.read_text(encoding="utf-8")
            else:
                logger.warning(f"Skill file not found: {file_path}")
                return f"Error: File {filename} not found in skill directory"
        except Exception as e:
            logger.error(f"Error reading skill file {filename}: {e}")
            return f"Error reading {filename}: {str(e)}"

    def _load_configs_from_frontmatter(self) -> None:
        """Parse SKILL.md frontmatter to load tool and resource configs."""
        try:
            content = self._read_md_file("SKILL.md")
            if not content.startswith("---"):
                return

            # Parse YAML frontmatter
            lines = content.split("\n")
            end_idx = None
            for i, line in enumerate(lines[1:], 1):
                if line.strip() == "---":
                    end_idx = i
                    break

            if end_idx:
                import yaml
                frontmatter = "\n".join(lines[1:end_idx])
                metadata = yaml.safe_load(frontmatter) or {}

                # Load tool configs
                tool_configs = metadata.get("tool_configs", [])
                self._tool_configs = [
                    {
                        "name": t.get("name", ""),
                        "description": t.get("description", ""),
                        "method": t.get("method", ""),
                        "args": t.get("args", []),
                        "requires_skill_loaded": t.get("requires_skill_loaded", True),
                    }
                    for t in tool_configs
                ] if tool_configs else []

                # Load resource configs
                resource_configs = metadata.get("resource_configs", [])
                self._resource_configs = [
                    {
                        "name": r.get("name", ""),
                        "description": r.get("description", ""),
                        "file": r.get("file"),
                        "content": r.get("content"),
                        "dynamic": r.get("dynamic", False),
                        "method": r.get("method"),
                    }
                    for r in resource_configs
                ] if resource_configs else []

                logger.debug(
                    f"Loaded configs for {self.id}: "
                    f"{len(self._tool_configs)} tools, {len(self._resource_configs)} resources"
                )
        except Exception as e:
            logger.warning(f"Failed to load configs from frontmatter for {self.id}: {e}")

    def get_file_content(self) -> str:
        """Get the original file-based content for this skill.

        Returns:
            Original SKILL.md content with YAML frontmatter stripped
        """
        content = self._read_md_file("SKILL.md")

        # Strip YAML frontmatter if present
        if content.startswith("---"):
            lines = content.split("\n")
            for i, line in enumerate(lines[1:], 1):
                if line.strip() == "---":
                    content = "\n".join(lines[i + 1 :]).strip()
                    break

        return content

    def load_core(self) -> str:
        """Level 2: Load XLSX skill instructions.

        Uses Redis custom content if available, otherwise falls back to SKILL.md.

        Returns:
            Complete skill context for spreadsheet operations
        """
        # Use custom content from Redis if available, otherwise use file content
        if self._custom_content is not None:
            static_content = self._custom_content
        else:
            static_content = self.get_file_content()

        return f"## XLSX Skill Activated\n\n{static_content}"

    def load_details(self, resource: str) -> str:
        """Level 3: Load detailed resources from .md files.

        Args:
            resource: "recalc" for recalculation script, "examples" for code examples,
                     "formatting" for formatting guide

        Returns:
            Detailed resource content from the corresponding .md file
        """
        resource_map = {
            "recalc": "recalc.md",
            "examples": "examples.md",
            "formatting": "formatting.md",
        }

        if resource in resource_map:
            return self._read_md_file(resource_map[resource])
        else:
            available = ", ".join(f"'{r}'" for r in resource_map.keys())
            return f"Unknown resource: {resource}. Available: {available}"


class SQLSkill(Skill):
    """SQL skill with database schema progressive disclosure.

    Provides database querying capabilities with on-demand schema loading.
    This keeps the base agent context lightweight while allowing full
    database introspection when needed.

    Content is loaded from .md files in src/langchain_docker/skills/sql/
    Dynamic database schema is injected at runtime.
    """

    def __init__(self, db_url: Optional[str] = None, read_only: Optional[bool] = None):
        """Initialize SQL skill.

        Args:
            db_url: Database URL (defaults to DATABASE_URL env var)
            read_only: Whether to enforce read-only mode (defaults to SQL_READ_ONLY env var)
        """
        self.id = "write_sql"
        self.name = "SQL Query Expert"
        self.description = "Write and execute SQL queries against the database"
        self.category = "database"
        self.is_builtin = True
        self.version = "2.0.0"
        self.db_url = db_url or get_database_url()
        self.read_only = read_only if read_only is not None else is_sql_read_only()
        self._db: Optional[SQLDatabase] = None
        self._skill_dir = SKILLS_DIR / "sql"
        self._custom_content = None
        self._custom_resources = None
        self._tool_configs = []
        self._resource_configs = []
        self._load_configs_from_frontmatter()

    def _get_db(self) -> SQLDatabase:
        """Get or create SQLDatabase instance.

        Returns:
            SQLDatabase wrapper for the configured database
        """
        if self._db is None:
            # Ensure demo database exists for SQLite
            if self.db_url.startswith("sqlite:///"):
                ensure_demo_database(self.db_url)
            self._db = SQLDatabase.from_uri(self.db_url)
        return self._db

    def _read_md_file(self, filename: str) -> str:
        """Read content from a markdown file in the skill directory.

        Args:
            filename: Name of the .md file to read

        Returns:
            File content or error message if file not found
        """
        file_path = self._skill_dir / filename
        try:
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                # Strip YAML frontmatter if present
                if content.startswith("---"):
                    lines = content.split("\n")
                    for i, line in enumerate(lines[1:], 1):
                        if line.strip() == "---":
                            content = "\n".join(lines[i + 1 :]).strip()
                            break
                return content
            else:
                logger.warning(f"Skill file not found: {file_path}")
                return f"Error: File {filename} not found in skill directory"
        except Exception as e:
            logger.error(f"Error reading skill file {filename}: {e}")
            return f"Error reading {filename}: {str(e)}"

    def _load_configs_from_frontmatter(self) -> None:
        """Parse SKILL.md frontmatter to load tool and resource configs."""
        try:
            file_path = self._skill_dir / "SKILL.md"
            if not file_path.exists():
                return

            content = file_path.read_text(encoding="utf-8")
            if not content.startswith("---"):
                return

            # Parse YAML frontmatter
            lines = content.split("\n")
            end_idx = None
            for i, line in enumerate(lines[1:], 1):
                if line.strip() == "---":
                    end_idx = i
                    break

            if end_idx:
                import yaml
                frontmatter = "\n".join(lines[1:end_idx])
                metadata = yaml.safe_load(frontmatter) or {}

                # Load tool configs
                tool_configs = metadata.get("tool_configs", [])
                self._tool_configs = [
                    {
                        "name": t.get("name", ""),
                        "description": t.get("description", ""),
                        "method": t.get("method", ""),
                        "args": t.get("args", []),
                        "requires_skill_loaded": t.get("requires_skill_loaded", True),
                    }
                    for t in tool_configs
                ] if tool_configs else []

                # Load resource configs
                resource_configs = metadata.get("resource_configs", [])
                self._resource_configs = [
                    {
                        "name": r.get("name", ""),
                        "description": r.get("description", ""),
                        "file": r.get("file"),
                        "content": r.get("content"),
                        "dynamic": r.get("dynamic", False),
                        "method": r.get("method"),
                    }
                    for r in resource_configs
                ] if resource_configs else []

                logger.debug(
                    f"Loaded configs for {self.id}: "
                    f"{len(self._tool_configs)} tools, {len(self._resource_configs)} resources"
                )
        except Exception as e:
            logger.warning(f"Failed to load configs from frontmatter for {self.id}: {e}")

    def get_file_content(self) -> str:
        """Get the original file-based content for this skill.

        Returns:
            Original SKILL.md content (static guidelines only)
        """
        return self._read_md_file("SKILL.md")

    def load_core(self) -> str:
        """Level 2: Load database schema and SQL guidelines.

        Combines dynamic database information with static content.
        Static content uses Redis custom content if available, otherwise SKILL.md.

        Returns:
            Complete skill context including tables, schema, and guidelines
        """
        db = self._get_db()
        tables = db.get_usable_table_names()
        schema = db.get_table_info()
        dialect = db.dialect

        read_only_note = ""
        if self.read_only:
            read_only_note = """
### Read-Only Mode
This database is in READ-ONLY mode. Only SELECT queries are allowed.
INSERT, UPDATE, DELETE, and other write operations will be rejected.
"""

        # Static content: prefer Redis custom content, fallback to file
        if self._custom_content is not None:
            static_content = self._custom_content
        else:
            static_content = self._read_md_file("SKILL.md")

        return f"""## SQL Skill Activated

### Database Information
- Dialect: {dialect}
- Available Tables: {', '.join(tables)}

### Database Schema
{schema}
{read_only_note}
{static_content}
"""

    def load_details(self, resource: str) -> str:
        """Level 3: Load sample rows or query examples.

        Args:
            resource: "samples" for sample rows (dynamic),
                     "examples" for query examples,
                     "patterns" for advanced patterns

        Returns:
            Detailed resource content
        """
        # "samples" is dynamic - needs to query the database
        if resource == "samples":
            db = self._get_db()
            tables = db.get_usable_table_names()
            samples = ["## Sample Data\n"]
            for table in tables[:5]:  # Limit to first 5 tables
                try:
                    result = db.run(f"SELECT * FROM {table} LIMIT 3")
                    samples.append(f"### {table}\n```\n{result}\n```")
                except Exception as e:
                    samples.append(f"### {table}\nError fetching samples: {e}")
            return "\n\n".join(samples)

        # Static resources loaded from .md files
        resource_map = {
            "examples": "examples.md",
            "patterns": "patterns.md",
            "anti_patterns": "anti_patterns.md",
            "dialect_reference": "dialect_reference.md",
        }

        if resource in resource_map:
            return self._read_md_file(resource_map[resource])
        else:
            available = "'samples', " + ", ".join(f"'{r}'" for r in resource_map.keys())
            return f"Unknown resource: {resource}. Available: {available}"

    def execute_query(self, query: str, read_only: bool | None = None) -> str:
        """Execute a SQL query with optional read-only enforcement.

        Args:
            query: SQL query string
            read_only: Override for read-only mode. If None, uses instance setting.
                       Set to False to allow write operations (for HITL-approved tools).

        Returns:
            Query results or error message
        """
        db = self._get_db()

        # Use explicit read_only if provided, otherwise use instance setting
        enforce_read_only = read_only if read_only is not None else self.read_only

        # Enforce read-only mode
        if enforce_read_only:
            query_upper = query.strip().upper()
            write_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE"]
            for keyword in write_keywords:
                if query_upper.startswith(keyword):
                    return f"Error: {keyword} operations are not allowed in read-only mode. Only SELECT queries are permitted."

        try:
            result = db.run(query)
            return result
        except Exception as e:
            return f"Query error: {str(e)}"

    def list_tables(self) -> str:
        """List all available tables.

        Returns:
            Comma-separated list of table names
        """
        db = self._get_db()
        tables = db.get_usable_table_names()
        return ", ".join(tables)

    def get_table_schema(self, table_name: str) -> str:
        """Get schema for a specific table.

        Args:
            table_name: Name of the table

        Returns:
            Table schema information
        """
        db = self._get_db()
        try:
            return db.get_table_info([table_name])
        except Exception as e:
            return f"Error getting schema for {table_name}: {str(e)}"

    def describe_table(self, table_name: str) -> str:
        """Get detailed schema information for a specific table.

        Includes column names, types, constraints, and any available index information.

        Args:
            table_name: Name of the table to describe

        Returns:
            Detailed table schema information
        """
        db = self._get_db()
        try:
            # Get basic table info
            schema_info = db.get_table_info([table_name])

            # Try to get additional index information if available
            try:
                if "sqlite" in str(db.dialect).lower():
                    # SQLite-specific index query
                    index_info = db.run(f"PRAGMA index_list('{table_name}')")
                    if index_info:
                        schema_info += f"\n\n## Indexes\n{index_info}"
                elif "postgresql" in str(db.dialect).lower():
                    # PostgreSQL-specific
                    index_query = f"""
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE tablename = '{table_name}'
                    """
                    index_info = db.run(index_query)
                    if index_info:
                        schema_info += f"\n\n## Indexes\n{index_info}"
            except Exception:
                # Index info is optional, don't fail if we can't get it
                pass

            return schema_info
        except Exception as e:
            return f"Error describing table {table_name}: {str(e)}"

    def explain_query(self, query: str) -> str:
        """Get the execution plan for a SQL query.

        Analyzes the query without executing it to show how the database
        would process the query. Useful for performance optimization.

        Args:
            query: The SQL query to analyze

        Returns:
            Query execution plan
        """
        db = self._get_db()
        try:
            # Determine the appropriate EXPLAIN syntax based on dialect
            dialect = str(db.dialect).lower()

            if "sqlite" in dialect:
                explain_query = f"EXPLAIN QUERY PLAN {query}"
            elif "postgresql" in dialect:
                explain_query = f"EXPLAIN (ANALYZE false, COSTS true, FORMAT TEXT) {query}"
            elif "mysql" in dialect:
                explain_query = f"EXPLAIN {query}"
            else:
                # Generic EXPLAIN for other databases
                explain_query = f"EXPLAIN {query}"

            result = db.run(explain_query)
            return f"## Query Execution Plan\n\n{result}"
        except Exception as e:
            return f"Error explaining query: {str(e)}"

    def validate_query(self, query: str) -> str:
        """Validate SQL syntax without executing the query.

        Checks if the query is syntactically correct by preparing it
        without actually running it.

        Args:
            query: The SQL query to validate

        Returns:
            Validation result (success or error details)
        """
        db = self._get_db()
        try:
            # Get the raw connection to prepare the statement
            from sqlalchemy import text
            from sqlalchemy.exc import SQLAlchemyError

            # Use EXPLAIN to validate without executing
            # This works because EXPLAIN parses the query
            dialect = str(db.dialect).lower()

            if "sqlite" in dialect:
                # SQLite: Use EXPLAIN to validate
                validate_query = f"EXPLAIN {query}"
            elif "postgresql" in dialect:
                # PostgreSQL: PREPARE statement validates syntax
                validate_query = f"EXPLAIN (ANALYZE false) {query}"
            elif "mysql" in dialect:
                # MySQL: EXPLAIN validates syntax
                validate_query = f"EXPLAIN {query}"
            else:
                validate_query = f"EXPLAIN {query}"

            # Try to run the explain query - if it fails, syntax is invalid
            db.run(validate_query)

            # If we get here, syntax is valid
            return "✓ Query syntax is valid.\n\nThe query is syntactically correct and can be executed."

        except SQLAlchemyError as e:
            error_msg = str(e)
            return f"✗ Query syntax error:\n\n{error_msg}\n\nPlease fix the syntax and try again."
        except Exception as e:
            return f"✗ Validation error: {str(e)}"


class JiraSkill(Skill):
    """Jira skill for read-only Jira integration.

    Provides querying capabilities for Jira issues, sprints, projects, and users.
    All operations are READ-ONLY - no create, update, delete, or transition operations.

    Content is loaded from .md files in src/langchain_docker/skills/jira/
    """

    def __init__(
        self,
        url: Optional[str] = None,
        bearer_token: Optional[str] = None,
        api_version: Optional[str] = None,
    ):
        """Initialize Jira skill.

        Args:
            url: Jira instance URL (defaults to JIRA_URL env var)
            bearer_token: Jira Bearer token (defaults to JIRA_BEARER_TOKEN env var)
            api_version: API version "2" or "3" (defaults to JIRA_API_VERSION env var)
        """
        self.id = "jira"
        self.name = "Jira Query Expert"
        self.description = "Query Jira issues, sprints, projects, and users (read-only)"
        self.category = "project_management"
        self.is_builtin = True
        self.version = "1.0.0"

        # Load config values
        self.url = url or get_jira_url()
        self.bearer_token = bearer_token or get_jira_bearer_token()
        self.api_version = api_version or get_jira_api_version()

        logger.info(f"[Jira] Initialized: url={self.url}, api_version={self.api_version}, token_configured={bool(self.bearer_token)}")

        self._skill_dir = SKILLS_DIR / "jira"
        self._session = None
        self._custom_content = None
        self._custom_resources = None
        self._tool_configs = []
        self._resource_configs = []
        self._load_configs_from_frontmatter()

    def _get_session(self):
        """Get or create requests session with Bearer token authentication.

        Returns:
            Configured requests session or None if not configured
        """
        if not self.url or not self.bearer_token:
            logger.warning("[Jira] Not configured - missing URL or bearer token")
            return None

        if self._session is None:
            import requests
            self._session = requests.Session()
            self._session.headers.update({
                "Authorization": f"Bearer {self.bearer_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            })
            logger.info("[Jira] Session created with Bearer token auth")

        return self._session

    def _read_md_file(self, filename: str) -> str:
        """Read content from a markdown file in the skill directory.

        Args:
            filename: Name of the .md file to read

        Returns:
            File content or error message if file not found
        """
        file_path = self._skill_dir / filename
        try:
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                # Strip YAML frontmatter if present
                if content.startswith("---"):
                    lines = content.split("\n")
                    for i, line in enumerate(lines[1:], 1):
                        if line.strip() == "---":
                            content = "\n".join(lines[i + 1 :]).strip()
                            break
                return content
            else:
                logger.warning(f"Skill file not found: {file_path}")
                return f"Error: File {filename} not found in skill directory"
        except Exception as e:
            logger.error(f"Error reading skill file {filename}: {e}")
            return f"Error reading {filename}: {str(e)}"

    def _load_configs_from_frontmatter(self) -> None:
        """Parse SKILL.md frontmatter to load tool and resource configs."""
        try:
            file_path = self._skill_dir / "SKILL.md"
            if not file_path.exists():
                return

            content = file_path.read_text(encoding="utf-8")
            if not content.startswith("---"):
                return

            # Parse YAML frontmatter
            lines = content.split("\n")
            end_idx = None
            for i, line in enumerate(lines[1:], 1):
                if line.strip() == "---":
                    end_idx = i
                    break

            if end_idx:
                import yaml
                frontmatter = "\n".join(lines[1:end_idx])
                metadata = yaml.safe_load(frontmatter) or {}

                # Load tool configs
                tool_configs = metadata.get("tool_configs", [])
                self._tool_configs = [
                    {
                        "name": t.get("name", ""),
                        "description": t.get("description", ""),
                        "method": t.get("method", ""),
                        "args": t.get("args", []),
                        "requires_skill_loaded": t.get("requires_skill_loaded", True),
                    }
                    for t in tool_configs
                ] if tool_configs else []

                # Load resource configs
                resource_configs = metadata.get("resource_configs", [])
                self._resource_configs = [
                    {
                        "name": r.get("name", ""),
                        "description": r.get("description", ""),
                        "file": r.get("file"),
                        "content": r.get("content"),
                        "dynamic": r.get("dynamic", False),
                        "method": r.get("method"),
                    }
                    for r in resource_configs
                ] if resource_configs else []

                logger.debug(
                    f"Loaded configs for {self.id}: "
                    f"{len(self._tool_configs)} tools, {len(self._resource_configs)} resources"
                )
        except Exception as e:
            logger.warning(f"Failed to load configs from frontmatter for {self.id}: {e}")

    def _api_get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make a GET request to the Jira API.

        Args:
            endpoint: API endpoint (e.g., "/rest/api/2/issue/PROJ-123")
            params: Optional query parameters

        Returns:
            JSON response as dictionary or error dict
        """
        session = self._get_session()
        if not session:
            logger.error("[Jira API] Not configured - missing JIRA_URL or JIRA_BEARER_TOKEN")
            return {"error": "Jira not configured. Set JIRA_URL and JIRA_BEARER_TOKEN environment variables."}

        url = f"{self.url.rstrip('/')}{endpoint}"
        logger.info(f"[Jira API] GET {url} params={params}")

        try:
            response = session.get(url, params=params, timeout=30)
            logger.info(f"[Jira API] Response: {response.status_code}")

            # Handle auth errors with clear messaging
            if response.status_code == 401:
                logger.error(f"[Jira API] AUTH ERROR 401: Token expired or invalid. Please refresh your OAuth token.")
                logger.error(f"[Jira API] Response: {response.text[:500]}")
                return {"error": "Jira authentication failed (401). Your OAuth token may be expired. Please refresh it."}

            if response.status_code == 403:
                logger.error(f"[Jira API] AUTH ERROR 403: Forbidden. Token may lack required scopes.")
                logger.error(f"[Jira API] Response: {response.text[:500]}")
                return {"error": "Jira forbidden (403). Your token may lack required scopes (read:jira-work, read:jira-user)."}

            if response.status_code >= 400:
                # Try to extract Jira error message
                error_detail = response.text[:500]
                try:
                    error_json = response.json()
                    if "errorMessages" in error_json:
                        error_detail = "; ".join(error_json["errorMessages"])
                    elif "message" in error_json:
                        error_detail = error_json["message"]
                except Exception:
                    pass
                logger.error(f"[Jira API] ERROR {response.status_code}: {error_detail}")
                return {"error": f"Jira API error ({response.status_code}): {error_detail}"}

            response.raise_for_status()
            result = response.json()
            logger.info(f"[Jira API] Success - response keys: {list(result.keys()) if isinstance(result, dict) else 'list'}")
            return result
        except Exception as e:
            logger.error(f"[Jira API] Exception: {type(e).__name__}: {str(e)}")
            return {"error": f"Jira API error: {str(e)}"}

    def get_file_content(self) -> str:
        """Get the original file-based content for this skill.

        Returns:
            Original SKILL.md content (static guidelines only)
        """
        return self._read_md_file("SKILL.md")

    def load_core(self) -> str:
        """Level 2: Load Jira skill instructions.

        Combines dynamic configuration status with static content.
        Static content uses Redis custom content if available, otherwise SKILL.md.

        Returns:
            Complete skill context for Jira operations
        """
        # Dynamic content: Check if Jira is configured
        config_status = ""
        if not is_jira_configured():
            config_status = """
### Configuration Status
**Warning**: Jira is not fully configured. Set the following environment variables:
- `JIRA_URL`: Your Jira instance URL
- `JIRA_BEARER_TOKEN`: Your Personal Access Token
"""
        else:
            config_status = f"""
### Configuration Status
- Connected to: {self.url}
- API Version: {self.api_version}
"""

        # Static content: prefer Redis custom content, fallback to file
        if self._custom_content is not None:
            static_content = self._custom_content
        else:
            static_content = self._read_md_file("SKILL.md")

        return f"""## Jira Skill Activated
{config_status}
{static_content}
"""

    def load_details(self, resource: str) -> str:
        """Level 3: Load detailed resources from .md files.

        Args:
            resource: "jql_reference" for JQL guide

        Returns:
            Detailed resource content from the corresponding .md file
        """
        resource_map = {
            "jql_reference": "jql_reference.md",
            "jql": "jql_reference.md",  # Alias
        }

        if resource in resource_map:
            return self._read_md_file(resource_map[resource])
        else:
            available = ", ".join(f"'{r}'" for r in set(resource_map.keys()))
            return f"Unknown resource: {resource}. Available: {available}"

    def search_issues(
        self,
        jql: str,
        fields: Optional[list[str]] = None,
        max_results: int = 50,
        start_at: int = 0,
    ) -> str:
        """Search for issues using JQL.

        Args:
            jql: JQL query string
            fields: Fields to return (default: key, summary, status, assignee, priority)
            max_results: Maximum results to return (default: 50)
            start_at: Starting index for pagination

        Returns:
            Formatted search results or error message
        """
        if fields is None:
            fields = ["key", "summary", "status", "assignee", "priority", "issuetype"]

        params = {
            "jql": jql,
            "fields": ",".join(fields),
            "maxResults": max_results,
            "startAt": start_at,
        }

        result = self._api_get(f"/rest/api/{self.api_version}/search", params)

        if "error" in result:
            return result["error"]

        issues = result.get("issues", [])
        total = result.get("total", 0)

        if not issues:
            return f"No issues found for query: {jql}"

        output = [f"Found {total} issues (showing {len(issues)}):"]
        for issue in issues:
            key = issue.get("key", "")
            fields_data = issue.get("fields", {})
            summary = fields_data.get("summary", "No summary")
            status = fields_data.get("status", {}).get("name", "Unknown")
            assignee = fields_data.get("assignee", {})
            assignee_name = assignee.get("displayName", "Unassigned") if assignee else "Unassigned"
            priority = fields_data.get("priority", {})
            priority_name = priority.get("name", "None") if priority else "None"
            issue_type = fields_data.get("issuetype", {}).get("name", "Unknown")

            output.append(f"\n**{key}** [{issue_type}] - {summary}")
            output.append(f"  Status: {status} | Priority: {priority_name} | Assignee: {assignee_name}")

        return "\n".join(output)

    def get_issue(self, issue_key: str, fields: Optional[list[str]] = None) -> str:
        """Get detailed information about a specific issue.

        Args:
            issue_key: Issue key (e.g., "PROJ-123")
            fields: Specific fields to return (default: all)

        Returns:
            Formatted issue details or error message
        """
        params = {}
        if fields:
            params["fields"] = ",".join(fields)

        result = self._api_get(f"/rest/api/{self.api_version}/issue/{issue_key}", params)

        if "error" in result:
            return result["error"]

        key = result.get("key", issue_key)
        fields_data = result.get("fields", {})

        summary = fields_data.get("summary", "No summary")
        description = fields_data.get("description", "No description")
        status = fields_data.get("status", {}).get("name", "Unknown")
        priority = fields_data.get("priority", {})
        priority_name = priority.get("name", "None") if priority else "None"
        issue_type = fields_data.get("issuetype", {}).get("name", "Unknown")
        assignee = fields_data.get("assignee", {})
        assignee_name = assignee.get("displayName", "Unassigned") if assignee else "Unassigned"
        reporter = fields_data.get("reporter", {})
        reporter_name = reporter.get("displayName", "Unknown") if reporter else "Unknown"
        created = fields_data.get("created", "Unknown")
        updated = fields_data.get("updated", "Unknown")
        labels = fields_data.get("labels", [])

        output = [
            f"# {key}: {summary}",
            f"",
            f"**Type:** {issue_type}",
            f"**Status:** {status}",
            f"**Priority:** {priority_name}",
            f"**Assignee:** {assignee_name}",
            f"**Reporter:** {reporter_name}",
            f"**Created:** {created}",
            f"**Updated:** {updated}",
        ]

        if labels:
            output.append(f"**Labels:** {', '.join(labels)}")

        output.append(f"\n## Description\n{description}")

        return "\n".join(output)

    def list_projects(self) -> str:
        """List all accessible projects.

        Returns:
            Formatted list of projects or error message
        """
        result = self._api_get(f"/rest/api/{self.api_version}/project")

        if isinstance(result, dict) and "error" in result:
            return result["error"]

        if not result:
            return "No projects found or accessible."

        output = ["**Available Projects:**\n"]
        for project in result:
            key = project.get("key", "")
            name = project.get("name", "")
            output.append(f"- **{key}**: {name}")

        return "\n".join(output)

    def get_sprints(self, board_id: int, state: str = "active") -> str:
        """Get sprints for a board.

        Args:
            board_id: Agile board ID
            state: Sprint state filter (active, closed, future)

        Returns:
            Formatted list of sprints or error message
        """
        params = {"state": state}
        result = self._api_get(f"/rest/agile/1.0/board/{board_id}/sprint", params)

        if "error" in result:
            return result["error"]

        sprints = result.get("values", [])

        if not sprints:
            return f"No {state} sprints found for board {board_id}."

        output = [f"**{state.title()} Sprints for Board {board_id}:**\n"]
        for sprint in sprints:
            sprint_id = sprint.get("id", "")
            name = sprint.get("name", "")
            state_name = sprint.get("state", "")
            start_date = sprint.get("startDate", "N/A")
            end_date = sprint.get("endDate", "N/A")

            output.append(f"- **{name}** (ID: {sprint_id})")
            output.append(f"  State: {state_name} | Start: {start_date} | End: {end_date}")

        return "\n".join(output)

    def get_sprint_issues(self, sprint_id: int, fields: Optional[list[str]] = None) -> str:
        """Get all issues in a sprint.

        Args:
            sprint_id: Sprint ID
            fields: Fields to return

        Returns:
            Formatted list of sprint issues or error message
        """
        if fields is None:
            fields = ["key", "summary", "status", "assignee", "priority", "issuetype"]

        params = {"fields": ",".join(fields)}
        result = self._api_get(f"/rest/agile/1.0/sprint/{sprint_id}/issue", params)

        if "error" in result:
            return result["error"]

        issues = result.get("issues", [])

        if not issues:
            return f"No issues found in sprint {sprint_id}."

        output = [f"**Issues in Sprint {sprint_id}:**\n"]
        for issue in issues:
            key = issue.get("key", "")
            fields_data = issue.get("fields", {})
            summary = fields_data.get("summary", "No summary")
            status = fields_data.get("status", {}).get("name", "Unknown")
            assignee = fields_data.get("assignee", {})
            assignee_name = assignee.get("displayName", "Unassigned") if assignee else "Unassigned"

            output.append(f"- **{key}**: {summary}")
            output.append(f"  Status: {status} | Assignee: {assignee_name}")

        return "\n".join(output)

    def get_changelog(self, issue_key: str) -> str:
        """Get the change history for an issue.

        Args:
            issue_key: Issue key (e.g., "PROJ-123")

        Returns:
            Formatted changelog or error message
        """
        params = {"expand": "changelog"}
        result = self._api_get(f"/rest/api/{self.api_version}/issue/{issue_key}", params)

        if "error" in result:
            return result["error"]

        changelog = result.get("changelog", {})
        histories = changelog.get("histories", [])

        if not histories:
            return f"No change history found for {issue_key}."

        output = [f"**Change History for {issue_key}:**\n"]
        for history in histories[:20]:  # Limit to last 20 changes
            author = history.get("author", {}).get("displayName", "Unknown")
            created = history.get("created", "Unknown")
            items = history.get("items", [])

            output.append(f"\n**{created}** by {author}:")
            for item in items:
                field = item.get("field", "")
                from_str = item.get("fromString", "None")
                to_str = item.get("toString", "None")
                output.append(f"  - {field}: '{from_str}' → '{to_str}'")

        return "\n".join(output)

    def get_comments(self, issue_key: str, max_results: int = 50) -> str:
        """Get comments on a Jira issue.

        Args:
            issue_key: Issue key (e.g., "PROJ-123")
            max_results: Maximum comments to return

        Returns:
            Formatted list of comments or error message
        """
        params = {"maxResults": max_results, "orderBy": "-created"}
        result = self._api_get(
            f"/rest/api/{self.api_version}/issue/{issue_key}/comment",
            params
        )

        if "error" in result:
            return result["error"]

        comments = result.get("comments", [])
        total = result.get("total", 0)

        if not comments:
            return f"No comments found on {issue_key}."

        output = [f"**Comments on {issue_key}** ({total} total, showing {len(comments)}):\n"]
        for comment in comments:
            author = comment.get("author", {}).get("displayName", "Unknown")
            created = comment.get("created", "Unknown")
            body = comment.get("body", "")
            # Truncate long comments
            if len(body) > 500:
                body = body[:500] + "..."

            output.append(f"**{author}** ({created}):")
            output.append(f"{body}\n")

        return "\n".join(output)

    def get_boards(self, project_key: Optional[str] = None, board_type: str = "scrum") -> str:
        """List all accessible agile boards.

        Args:
            project_key: Optional project key to filter boards
            board_type: Board type filter (scrum, kanban, or empty for all)

        Returns:
            Formatted list of boards or error message
        """
        params = {}
        if project_key:
            params["projectKeyOrId"] = project_key
        if board_type:
            params["type"] = board_type

        result = self._api_get("/rest/agile/1.0/board", params)

        if "error" in result:
            return result["error"]

        boards = result.get("values", [])

        if not boards:
            return "No boards found."

        output = ["**Available Boards:**\n"]
        for board in boards:
            board_id = board.get("id", "")
            name = board.get("name", "")
            b_type = board.get("type", "")
            project = board.get("location", {}).get("projectKey", "N/A")

            output.append(f"- **{name}** (ID: {board_id})")
            output.append(f"  Type: {b_type} | Project: {project}")

        return "\n".join(output)

    def get_worklogs(self, issue_key: str) -> str:
        """Get work logs for a Jira issue.

        Args:
            issue_key: Issue key (e.g., "PROJ-123")

        Returns:
            Formatted list of worklogs or error message
        """
        result = self._api_get(f"/rest/api/{self.api_version}/issue/{issue_key}/worklog")

        if "error" in result:
            return result["error"]

        worklogs = result.get("worklogs", [])

        if not worklogs:
            return f"No work logs found on {issue_key}."

        total_seconds = sum(w.get("timeSpentSeconds", 0) for w in worklogs)
        total_hours = total_seconds / 3600

        output = [f"**Work Logs for {issue_key}** (Total: {total_hours:.1f}h):\n"]
        for log in worklogs:
            author = log.get("author", {}).get("displayName", "Unknown")
            started = log.get("started", "Unknown")
            time_spent = log.get("timeSpent", "Unknown")
            comment = log.get("comment", "")

            output.append(f"- **{author}** logged {time_spent} on {started}")
            if comment:
                truncated = comment[:100] + "..." if len(comment) > 100 else comment
                output.append(f"  Comment: {truncated}")

        return "\n".join(output)


class KnowledgeBaseSkill(Skill):
    """Knowledge Base skill for RAG (Retrieval-Augmented Generation).

    Provides semantic search over the vector knowledge base containing
    uploaded documents. Enables agents to retrieve relevant context
    for answering questions.

    Content is loaded from .md files in src/langchain_docker/skills/knowledge_base/
    """

    def __init__(self):
        """Initialize Knowledge Base skill."""
        self.id = "knowledge_base"
        self.name = "Knowledge Base Search"
        self.description = (
            "Search and retrieve information from the vector knowledge base (RAG)"
        )
        self.category = "knowledge"
        self.is_builtin = True
        self.version = "1.0.0"
        self._skill_dir = SKILLS_DIR / "knowledge_base"
        self._custom_content = None
        self._custom_resources = None
        self._tool_configs = []
        self._resource_configs = []
        self._kb_service = None
        self._load_configs_from_frontmatter()

    def _get_kb_service(self):
        """Get the knowledge base service (lazy loaded).

        Returns:
            KnowledgeBaseService instance or None if not available
        """
        if self._kb_service is None:
            try:
                from langchain_docker.api.services.knowledge_base_service import (
                    KnowledgeBaseService,
                )
                self._kb_service = KnowledgeBaseService()
            except Exception as e:
                logger.warning(f"Failed to initialize KnowledgeBaseService: {e}")
                self._kb_service = None
        return self._kb_service

    def _read_md_file(self, filename: str) -> str:
        """Read content from a markdown file in the skill directory.

        Args:
            filename: Name of the .md file to read

        Returns:
            File content or error message if file not found
        """
        file_path = self._skill_dir / filename
        try:
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                # Strip YAML frontmatter if present
                if content.startswith("---"):
                    lines = content.split("\n")
                    for i, line in enumerate(lines[1:], 1):
                        if line.strip() == "---":
                            content = "\n".join(lines[i + 1 :]).strip()
                            break
                return content
            else:
                logger.warning(f"Skill file not found: {file_path}")
                return f"Error: File {filename} not found in skill directory"
        except Exception as e:
            logger.error(f"Error reading skill file {filename}: {e}")
            return f"Error reading {filename}: {str(e)}"

    def _load_configs_from_frontmatter(self) -> None:
        """Parse SKILL.md frontmatter to load tool and resource configs."""
        try:
            file_path = self._skill_dir / "SKILL.md"
            if not file_path.exists():
                return

            content = file_path.read_text(encoding="utf-8")
            if not content.startswith("---"):
                return

            # Parse YAML frontmatter
            lines = content.split("\n")
            end_idx = None
            for i, line in enumerate(lines[1:], 1):
                if line.strip() == "---":
                    end_idx = i
                    break

            if end_idx:
                import yaml
                frontmatter = "\n".join(lines[1:end_idx])
                metadata = yaml.safe_load(frontmatter) or {}

                # Load tool configs
                tool_configs = metadata.get("tool_configs", [])
                self._tool_configs = [
                    {
                        "name": t.get("name", ""),
                        "description": t.get("description", ""),
                        "method": t.get("method", ""),
                        "args": t.get("args", []),
                        "requires_skill_loaded": t.get("requires_skill_loaded", True),
                    }
                    for t in tool_configs
                ] if tool_configs else []

                # Load resource configs
                resource_configs = metadata.get("resource_configs", [])
                self._resource_configs = [
                    {
                        "name": r.get("name", ""),
                        "description": r.get("description", ""),
                        "file": r.get("file"),
                        "content": r.get("content"),
                        "dynamic": r.get("dynamic", False),
                        "method": r.get("method"),
                    }
                    for r in resource_configs
                ] if resource_configs else []

                logger.debug(
                    f"Loaded configs for {self.id}: "
                    f"{len(self._tool_configs)} tools, {len(self._resource_configs)} resources"
                )
        except Exception as e:
            logger.warning(f"Failed to load configs from frontmatter for {self.id}: {e}")

    def get_file_content(self) -> str:
        """Get the original file-based content for this skill.

        Returns:
            Original SKILL.md content (static guidelines only)
        """
        return self._read_md_file("SKILL.md")

    def load_core(self) -> str:
        """Level 2: Load knowledge base skill instructions.

        Combines dynamic status information with static content.
        Static content uses Redis custom content if available, otherwise SKILL.md.

        Returns:
            Complete skill context for knowledge base operations
        """
        # Dynamic content: Check if knowledge base is available
        kb_service = self._get_kb_service()
        if kb_service and kb_service.is_available:
            try:
                stats = kb_service.get_stats()
                status = f"""
### Knowledge Base Status
- **Available**: Yes
- **Documents**: {stats.total_documents}
- **Chunks**: {stats.total_chunks}
- **Collections**: {stats.total_collections}
- **Index Size**: {stats.index_size}
"""
            except Exception as e:
                logger.warning(f"Failed to get KB stats: {e}")
                status = """
### Knowledge Base Status
- **Available**: Yes (stats unavailable)
"""
        else:
            status = """
### Knowledge Base Status
**Warning**: Knowledge base is not available. OpenSearch may not be configured.

To enable the knowledge base:
1. Set `OPENSEARCH_URL` in your environment
2. Ensure OpenSearch is running (docker-compose up opensearch)
"""

        # Static content: prefer Redis custom content, fallback to file
        if self._custom_content is not None:
            static_content = self._custom_content
        else:
            static_content = self._read_md_file("SKILL.md")

        return f"""## Knowledge Base Skill Activated
{status}
{static_content}
"""

    def load_details(self, resource: str) -> str:
        """Level 3: Load detailed resources.

        Args:
            resource: "search_tips" for search guidance

        Returns:
            Detailed resource content
        """
        if resource == "search_tips":
            # Return inline search tips
            return """## Search Tips
- Use specific keywords related to your topic
- Try different phrasings if initial search doesn't return good results
- Use collection filters to narrow down results
- Higher top_k values give more context but may include less relevant results
"""
        else:
            return f"Unknown resource: {resource}. Available: 'search_tips'"

    def search(
        self,
        query: str,
        top_k: int = 5,
        collection: Optional[str] = None,
    ) -> str:
        """Search the knowledge base.

        Args:
            query: Search query
            top_k: Number of results to return
            collection: Optional collection filter

        Returns:
            Formatted search results or error message
        """
        kb_service = self._get_kb_service()
        if not kb_service or not kb_service.is_available:
            return "Error: Knowledge base is not available. Ensure OpenSearch is configured."

        try:
            results = kb_service.search(
                query=query,
                top_k=top_k,
                collection=collection,
            )

            if not results:
                return f"No results found for query: '{query}'"

            output = [f"**Search Results for '{query}'** ({len(results)} results):\n"]
            for i, result in enumerate(results, 1):
                source = result.metadata.get("filename", "Unknown")
                score = f"{result.score:.2f}" if result.score else "N/A"
                content = result.content[:500] + "..." if len(result.content) > 500 else result.content

                output.append(f"\n**Result {i}** (Score: {score}, Source: {source})")
                output.append(f"```\n{content}\n```")

            return "\n".join(output)
        except Exception as e:
            logger.error(f"Knowledge base search error: {e}")
            return f"Error searching knowledge base: {str(e)}"

    def list_documents(self, collection: Optional[str] = None) -> str:
        """List documents in the knowledge base.

        Args:
            collection: Optional collection filter

        Returns:
            Formatted list of documents
        """
        kb_service = self._get_kb_service()
        if not kb_service or not kb_service.is_available:
            return "Error: Knowledge base is not available."

        try:
            docs = kb_service.list_documents(collection=collection, limit=50)

            if not docs:
                return "No documents found in the knowledge base."

            output = [f"**Documents in Knowledge Base** ({len(docs)} documents):\n"]
            for doc in docs:
                collection_str = f" (Collection: {doc.collection})" if doc.collection else ""
                output.append(
                    f"- **{doc.filename}** ({doc.chunk_count} chunks){collection_str}\n"
                    f"  ID: {doc.id} | Type: {doc.content_type}"
                )

            return "\n".join(output)
        except Exception as e:
            logger.error(f"List documents error: {e}")
            return f"Error listing documents: {str(e)}"

    def list_collections(self) -> str:
        """List all collections in the knowledge base.

        Returns:
            Formatted list of collections
        """
        kb_service = self._get_kb_service()
        if not kb_service or not kb_service.is_available:
            return "Error: Knowledge base is not available."

        try:
            collections = kb_service.list_collections()

            if not collections:
                return "No collections found. Documents are in the default collection."

            output = ["**Collections in Knowledge Base:**\n"]
            for col in collections:
                output.append(f"- **{col.name}** ({col.document_count} documents)")

            return "\n".join(output)
        except Exception as e:
            logger.error(f"List collections error: {e}")
            return f"Error listing collections: {str(e)}"

    def get_stats(self) -> str:
        """Get knowledge base statistics.

        Returns:
            Formatted statistics
        """
        kb_service = self._get_kb_service()
        if not kb_service:
            return "Error: Knowledge base service not initialized."

        try:
            stats = kb_service.get_stats()
            return f"""**Knowledge Base Statistics:**
- Available: {stats.available}
- Total Documents: {stats.total_documents}
- Total Chunks: {stats.total_chunks}
- Total Collections: {stats.total_collections}
- Index Size: {stats.index_size}
- Last Updated: {stats.last_updated}
"""
        except Exception as e:
            logger.error(f"Get stats error: {e}")
            return f"Error getting statistics: {str(e)}"


class KBIngestionSkill(Skill):
    """Knowledge Base Ingestion skill for adding content to the vector store.

    Provides tools for ingesting text content, URLs, and managing documents
    in the knowledge base. Complements the KnowledgeBaseSkill for search.

    Content is loaded from .md files in src/langchain_docker/skills/kb_ingest/
    """

    def __init__(self):
        """Initialize KB Ingestion skill."""
        self.id = "kb_ingest"
        self.name = "Knowledge Base Ingestion"
        self.description = (
            "Ingest and manage documents in the vector knowledge base"
        )
        self.category = "knowledge"
        self.is_builtin = True
        self.version = "1.0.0"
        self._skill_dir = SKILLS_DIR / "kb_ingest"
        self._custom_content = None
        self._custom_resources = None
        self._tool_configs = []
        self._resource_configs = []
        self._kb_service = None
        self._load_configs_from_frontmatter()

    def _get_kb_service(self):
        """Get the knowledge base service (lazy loaded).

        Returns:
            KnowledgeBaseService instance or None if not available
        """
        if self._kb_service is None:
            try:
                from langchain_docker.api.services.knowledge_base_service import (
                    KnowledgeBaseService,
                )
                self._kb_service = KnowledgeBaseService()
            except Exception as e:
                logger.warning(f"Failed to initialize KnowledgeBaseService: {e}")
                self._kb_service = None
        return self._kb_service

    def _read_md_file(self, filename: str) -> str:
        """Read content from a markdown file in the skill directory.

        Args:
            filename: Name of the .md file to read

        Returns:
            File content or error message if file not found
        """
        file_path = self._skill_dir / filename
        try:
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                # Strip YAML frontmatter if present
                if content.startswith("---"):
                    lines = content.split("\n")
                    for i, line in enumerate(lines[1:], 1):
                        if line.strip() == "---":
                            content = "\n".join(lines[i + 1 :]).strip()
                            break
                return content
            else:
                logger.warning(f"Skill file not found: {file_path}")
                return f"Error: File {filename} not found in skill directory"
        except Exception as e:
            logger.error(f"Error reading skill file {filename}: {e}")
            return f"Error reading {filename}: {str(e)}"

    def _load_configs_from_frontmatter(self) -> None:
        """Parse SKILL.md frontmatter to load tool and resource configs."""
        try:
            file_path = self._skill_dir / "SKILL.md"
            if not file_path.exists():
                return

            content = file_path.read_text(encoding="utf-8")
            if not content.startswith("---"):
                return

            # Extract frontmatter
            lines = content.split("\n")
            frontmatter_end = -1
            for i, line in enumerate(lines[1:], 1):
                if line.strip() == "---":
                    frontmatter_end = i
                    break

            if frontmatter_end == -1:
                return

            import yaml
            frontmatter_text = "\n".join(lines[1:frontmatter_end])
            frontmatter = yaml.safe_load(frontmatter_text)

            if frontmatter:
                self._tool_configs = frontmatter.get("tool_configs", [])
                self._resource_configs = frontmatter.get("resource_configs", [])
                logger.debug(
                    f"Loaded configs for {self.id}: "
                    f"{len(self._tool_configs)} tools, {len(self._resource_configs)} resources"
                )
        except Exception as e:
            logger.warning(f"Failed to load configs from frontmatter for {self.id}: {e}")

    def get_file_content(self) -> str:
        """Get the original file-based content for this skill.

        Returns:
            Original SKILL.md content (static guidelines only)
        """
        return self._read_md_file("SKILL.md")

    def load_core(self) -> str:
        """Level 2: Load KB ingestion skill instructions.

        Combines dynamic status information with static content.

        Returns:
            Complete skill context for KB ingestion operations
        """
        # Dynamic content: Check if knowledge base is available
        kb_service = self._get_kb_service()
        if kb_service and kb_service.is_available:
            try:
                stats = kb_service.get_stats()
                status = f"""
### Knowledge Base Status
- **Available**: Yes
- **Documents**: {stats.total_documents}
- **Chunks**: {stats.total_chunks}
- **Collections**: {stats.total_collections}
- **Index Size**: {stats.index_size}
"""
            except Exception as e:
                logger.warning(f"Failed to get KB stats: {e}")
                status = """
### Knowledge Base Status
- **Available**: Yes (stats unavailable)
"""
        else:
            status = """
### Knowledge Base Status
**Warning**: Knowledge base is not available. OpenSearch may not be configured.

To enable the knowledge base:
1. Set `OPENSEARCH_URL` in your environment
2. Ensure OpenSearch is running (docker-compose up opensearch)
"""

        # Static content: prefer Redis custom content, fallback to file
        if self._custom_content is not None:
            static_content = self._custom_content
        else:
            static_content = self._read_md_file("SKILL.md")

        return f"""## Knowledge Base Ingestion Skill Activated
{status}
{static_content}
"""

    def load_details(self, resource: str) -> str:
        """Level 3: Load detailed resources.

        Args:
            resource: "ingestion_guidelines" for ingestion guidance

        Returns:
            Detailed resource content
        """
        if resource == "ingestion_guidelines":
            return """## Ingestion Guidelines

### Text Content
- Use descriptive titles that help identify the content
- Organize related content into collections
- Keep individual documents focused on a single topic
- Larger documents are automatically chunked for better search

### URL Content
- Web pages are fetched and converted to plain text
- JavaScript-heavy pages may not extract well
- Consider using the text ingestion for better control

### Collections
- Use collections to organize documents by topic or source
- Collection names should be lowercase with underscores
- Examples: "company_policies", "technical_docs", "meeting_notes"
"""
        else:
            return f"Unknown resource: {resource}. Available: 'ingestion_guidelines'"

    def ingest_text(
        self,
        text: str,
        title: str,
        collection: Optional[str] = None,
    ) -> str:
        """Ingest plain text content into the knowledge base.

        Args:
            text: The text content to ingest
            title: Title/name for the document
            collection: Optional collection to add the document to

        Returns:
            Success message with document details or error message
        """
        kb_service = self._get_kb_service()
        if not kb_service or not kb_service.is_available:
            return "Error: Knowledge base is not available. Ensure OpenSearch is configured."

        try:
            doc = kb_service.upload_text(
                text=text,
                title=title,
                collection=collection,
            )

            collection_str = f" in collection '{collection}'" if collection else ""
            return f"""**Document Ingested Successfully**
- **Title**: {doc.filename}
- **ID**: {doc.id}
- **Chunks**: {doc.chunk_count}
- **Size**: {doc.size} bytes{collection_str}

The content has been processed and indexed for semantic search.
"""
        except Exception as e:
            logger.error(f"Text ingestion error: {e}")
            return f"Error ingesting text: {str(e)}"

    def ingest_url(
        self,
        url: str,
        collection: Optional[str] = None,
    ) -> str:
        """Fetch and ingest content from a URL into the knowledge base.

        Args:
            url: The URL to fetch content from
            collection: Optional collection to add the document to

        Returns:
            Success message with document details or error message
        """
        kb_service = self._get_kb_service()
        if not kb_service or not kb_service.is_available:
            return "Error: Knowledge base is not available. Ensure OpenSearch is configured."

        try:
            import requests
            from bs4 import BeautifulSoup
        except ImportError:
            return "Error: URL ingestion requires 'requests' and 'beautifulsoup4' packages."

        try:
            # Fetch URL content
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; KnowledgeBot/1.0)"
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            # Parse HTML and extract text
            soup = BeautifulSoup(response.text, "html.parser")

            # Remove script and style elements
            for element in soup(["script", "style", "nav", "footer", "header"]):
                element.decompose()

            # Get text content
            text = soup.get_text(separator="\n", strip=True)

            # Get title
            title = soup.title.string if soup.title else url
            title = title[:100] if title else url[:100]

            # Upload to knowledge base
            doc = kb_service.upload_text(
                text=text,
                title=title,
                collection=collection,
                metadata={"source_url": url},
            )

            collection_str = f" in collection '{collection}'" if collection else ""
            return f"""**URL Content Ingested Successfully**
- **Title**: {doc.filename}
- **Source**: {url}
- **ID**: {doc.id}
- **Chunks**: {doc.chunk_count}
- **Size**: {doc.size} bytes{collection_str}

The web content has been processed and indexed for semantic search.
"""
        except requests.RequestException as e:
            logger.error(f"URL fetch error: {e}")
            return f"Error fetching URL: {str(e)}"
        except Exception as e:
            logger.error(f"URL ingestion error: {e}")
            return f"Error ingesting URL content: {str(e)}"

    def delete_document(self, document_id: str) -> str:
        """Delete a document from the knowledge base.

        Args:
            document_id: The ID of the document to delete

        Returns:
            Success or error message
        """
        kb_service = self._get_kb_service()
        if not kb_service or not kb_service.is_available:
            return "Error: Knowledge base is not available."

        try:
            deleted = kb_service.delete_document(document_id)
            if deleted:
                return f"**Document Deleted**\nDocument ID `{document_id}` has been removed from the knowledge base."
            else:
                return f"Document ID `{document_id}` not found in the knowledge base."
        except Exception as e:
            logger.error(f"Delete document error: {e}")
            return f"Error deleting document: {str(e)}"

    def get_document(self, document_id: str) -> str:
        """Get information about a specific document.

        Args:
            document_id: The ID of the document to retrieve

        Returns:
            Document details or error message
        """
        kb_service = self._get_kb_service()
        if not kb_service or not kb_service.is_available:
            return "Error: Knowledge base is not available."

        try:
            doc = kb_service.get_document(document_id)
            if doc:
                collection_str = f"\n- **Collection**: {doc.collection}" if doc.collection else ""
                return f"""**Document Details**
- **Filename**: {doc.filename}
- **ID**: {doc.id}
- **Type**: {doc.content_type}
- **Chunks**: {doc.chunk_count}
- **Size**: {doc.size} bytes{collection_str}
- **Created**: {doc.created_at}
"""
            else:
                return f"Document ID `{document_id}` not found in the knowledge base."
        except Exception as e:
            logger.error(f"Get document error: {e}")
            return f"Error getting document: {str(e)}"


class WebPerformanceSkill(Skill):
    """Web Performance Analysis skill using Chrome DevTools MCP integration.

    Provides guidance and structured workflows for analyzing website performance
    including Core Web Vitals, caching, API latency, and optimization recommendations.

    Content is loaded from .md files in src/langchain_docker/skills/web_performance/
    """

    def __init__(self):
        """Initialize Web Performance skill."""
        self.id = "web_performance"
        self.name = "Web Performance Analysis"
        self.description = (
            "Analyze website performance including Core Web Vitals, caching, "
            "API latency, and provide optimization recommendations"
        )
        self.category = "performance"
        self.is_builtin = True
        self.version = "1.0.0"
        self._skill_dir = SKILLS_DIR / "web_performance"
        self._custom_content = None
        self._custom_resources = None
        self._tool_configs = []
        self._resource_configs = []
        self._load_configs_from_frontmatter()

    def _read_md_file(self, filename: str) -> str:
        """Read content from a markdown file in the skill directory.

        Args:
            filename: Name of the .md file to read

        Returns:
            File content or error message if file not found
        """
        file_path = self._skill_dir / filename
        try:
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                # Strip YAML frontmatter if present
                if content.startswith("---"):
                    lines = content.split("\n")
                    for i, line in enumerate(lines[1:], 1):
                        if line.strip() == "---":
                            content = "\n".join(lines[i + 1 :]).strip()
                            break
                return content
            else:
                logger.warning(f"Skill file not found: {file_path}")
                return f"Error: File {filename} not found in skill directory"
        except Exception as e:
            logger.error(f"Error reading skill file {filename}: {e}")
            return f"Error reading {filename}: {str(e)}"

    def _load_configs_from_frontmatter(self) -> None:
        """Parse SKILL.md frontmatter to load tool and resource configs."""
        try:
            file_path = self._skill_dir / "SKILL.md"
            if not file_path.exists():
                return

            content = file_path.read_text(encoding="utf-8")
            if not content.startswith("---"):
                return

            # Extract frontmatter
            lines = content.split("\n")
            frontmatter_end = -1
            for i, line in enumerate(lines[1:], 1):
                if line.strip() == "---":
                    frontmatter_end = i
                    break

            if frontmatter_end == -1:
                return

            import yaml
            frontmatter_text = "\n".join(lines[1:frontmatter_end])
            frontmatter = yaml.safe_load(frontmatter_text)

            if frontmatter:
                self._tool_configs = frontmatter.get("tool_configs", [])
                self._resource_configs = frontmatter.get("resource_configs", [])
                logger.debug(
                    f"Loaded configs for {self.id}: "
                    f"{len(self._tool_configs)} tools, {len(self._resource_configs)} resources"
                )
        except Exception as e:
            logger.warning(f"Failed to load configs from frontmatter for {self.id}: {e}")

    def get_file_content(self) -> str:
        """Get the original file-based content for this skill.

        Returns:
            Original SKILL.md content (static guidelines only)
        """
        return self._read_md_file("SKILL.md")

    def load_core(self) -> str:
        """Level 2: Load web performance skill instructions.

        Returns:
            Complete skill context for performance analysis
        """
        # Static content: prefer Redis custom content, fallback to file
        if self._custom_content is not None:
            static_content = self._custom_content
        else:
            static_content = self._read_md_file("SKILL.md")

        # Add tool availability information - Chrome DevTools MCP only
        tool_info = """## Chrome DevTools MCP Tools

This skill provides **interactive browser-based performance analysis** using Chrome DevTools MCP.

### Available MCP Tools

| Tool | Description | Use Case |
|------|-------------|----------|
| `mcp__chrome-devtools__list_pages` | List open browser tabs | Get available pages |
| `mcp__chrome-devtools__select_page` | Select a page for inspection | Focus on target page |
| `mcp__chrome-devtools__new_page` | Create new browser tab | Navigate to target URL |
| `mcp__chrome-devtools__navigate_page` | Navigate current page | Load target URL |
| `mcp__chrome-devtools__performance_start_trace` | Start performance recording | Begin trace capture |
| `mcp__chrome-devtools__performance_stop_trace` | Stop and get trace results | Get CWV metrics |
| `mcp__chrome-devtools__performance_analyze_insight` | Analyze specific insight | Deep dive into metrics |
| `mcp__chrome-devtools__list_network_requests` | List all network requests | Analyze request patterns |
| `mcp__chrome-devtools__get_network_request` | Get request details + headers | Check caching, timing |
| `mcp__chrome-devtools__take_screenshot` | Capture page state | Visual verification |
| `mcp__chrome-devtools__take_snapshot` | Get accessibility tree | DOM structure analysis |

### Quick Start Workflow

1. **Get browser context**: `mcp__chrome-devtools__list_pages()`
2. **Navigate to URL**: `mcp__chrome-devtools__new_page(url="https://example.com")`
3. **Start trace**: `mcp__chrome-devtools__performance_start_trace(reload=true, autoStop=true)`
4. **Analyze results**: `mcp__chrome-devtools__performance_analyze_insight(...)`
5. **Check network**: `mcp__chrome-devtools__list_network_requests()`
"""

        return f"""## Web Performance Analysis Skill Activated

{tool_info}

{static_content}
"""

    def load_details(self, resource: str) -> str:
        """Level 3: Load detailed resources.

        Args:
            resource: Resource identifier

        Returns:
            Detailed resource content
        """
        if resource == "cwv_thresholds":
            return """## Core Web Vitals Thresholds (2024)

| Metric | Good | Needs Improvement | Poor |
|--------|------|-------------------|------|
| **LCP** | ≤ 2.5s | 2.5s - 4.0s | > 4.0s |
| **INP** | ≤ 200ms | 200ms - 500ms | > 500ms |
| **CLS** | ≤ 0.1 | 0.1 - 0.25 | > 0.25 |
| **FCP** | ≤ 1.8s | 1.8s - 3.0s | > 3.0s |
| **TBT** | ≤ 200ms | 200ms - 600ms | > 600ms |
| **Speed Index** | ≤ 3.4s | 3.4s - 5.8s | > 5.8s |
| **TTFB** | ≤ 0.8s | 0.8s - 1.8s | > 1.8s |
"""
        elif resource == "caching_headers":
            return """## Caching Headers Reference

### Cache-Control Directives

| Directive | Description | Use Case |
|-----------|-------------|----------|
| `max-age=N` | Fresh for N seconds | All cacheable resources |
| `s-maxage=N` | CDN cache time | CDN-specific caching |
| `no-cache` | Must revalidate | Dynamic content |
| `no-store` | Never cache | Sensitive data |
| `immutable` | Never changes | Versioned assets |
| `public` | Any cache can store | Public resources |
| `private` | Browser only | User-specific data |

### Recommended Cache Settings

| Resource Type | Cache-Control Value | TTL |
|---------------|---------------------|-----|
| Versioned JS/CSS | `max-age=31536000, immutable` | 1 year |
| Images | `max-age=2592000` | 30 days |
| Fonts | `max-age=31536000` | 1 year |
| HTML | `no-cache` or `max-age=0` | Always revalidate |
| API responses | `max-age=0, must-revalidate` | Based on data |

### Compression

| Format | Compression Ratio | Browser Support |
|--------|-------------------|-----------------|
| gzip | 70-80% | Universal |
| Brotli (br) | 80-90% | Modern browsers |
"""
        elif resource == "metric_explanations":
            return """## Performance Metrics Explained

### LCP (Largest Contentful Paint) - Loading

| Aspect | Description |
|--------|-------------|
| What it measures | Time until largest content element is visible |
| Why it matters | Users perceive this as "page loaded" |
| Target | ≤ 2.5 seconds |

| LCP Element Types | Examples |
|-------------------|----------|
| `<img>` | Hero images, product images |
| `<video>` poster | Video thumbnails |
| Background images | CSS `background-image` |
| Block-level text | Headings, paragraphs |

| Common Causes | Solution |
|---------------|----------|
| Slow server response | Use CDN, optimize backend |
| Render-blocking resources | Defer non-critical CSS/JS |
| Large images | Compress, use WebP/AVIF |
| Client-side rendering | Use SSR/SSG |

---

### INP (Interaction to Next Paint) - Responsiveness

| Aspect | Description |
|--------|-------------|
| What it measures | Latency of user interactions |
| Why it matters | Users expect instant feedback |
| Target | ≤ 200 milliseconds |

| Interaction Types | Examples |
|-------------------|----------|
| Click/Tap | Buttons, links, toggles |
| Key press | Form inputs, shortcuts |
| Touch | Swipes, pinch-zoom |

| Common Causes | Solution |
|---------------|----------|
| Long JavaScript tasks | Break into chunks < 50ms |
| Large DOM | Virtualize lists |
| Heavy event handlers | Debounce/throttle |

---

### CLS (Cumulative Layout Shift) - Stability

| Aspect | Description |
|--------|-------------|
| What it measures | How much content moves unexpectedly |
| Why it matters | Prevents accidental clicks |
| Target | ≤ 0.1 |

| Common Causes | Solution |
|---------------|----------|
| Images without dimensions | Add width/height attributes |
| Ads without reserved space | Use CSS aspect-ratio |
| Dynamic content injection | Use skeleton screens |
| Font loading (FOUT) | Use font-display: swap |

---

### TBT (Total Blocking Time) - Interactivity

| Aspect | Description |
|--------|-------------|
| What it measures | Sum of blocking time for long tasks |
| Why it matters | Indicates responsiveness during load |
| Target | ≤ 200 milliseconds |

| Task Duration | Blocking Time |
|---------------|---------------|
| < 50ms | 0ms (not blocking) |
| 100ms | 50ms blocking |
| 200ms | 150ms blocking |
| 500ms | 450ms blocking |

---

### TTFB (Time to First Byte) - Server

| Aspect | Description |
|--------|-------------|
| What it measures | Time from request to first response byte |
| Why it matters | Sets floor for all other metrics |
| Target | ≤ 800 milliseconds |

| TTFB Components | Target |
|-----------------|--------|
| DNS Lookup | < 50ms |
| TCP Connection | < 100ms |
| TLS Handshake | < 100ms |
| Server Processing | < 200ms |
"""
        elif resource == "resource_budgets":
            return """## Resource Size Budgets

### File Size Guidelines

| Resource Type | Budget | Notes |
|---------------|--------|-------|
| HTML | < 100KB | After compression |
| Critical CSS | < 14KB | Inlined in `<head>` |
| Total CSS | < 100KB | All stylesheets |
| Initial JS | < 200KB | For first load |
| Total JS | < 500KB | All JavaScript |
| Hero Images | < 200KB | Above-the-fold |
| Total Fonts | < 100KB | All font files |
| Page Weight | < 2MB | All resources |

### Request Count Guidelines

| Resource Type | Max Count | Notes |
|---------------|-----------|-------|
| Total Requests | < 50 | Initial page load |
| JavaScript | < 10 | Use bundling |
| CSS Files | < 5 | Combine sheets |
| Images | < 20 | Lazy load below-fold |
| Fonts | < 4 | Subset characters |
| Third-party | < 10 | Audit impact |

### Compression Expectations

| Original | gzip | Brotli |
|----------|------|--------|
| 100KB | 20-30KB | 15-25KB |
| 500KB | 100-150KB | 75-125KB |
| 1MB | 200-300KB | 150-250KB |
"""
        elif resource == "network_timing":
            return """## Network Timing Breakdown

### Request Timing Phases

| Phase | Description | Target | Action if Slow |
|-------|-------------|--------|----------------|
| **Queuing** | Waiting for network slot | < 10ms | Reduce concurrent requests |
| **Stalled** | Waiting before request | < 50ms | Check for blocking resources |
| **DNS** | Domain name resolution | < 50ms | Use DNS prefetch, faster DNS |
| **Initial Connection** | TCP handshake | < 100ms | Use HTTP/2, connection pooling |
| **SSL** | TLS negotiation | < 100ms | Use TLS 1.3, session resumption |
| **TTFB** | Server processing | < 200ms | Optimize backend, use caching |
| **Content Download** | Transfer bytes | Varies | Compress, use CDN, optimize size |

### Analyzing Network Requests

Use `mcp__chrome-devtools__get_network_request(reqid=N)` to get detailed timing for specific requests.

### Slow Request Indicators

| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| High DNS | Many unique domains | Consolidate domains, DNS prefetch |
| High Connection | Cold connections | Keep-alive, HTTP/2, preconnect |
| High SSL | TLS overhead | TLS 1.3, session tickets |
| High TTFB | Slow backend | Optimize queries, add caching |
| High Download | Large payload | Compress, paginate, lazy load |
"""
        else:
            return f"Unknown resource: {resource}. Available: 'cwv_thresholds', 'caching_headers', 'metric_explanations', 'resource_budgets', 'network_timing'"

    def analyze_performance(self, url: str) -> str:
        """Provide comprehensive performance analysis guidance for a URL.

        Args:
            url: The URL to analyze

        Returns:
            Performance analysis context and recommendations
        """
        return f"""## Performance Analysis Plan for {url}

### Chrome DevTools MCP Analysis

This skill uses Chrome DevTools MCP for interactive browser-based performance analysis.

**Prerequisites:** Ensure chrome-devtools MCP server is enabled.

### Step-by-Step Workflow

1. **Get browser context**:
   ```
   mcp__chrome-devtools__list_pages()
   ```

2. **Create or select a page**:
   ```
   mcp__chrome-devtools__new_page(url="{url}")
   ```

3. **Start performance trace**:
   ```
   mcp__chrome-devtools__performance_start_trace(reload=true, autoStop=true)
   ```

4. **Analyze insights** (after trace completes):
   ```
   mcp__chrome-devtools__performance_analyze_insight(insightSetId="...", insightName="...")
   ```

5. **Inspect network requests**:
   ```
   mcp__chrome-devtools__list_network_requests()
   ```

### Core Web Vitals Reference (2024)

| Metric | Good | Needs Work | Poor |
|--------|------|------------|------|
| **LCP** | ≤2.5s | 2.5-4.0s | >4.0s |
| **INP** | ≤200ms | 200-500ms | >500ms |
| **CLS** | ≤0.1 | 0.1-0.25 | >0.25 |
| **FCP** | ≤1.8s | 1.8-3.0s | >3.0s |
| **TTFB** | ≤0.8s | 0.8-1.8s | >1.8s |

### Key Issues to Look For

| Issue | Symptom | MCP Tool to Use |
|-------|---------|-----------------|
| Large Images | Slow LCP | `list_network_requests` (filter images) |
| Slow API | High TTFB on XHR | `get_network_request` (timing details) |
| Missing Caching | Repeat downloads | `get_network_request` (check headers) |
| Long Tasks | High TBT | `performance_analyze_insight` |
| Layout Shifts | High CLS | `performance_analyze_insight` |

**NOTE**: For automated audits without browser interaction, use the `lighthouse_performance_analyst` agent instead.
"""

    def check_caching(self, url: str) -> str:
        """Provide caching analysis guidance for a URL.

        Args:
            url: The URL to check caching for

        Returns:
            Caching best practices and analysis guidance
        """
        return f"""## Caching Analysis for {url}

### ⚠️ Browser Automation Required
To inspect actual HTTP headers, the chrome-devtools MCP server must be connected. Use:
- `mcp__chrome-devtools__list_network_requests` - List all requests
- `mcp__chrome-devtools__get_network_request` - Get headers for specific request

### Caching Headers Reference

| Header | Recommended Value | Purpose |
|--------|-------------------|---------|
| **Cache-Control** | `max-age=31536000, immutable` | Long-term caching for versioned assets |
| **ETag** | Auto-generated hash | Conditional request validation |
| **Expires** | Future date | Legacy cache control |
| **Content-Encoding** | `gzip` or `br` | Compression for text resources |
| **Vary** | `Accept-Encoding` | Proper cache key for compressed |

### Optimal Caching by Resource Type

| Resource | Recommended Strategy |
|----------|---------------------|
| **JS/CSS (versioned)** | `max-age=31536000, immutable` |
| **Images** | `max-age=86400` to `max-age=31536000` |
| **Fonts** | `max-age=31536000` + preload |
| **HTML** | `no-cache` or short max-age |
| **API responses** | Depends on data freshness |

### Common Caching Issues

1. **Missing Cache-Control**: Browser fetches every time
2. **Short TTL**: Frequent unnecessary revalidation
3. **No Compression**: Larger transfer sizes (enable gzip/brotli)
4. **Missing ETag**: No conditional requests possible

### What to Check on {url}

- Static assets (.js, .css, images) should have long cache TTL
- Versioned files (hash in filename) can use `immutable`
- Check if compression is enabled for text resources
- Verify CDN is properly caching static content

**ANALYSIS COMPLETE** - Use chrome-devtools MCP to inspect actual headers, or provide these best practices to the user.
"""

    def analyze_api_calls(self, url: str) -> str:
        """Provide guidance for API call analysis.

        Args:
            url: The URL to analyze API calls for

        Returns:
            API analysis guidance
        """
        return f"""## API Performance Analysis for {url}

### ⚠️ Browser Automation Required
To capture actual API calls and timing, the chrome-devtools MCP server must be connected. Use:
- `mcp__chrome-devtools__list_network_requests` with resourceTypes: ["xhr", "fetch"]
- `mcp__chrome-devtools__get_network_request` for detailed timing

### API Timing Thresholds

| Phase | Good | Action Needed |
|-------|------|---------------|
| **DNS** | <50ms | Check DNS provider, enable DNS prefetch |
| **Connect** | <100ms | Use HTTP/2, connection pooling |
| **TLS** | <100ms | Enable TLS 1.3, session resumption |
| **TTFB** | <200ms | Optimize server processing |
| **Total** | <500ms | Review entire request lifecycle |

### Common API Performance Issues

| Issue | Impact | Solution |
|-------|--------|----------|
| **Slow Response (>500ms)** | Poor UX | Server optimization, caching |
| **Sequential Requests** | Waterfall delays | Use Promise.all for parallel |
| **Auth Bottlenecks** | Multiple token calls | Cache tokens, use refresh |
| **Large Payloads (>100KB)** | Slow download | Pagination, field selection |
| **Redundant Requests** | Wasted bandwidth | Request deduplication |

### API Optimization Checklist

✓ Response time <500ms for critical APIs
✓ Payload size <100KB (use pagination)
✓ Parallel requests for independent data
✓ Auth tokens cached appropriately
✓ Response caching where appropriate
✓ Compression enabled (gzip/brotli)

### What to Analyze on {url}

- Identify all XHR/fetch calls during page load
- Check for slow APIs (>500ms TTFB)
- Look for request waterfall patterns
- Verify auth calls aren't bottlenecks
- Check response payload sizes

**ANALYSIS COMPLETE** - Use chrome-devtools MCP for live API capture, or provide these guidelines to the user.
"""

    def get_recommendations(self, metrics: str) -> str:
        """Generate optimization recommendations based on metrics.

        Args:
            metrics: JSON string or description of performance metrics

        Returns:
            Optimization recommendations
        """
        return f"""## Performance Optimization Recommendations

Based on analysis: {metrics}

---

### Optimization Priority Matrix

| Priority | Category | Impact | Effort |
|----------|----------|--------|--------|
| 1 | Critical Rendering Path | High | Medium |
| 2 | Image Optimization | High | Low |
| 3 | Caching Strategy | Medium | Low |
| 4 | JavaScript Optimization | High | High |
| 5 | API Performance | Medium | Medium |

---

### Critical Rendering Path Optimizations

| Issue | Solution | Impact on Metric |
|-------|----------|------------------|
| Render-blocking JS | Add `defer` attribute | FCP, LCP |
| Render-blocking CSS | Inline critical CSS | FCP |
| Late resource discovery | Add `<link rel="preload">` | LCP |
| No resource hints | Add `<link rel="preconnect">` | TTFB |

**Implementation:**

| Resource | HTML Code |
|----------|-----------|
| Defer JS | `<script src="app.js" defer></script>` |
| Preload LCP image | `<link rel="preload" href="hero.webp" as="image">` |
| Preload font | `<link rel="preload" href="font.woff2" as="font" crossorigin>` |
| Preconnect CDN | `<link rel="preconnect" href="https://cdn.example.com">` |

---

### Image Optimizations

| Optimization | Benefit | Implementation |
|--------------|---------|----------------|
| Use WebP/AVIF | 30-50% smaller | Convert images |
| Lazy loading | Faster initial load | `loading="lazy"` |
| Responsive images | Right size per device | `srcset` attribute |
| Add dimensions | Prevents CLS | `width` + `height` |

**Image Format Comparison:**

| Format | Quality | Size vs JPEG | Browser Support |
|--------|---------|--------------|-----------------|
| JPEG | Good | Baseline | Universal |
| WebP | Good | -30% | 97%+ |
| AVIF | Excellent | -50% | 92%+ |

---

### Caching Strategy

| Resource Type | Cache-Control | TTL |
|---------------|---------------|-----|
| Versioned JS/CSS | `max-age=31536000, immutable` | 1 year |
| Images | `max-age=2592000` | 30 days |
| Fonts | `max-age=31536000` | 1 year |
| HTML | `no-cache` | Always validate |
| API responses | `max-age=0, stale-while-revalidate=60` | Instant + 1 min stale |

---

### JavaScript Optimizations

| Issue | Impact | Solution |
|-------|--------|----------|
| Large bundles | Slow parse | Code splitting |
| Unused code | Wasted bytes | Tree shaking |
| Long tasks | Poor INP | Break into < 50ms chunks |
| Synchronous execution | Blocks main thread | Use async/defer |

---

### API Optimizations

| Issue | Target | Solution |
|-------|--------|----------|
| Slow response | < 500ms TTFB | Server optimization, caching |
| Large payload | < 100KB | Pagination, field selection |
| Sequential requests | N/A | Use Promise.all for parallel |
| Auth overhead | < 100ms | Cache tokens, use refresh tokens |

---

### Quick Wins Checklist

| Action | Metric Impact | Effort |
|--------|---------------|--------|
| Add image dimensions | CLS | Low |
| Enable gzip/brotli | All | Low |
| Use CDN | LCP, TTFB | Low |
| Remove unused CSS/JS | LCP, TBT | Medium |
| Optimize fonts | CLS, FCP | Medium |
| Enable HTTP/2 | All | Low |
"""


class LighthouseSkill(Skill):
    """Lighthouse Performance Analysis skill using Lighthouse CLI.

    Provides automated performance audits with Core Web Vitals,
    opportunities, and diagnostics using Lighthouse CLI tools.

    Content is loaded from .md files in src/langchain_docker/skills/lighthouse/
    """

    def __init__(self):
        """Initialize Lighthouse skill."""
        self.id = "lighthouse"
        self.name = "Lighthouse Performance Analysis"
        self.description = (
            "Automated Lighthouse CLI performance audits with Core Web Vitals, "
            "opportunities, diagnostics, and optimization recommendations"
        )
        self.category = "performance"
        self.is_builtin = True
        self.version = "1.0.0"
        self._skill_dir = SKILLS_DIR / "lighthouse"
        self._custom_content = None
        self._custom_resources = None
        self._tool_configs = []
        self._resource_configs = []
        self._load_configs_from_frontmatter()

    def _read_md_file(self, filename: str) -> str:
        """Read content from a markdown file in the skill directory."""
        file_path = self._skill_dir / filename
        try:
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                # Strip YAML frontmatter if present
                if content.startswith("---"):
                    lines = content.split("\n")
                    for i, line in enumerate(lines[1:], 1):
                        if line.strip() == "---":
                            content = "\n".join(lines[i + 1 :]).strip()
                            break
                return content
            else:
                logger.warning(f"Skill file not found: {file_path}")
                return f"Error: File {filename} not found in skill directory"
        except Exception as e:
            logger.error(f"Error reading skill file {filename}: {e}")
            return f"Error reading {filename}: {str(e)}"

    def _load_configs_from_frontmatter(self) -> None:
        """Parse SKILL.md frontmatter to load tool and resource configs."""
        try:
            file_path = self._skill_dir / "SKILL.md"
            if not file_path.exists():
                return

            content = file_path.read_text(encoding="utf-8")
            if not content.startswith("---"):
                return

            # Extract frontmatter
            lines = content.split("\n")
            frontmatter_end = -1
            for i, line in enumerate(lines[1:], 1):
                if line.strip() == "---":
                    frontmatter_end = i
                    break

            if frontmatter_end == -1:
                return

            import yaml
            frontmatter_text = "\n".join(lines[1:frontmatter_end])
            frontmatter = yaml.safe_load(frontmatter_text)

            if frontmatter:
                self._tool_configs = frontmatter.get("tool_configs", [])
                self._resource_configs = frontmatter.get("resource_configs", [])
                logger.debug(
                    f"Loaded configs for {self.id}: "
                    f"{len(self._tool_configs)} tools, {len(self._resource_configs)} resources"
                )
        except Exception as e:
            logger.warning(f"Failed to load configs from frontmatter for {self.id}: {e}")

    def get_file_content(self) -> str:
        """Get the original file-based content for this skill."""
        return self._read_md_file("SKILL.md")

    def load_core(self) -> str:
        """Level 2: Load Lighthouse skill instructions.

        Returns:
            Complete skill context for Lighthouse performance analysis
        """
        # Static content: prefer Redis custom content, fallback to file
        if self._custom_content is not None:
            static_content = self._custom_content
        else:
            static_content = self._read_md_file("SKILL.md")

        # Add tool availability information
        tool_info = """## Lighthouse CLI Tools

These tools provide comprehensive performance metrics using Lighthouse CLI:

| Tool | Description | Use When |
|------|-------------|----------|
| `lighthouse_audit` | Full audit: score, Core Web Vitals, opportunities, diagnostics | Complete analysis |
| `lighthouse_cwv` | Core Web Vitals with pass/fail status and thresholds | Quick health check |
| `lighthouse_opportunities` | Prioritized opportunities grouped by category with savings | Finding what to fix |
| `lighthouse_diagnostics` | DOM size, main thread work, long tasks | Deep investigation |

### Tool Parameters

All tools support:
- `url` (required): The URL to analyze
- `device` (optional): "mobile" (default) or "desktop"
"""

        return f"""## Lighthouse Performance Analysis Skill Activated

{tool_info}

{static_content}
"""

    def load_details(self, resource: str) -> str:
        """Level 3: Load detailed resources."""
        if resource == "cwv_thresholds":
            return """## Core Web Vitals Thresholds (2024)

### Performance Score Ranges

| Score Range | Status | Meaning |
|-------------|--------|---------|
| 90-100 | Good | Excellent performance |
| 50-89 | Needs Improvement | Noticeable issues |
| 0-49 | Poor | Significant problems |

### Lighthouse Score Weights

| Metric | Weight | Description |
|--------|--------|-------------|
| TBT (Total Blocking Time) | 30% | Main thread blocking time |
| LCP (Largest Contentful Paint) | 25% | Largest content render time |
| CLS (Cumulative Layout Shift) | 25% | Visual stability score |
| FCP (First Contentful Paint) | 10% | First content render time |
| Speed Index | 10% | Visual completeness speed |

### Metric Thresholds

| Metric | Good | Needs Improvement | Poor |
|--------|------|-------------------|------|
| **LCP** | <= 2.5s | 2.5s - 4.0s | > 4.0s |
| **INP** | <= 200ms | 200ms - 500ms | > 500ms |
| **CLS** | <= 0.1 | 0.1 - 0.25 | > 0.25 |
| **FCP** | <= 1.8s | 1.8s - 3.0s | > 3.0s |
| **TBT** | <= 200ms | 200ms - 600ms | > 600ms |
| **SI** | <= 3.4s | 3.4s - 5.8s | > 5.8s |
| **TTFB** | <= 0.8s | 0.8s - 1.8s | > 1.8s |
"""
        elif resource == "lighthouse_scoring":
            return """## Lighthouse Scoring System

### How Performance Score is Calculated

Lighthouse uses a weighted average of metric scores:

| Metric | Weight | Impact |
|--------|--------|--------|
| Total Blocking Time (TBT) | 30% | Highest impact on score |
| Largest Contentful Paint (LCP) | 25% | Major factor |
| Cumulative Layout Shift (CLS) | 25% | Major factor |
| First Contentful Paint (FCP) | 10% | Minor factor |
| Speed Index | 10% | Minor factor |

### Score Calculation

1. Each metric is converted to a 0-100 score using log-normal distributions
2. Scores are weighted according to the table above
3. Final score is the weighted average

### Improving Your Score

| Priority | Focus On | Why |
|----------|----------|-----|
| 1 | TBT | 30% weight, often the biggest issue |
| 2 | LCP + CLS | Combined 50% of score |
| 3 | FCP + SI | Polish for perfect score |
"""
        elif resource == "metric_explanations":
            return """## Lighthouse Metrics Explained

### LCP (Largest Contentful Paint)

| Aspect | Description |
|--------|-------------|
| What it measures | Time until largest content element is visible |
| Why it matters | Users perceive this as "page loaded" |
| Target | <= 2.5 seconds |
| Weight in score | 25% |

### TBT (Total Blocking Time)

| Aspect | Description |
|--------|-------------|
| What it measures | Sum of blocking time for long tasks (>50ms) |
| Why it matters | Indicates main thread responsiveness |
| Target | <= 200 milliseconds |
| Weight in score | 30% |

### CLS (Cumulative Layout Shift)

| Aspect | Description |
|--------|-------------|
| What it measures | Visual stability during page load |
| Why it matters | Prevents accidental clicks from shifting content |
| Target | <= 0.1 |
| Weight in score | 25% |

### FCP (First Contentful Paint)

| Aspect | Description |
|--------|-------------|
| What it measures | Time until first content appears |
| Why it matters | First sign that page is loading |
| Target | <= 1.8 seconds |
| Weight in score | 10% |

### Speed Index

| Aspect | Description |
|--------|-------------|
| What it measures | How quickly content is visually displayed |
| Why it matters | Overall perception of load speed |
| Target | <= 3.4 seconds |
| Weight in score | 10% |
"""
        else:
            return f"Resource '{resource}' not found. Available: cwv_thresholds, lighthouse_scoring, metric_explanations"


class CustomSkill(Skill):
    """User-created skill following SKILL.md format.

    Supports the full progressive disclosure pattern with:
    - YAML frontmatter for metadata
    - Markdown body for core instructions
    - Additional resource files
    - Bundled executable scripts
    """

    def __init__(
        self,
        skill_id: str,
        name: str,
        description: str,
        category: str = "general",
        version: str = "1.0.0",
        author: Optional[str] = None,
        core_content: str = "",
        resources: Optional[list[SkillResource]] = None,
        scripts: Optional[list[SkillScript]] = None,
    ):
        """Initialize a custom skill.

        Args:
            skill_id: Unique skill identifier
            name: Human-readable skill name
            description: Brief description of what the skill does
            category: Skill category
            version: Skill version
            author: Skill author
            core_content: Main skill instructions (Level 2)
            resources: Additional resource files (Level 3)
            scripts: Executable scripts
        """
        self.id = skill_id
        self.name = name
        self.description = description
        self.category = category
        self.version = version
        self.author = author
        self._core_content = core_content
        self._resources = resources or []
        self._scripts = scripts or []
        self.is_builtin = False
        self.created_at = datetime.utcnow().isoformat()
        self.updated_at = self.created_at

    def load_core(self) -> str:
        """Level 2: Load core skill content.

        Returns:
            Main skill instructions in markdown format
        """
        # Build the skill context
        content = f"""## {self.name} Skill Activated

{self._core_content}
"""
        # Add references to available resources
        if self._resources:
            content += "\n### Additional Resources\n"
            content += "The following resources are available for more details:\n"
            for resource in self._resources:
                content += f"- `{resource.name}`: {resource.description}\n"

        # Add references to available scripts
        if self._scripts:
            content += "\n### Available Scripts\n"
            content += "The following scripts can be executed:\n"
            for script in self._scripts:
                content += f"- `{script.name}` ({script.language}): {script.description}\n"

        return content

    def load_details(self, resource: str) -> str:
        """Level 3: Load a specific resource.

        Args:
            resource: Resource name to load

        Returns:
            Resource content or error message
        """
        # Check if it's a resource file
        for res in self._resources:
            if res.name == resource:
                return f"## {res.name}\n\n{res.content}"

        # Check if it's a script
        for script in self._scripts:
            if script.name == resource:
                return f"## {script.name} ({script.language})\n\n```{script.language}\n{script.content}\n```"

        available = [r.name for r in self._resources] + [s.name for s in self._scripts]
        return f"Unknown resource: {resource}. Available: {', '.join(available)}"

    def execute_script(self, script_name: str, args: dict[str, Any] = None) -> str:
        """Execute a bundled script.

        Args:
            script_name: Name of the script to execute
            args: Arguments to pass to the script

        Returns:
            Script output or error message
        """
        script = None
        for s in self._scripts:
            if s.name == script_name:
                script = s
                break

        if not script:
            available = [s.name for s in self._scripts]
            return f"Unknown script: {script_name}. Available: {', '.join(available)}"

        # For now, return the script content
        # In production, this would execute in a sandbox
        return f"Script execution not yet implemented. Script content:\n{script.content}"

    def update(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        version: Optional[str] = None,
        author: Optional[str] = None,
        core_content: Optional[str] = None,
        resources: Optional[list[SkillResource]] = None,
        scripts: Optional[list[SkillScript]] = None,
    ) -> None:
        """Update skill properties.

        Args:
            name: New name (optional)
            description: New description (optional)
            category: New category (optional)
            version: New version (optional)
            author: New author (optional)
            core_content: New core content (optional)
            resources: New resources (optional)
            scripts: New scripts (optional)
        """
        if name is not None:
            self.name = name
        if description is not None:
            self.description = description
        if category is not None:
            self.category = category
        if version is not None:
            self.version = version
        if author is not None:
            self.author = author
        if core_content is not None:
            self._core_content = core_content
        if resources is not None:
            self._resources = resources
        if scripts is not None:
            self._scripts = scripts
        self.updated_at = datetime.utcnow().isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert skill to dictionary representation.

        Returns:
            Dictionary with all skill data
        """
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "version": self.version,
            "author": self.author,
            "is_builtin": self.is_builtin,
            "core_content": self._core_content,
            "resources": [
                {"name": r.name, "description": r.description, "content": r.content}
                for r in self._resources
            ],
            "scripts": [
                {
                    "name": s.name,
                    "description": s.description,
                    "language": s.language,
                    "content": s.content,
                }
                for s in self._scripts
            ],
            "tool_configs": getattr(self, "_tool_configs", []),
            "resource_configs": getattr(self, "_resource_configs", []),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_skill_md(cls, content: str) -> "CustomSkill":
        """Parse a SKILL.md file content into a CustomSkill.

        Args:
            content: Full SKILL.md content with YAML frontmatter

        Returns:
            CustomSkill instance
        """
        # Parse YAML frontmatter
        frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)

        if not frontmatter_match:
            raise ValueError("Invalid SKILL.md format: missing YAML frontmatter")

        import yaml

        frontmatter = yaml.safe_load(frontmatter_match.group(1))
        body = frontmatter_match.group(2).strip()

        # Generate ID from name if not provided
        skill_id = frontmatter.get("id") or re.sub(
            r"[^a-z0-9]+", "_", frontmatter["name"].lower()
        ).strip("_")

        return cls(
            skill_id=skill_id,
            name=frontmatter["name"],
            description=frontmatter["description"],
            category=frontmatter.get("category", "general"),
            version=frontmatter.get("version", "1.0.0"),
            author=frontmatter.get("author"),
            core_content=body,
        )

    def to_skill_md(self) -> str:
        """Export skill as SKILL.md format.

        Returns:
            SKILL.md content with YAML frontmatter
        """
        import yaml

        frontmatter = {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "version": self.version,
        }
        if self.author:
            frontmatter["author"] = self.author

        return f"---\n{yaml.dump(frontmatter, default_flow_style=False)}---\n\n{self._core_content}"


class SkillRegistry:
    """Registry of available skills for progressive disclosure.

    Manages skill metadata (Level 1) and provides access to
    on-demand skill loading (Levels 2 and 3).

    Supports both built-in skills (SQLSkill, etc.) and custom
    user-created skills following the SKILL.md format.

    When redis_url is provided, custom skills are persisted with
    immutable version history and usage metrics tracking.
    """

    def __init__(self, redis_url: Optional[str] = None):
        """Initialize skill registry with built-in skills.

        Args:
            redis_url: Optional Redis URL for persistent storage and versioning.
                       If not provided, skills are stored in-memory only.
        """
        self._skills: dict[str, Skill] = {}
        self._custom_skills: dict[str, CustomSkill] = {}
        self._redis_url = redis_url
        self._redis_store: Optional["RedisSkillStore"] = None

        # Initialize Redis store if URL provided
        if redis_url:
            try:
                from langchain_docker.api.services.redis_skill_store import RedisSkillStore
                self._redis_store = RedisSkillStore(redis_url)
                logger.info("SkillRegistry initialized with Redis versioning support")
            except Exception as e:
                logger.warning(f"Failed to initialize Redis skill store: {e}")
                self._redis_store = None

        self._register_builtin_skills()

        # Load custom skills from Redis if available
        if self._redis_store:
            self._load_custom_from_redis()

    def _register_builtin_skills(self) -> None:
        """Register all built-in skills, loading custom content from Redis if available."""
        builtin_skills = [
            SQLSkill(),
            XLSXSkill(),
            JiraSkill(),
            KnowledgeBaseSkill(),
            KBIngestionSkill(),
            WebPerformanceSkill(),
            LighthouseSkill(),
        ]

        for skill in builtin_skills:
            skill.is_builtin = True

            # Check Redis for custom content
            if self._redis_store:
                try:
                    versioned = self._redis_store.get_skill(skill.id)
                    if versioned and versioned.active_version_data:
                        active = versioned.active_version_data
                        skill.set_custom_content(
                            content=active.core_content,
                            resources=[r for r in active.resources] if active.resources else None,
                        )
                        logger.info(
                            f"Loaded custom content for built-in skill: {skill.id} "
                            f"(v{active.version_number})"
                        )
                except Exception as e:
                    logger.warning(f"Failed to load custom content for {skill.id}: {e}")

            self.register(skill)

    def _load_custom_from_redis(self) -> None:
        """Load custom skills from Redis on startup."""
        if not self._redis_store:
            return

        try:
            skill_ids = self._redis_store.list_custom_skill_ids()
            for skill_id in skill_ids:
                versioned_skill = self._redis_store.get_skill(skill_id)
                if versioned_skill and versioned_skill.active_version_data:
                    active = versioned_skill.active_version_data
                    # Create in-memory CustomSkill from active version
                    skill = CustomSkill(
                        skill_id=skill_id,
                        name=active.name,
                        description=active.description,
                        category=active.category,
                        version=active.semantic_version,
                        author=active.author,
                        core_content=active.core_content,
                        resources=[
                            SkillResource(r.name, r.description, r.content)
                            for r in active.resources
                        ],
                        scripts=[
                            SkillScript(s.name, s.description, s.language, s.content)
                            for s in active.scripts
                        ],
                    )
                    skill.created_at = versioned_skill.created_at.isoformat()
                    skill.updated_at = versioned_skill.updated_at.isoformat()
                    self._skills[skill_id] = skill
                    self._custom_skills[skill_id] = skill
                    logger.debug(f"Loaded custom skill from Redis: {skill_id}")

            logger.info(f"Loaded {len(skill_ids)} custom skills from Redis")
        except Exception as e:
            logger.error(f"Failed to load custom skills from Redis: {e}")

    def register(self, skill: Skill) -> None:
        """Register a skill.

        Args:
            skill: Skill instance to register
        """
        self._skills[skill.id] = skill
        logger.info(f"Registered skill: {skill.id} ({skill.name})")

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """Get a skill by ID.

        Args:
            skill_id: Skill identifier

        Returns:
            Skill if found, None otherwise
        """
        return self._skills.get(skill_id)

    def list_skills(self) -> list[dict[str, Any]]:
        """List all available skills (Level 1 metadata).

        Returns:
            List of skill metadata dictionaries
        """
        return [
            {
                "id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "category": skill.category,
            }
            for skill in self._skills.values()
        ]

    def get_all_skills(self) -> list["Skill"]:
        """Get all registered Skill objects.

        This method returns the actual Skill instances, not dictionaries.
        Useful for migration or when direct access to Skill methods is needed.

        Returns:
            List of Skill objects
        """
        return list(self._skills.values())

    def get_skill_summary(self) -> str:
        """Get a summary of available skills for agent prompts.

        Returns:
            Formatted string listing available skills
        """
        lines = ["Available skills (use load_sql_skill to activate):"]
        for skill in self._skills.values():
            lines.append(f"- {skill.id}: {skill.description}")
        return "\n".join(lines)

    def load_skill(self, skill_id: str, session_id: Optional[str] = None) -> str:
        """Load a skill's core content (Level 2).

        Args:
            skill_id: Skill identifier
            session_id: Optional session ID for metrics tracking

        Returns:
            Skill core content or error message
        """
        skill = self.get_skill(skill_id)
        if not skill:
            available = ", ".join(self._skills.keys())
            return f"Unknown skill: {skill_id}. Available skills: {available}"

        # Track metrics in Redis if available
        if self._redis_store:
            try:
                # Get active version number for custom skills
                version_number = None
                if skill_id in self._custom_skills:
                    meta = self._redis_store.get_skill_meta(skill_id)
                    if meta:
                        version_number = meta.get("active_version")
                self._redis_store.record_skill_load(
                    skill_id,
                    session_id=session_id,
                    version_number=version_number,
                )
            except Exception as e:
                logger.warning(f"Failed to record skill load metrics: {e}")

        # Add custom span for skill loading visibility in Phoenix
        tracer = get_tracer()
        if tracer:
            with tracer.start_as_current_span("skill.load_core") as span:
                span.set_attribute("skill.id", skill_id)
                span.set_attribute("skill.name", skill.name)
                span.set_attribute("skill.category", skill.category)
                content = skill.load_core()
                span.set_attribute("content_length", len(content))
                return content

        return skill.load_core()

    def load_skill_details(self, skill_id: str, resource: str) -> str:
        """Load a skill's detailed resources (Level 3).

        Args:
            skill_id: Skill identifier
            resource: Resource identifier

        Returns:
            Detailed resource content or error message
        """
        skill = self.get_skill(skill_id)
        if not skill:
            available = ", ".join(self._skills.keys())
            return f"Unknown skill: {skill_id}. Available skills: {available}"

        # Add custom span for skill details loading visibility in Phoenix
        tracer = get_tracer()
        if tracer:
            with tracer.start_as_current_span("skill.load_details") as span:
                span.set_attribute("skill.id", skill_id)
                span.set_attribute("skill.name", skill.name)
                span.set_attribute("resource", resource)
                content = skill.load_details(resource)
                span.set_attribute("content_length", len(content))
                return content

        return skill.load_details(resource)

    # Custom Skill CRUD Operations

    def create_custom_skill(
        self,
        name: str,
        description: str,
        core_content: str,
        skill_id: Optional[str] = None,
        category: str = "general",
        version: str = "1.0.0",
        author: Optional[str] = None,
        resources: Optional[list[dict]] = None,
        scripts: Optional[list[dict]] = None,
    ) -> CustomSkill:
        """Create a new custom skill.

        Args:
            name: Skill name
            description: Skill description
            core_content: Main skill instructions
            skill_id: Custom ID (auto-generated if not provided)
            category: Skill category
            version: Skill version
            author: Skill author
            resources: Additional resource files
            scripts: Executable scripts

        Returns:
            Created CustomSkill instance

        Raises:
            ValueError: If skill_id already exists
        """
        # Generate ID from name if not provided
        if not skill_id:
            skill_id = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")

        # Check for duplicates
        if skill_id in self._skills:
            raise ValueError(f"Skill with ID '{skill_id}' already exists")

        # Convert resource/script dicts to objects
        skill_resources = []
        if resources:
            for r in resources:
                skill_resources.append(
                    SkillResource(
                        name=r["name"],
                        description=r.get("description", ""),
                        content=r.get("content", ""),
                    )
                )

        skill_scripts = []
        if scripts:
            for s in scripts:
                skill_scripts.append(
                    SkillScript(
                        name=s["name"],
                        description=s.get("description", ""),
                        language=s.get("language", "python"),
                        content=s.get("content", ""),
                    )
                )

        # Create the skill
        skill = CustomSkill(
            skill_id=skill_id,
            name=name,
            description=description,
            category=category,
            version=version,
            author=author,
            core_content=core_content,
            resources=skill_resources,
            scripts=skill_scripts,
        )

        # Register it
        self._skills[skill_id] = skill
        self._custom_skills[skill_id] = skill

        # Save to Redis with versioning if available
        if self._redis_store:
            try:
                from langchain_docker.api.services.versioned_skill import (
                    SkillVersion,
                    SkillVersionResource,
                    SkillVersionScript,
                )

                skill_version = SkillVersion(
                    version_number=1,
                    semantic_version=version,
                    name=name,
                    description=description,
                    category=category,
                    author=author,
                    core_content=core_content,
                    resources=[
                        SkillVersionResource(r.name, r.description, r.content)
                        for r in skill_resources
                    ],
                    scripts=[
                        SkillVersionScript(s.name, s.description, s.language, s.content)
                        for s in skill_scripts
                    ],
                    change_summary="Initial version",
                )
                self._redis_store.save_new_version(
                    skill_id=skill_id,
                    version=skill_version,
                    set_active=True,
                    is_builtin=False,
                )
                logger.debug(f"Saved skill to Redis: {skill_id} (version 1)")
            except Exception as e:
                logger.warning(f"Failed to save skill to Redis: {e}")

        logger.info(f"Created custom skill: {skill_id} ({name})")

        return skill

    def update_custom_skill(
        self,
        skill_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        core_content: Optional[str] = None,
        category: Optional[str] = None,
        version: Optional[str] = None,
        author: Optional[str] = None,
        resources: Optional[list[dict]] = None,
        scripts: Optional[list[dict]] = None,
        change_summary: Optional[str] = None,
    ) -> CustomSkill:
        """Update an existing custom skill.

        When Redis is configured, this creates a new immutable version
        rather than mutating the existing skill in place.

        Args:
            skill_id: Skill ID to update
            name: New name (optional)
            description: New description (optional)
            core_content: New core content (optional)
            category: New category (optional)
            version: New version (optional)
            author: New author (optional)
            resources: New resources (optional)
            scripts: New scripts (optional)
            change_summary: Description of what changed (for version history)

        Returns:
            Updated CustomSkill instance

        Raises:
            ValueError: If skill not found or is a built-in skill
        """
        skill = self._custom_skills.get(skill_id)
        if not skill:
            if skill_id in self._skills:
                raise ValueError(f"Use update_builtin_skill() for built-in skills: {skill_id}")
            raise ValueError(f"Skill not found: {skill_id}")

        # Convert resource/script dicts to objects if provided
        skill_resources = None
        if resources is not None:
            skill_resources = []
            for r in resources:
                skill_resources.append(
                    SkillResource(
                        name=r["name"],
                        description=r.get("description", ""),
                        content=r.get("content", ""),
                    )
                )

        skill_scripts = None
        if scripts is not None:
            skill_scripts = []
            for s in scripts:
                skill_scripts.append(
                    SkillScript(
                        name=s["name"],
                        description=s.get("description", ""),
                        language=s.get("language", "python"),
                        content=s.get("content", ""),
                    )
                )

        # Update the in-memory skill
        skill.update(
            name=name,
            description=description,
            category=category,
            version=version,
            author=author,
            core_content=core_content,
            resources=skill_resources,
            scripts=skill_scripts,
        )

        # Save new version to Redis if available
        if self._redis_store:
            try:
                from langchain_docker.api.services.versioned_skill import (
                    SkillVersion,
                    SkillVersionResource,
                    SkillVersionScript,
                )

                # Get the next version number
                current_count = self._redis_store.get_version_count(skill_id)
                next_version_number = current_count + 1

                # Get the updated values
                final_resources = skill_resources if skill_resources is not None else skill._resources
                final_scripts = skill_scripts if skill_scripts is not None else skill._scripts

                skill_version = SkillVersion(
                    version_number=next_version_number,
                    semantic_version=skill.version,
                    name=skill.name,
                    description=skill.description,
                    category=skill.category,
                    author=skill.author,
                    core_content=skill._core_content,
                    resources=[
                        SkillVersionResource(r.name, r.description, r.content)
                        for r in final_resources
                    ],
                    scripts=[
                        SkillVersionScript(s.name, s.description, s.language, s.content)
                        for s in final_scripts
                    ],
                    change_summary=change_summary,
                )
                self._redis_store.save_new_version(
                    skill_id=skill_id,
                    version=skill_version,
                    set_active=True,
                    is_builtin=False,
                )
                logger.debug(f"Saved new version to Redis: {skill_id} (version {next_version_number})")
            except Exception as e:
                logger.warning(f"Failed to save skill version to Redis: {e}")

        logger.info(f"Updated custom skill: {skill_id}")
        return skill

    def update_builtin_skill(
        self,
        skill_id: str,
        core_content: Optional[str] = None,
        resources: Optional[list[dict]] = None,
        change_summary: Optional[str] = None,
    ) -> Skill:
        """Update a built-in skill's content.

        Saves to Redis and updates in-memory skill.
        Only core_content and resources can be updated (not name/description/category).
        Requires Redis for persistence.

        Args:
            skill_id: Skill ID to update
            core_content: New core content (optional)
            resources: New resources (optional)
            change_summary: Description of what changed (for version history)

        Returns:
            Updated Skill instance

        Raises:
            ValueError: If skill not found, not a built-in skill, or Redis not configured
        """
        skill = self.get_skill(skill_id)
        if not skill:
            raise ValueError(f"Skill not found: {skill_id}")

        if not getattr(skill, "is_builtin", False):
            raise ValueError(f"Use update_custom_skill() for custom skills: {skill_id}")

        if not self._redis_store:
            raise ValueError("Redis is required for editing built-in skills")

        # Determine the content to save
        if core_content is None:
            # Use existing custom content or get from file
            if skill._custom_content is not None:
                core_content = skill._custom_content
            else:
                core_content = skill.get_file_content()

        # Convert resources if provided
        skill_resources = []
        if resources is not None:
            for r in resources:
                skill_resources.append(
                    SkillResource(
                        name=r["name"],
                        description=r.get("description", ""),
                        content=r.get("content", ""),
                    )
                )

        try:
            from langchain_docker.api.services.versioned_skill import (
                SkillVersion,
                SkillVersionResource,
            )

            # Get the next version number
            current_count = self._redis_store.get_version_count(skill_id)
            next_version_number = current_count + 1

            # Calculate semantic version
            semantic_version = f"1.{next_version_number - 1}.0"

            skill_version = SkillVersion(
                version_number=next_version_number,
                semantic_version=semantic_version,
                name=skill.name,
                description=skill.description,
                category=skill.category,
                author="user",
                core_content=core_content,
                resources=[
                    SkillVersionResource(r.name, r.description, r.content)
                    for r in skill_resources
                ],
                scripts=[],
                change_summary=change_summary or f"Updated built-in skill content",
            )

            self._redis_store.save_new_version(
                skill_id=skill_id,
                version=skill_version,
                set_active=True,
                is_builtin=True,
            )

            # Update in-memory skill
            skill.set_custom_content(core_content, skill_resources)

            logger.info(f"Updated built-in skill: {skill_id} (v{next_version_number})")
            return skill

        except Exception as e:
            logger.error(f"Failed to update built-in skill: {e}")
            raise ValueError(f"Failed to update skill: {e}")

    def reset_builtin_skill(self, skill_id: str) -> Skill:
        """Reset a built-in skill to its original file-based content.

        Clears all Redis versions and custom content.

        Args:
            skill_id: Skill ID to reset

        Returns:
            Reset Skill instance

        Raises:
            ValueError: If skill not found or not a built-in skill
        """
        skill = self.get_skill(skill_id)
        if not skill:
            raise ValueError(f"Skill not found: {skill_id}")

        if not getattr(skill, "is_builtin", False):
            raise ValueError(f"Only built-in skills can be reset: {skill_id}")

        # Clear Redis versions if available
        if self._redis_store:
            try:
                self._redis_store.delete_skill(skill_id)
                logger.debug(f"Cleared Redis versions for built-in skill: {skill_id}")
            except Exception as e:
                logger.warning(f"Failed to clear Redis versions: {e}")

        # Clear in-memory custom content
        skill.clear_custom_content()

        logger.info(f"Reset built-in skill to file defaults: {skill_id}")
        return skill

    def delete_custom_skill(self, skill_id: str) -> bool:
        """Delete a custom skill.

        Args:
            skill_id: Skill ID to delete

        Returns:
            True if deleted

        Raises:
            ValueError: If skill not found or is a built-in skill
        """
        if skill_id not in self._custom_skills:
            if skill_id in self._skills:
                raise ValueError(f"Cannot delete built-in skill: {skill_id}")
            raise ValueError(f"Skill not found: {skill_id}")

        del self._skills[skill_id]
        del self._custom_skills[skill_id]

        # Delete from Redis if available
        if self._redis_store:
            try:
                self._redis_store.delete_skill(skill_id)
                logger.debug(f"Deleted skill from Redis: {skill_id}")
            except Exception as e:
                logger.warning(f"Failed to delete skill from Redis: {e}")

        logger.info(f"Deleted custom skill: {skill_id}")
        return True

    def get_skill_full(self, skill_id: str) -> Optional[dict[str, Any]]:
        """Get full skill information including content.

        Args:
            skill_id: Skill identifier

        Returns:
            Full skill data or None if not found
        """
        skill = self.get_skill(skill_id)
        if not skill:
            return None

        if isinstance(skill, CustomSkill):
            return skill.to_dict()

        # For built-in skills, return editable content
        # If custom content exists, return that; otherwise return file content
        if skill._custom_content is not None:
            editable_content = skill._custom_content
        else:
            editable_content = skill.get_file_content()

        # Get version info if available
        version = "1.0.0"
        if self._redis_store:
            meta = self._redis_store.get_skill_meta(skill_id)
            if meta:
                active_version = meta.get("active_version", 1)
                version = f"1.{active_version - 1}.0"

        return {
            "id": skill.id,
            "name": skill.name,
            "description": skill.description,
            "category": skill.category,
            "is_builtin": True,
            "version": version,
            "core_content": editable_content,  # Editable static content
            "resources": [],
            "scripts": [],
            "tool_configs": skill.get_tool_configs(),
            "resource_configs": skill.get_resource_configs(),
            "has_custom_content": skill.has_custom_content(),
        }

    def list_skills_full(self) -> list[dict[str, Any]]:
        """List all skills with full metadata.

        Returns:
            List of skill dictionaries with metadata
        """
        skills = []
        for skill in self._skills.values():
            is_builtin = not isinstance(skill, CustomSkill)
            skill_data = {
                "id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "category": skill.category,
                "is_builtin": is_builtin,
            }

            if isinstance(skill, CustomSkill):
                skill_data["version"] = skill.version
                skill_data["author"] = skill.author
                skill_data["created_at"] = skill.created_at
                skill_data["updated_at"] = skill.updated_at

            skills.append(skill_data)

        return skills

    def import_skill_md(self, content: str) -> CustomSkill:
        """Import a skill from SKILL.md format.

        Args:
            content: Full SKILL.md content with YAML frontmatter

        Returns:
            Created CustomSkill instance
        """
        skill = CustomSkill.from_skill_md(content)

        # Check for duplicates
        if skill.id in self._skills:
            raise ValueError(f"Skill with ID '{skill.id}' already exists")

        self._skills[skill.id] = skill
        self._custom_skills[skill.id] = skill
        logger.info(f"Imported skill from SKILL.md: {skill.id}")

        return skill

    def export_skill_md(self, skill_id: str) -> str:
        """Export a skill as SKILL.md format.

        Args:
            skill_id: Skill ID to export

        Returns:
            SKILL.md content

        Raises:
            ValueError: If skill not found or is a built-in skill
        """
        skill = self._custom_skills.get(skill_id)
        if not skill:
            if skill_id in self._skills:
                raise ValueError(f"Cannot export built-in skill: {skill_id}")
            raise ValueError(f"Skill not found: {skill_id}")

        return skill.to_skill_md()

    # ========================================================================
    # Versioning Methods (require Redis)
    # ========================================================================

    def list_versions(
        self,
        skill_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Optional[list], Optional[int], Optional[int]]:
        """List versions of a skill.

        Args:
            skill_id: Skill identifier
            limit: Maximum versions to return
            offset: Offset for pagination

        Returns:
            Tuple of (versions list, total count, active version number)
            Returns (None, None, None) if skill not found or Redis not configured
        """
        if not self._redis_store:
            # Return minimal info for non-Redis mode
            skill = self._custom_skills.get(skill_id)
            if not skill:
                return None, None, None

            # Create a single "version" representing current state
            from langchain_docker.api.services.versioned_skill import (
                SkillVersion,
                SkillVersionResource,
                SkillVersionScript,
            )

            version = SkillVersion(
                version_number=1,
                semantic_version=skill.version,
                name=skill.name,
                description=skill.description,
                category=skill.category,
                author=skill.author,
                core_content=skill._core_content,
                resources=[
                    SkillVersionResource(r.name, r.description, r.content)
                    for r in skill._resources
                ],
                scripts=[
                    SkillVersionScript(s.name, s.description, s.language, s.content)
                    for s in skill._scripts
                ],
            )
            return [version], 1, 1

        try:
            versions = self._redis_store.list_versions(
                skill_id, limit=limit, offset=offset, reverse=True
            )
            total = self._redis_store.get_version_count(skill_id)
            meta = self._redis_store.get_skill_meta(skill_id)
            active_version = meta.get("active_version", 1) if meta else 1
            return versions, total, active_version
        except Exception as e:
            logger.warning(f"Failed to list versions: {e}")
            return None, None, None

    def get_version(
        self,
        skill_id: str,
        version_number: int,
    ) -> tuple[Optional[Any], Optional[int]]:
        """Get a specific version of a skill.

        Args:
            skill_id: Skill identifier
            version_number: Version number to retrieve

        Returns:
            Tuple of (SkillVersion, active version number)
            Returns (None, None) if not found
        """
        if not self._redis_store:
            # In non-Redis mode, only version 1 exists
            if version_number != 1:
                return None, None

            skill = self._custom_skills.get(skill_id)
            if not skill:
                return None, None

            from langchain_docker.api.services.versioned_skill import (
                SkillVersion,
                SkillVersionResource,
                SkillVersionScript,
            )

            version = SkillVersion(
                version_number=1,
                semantic_version=skill.version,
                name=skill.name,
                description=skill.description,
                category=skill.category,
                author=skill.author,
                core_content=skill._core_content,
                resources=[
                    SkillVersionResource(r.name, r.description, r.content)
                    for r in skill._resources
                ],
                scripts=[
                    SkillVersionScript(s.name, s.description, s.language, s.content)
                    for s in skill._scripts
                ],
            )
            return version, 1

        try:
            version = self._redis_store.get_version(skill_id, version_number)
            meta = self._redis_store.get_skill_meta(skill_id)
            active_version = meta.get("active_version", 1) if meta else 1
            return version, active_version
        except Exception as e:
            logger.warning(f"Failed to get version: {e}")
            return None, None

    def set_active_version(self, skill_id: str, version_number: int) -> bool:
        """Set the active version for a skill.

        This allows rolling back to a previous version.

        Args:
            skill_id: Skill identifier
            version_number: Version number to activate

        Returns:
            True if successful, False otherwise
        """
        if not self._redis_store:
            logger.warning("Versioning requires Redis configuration")
            return False

        try:
            success = self._redis_store.set_active_version(skill_id, version_number)
            if success:
                # Update in-memory skill to match activated version
                version = self._redis_store.get_version(skill_id, version_number)
                if version and skill_id in self._custom_skills:
                    skill = self._custom_skills[skill_id]
                    skill.update(
                        name=version.name,
                        description=version.description,
                        category=version.category,
                        version=version.semantic_version,
                        author=version.author,
                        core_content=version.core_content,
                        resources=[
                            SkillResource(r.name, r.description, r.content)
                            for r in version.resources
                        ],
                        scripts=[
                            SkillScript(s.name, s.description, s.language, s.content)
                            for s in version.scripts
                        ],
                    )
                logger.info(f"Activated version {version_number} for skill: {skill_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to set active version: {e}")
            return False

    def get_metrics(self, skill_id: str) -> Optional[Any]:
        """Get usage metrics for a skill.

        Args:
            skill_id: Skill identifier

        Returns:
            SkillUsageMetrics or None if not available
        """
        if not self._redis_store:
            return None

        try:
            return self._redis_store.get_metrics(skill_id)
        except Exception as e:
            logger.warning(f"Failed to get metrics: {e}")
            return None

    @property
    def has_redis(self) -> bool:
        """Check if Redis versioning is available."""
        return self._redis_store is not None
