"""Gated domain tools that require skills to be loaded.

This module provides middleware-aware versions of domain tools (SQL, Jira, etc.)
that check if the required skill is loaded before executing.

These tools use ToolRuntime to access state and return Command objects
to provide proper feedback to the agent.
"""

import logging
from typing import Optional

from langchain.tools import tool, ToolRuntime
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from langchain_docker.skills.middleware.state import SkillAwareState

logger = logging.getLogger(__name__)


def is_skill_loaded(state: SkillAwareState, skill_id: str) -> bool:
    """Check if a skill is loaded in the current state."""
    return skill_id in state.get("skills_loaded", [])


def skill_required_error(skill_id: str, tool_call_id: str, tool_name: str) -> Command:
    """Create an error Command when a required skill is not loaded."""
    error_msg = (
        f"The '{tool_name}' tool requires the '{skill_id}' skill to be loaded first.\n"
        f"Please use load_skill('{skill_id}') before using this tool."
    )
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=error_msg,
                    tool_call_id=tool_call_id,
                )
            ],
        },
    )


# =============================================================================
# SQL Domain Tools (require "write_sql" skill)
# =============================================================================

def create_gated_sql_query_tool(sql_skill):
    """Create a gated SQL query tool that requires write_sql skill.

    Args:
        sql_skill: The SQL skill instance with execute_query method

    Returns:
        A tool function that checks skill state before executing
    """

    @tool
    def sql_query(
        query: str,
        runtime: ToolRuntime,
    ) -> str | Command:
        """Execute a SQL query against the database.

        In read-only mode, only SELECT queries are allowed.
        Requires the 'write_sql' skill to be loaded first.

        Args:
            query: The SQL query to execute (SELECT only in read-only mode)

        Returns:
            Query results or error message
        """
        state: SkillAwareState = runtime.state

        # Check if skill is loaded
        if not is_skill_loaded(state, "write_sql"):
            return skill_required_error("write_sql", runtime.tool_call_id, "sql_query")

        # Skill is loaded, execute query
        try:
            result = sql_skill.execute_query(query)
            return result
        except Exception as e:
            logger.error(f"SQL query error: {e}")
            return f"Error executing query: {str(e)}"

    return sql_query


def create_gated_sql_list_tables_tool(sql_skill):
    """Create a gated SQL list tables tool that requires write_sql skill.

    Args:
        sql_skill: The SQL skill instance with list_tables method

    Returns:
        A tool function that checks skill state before executing
    """

    @tool
    def sql_list_tables(
        runtime: ToolRuntime,
    ) -> str | Command:
        """List all available tables in the database.

        Requires the 'write_sql' skill to be loaded first.

        Returns:
            Comma-separated list of table names
        """
        state: SkillAwareState = runtime.state

        # Check if skill is loaded
        if not is_skill_loaded(state, "write_sql"):
            return skill_required_error("write_sql", runtime.tool_call_id, "sql_list_tables")

        # Skill is loaded, list tables
        try:
            result = sql_skill.list_tables()
            return result
        except Exception as e:
            logger.error(f"SQL list tables error: {e}")
            return f"Error listing tables: {str(e)}"

    return sql_list_tables


def create_gated_sql_get_samples_tool(sql_skill):
    """Create a gated SQL get samples tool that requires write_sql skill.

    Args:
        sql_skill: The SQL skill instance with load_details method

    Returns:
        A tool function that checks skill state before executing
    """

    @tool
    def sql_get_samples(
        runtime: ToolRuntime,
    ) -> str | Command:
        """Get sample rows from database tables.

        Returns sample data from each table to help understand
        the data structure and content.
        Requires the 'write_sql' skill to be loaded first.

        Returns:
            Sample rows from each table
        """
        state: SkillAwareState = runtime.state

        # Check if skill is loaded
        if not is_skill_loaded(state, "write_sql"):
            return skill_required_error("write_sql", runtime.tool_call_id, "sql_get_samples")

        # Skill is loaded, get samples
        try:
            result = sql_skill.load_details("samples")
            return result
        except Exception as e:
            logger.error(f"SQL get samples error: {e}")
            return f"Error getting samples: {str(e)}"

    return sql_get_samples


