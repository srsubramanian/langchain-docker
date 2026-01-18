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
    """

    id: str
    name: str
    description: str
    category: str

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
        self._skill_dir = SKILLS_DIR / "xlsx"

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

    def load_core(self) -> str:
        """Level 2: Load XLSX skill instructions from SKILL.md.

        Returns:
            Complete skill context for spreadsheet operations
        """
        content = self._read_md_file("SKILL.md")

        # Strip YAML frontmatter if present
        if content.startswith("---"):
            # Find the second '---' delimiter
            lines = content.split("\n")
            in_frontmatter = True
            body_start = 0
            for i, line in enumerate(lines[1:], 1):
                if line.strip() == "---":
                    body_start = i + 1
                    break

            if body_start > 0:
                content = "\n".join(lines[body_start:]).strip()

        return f"## XLSX Skill Activated\n\n{content}"

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
        self.db_url = db_url or get_database_url()
        self.read_only = read_only if read_only is not None else is_sql_read_only()
        self._db: Optional[SQLDatabase] = None
        self._skill_dir = SKILLS_DIR / "sql"

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

    def load_core(self) -> str:
        """Level 2: Load database schema and SQL guidelines.

        Combines static content from SKILL.md with dynamic database information.

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

        # Load static guidelines from SKILL.md
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
        }

        if resource in resource_map:
            return self._read_md_file(resource_map[resource])
        else:
            available = "'samples', " + ", ".join(f"'{r}'" for r in resource_map.keys())
            return f"Unknown resource: {resource}. Available: {available}"

    def execute_query(self, query: str) -> str:
        """Execute a SQL query with read-only enforcement.

        Args:
            query: SQL query string

        Returns:
            Query results or error message
        """
        db = self._get_db()

        # Enforce read-only mode
        if self.read_only:
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
        logger.info("[Jira Debug] JiraSkill.__init__() called")
        self.id = "jira"
        self.name = "Jira Query Expert"
        self.description = "Query Jira issues, sprints, projects, and users (read-only)"
        self.category = "project_management"
        self.is_builtin = True

        # Load config values and log them
        self.url = url or get_jira_url()
        self.bearer_token = bearer_token or get_jira_bearer_token()
        self.api_version = api_version or get_jira_api_version()

        logger.info(f"[Jira Debug] JiraSkill initialized:")
        logger.info(f"[Jira Debug]   URL: {self.url}")
        logger.info(f"[Jira Debug]   Bearer token configured: {bool(self.bearer_token)}")
        if self.bearer_token:
            token_preview = self.bearer_token[:20] + "..." if len(self.bearer_token) > 20 else "[short token]"
            logger.info(f"[Jira Debug]   Token preview: {token_preview}")
        logger.info(f"[Jira Debug]   API version: {self.api_version}")
        logger.info(f"[Jira Debug]   is_jira_configured(): {is_jira_configured()}")

        self._skill_dir = SKILLS_DIR / "jira"
        self._session = None

    def _get_session(self):
        """Get or create requests session with Bearer token authentication.

        Returns:
            Configured requests session or None if not configured
        """
        logger.info(f"[Jira Debug] _get_session() called")
        logger.info(f"[Jira Debug] URL configured: {bool(self.url)}")
        logger.info(f"[Jira Debug] URL value: {self.url}")
        logger.info(f"[Jira Debug] Bearer token configured: {bool(self.bearer_token)}")
        if self.bearer_token:
            token_preview = self.bearer_token[:20] + "..." if len(self.bearer_token) > 20 else self.bearer_token
            logger.info(f"[Jira Debug] Token prefix: {token_preview}")

        if not self.url or not self.bearer_token:
            logger.warning("[Jira Debug] Missing URL or bearer token - returning None")
            return None

        if self._session is None:
            import requests

            logger.info("[Jira Debug] Creating new requests session")
            self._session = requests.Session()
            self._session.headers.update({
                "Authorization": f"Bearer {self.bearer_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            })
            logger.info("[Jira Debug] Session headers configured")

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

    def _api_get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make a GET request to the Jira API.

        Args:
            endpoint: API endpoint (e.g., "/rest/api/2/issue/PROJ-123")
            params: Optional query parameters

        Returns:
            JSON response as dictionary or error dict
        """
        logger.info(f"[Jira Debug] _api_get() called")
        logger.info(f"[Jira Debug] Endpoint: {endpoint}")
        logger.info(f"[Jira Debug] Params: {params}")

        session = self._get_session()
        if not session:
            logger.error("[Jira Debug] No session - Jira not configured")
            return {"error": "Jira not configured. Set JIRA_URL and JIRA_BEARER_TOKEN environment variables."}

        url = f"{self.url.rstrip('/')}{endpoint}"
        logger.info(f"[Jira Debug] Full URL: {url}")

        try:
            logger.info("[Jira Debug] Making GET request...")
            response = session.get(url, params=params, timeout=30)
            logger.info(f"[Jira Debug] Response status code: {response.status_code}")
            logger.info(f"[Jira Debug] Response headers: {dict(response.headers)}")

            if response.status_code >= 400:
                logger.error(f"[Jira Debug] Error response body: {response.text[:500]}")

            response.raise_for_status()
            result = response.json()
            logger.info(f"[Jira Debug] Response JSON keys: {list(result.keys()) if isinstance(result, dict) else 'list'}")
            return result
        except Exception as e:
            logger.error(f"[Jira Debug] Exception type: {type(e).__name__}")
            logger.error(f"[Jira Debug] Exception message: {str(e)}")
            import traceback
            logger.error(f"[Jira Debug] Traceback:\n{traceback.format_exc()}")
            return {"error": f"Jira API error: {str(e)}"}

    def load_core(self) -> str:
        """Level 2: Load Jira skill instructions from SKILL.md.

        Returns:
            Complete skill context for Jira operations
        """
        # Check if Jira is configured
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

        # Load static content from SKILL.md
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
    """

    def __init__(self):
        """Initialize skill registry with built-in skills."""
        self._skills: dict[str, Skill] = {}
        self._custom_skills: dict[str, CustomSkill] = {}
        self._register_builtin_skills()

    def _register_builtin_skills(self) -> None:
        """Register all built-in skills."""
        # SQL skill
        sql_skill = SQLSkill()
        sql_skill.is_builtin = True  # Mark as built-in
        self.register(sql_skill)

        # XLSX skill (from Anthropic skills repository)
        xlsx_skill = XLSXSkill()
        self.register(xlsx_skill)

        # Jira skill (read-only Jira integration)
        jira_skill = JiraSkill()
        self.register(jira_skill)

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

    def load_skill(self, skill_id: str) -> str:
        """Load a skill's core content (Level 2).

        Args:
            skill_id: Skill identifier

        Returns:
            Skill core content or error message
        """
        skill = self.get_skill(skill_id)
        if not skill:
            available = ", ".join(self._skills.keys())
            return f"Unknown skill: {skill_id}. Available skills: {available}"

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
    ) -> CustomSkill:
        """Update an existing custom skill.

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

        Returns:
            Updated CustomSkill instance

        Raises:
            ValueError: If skill not found or is a built-in skill
        """
        skill = self._custom_skills.get(skill_id)
        if not skill:
            if skill_id in self._skills:
                raise ValueError(f"Cannot update built-in skill: {skill_id}")
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

        # Update the skill
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

        logger.info(f"Updated custom skill: {skill_id}")
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

        # For built-in skills, return basic info
        return {
            "id": skill.id,
            "name": skill.name,
            "description": skill.description,
            "category": skill.category,
            "is_builtin": True,
            "core_content": skill.load_core(),
            "resources": [],
            "scripts": [],
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
