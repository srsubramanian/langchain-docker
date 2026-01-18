"""SQL tool provider for database operations."""

import logging
from typing import TYPE_CHECKING, Callable

from langchain_docker.api.services.hitl_tool_wrapper import HITLConfig
from langchain_docker.api.services.tools.base import (
    ToolParameter,
    ToolProvider,
    ToolTemplate,
)
from langchain_docker.core.tracing import get_tracer

if TYPE_CHECKING:
    from langchain_docker.api.services.skill_registry import SkillRegistry, SQLSkill

logger = logging.getLogger(__name__)


class SQLToolProvider(ToolProvider):
    """Tool provider for SQL/database operations.

    Provides tools for:
    - Loading SQL skill (progressive disclosure)
    - Executing read-only queries
    - Listing tables
    - Getting sample data
    - Executing write operations (with HITL approval)
    """

    def get_skill_id(self) -> str:
        """Return the SQL skill ID."""
        return "write_sql"

    def get_templates(self) -> list[ToolTemplate]:
        """Return all SQL tool templates."""
        return [
            ToolTemplate(
                id="load_sql_skill",
                name="Load SQL Skill",
                description="Load SQL skill with database schema (progressive disclosure)",
                category="database",
                parameters=[],
                factory=self._create_load_sql_skill_tool,
            ),
            ToolTemplate(
                id="sql_query",
                name="SQL Query",
                description="Execute a read-only SQL query against the database",
                category="database",
                parameters=[],
                factory=self._create_sql_query_tool,
            ),
            ToolTemplate(
                id="sql_list_tables",
                name="List Tables",
                description="List all available tables in the database",
                category="database",
                parameters=[],
                factory=self._create_sql_list_tables_tool,
            ),
            ToolTemplate(
                id="sql_get_samples",
                name="Get Sample Rows",
                description="Get sample rows from database tables",
                category="database",
                parameters=[],
                factory=self._create_sql_get_samples_tool,
            ),
            ToolTemplate(
                id="sql_execute",
                name="SQL Execute (Write)",
                description="Execute INSERT, UPDATE, or DELETE SQL statements. Requires human approval before execution.",
                category="database",
                parameters=[],
                factory=self._create_sql_execute_tool,
                requires_approval=HITLConfig(
                    enabled=True,
                    message="This will modify the database. Please review the SQL statement before approving.",
                    show_args=True,
                    timeout_seconds=300,
                ),
            ),
        ]

    def _create_load_sql_skill_tool(self) -> Callable[[], str]:
        """Create load SQL skill tool for progressive disclosure."""
        sql_skill = self.get_skill()

        def load_sql_skill() -> str:
            """Load the SQL skill with database schema and guidelines.

            Call this tool before writing SQL queries to get the database schema,
            available tables, and SQL guidelines. This enables you to write
            accurate queries against the database.

            Returns:
                Database schema, available tables, and SQL guidelines
            """
            tracer = get_tracer()
            if tracer:
                with tracer.start_as_current_span("skill.load_core") as span:
                    span.set_attribute("skill.id", "write_sql")
                    span.set_attribute("skill.name", sql_skill.name)
                    span.set_attribute("skill.category", sql_skill.category)
                    content = sql_skill.load_core()
                    span.set_attribute("content_length", len(content))
                    return content
            return sql_skill.load_core()

        return load_sql_skill

    def _create_sql_query_tool(self) -> Callable[[str], str]:
        """Create SQL query execution tool."""
        sql_skill = self.get_skill()

        def sql_query(query: str) -> str:
            """Execute a SQL query against the database.

            In read-only mode, only SELECT queries are allowed.
            Use load_sql_skill first to get the database schema.

            Args:
                query: The SQL query to execute (SELECT only in read-only mode)

            Returns:
                Query results or error message
            """
            return sql_skill.execute_query(query)

        return sql_query

    def _create_sql_list_tables_tool(self) -> Callable[[], str]:
        """Create SQL list tables tool."""
        sql_skill = self.get_skill()

        def sql_list_tables() -> str:
            """List all available tables in the database.

            Returns:
                Comma-separated list of table names
            """
            return sql_skill.list_tables()

        return sql_list_tables

    def _create_sql_get_samples_tool(self) -> Callable[[], str]:
        """Create SQL get samples tool."""
        sql_skill = self.get_skill()

        def sql_get_samples() -> str:
            """Get sample rows from database tables.

            Returns sample data from each table to help understand
            the data structure and content.

            Returns:
                Sample rows from each table
            """
            return sql_skill.load_details("samples")

        return sql_get_samples

    def _create_sql_execute_tool(self) -> Callable[[str], str]:
        """Create SQL execute tool for write operations.

        This tool allows INSERT, UPDATE, and DELETE operations
        but is configured to require HITL approval.
        """
        sql_skill = self.get_skill()

        def sql_execute(query: str) -> str:
            """Execute a SQL write statement (INSERT, UPDATE, DELETE).

            WARNING: This tool modifies data. Requires human approval.

            Args:
                query: The SQL statement to execute (INSERT, UPDATE, DELETE)

            Returns:
                Execution result or error message
            """
            query_upper = query.strip().upper()
            if query_upper.startswith("SELECT"):
                return "Error: Use sql_query for SELECT statements. This tool is for write operations only."

            if not any(
                query_upper.startswith(op)
                for op in ["INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER"]
            ):
                return "Error: Only INSERT, UPDATE, DELETE, CREATE, DROP, ALTER statements are allowed."

            return sql_skill.execute_query(query, read_only=False)

        return sql_execute
