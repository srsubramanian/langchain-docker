"""Tool registry service for exposing tools as discoverable templates."""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from langchain_docker.api.services.hitl_tool_wrapper import HITLConfig
from langchain_docker.core.tracing import get_tracer

logger = logging.getLogger(__name__)

# Type aliases for tool function signatures
SQLToolFunc = Callable[[], str] | Callable[[str], str]
JiraToolFunc = Callable[[], str] | Callable[[str], str] | Callable[[str, int], str]
ToolFunc = SQLToolFunc | JiraToolFunc
ToolFactory = Callable[..., ToolFunc]


@dataclass
class ToolParameter:
    """Parameter definition for a configurable tool."""

    name: str
    type: str  # "string", "number", "boolean"
    description: str
    default: Any = None
    required: bool = False


@dataclass
class ToolTemplate:
    """Tool template with metadata and configuration options.

    Attributes:
        id: Unique identifier for the tool
        name: Human-readable name
        description: Tool description shown to agents
        category: Tool category for grouping
        parameters: Configurable parameters
        factory: Function that creates the actual tool
        requires_approval: Optional HITL configuration for tools requiring human approval
    """

    id: str
    name: str
    description: str
    category: str  # "math", "weather", "research", "finance", "database", "project_management"
    parameters: list[ToolParameter] = field(default_factory=list)
    factory: ToolFactory | None = None
    requires_approval: Optional[HITLConfig] = None


