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
# Dynamic Tool Factory - Creates tools from skill tool_configs
# =============================================================================

def create_dynamic_tool_from_config(
    skill_id: str,
    skill_instance,
    tool_config: dict,
) -> Optional[callable]:
    """Create a gated tool dynamically from a tool config.

    This factory creates tools based on the tool_configs defined in SKILL.md
    frontmatter, allowing tools to be defined declaratively and edited via API.

    Args:
        skill_id: The skill identifier (e.g., "write_sql", "jira")
        skill_instance: The skill instance with the methods to call
        tool_config: Tool configuration dict with name, description, method, args

    Returns:
        A tool function or None if the method doesn't exist
    """
    from langchain_core.tools import StructuredTool
    from pydantic import Field, create_model
    from typing import Any

    tool_name = tool_config.get("name", "")
    tool_description = tool_config.get("description", "")
    method_name = tool_config.get("method", "")
    args_config = tool_config.get("args", [])
    requires_skill = tool_config.get("requires_skill_loaded", True)

    # Check if the method exists on the skill
    if not hasattr(skill_instance, method_name):
        logger.warning(f"Skill {skill_id} has no method '{method_name}' for tool '{tool_name}'")
        return None

    method = getattr(skill_instance, method_name)

    # Build dynamic Pydantic model for input args
    field_definitions = {}
    for arg in args_config:
        arg_name = arg.get("name", "")
        arg_type_str = arg.get("type", "string")
        arg_desc = arg.get("description", "")
        arg_required = arg.get("required", True)
        arg_default = arg.get("default")

        # Map type strings to Python types
        type_map = {
            "string": str,
            "str": str,
            "int": int,
            "integer": int,
            "bool": bool,
            "boolean": bool,
            "float": float,
            "number": float,
        }
        arg_type = type_map.get(arg_type_str, str)

        if arg_required:
            field_definitions[arg_name] = (arg_type, Field(description=arg_desc))
        else:
            field_definitions[arg_name] = (
                Optional[arg_type],
                Field(default=arg_default, description=arg_desc),
            )

    # Create dynamic input model (empty model if no args)
    if field_definitions:
        DynamicInput = create_model(f"{tool_name}Input", **field_definitions)
    else:
        DynamicInput = create_model(f"{tool_name}Input")

    # Create the tool function with skill gating
    def create_tool_func():
        def tool_func(runtime: ToolRuntime, **kwargs) -> str:
            """Dynamically generated tool function."""
            state: SkillAwareState = runtime.state

            # Check if skill is loaded (if required)
            if requires_skill and not is_skill_loaded(state, skill_id):
                return skill_required_error(skill_id, runtime.tool_call_id, tool_name)

            # Call the skill method with the provided args
            try:
                result = method(**kwargs)
                return result
            except Exception as e:
                logger.error(f"{tool_name} error: {e}")
                return f"Error in {tool_name}: {str(e)}"

        return tool_func

    tool_func = create_tool_func()

    # Create StructuredTool with the dynamic input model
    # For tools with no args, we need to handle differently
    if field_definitions:
        structured_tool = StructuredTool.from_function(
            func=tool_func,
            name=tool_name,
            description=f"{tool_description}\n\nRequires the '{skill_id}' skill to be loaded first.",
            args_schema=DynamicInput,
        )
    else:
        # For tools with no args, use StructuredTool with an empty schema
        def no_args_func(runtime: ToolRuntime) -> str:
            state: SkillAwareState = runtime.state
            if requires_skill and not is_skill_loaded(state, skill_id):
                return skill_required_error(skill_id, runtime.tool_call_id, tool_name)
            try:
                result = method()
                return result
            except Exception as e:
                logger.error(f"{tool_name} error: {e}")
                return f"Error in {tool_name}: {str(e)}"

        structured_tool = StructuredTool.from_function(
            func=no_args_func,
            name=tool_name,
            description=f"{tool_description}\n\nRequires the '{skill_id}' skill to be loaded first.",
            args_schema=DynamicInput,
        )

    return structured_tool


def create_gated_tools_from_configs(skill_id: str, skill_instance) -> list:
    """Create gated tools dynamically from a skill's tool_configs.

    Reads the tool configurations from the skill instance (loaded from SKILL.md
    frontmatter) and creates corresponding gated tools.

    Args:
        skill_id: The skill identifier
        skill_instance: The skill instance with get_tool_configs() method

    Returns:
        List of gated tool functions
    """
    tools = []

    # Get tool configs from the skill
    if not hasattr(skill_instance, "get_tool_configs"):
        logger.debug(f"Skill {skill_id} has no get_tool_configs method, using static tools")
        return []

    tool_configs = skill_instance.get_tool_configs()
    if not tool_configs:
        logger.debug(f"Skill {skill_id} has no tool_configs defined")
        return []

    for config in tool_configs:
        tool = create_dynamic_tool_from_config(skill_id, skill_instance, config)
        if tool:
            tools.append(tool)
            logger.debug(f"Created dynamic tool '{config.get('name')}' for skill '{skill_id}'")

    return tools


# =============================================================================
# Factory function to create all gated tools for a registry
# =============================================================================

def create_gated_tools_for_skill(skill_id: str, skill_instance, use_dynamic: bool = True) -> list:
    """Create all gated tools for a given skill.

    By default, this function first tries to create tools dynamically from
    the skill's tool_configs (loaded from SKILL.md frontmatter). If no configs
    are found, it falls back to using hardcoded static tool factories.

    Args:
        skill_id: The skill identifier ("write_sql", "jira", etc.)
        skill_instance: The skill instance with the necessary methods
        use_dynamic: If True, try dynamic tool creation first (default: True)

    Returns:
        List of gated tool functions
    """
    # Try dynamic tool creation first if enabled
    if use_dynamic:
        dynamic_tools = create_gated_tools_from_configs(skill_id, skill_instance)
        if dynamic_tools:
            logger.info(f"Created {len(dynamic_tools)} dynamic tools for skill '{skill_id}'")
            return dynamic_tools

    # Fallback to static tool factories
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

    if tools:
        logger.info(f"Created {len(tools)} static tools for skill '{skill_id}'")

    return tools