# =============================================================================
# Jira Domain Tools (require "jira" skill)
# =============================================================================

def create_gated_jira_search_tool(jira_skill, max_results: int = 50):
    """Create a gated Jira search tool that requires jira skill.

    Args:
        jira_skill: The Jira skill instance with search_issues method
        max_results: Maximum number of results to return

    Returns:
        A tool function that checks skill state before executing
    """

    @tool
    def jira_search(
        jql: str,
        runtime: ToolRuntime,
    ) -> str | Command:
        """Search for Jira issues using JQL (Jira Query Language).

        Requires the 'jira' skill to be loaded first.
        Use jira_jql_reference for detailed JQL syntax help.

        Args:
            jql: JQL query string (e.g., "project = PROJ AND status = Open")

        Returns:
            Search results with issue keys, summaries, and status
        """
        state: SkillAwareState = runtime.state

        # Check if skill is loaded
        if not is_skill_loaded(state, "jira"):
            return skill_required_error("jira", runtime.tool_call_id, "jira_search")

        # Skill is loaded, execute search
        try:
            logger.info(f"[Gated Jira] Executing search with JQL: {jql}")
            result = jira_skill.search_issues(jql, max_results=max_results)
            return result
        except Exception as e:
            logger.error(f"Jira search error: {e}")
            return f"Error searching Jira: {str(e)}"

    return jira_search


def create_gated_jira_get_issue_tool(jira_skill):
    """Create a gated Jira get issue tool that requires jira skill.

    Args:
        jira_skill: The Jira skill instance with get_issue method

    Returns:
        A tool function that checks skill state before executing
    """

    @tool
    def jira_get_issue(
        issue_key: str,
        runtime: ToolRuntime,
    ) -> str | Command:
        """Get detailed information about a specific Jira issue.

        Requires the 'jira' skill to be loaded first.

        Args:
            issue_key: Issue key (e.g., "PROJ-123")

        Returns:
            Detailed issue information including description, status, assignee, etc.
        """
        state: SkillAwareState = runtime.state

        # Check if skill is loaded
        if not is_skill_loaded(state, "jira"):
            return skill_required_error("jira", runtime.tool_call_id, "jira_get_issue")

        # Skill is loaded, get issue
        try:
            logger.info(f"[Gated Jira] Getting issue: {issue_key}")
            result = jira_skill.get_issue(issue_key)
            return result
        except Exception as e:
            logger.error(f"Jira get issue error: {e}")
            return f"Error getting Jira issue: {str(e)}"

    return jira_get_issue


def create_gated_jira_list_projects_tool(jira_skill):
    """Create a gated Jira list projects tool that requires jira skill.

    Args:
        jira_skill: The Jira skill instance with list_projects method

    Returns:
        A tool function that checks skill state before executing
    """

    @tool
    def jira_list_projects(
        runtime: ToolRuntime,
    ) -> str | Command:
        """List all accessible Jira projects.

        Requires the 'jira' skill to be loaded first.

        Returns:
            List of projects with their keys and names
        """
        state: SkillAwareState = runtime.state

        # Check if skill is loaded
        if not is_skill_loaded(state, "jira"):
            return skill_required_error("jira", runtime.tool_call_id, "jira_list_projects")

        # Skill is loaded, list projects
        try:
            logger.info("[Gated Jira] Listing projects")
            result = jira_skill.list_projects()
            return result
        except Exception as e:
            logger.error(f"Jira list projects error: {e}")
            return f"Error listing Jira projects: {str(e)}"

    return jira_list_projects