class ToolRegistry:
    """Registry of available tool templates.

    Provides a discoverable catalog of tools that can be used to build
    custom agents. Each tool template includes metadata, documentation,
    and optionally configurable parameters.
    """

    def __init__(self):
        """Initialize tool registry and register built-in tools."""
        self._tools: dict[str, ToolTemplate] = {}
        self._register_builtin_tools()

    def _register_builtin_tools(self) -> None:
        """Register all built-in tools as templates."""
        # Database/SQL tools - progressive disclosure pattern
        self.register(
            ToolTemplate(
                id="load_sql_skill",
                name="Load SQL Skill",
                description="Load SQL skill with database schema (progressive disclosure)",
                category="database",
                parameters=[],
                factory=lambda: self._create_load_sql_skill_tool(),
            )
        )

        self.register(
            ToolTemplate(
                id="sql_query",
                name="SQL Query",
                description="Execute a read-only SQL query against the database",
                category="database",
                parameters=[],
                factory=lambda: self._create_sql_query_tool(),
            )
        )

        self.register(
            ToolTemplate(
                id="sql_list_tables",
                name="List Tables",
                description="List all available tables in the database",
                category="database",
                parameters=[],
                factory=lambda: self._create_sql_list_tables_tool(),
            )
        )

        self.register(
            ToolTemplate(
                id="sql_get_samples",
                name="Get Sample Rows",
                description="Get sample rows from database tables",
                category="database",
                parameters=[],
                factory=lambda: self._create_sql_get_samples_tool(),
            )
        )

        # SQL write tool - requires HITL approval
        self.register(
            ToolTemplate(
                id="sql_execute",
                name="SQL Execute (Write)",
                description="Execute INSERT, UPDATE, or DELETE SQL statements. Requires human approval before execution.",
                category="database",
                parameters=[],
                factory=lambda: self._create_sql_execute_tool(),
                requires_approval=HITLConfig(
                    enabled=True,
                    message="This will modify the database. Please review the SQL statement before approving.",
                    show_args=True,
                    timeout_seconds=300,
                ),
            )
        )

        # Jira tools - read-only project management
        self.register(
            ToolTemplate(
                id="load_jira_skill",
                name="Load Jira Skill",
                description="Load Jira skill with context and guidelines (progressive disclosure)",
                category="project_management",
                parameters=[],
                factory=lambda: self._create_load_jira_skill_tool(),
            )
        )

        self.register(
            ToolTemplate(
                id="jira_search",
                name="Search Jira Issues",
                description="Search for Jira issues using JQL (Jira Query Language)",
                category="project_management",
                parameters=[
                    ToolParameter(
                        name="max_results",
                        type="number",
                        description="Maximum number of results to return",
                        default=50,
                        required=False,
                    )
                ],
                factory=self._create_jira_search_tool,
            )
        )

        self.register(
            ToolTemplate(
                id="jira_get_issue",
                name="Get Jira Issue",
                description="Get detailed information about a specific Jira issue",
                category="project_management",
                parameters=[],
                factory=lambda: self._create_jira_get_issue_tool(),
            )
        )

        self.register(
            ToolTemplate(
                id="jira_list_projects",
                name="List Jira Projects",
                description="List all accessible Jira projects",
                category="project_management",
                parameters=[],
                factory=lambda: self._create_jira_list_projects_tool(),
            )
        )

        self.register(
            ToolTemplate(
                id="jira_get_sprints",
                name="Get Jira Sprints",
                description="Get sprints for a Jira board",
                category="project_management",
                parameters=[],
                factory=lambda: self._create_jira_get_sprints_tool(),
            )
        )

        self.register(
            ToolTemplate(
                id="jira_get_changelog",
                name="Get Jira Changelog",
                description="Get the change history for a Jira issue",
                category="project_management",
                parameters=[],
                factory=lambda: self._create_jira_get_changelog_tool(),
            )
        )

        self.register(
            ToolTemplate(
                id="jira_jql_reference",
                name="JQL Reference",
                description="Load JQL (Jira Query Language) reference documentation",
                category="project_management",
                parameters=[],
                factory=lambda: self._create_jira_jql_reference_tool(),
            )
        )

        # New Jira tools
        self.register(
            ToolTemplate(
                id="jira_get_comments",
                name="Get Jira Comments",
                description="Get comments on a Jira issue",
                category="project_management",
                parameters=[
                    ToolParameter(
                        name="max_results",
                        description="Maximum comments to return (default: 50)",
                        type="int",
                        required=False,
                        default=50,
                    ),
                ],
                factory=lambda: self._create_jira_get_comments_tool(),
            )
        )

        self.register(
            ToolTemplate(
                id="jira_get_boards",
                name="List Jira Boards",
                description="List all accessible agile boards",
                category="project_management",
                parameters=[
                    ToolParameter(
                        name="project_key",
                        description="Optional project key to filter boards",
                        type="string",
                        required=False,
                    ),
                    ToolParameter(
                        name="board_type",
                        description="Board type: scrum, kanban, or empty for all",
                        type="string",
                        required=False,
                        default="scrum",
                    ),
                ],
                factory=lambda: self._create_jira_get_boards_tool(),
            )
        )

        self.register(
            ToolTemplate(
                id="jira_get_worklogs",
                name="Get Jira Worklogs",
                description="Get work logs for a Jira issue",
                category="project_management",
                parameters=[],
                factory=lambda: self._create_jira_get_worklogs_tool(),
            )
        )

        self.register(
            ToolTemplate(
                id="jira_get_sprint_issues",
                name="Get Jira Sprint Issues",
                description="Get all issues in a specific sprint",
                category="project_management",
                parameters=[],
                factory=lambda: self._create_jira_get_sprint_issues_tool(),
            )
        )

    # SQL tool factory methods
    def _get_sql_skill(self) -> Any:
        """Get SQL skill from SkillRegistry (lazy loading)."""
        if not hasattr(self, "_skill_registry"):
            from langchain_docker.api.services.skill_registry import SkillRegistry
            self._skill_registry = SkillRegistry()
        return self._skill_registry.get_skill("write_sql")

    def _create_load_sql_skill_tool(self) -> Callable[[], str]:
        """Create load SQL skill tool for progressive disclosure."""
        sql_skill = self._get_sql_skill()

        def load_sql_skill() -> str:
            """Load the SQL skill with database schema and guidelines.

            Call this tool before writing SQL queries to get the database schema,
            available tables, and SQL guidelines. This enables you to write
            accurate queries against the database.

            Returns:
                Database schema, available tables, and SQL guidelines
            """
            # Add custom span for skill loading visibility in Phoenix
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
        sql_skill = self._get_sql_skill()

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
        sql_skill = self._get_sql_skill()

        def sql_list_tables() -> str:
            """List all available tables in the database.

            Returns:
                Comma-separated list of table names
            """
            return sql_skill.list_tables()

        return sql_list_tables

    def _create_sql_get_samples_tool(self) -> Callable[[], str]:
        """Create SQL get samples tool."""
        sql_skill = self._get_sql_skill()

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
        sql_skill = self._get_sql_skill()

        def sql_execute(query: str) -> str:
            """Execute a SQL write statement (INSERT, UPDATE, DELETE).

            WARNING: This tool modifies data. Requires human approval.

            Args:
                query: The SQL statement to execute (INSERT, UPDATE, DELETE)

            Returns:
                Execution result or error message
            """
            # Validate that it's a write operation
            query_upper = query.strip().upper()
            if query_upper.startswith("SELECT"):
                return "Error: Use sql_query for SELECT statements. This tool is for write operations only."

            if not any(
                query_upper.startswith(op)
                for op in ["INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER"]
            ):
                return "Error: Only INSERT, UPDATE, DELETE, CREATE, DROP, ALTER statements are allowed."

            # Execute the write query
            # Note: The HITL wrapper will intercept this before execution
            return sql_skill.execute_query(query, read_only=False)

        return sql_execute

    # Jira tool factory methods
    def _get_jira_skill(self) -> Any:
        """Get Jira skill from SkillRegistry (lazy loading)."""
        logger.info("[Jira Tool] _get_jira_skill() called")
        if not hasattr(self, "_skill_registry"):
            logger.info("[Jira Tool] Creating new SkillRegistry instance")
            from langchain_docker.api.services.skill_registry import SkillRegistry
            self._skill_registry = SkillRegistry()
        jira_skill = self._skill_registry.get_skill("jira")
        logger.info(f"[Jira Tool] Retrieved jira skill: {jira_skill}")
        if jira_skill:
            logger.info(f"[Jira Tool] Jira URL: {jira_skill.url}")
            logger.info(f"[Jira Tool] Jira bearer_token configured: {bool(jira_skill.bearer_token)}")
        return jira_skill

    def _create_load_jira_skill_tool(self) -> Callable[[], str]:
        """Create load Jira skill tool for progressive disclosure."""
        jira_skill = self._get_jira_skill()

        def load_jira_skill() -> str:
            """Load the Jira skill with context and guidelines.

            Call this tool before querying Jira to get the configuration status,
            available operations, and JQL guidelines. This enables you to write
            accurate queries against Jira.

            Returns:
                Jira skill context including configuration and guidelines
            """
            # Add custom span for skill loading visibility in Phoenix
            tracer = get_tracer()
            if tracer:
                with tracer.start_as_current_span("skill.load_core") as span:
                    span.set_attribute("skill.id", "jira")
                    span.set_attribute("skill.name", jira_skill.name)
                    span.set_attribute("skill.category", jira_skill.category)
                    content = jira_skill.load_core()
                    span.set_attribute("content_length", len(content))
                    return content
            return jira_skill.load_core()

        return load_jira_skill

    def _create_jira_search_tool(self, max_results: int = 50) -> Callable[[str], str]:
        """Create Jira search tool with configurable max results."""
        jira_skill = self._get_jira_skill()
        logger.info(f"[Jira Tool] Creating jira_search tool with max_results={max_results}")
        logger.info(f"[Jira Tool] jira_skill instance: {jira_skill}")

        def jira_search(jql: str) -> str:
            """Search for Jira issues using JQL (Jira Query Language).

            Use load_jira_skill first to get JQL guidelines and available operations.
            Use jira_jql_reference for detailed JQL syntax help.

            Args:
                jql: JQL query string (e.g., "project = PROJ AND status = Open")

            Returns:
                Search results with issue keys, summaries, and status
            """
            logger.info(f"[Jira Tool] jira_search() called with JQL: {jql}")
            try:
                result = jira_skill.search_issues(jql, max_results=max_results)
                preview = result[:200] + "..." if len(result) > 200 else result
                logger.info(f"[Jira Tool] jira_search() result preview: {preview}")
                return result
            except Exception as e:
                logger.error(f"[Jira Tool] jira_search() exception: {type(e).__name__}: {str(e)}")
                import traceback
                logger.error(f"[Jira Tool] Traceback:\n{traceback.format_exc()}")
                raise

        return jira_search

    def _create_jira_get_issue_tool(self) -> Callable[[str], str]:
        """Create Jira get issue tool."""
        jira_skill = self._get_jira_skill()
        logger.info("[Jira Tool] Creating jira_get_issue tool")

        def jira_get_issue(issue_key: str) -> str:
            """Get detailed information about a specific Jira issue.

            Args:
                issue_key: Issue key (e.g., "PROJ-123")

            Returns:
                Detailed issue information including description, status, assignee, etc.
            """
            logger.info(f"[Jira Tool] jira_get_issue() called with issue_key: {issue_key}")
            try:
                result = jira_skill.get_issue(issue_key)
                preview = result[:200] + "..." if len(result) > 200 else result
                logger.info(f"[Jira Tool] jira_get_issue() result preview: {preview}")
                return result
            except Exception as e:
                logger.error(f"[Jira Tool] jira_get_issue() exception: {type(e).__name__}: {str(e)}")
                import traceback
                logger.error(f"[Jira Tool] Traceback:\n{traceback.format_exc()}")
                raise

        return jira_get_issue

    def _create_jira_list_projects_tool(self) -> Callable[[], str]:
        """Create Jira list projects tool."""
        jira_skill = self._get_jira_skill()
        logger.info("[Jira Tool] Creating jira_list_projects tool")

        def jira_list_projects() -> str:
            """List all accessible Jira projects.

            Returns:
                List of projects with their keys and names
            """
            logger.info("[Jira Tool] jira_list_projects() called")
            try:
                result = jira_skill.list_projects()
                preview = result[:200] + "..." if len(result) > 200 else result
                logger.info(f"[Jira Tool] jira_list_projects() result preview: {preview}")
                return result
            except Exception as e:
                logger.error(f"[Jira Tool] jira_list_projects() exception: {type(e).__name__}: {str(e)}")
                import traceback
                logger.error(f"[Jira Tool] Traceback:\n{traceback.format_exc()}")
                raise

        return jira_list_projects

    def _create_jira_get_sprints_tool(self) -> Callable[[int, str], str]:
        """Create Jira get sprints tool."""
        jira_skill = self._get_jira_skill()

        def jira_get_sprints(board_id: int, state: str = "active") -> str:
            """Get sprints for a Jira board.

            Args:
                board_id: The ID of the agile board
                state: Sprint state filter - "active", "closed", or "future"

            Returns:
                List of sprints with their IDs, names, and dates
            """
            return jira_skill.get_sprints(board_id, state)

        return jira_get_sprints

    def _create_jira_get_changelog_tool(self) -> Callable[[str], str]:
        """Create Jira get changelog tool."""
        jira_skill = self._get_jira_skill()

        def jira_get_changelog(issue_key: str) -> str:
            """Get the change history for a Jira issue.

            Args:
                issue_key: Issue key (e.g., "PROJ-123")

            Returns:
                Change history showing who changed what and when
            """
            return jira_skill.get_changelog(issue_key)

        return jira_get_changelog

    def _create_jira_jql_reference_tool(self) -> Callable[[], str]:
        """Create Jira JQL reference tool."""
        jira_skill = self._get_jira_skill()

        def jira_jql_reference() -> str:
            """Load JQL (Jira Query Language) reference documentation.

            Returns detailed JQL syntax guide including:
            - Field names and operators
            - Functions (currentUser(), openSprints(), etc.)
            - Date/time handling
            - Common query patterns

            Returns:
                JQL reference documentation
            """
            return jira_skill.load_details("jql_reference")

        return jira_jql_reference

    def _create_jira_get_comments_tool(self) -> Callable[[str, int], str]:
        """Create Jira get comments tool."""
        jira_skill = self._get_jira_skill()
        logger.info("[Jira Tool] Creating jira_get_comments tool")

        def jira_get_comments(issue_key: str, max_results: int = 50) -> str:
            """Get comments on a Jira issue.

            Args:
                issue_key: Issue key (e.g., "PROJ-123")
                max_results: Maximum comments to return (default: 50)

            Returns:
                Formatted list of comments
            """
            logger.info(f"[Jira Tool] jira_get_comments() called with issue_key: {issue_key}")
            try:
                result = jira_skill.get_comments(issue_key, max_results)
                preview = result[:200] + "..." if len(result) > 200 else result
                logger.info(f"[Jira Tool] jira_get_comments() result preview: {preview}")
                return result
            except Exception as e:
                logger.error(f"[Jira Tool] jira_get_comments() exception: {type(e).__name__}: {str(e)}")
                return f"Error getting comments: {str(e)}"

        return jira_get_comments

    def _create_jira_get_boards_tool(self) -> Callable[[], str]:
        """Create Jira get boards tool."""
        jira_skill = self._get_jira_skill()
        logger.info("[Jira Tool] Creating jira_get_boards tool")

        def jira_get_boards(
            project_key: str | None = None,
            board_type: str = "scrum"
        ) -> str:
            """List all accessible agile boards.

            Args:
                project_key: Optional project key to filter boards
                board_type: Board type filter (scrum, kanban, or empty for all)

            Returns:
                Formatted list of boards
            """
            logger.info(f"[Jira Tool] jira_get_boards() called with project_key={project_key}, board_type={board_type}")
            try:
                result = jira_skill.get_boards(project_key, board_type)
                preview = result[:200] + "..." if len(result) > 200 else result
                logger.info(f"[Jira Tool] jira_get_boards() result preview: {preview}")
                return result
            except Exception as e:
                logger.error(f"[Jira Tool] jira_get_boards() exception: {type(e).__name__}: {str(e)}")
                return f"Error getting boards: {str(e)}"

        return jira_get_boards

    def _create_jira_get_worklogs_tool(self) -> Callable[[str], str]:
        """Create Jira get worklogs tool."""
        jira_skill = self._get_jira_skill()
        logger.info("[Jira Tool] Creating jira_get_worklogs tool")

        def jira_get_worklogs(issue_key: str) -> str:
            """Get work logs for a Jira issue.

            Args:
                issue_key: Issue key (e.g., "PROJ-123")

            Returns:
                Formatted list of worklogs with time tracking
            """
            logger.info(f"[Jira Tool] jira_get_worklogs() called with issue_key: {issue_key}")
            try:
                result = jira_skill.get_worklogs(issue_key)
                preview = result[:200] + "..." if len(result) > 200 else result
                logger.info(f"[Jira Tool] jira_get_worklogs() result preview: {preview}")
                return result
            except Exception as e:
                logger.error(f"[Jira Tool] jira_get_worklogs() exception: {type(e).__name__}: {str(e)}")
                return f"Error getting worklogs: {str(e)}"

        return jira_get_worklogs

    def _create_jira_get_sprint_issues_tool(self) -> Callable[[int], str]:
        """Create Jira get sprint issues tool."""
        jira_skill = self._get_jira_skill()
        logger.info("[Jira Tool] Creating jira_get_sprint_issues tool")

        def jira_get_sprint_issues(sprint_id: int) -> str:
            """Get all issues in a specific sprint.

            Args:
                sprint_id: The sprint ID

            Returns:
                Formatted list of issues in the sprint
            """
            logger.info(f"[Jira Tool] jira_get_sprint_issues() called with sprint_id: {sprint_id}")
            try:
                result = jira_skill.get_sprint_issues(sprint_id)
                preview = result[:200] + "..." if len(result) > 200 else result
                logger.info(f"[Jira Tool] jira_get_sprint_issues() result preview: {preview}")
                return result
            except Exception as e:
                logger.error(f"[Jira Tool] jira_get_sprint_issues() exception: {type(e).__name__}: {str(e)}")
                return f"Error getting sprint issues: {str(e)}"

        return jira_get_sprint_issues

    # Registry methods
    def register(self, template: ToolTemplate) -> None:
        """Register a tool template.

        Args:
            template: Tool template to register
        """
        self._tools[template.id] = template

    def list_tools(self) -> list[ToolTemplate]:
        """List all available tool templates.

        Returns:
            List of all tool templates
        """
        return list(self._tools.values())

    def get_tool(self, tool_id: str) -> ToolTemplate | None:
        """Get a tool template by ID.

        Args:
            tool_id: Tool identifier

        Returns:
            Tool template if found, None otherwise
        """
        return self._tools.get(tool_id)

    def list_by_category(self, category: str) -> list[ToolTemplate]:
        """List tools in a specific category.

        Args:
            category: Category name

        Returns:
            List of tools in the category
        """
        return [t for t in self._tools.values() if t.category == category]

    def get_categories(self) -> list[str]:
        """Get all unique tool categories.

        Returns:
            List of category names
        """
        return list(sorted(set(t.category for t in self._tools.values())))

    def create_tool_instance(
        self, tool_id: str, config: dict[str, Any] | None = None
    ) -> ToolFunc:
        """Create a tool instance with the given configuration.

        Args:
            tool_id: Tool template ID
            config: Optional configuration parameters

        Returns:
            Callable tool function

        Raises:
            ValueError: If tool not found or factory not configured
        """
        template = self.get_tool(tool_id)
        if not template:
            raise ValueError(f"Unknown tool: {tool_id}")

        if not template.factory:
            raise ValueError(f"Tool {tool_id} has no factory configured")

        if template.parameters and config:
            # Filter config to only include valid parameters
            valid_params = {p.name for p in template.parameters}
            filtered_config = {k: v for k, v in config.items() if k in valid_params}
            return template.factory(**filtered_config)

        return template.factory()

    def to_dict_list(self) -> list[dict]:
        """Convert all templates to dictionary format for API response.

        Returns:
            List of tool templates as dictionaries
        """
        return [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "parameters": [
                    {
                        "name": p.name,
                        "type": p.type,
                        "description": p.description,
                        "default": p.default,
                        "required": p.required,
                    }
                    for p in t.parameters
                ],
            }
            for t in self._tools.values()
        ]
