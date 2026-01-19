"""Jira tool provider for project management operations."""

import logging
import traceback
from typing import TYPE_CHECKING, Callable, Optional

from langchain_docker.api.services.tools.base import (
    ToolParameter,
    ToolProvider,
    ToolTemplate,
)
from langchain_docker.core.tracing import get_tracer

if TYPE_CHECKING:
    from langchain_docker.api.services.skill_registry import JiraSkill, SkillRegistry

logger = logging.getLogger(__name__)


class JiraToolProvider(ToolProvider):
    """Tool provider for Jira/project management operations.

    Provides tools for:
    - Loading Jira skill (progressive disclosure)
    - Searching issues with JQL
    - Getting issue details
    - Listing projects
    - Managing sprints
    - Viewing changelogs
    - Getting comments, boards, worklogs
    """

    def get_skill_id(self) -> str:
        """Return the Jira skill ID."""
        return "jira"

    def get_skill(self) -> "JiraSkill":
        """Get the Jira skill (lazy loaded with logging)."""
        if self._skill is None:
            logger.info("[JiraToolProvider] Loading jira skill")
            self._skill = self._skill_registry.get_skill(self.get_skill_id())
            if self._skill:
                logger.info(f"[JiraToolProvider] Jira URL: {self._skill.url}")
                logger.info(f"[JiraToolProvider] Token configured: {bool(self._skill.bearer_token)}")
        return self._skill

    def get_templates(self) -> list[ToolTemplate]:
        """Return all Jira tool templates."""
        return [
            # Progressive disclosure tool
            ToolTemplate(
                id="load_jira_skill",
                name="Load Jira Skill",
                description="Load Jira skill with context and guidelines (progressive disclosure)",
                category="project_management",
                parameters=[],
                factory=self._create_load_jira_skill_tool,
            ),
            # Issue tools
            ToolTemplate(
                id="jira_search",
                name="Search Jira Issues",
                description="Search for Jira issues using JQL (Jira Query Language)",
                category="project_management",
                parameters=[
                    ToolParameter(
                        name="max_results",
                        type="int",
                        description="Maximum number of results to return",
                        default=50,
                        required=False,
                    )
                ],
                factory=self._create_jira_search_tool,
            ),
            ToolTemplate(
                id="jira_get_issue",
                name="Get Jira Issue",
                description="Get detailed information about a specific Jira issue",
                category="project_management",
                parameters=[],
                factory=self._create_jira_get_issue_tool,
            ),
            ToolTemplate(
                id="jira_get_changelog",
                name="Get Jira Changelog",
                description="Get field change history (status, assignee, priority changes) - NOT for user comments",
                category="project_management",
                parameters=[],
                factory=self._create_jira_get_changelog_tool,
            ),
            ToolTemplate(
                id="jira_get_comments",
                name="Get Jira Comments",
                description="Get user comments and discussion threads on a Jira issue - use this for reading comments",
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
                factory=self._create_jira_get_comments_tool,
            ),
            ToolTemplate(
                id="jira_get_worklogs",
                name="Get Jira Worklogs",
                description="Get work logs for a Jira issue",
                category="project_management",
                parameters=[],
                factory=self._create_jira_get_worklogs_tool,
            ),
            # Project tools
            ToolTemplate(
                id="jira_list_projects",
                name="List Jira Projects",
                description="List all accessible Jira projects",
                category="project_management",
                parameters=[],
                factory=self._create_jira_list_projects_tool,
            ),
            # Board/Sprint tools
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
                factory=self._create_jira_get_boards_tool,
            ),
            ToolTemplate(
                id="jira_get_sprints",
                name="Get Jira Sprints",
                description="Get sprints for a Jira board",
                category="project_management",
                parameters=[],
                factory=self._create_jira_get_sprints_tool,
            ),
            ToolTemplate(
                id="jira_get_sprint_issues",
                name="Get Jira Sprint Issues",
                description="Get all issues in a specific sprint",
                category="project_management",
                parameters=[],
                factory=self._create_jira_get_sprint_issues_tool,
            ),
            # Reference tools
            ToolTemplate(
                id="jira_jql_reference",
                name="JQL Reference",
                description="Load JQL (Jira Query Language) reference documentation",
                category="project_management",
                parameters=[],
                factory=self._create_jira_jql_reference_tool,
            ),
        ]

    # Factory methods

    def _create_load_jira_skill_tool(self) -> Callable[[], str]:
        """Create load Jira skill tool for progressive disclosure."""
        jira_skill = self.get_skill()

        def load_jira_skill() -> str:
            """Load the Jira skill with context and guidelines.

            Call this tool before querying Jira to get the configuration status,
            available operations, and JQL guidelines.

            Returns:
                Jira skill context including configuration and guidelines
            """
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
        jira_skill = self.get_skill()
        logger.info(f"[JiraToolProvider] Creating jira_search tool with max_results={max_results}")

        def jira_search(jql: str) -> str:
            """Search for Jira issues using JQL (Jira Query Language).

            Args:
                jql: JQL query string (e.g., "project = PROJ AND status = Open")

            Returns:
                Search results with issue keys, summaries, and status
            """
            logger.info(f"[JiraToolProvider] jira_search() called with JQL: {jql}")
            try:
                result = jira_skill.search_issues(jql, max_results=max_results)
                preview = result[:200] + "..." if len(result) > 200 else result
                logger.info(f"[JiraToolProvider] jira_search() result preview: {preview}")
                return result
            except Exception as e:
                logger.error(f"[JiraToolProvider] jira_search() exception: {type(e).__name__}: {str(e)}")
                logger.error(f"[JiraToolProvider] Traceback:\n{traceback.format_exc()}")
                raise

        return jira_search

    def _create_jira_get_issue_tool(self) -> Callable[[str], str]:
        """Create Jira get issue tool."""
        jira_skill = self.get_skill()
        logger.info("[JiraToolProvider] Creating jira_get_issue tool")

        def jira_get_issue(issue_key: str) -> str:
            """Get detailed information about a specific Jira issue.

            Args:
                issue_key: Issue key (e.g., "PROJ-123")

            Returns:
                Detailed issue information including description, status, assignee, etc.
            """
            logger.info(f"[JiraToolProvider] jira_get_issue() called with issue_key: {issue_key}")
            try:
                result = jira_skill.get_issue(issue_key)
                preview = result[:200] + "..." if len(result) > 200 else result
                logger.info(f"[JiraToolProvider] jira_get_issue() result preview: {preview}")
                return result
            except Exception as e:
                logger.error(f"[JiraToolProvider] jira_get_issue() exception: {type(e).__name__}: {str(e)}")
                logger.error(f"[JiraToolProvider] Traceback:\n{traceback.format_exc()}")
                raise

        return jira_get_issue

    def _create_jira_list_projects_tool(self) -> Callable[[], str]:
        """Create Jira list projects tool."""
        jira_skill = self.get_skill()
        logger.info("[JiraToolProvider] Creating jira_list_projects tool")

        def jira_list_projects() -> str:
            """List all accessible Jira projects.

            Returns:
                List of projects with their keys and names
            """
            logger.info("[JiraToolProvider] jira_list_projects() called")
            try:
                result = jira_skill.list_projects()
                preview = result[:200] + "..." if len(result) > 200 else result
                logger.info(f"[JiraToolProvider] jira_list_projects() result preview: {preview}")
                return result
            except Exception as e:
                logger.error(f"[JiraToolProvider] jira_list_projects() exception: {type(e).__name__}: {str(e)}")
                logger.error(f"[JiraToolProvider] Traceback:\n{traceback.format_exc()}")
                raise

        return jira_list_projects

    def _create_jira_get_sprints_tool(self) -> Callable[[int, str], str]:
        """Create Jira get sprints tool."""
        jira_skill = self.get_skill()

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
        jira_skill = self.get_skill()

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
        jira_skill = self.get_skill()

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
        jira_skill = self.get_skill()
        logger.info("[JiraToolProvider] Creating jira_get_comments tool")

        def jira_get_comments(issue_key: str, max_results: int = 50) -> str:
            """Get comments on a Jira issue.

            Args:
                issue_key: Issue key (e.g., "PROJ-123")
                max_results: Maximum comments to return (default: 50)

            Returns:
                Formatted list of comments
            """
            logger.info(f"[JiraToolProvider] jira_get_comments() called with issue_key: {issue_key}")
            try:
                result = jira_skill.get_comments(issue_key, max_results)
                preview = result[:200] + "..." if len(result) > 200 else result
                logger.info(f"[JiraToolProvider] jira_get_comments() result preview: {preview}")
                return result
            except Exception as e:
                logger.error(f"[JiraToolProvider] jira_get_comments() exception: {type(e).__name__}: {str(e)}")
                return f"Error getting comments: {str(e)}"

        return jira_get_comments

    def _create_jira_get_boards_tool(self) -> Callable[[], str]:
        """Create Jira get boards tool."""
        jira_skill = self.get_skill()
        logger.info("[JiraToolProvider] Creating jira_get_boards tool")

        def jira_get_boards(
            project_key: Optional[str] = None,
            board_type: str = "scrum"
        ) -> str:
            """List all accessible agile boards.

            Args:
                project_key: Optional project key to filter boards
                board_type: Board type filter (scrum, kanban, or empty for all)

            Returns:
                Formatted list of boards
            """
            logger.info(f"[JiraToolProvider] jira_get_boards() called with project_key={project_key}, board_type={board_type}")
            try:
                result = jira_skill.get_boards(project_key, board_type)
                preview = result[:200] + "..." if len(result) > 200 else result
                logger.info(f"[JiraToolProvider] jira_get_boards() result preview: {preview}")
                return result
            except Exception as e:
                logger.error(f"[JiraToolProvider] jira_get_boards() exception: {type(e).__name__}: {str(e)}")
                return f"Error getting boards: {str(e)}"

        return jira_get_boards

    def _create_jira_get_worklogs_tool(self) -> Callable[[str], str]:
        """Create Jira get worklogs tool."""
        jira_skill = self.get_skill()
        logger.info("[JiraToolProvider] Creating jira_get_worklogs tool")

        def jira_get_worklogs(issue_key: str) -> str:
            """Get work logs for a Jira issue.

            Args:
                issue_key: Issue key (e.g., "PROJ-123")

            Returns:
                Formatted list of worklogs with time tracking
            """
            logger.info(f"[JiraToolProvider] jira_get_worklogs() called with issue_key: {issue_key}")
            try:
                result = jira_skill.get_worklogs(issue_key)
                preview = result[:200] + "..." if len(result) > 200 else result
                logger.info(f"[JiraToolProvider] jira_get_worklogs() result preview: {preview}")
                return result
            except Exception as e:
                logger.error(f"[JiraToolProvider] jira_get_worklogs() exception: {type(e).__name__}: {str(e)}")
                return f"Error getting worklogs: {str(e)}"

        return jira_get_worklogs

    def _create_jira_get_sprint_issues_tool(self) -> Callable[[int], str]:
        """Create Jira get sprint issues tool."""
        jira_skill = self.get_skill()
        logger.info("[JiraToolProvider] Creating jira_get_sprint_issues tool")

        def jira_get_sprint_issues(sprint_id: int) -> str:
            """Get all issues in a specific sprint.

            Args:
                sprint_id: The sprint ID

            Returns:
                Formatted list of issues in the sprint
            """
            logger.info(f"[JiraToolProvider] jira_get_sprint_issues() called with sprint_id: {sprint_id}")
            try:
                result = jira_skill.get_sprint_issues(sprint_id)
                preview = result[:200] + "..." if len(result) > 200 else result
                logger.info(f"[JiraToolProvider] jira_get_sprint_issues() result preview: {preview}")
                return result
            except Exception as e:
                logger.error(f"[JiraToolProvider] jira_get_sprint_issues() exception: {type(e).__name__}: {str(e)}")
                return f"Error getting sprint issues: {str(e)}"

        return jira_get_sprint_issues