def create_gated_jira_get_sprints_tool(jira_skill):
    """Create a gated Jira get sprints tool that requires jira skill.

    Args:
        jira_skill: The Jira skill instance with get_sprints method

    Returns:
        A tool function that checks skill state before executing
    """

    @tool
    def jira_get_sprints(
        board_id: int,
        state_filter: str = "active",
        runtime: ToolRuntime = None,
    ) -> str | Command:
        """Get sprints for a Jira board.

        Requires the 'jira' skill to be loaded first.

        Args:
            board_id: The ID of the agile board
            state_filter: Sprint state filter - "active", "closed", or "future"

        Returns:
            List of sprints with their IDs, names, and dates
        """
        state: SkillAwareState = runtime.state

        # Check if skill is loaded
        if not is_skill_loaded(state, "jira"):
            return skill_required_error("jira", runtime.tool_call_id, "jira_get_sprints")

        # Skill is loaded, get sprints
        try:
            result = jira_skill.get_sprints(board_id, state_filter)
            return result
        except Exception as e:
            logger.error(f"Jira get sprints error: {e}")
            return f"Error getting Jira sprints: {str(e)}"

    return jira_get_sprints


def create_gated_jira_get_changelog_tool(jira_skill):
    """Create a gated Jira get changelog tool that requires jira skill.

    Args:
        jira_skill: The Jira skill instance with get_changelog method

    Returns:
        A tool function that checks skill state before executing
    """

    @tool
    def jira_get_changelog(
        issue_key: str,
        runtime: ToolRuntime,
    ) -> str | Command:
        """Get the change history for a Jira issue.

        Requires the 'jira' skill to be loaded first.

        Args:
            issue_key: Issue key (e.g., "PROJ-123")

        Returns:
            Change history showing who changed what and when
        """
        state: SkillAwareState = runtime.state

        # Check if skill is loaded
        if not is_skill_loaded(state, "jira"):
            return skill_required_error("jira", runtime.tool_call_id, "jira_get_changelog")

        # Skill is loaded, get changelog
        try:
            result = jira_skill.get_changelog(issue_key)
            return result
        except Exception as e:
            logger.error(f"Jira get changelog error: {e}")
            return f"Error getting Jira changelog: {str(e)}"

    return jira_get_changelog


def create_gated_jira_jql_reference_tool(jira_skill):
    """Create a gated Jira JQL reference tool that requires jira skill.

    Args:
        jira_skill: The Jira skill instance with load_details method

    Returns:
        A tool function that checks skill state before executing
    """

    @tool
    def jira_jql_reference(
        runtime: ToolRuntime,
    ) -> str | Command:
        """Load JQL (Jira Query Language) reference documentation.

        Requires the 'jira' skill to be loaded first.

        Returns detailed JQL syntax guide including:
        - Field names and operators
        - Functions (currentUser(), openSprints(), etc.)
        - Date/time handling
        - Common query patterns

        Returns:
            JQL reference documentation
        """
        state: SkillAwareState = runtime.state

        # Check if skill is loaded
        if not is_skill_loaded(state, "jira"):
            return skill_required_error("jira", runtime.tool_call_id, "jira_jql_reference")

        # Skill is loaded, get JQL reference
        try:
            result = jira_skill.load_details("jql_reference")
            return result
        except Exception as e:
            logger.error(f"Jira JQL reference error: {e}")
            return f"Error loading JQL reference: {str(e)}"

    return jira_jql_reference


# =============================================================================
# Factory function to create all gated tools for a registry
# =============================================================================

def create_gated_tools_for_skill(skill_id: str, skill_instance) -> list:
    """Create all gated tools for a given skill.

    Args:
        skill_id: The skill identifier ("write_sql", "jira", etc.)
        skill_instance: The skill instance with the necessary methods

    Returns:
        List of gated tool functions
    """
    tools = []

    if skill_id == "write_sql":
        tools = [
            create_gated_sql_query_tool(skill_instance),
            create_gated_sql_list_tables_tool(skill_instance),
            create_gated_sql_get_samples_tool(skill_instance),
        ]
    elif skill_id == "jira":
        tools = [
            create_gated_jira_search_tool(skill_instance),
            create_gated_jira_get_issue_tool(skill_instance),
            create_gated_jira_list_projects_tool(skill_instance),
            create_gated_jira_get_sprints_tool(skill_instance),
            create_gated_jira_get_changelog_tool(skill_instance),
            create_gated_jira_jql_reference_tool(skill_instance),
        ]

    return tools
