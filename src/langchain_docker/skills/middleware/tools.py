"""Skill-aware tools using ToolRuntime and Command.

This module provides:
1. Tools for loading skills and listing loaded skills
2. A decorator for creating gated tools that require specific skills
3. Helper functions for checking skill state in tools
"""

import logging
from functools import wraps
from typing import Callable, Optional, TypeVar

from langchain.tools import tool, ToolRuntime
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from langchain_docker.skills.middleware.registry import SkillRegistry
from langchain_docker.skills.middleware.state import SkillAwareState

logger = logging.getLogger(__name__)

T = TypeVar("T")


def create_load_skill_tool(registry: SkillRegistry):
    """Create a load_skill tool bound to a specific registry.

    The tool loads a skill's core content and updates the agent's state
    to track that the skill has been loaded.

    Args:
        registry: The skill registry to load skills from

    Returns:
        A tool function that can be added to an agent
    """

    @tool
    def load_skill(
        skill_id: str,
        runtime: ToolRuntime,
    ) -> Command:
        """Load a skill to get specialized knowledge and capabilities.

        Args:
            skill_id: The ID of the skill to load (e.g., "write_sql", "jira")

        Returns:
            The skill content with instructions and guidelines
        """
        # Get current state
        state: SkillAwareState = runtime.state
        skills_loaded = list(state.get("skills_loaded", []))
        skill_load_count = dict(state.get("skill_load_count", {}))

        # Check if skill exists
        skill = registry.get(skill_id)
        if not skill:
            available = ", ".join(s.id for s in registry.list_skills())
            error_msg = f"Unknown skill: {skill_id}. Available skills: {available}"
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=error_msg,
                            tool_call_id=runtime.tool_call_id,
                        )
                    ],
                },
            )

        # Check if already loaded
        if skill_id in skills_loaded:
            load_count = skill_load_count.get(skill_id, 1)
            msg = (
                f"Skill '{skill_id}' is already loaded (loaded {load_count} time(s)). "
                f"You can proceed with using its tools without loading again."
            )
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=msg,
                            tool_call_id=runtime.tool_call_id,
                        )
                    ],
                },
            )

        # Load the skill content
        try:
            content = skill.get_core_content()
        except Exception as e:
            logger.error(f"Failed to load skill {skill_id}: {e}")
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=f"Error loading skill '{skill_id}': {str(e)}",
                            tool_call_id=runtime.tool_call_id,
                        )
                    ],
                },
            )

        # Update state to track loaded skill
        skills_loaded.append(skill_id)
        skill_load_count[skill_id] = skill_load_count.get(skill_id, 0) + 1

        # Build response with skill content
        response = f"## Skill Loaded: {skill.name}\n\n{content}"

        logger.info(f"Loaded skill: {skill_id}")

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=response,
                        tool_call_id=runtime.tool_call_id,
                    )
                ],
                "skills_loaded": skills_loaded,
                "skill_load_count": skill_load_count,
            },
        )

    return load_skill


def create_list_loaded_skills_tool():
    """Create a tool for listing currently loaded skills.

    Returns:
        A tool function that lists loaded skills from state
    """

    @tool
    def list_loaded_skills(
        runtime: ToolRuntime,
    ) -> str:
        """List all skills that have been loaded in this conversation.

        Returns:
            A list of loaded skill IDs, or a message if none are loaded
        """
        state: SkillAwareState = runtime.state
        skills_loaded = state.get("skills_loaded", [])

        if not skills_loaded:
            return "No skills have been loaded yet. Use load_skill(skill_id) to load one."

        skill_load_count = state.get("skill_load_count", {})
        lines = ["Currently loaded skills:"]
        for skill_id in skills_loaded:
            count = skill_load_count.get(skill_id, 1)
            lines.append(f"- {skill_id} (loaded {count} time(s))")

        return "\n".join(lines)

    return list_loaded_skills


def create_gated_tool(
    tool_func: Callable[..., T],
    required_skill: str,
    tool_name: Optional[str] = None,
    tool_description: Optional[str] = None,
) -> Callable[..., T | Command]:
    """Create a gated version of a tool that requires a skill to be loaded.

    This decorator wraps a tool function to check if the required skill
    is loaded before executing. If not, it returns an error message
    instructing the agent to load the skill first.

    Args:
        tool_func: The original tool function
        required_skill: The skill ID that must be loaded
        tool_name: Override the tool name (uses function name if not provided)
        tool_description: Override the tool description

    Returns:
        A wrapped tool function with skill gating

    Example:
        @tool
        def sql_query(query: str) -> str:
            '''Execute a SQL query.'''
            return execute_query(query)

        # Create gated version
        gated_sql_query = create_gated_tool(sql_query, required_skill="write_sql")

        # Or use as decorator pattern
        def make_sql_query_tool():
            @tool
            def sql_query(query: str, runtime: ToolRuntime) -> str | Command:
                # Check skill is loaded
                if not is_skill_loaded(runtime.state, "write_sql"):
                    return skill_not_loaded_error("write_sql", runtime.tool_call_id)
                return execute_query(query)
            return sql_query
    """

    @wraps(tool_func)
    def gated_wrapper(*args, runtime: ToolRuntime, **kwargs) -> T | Command:
        # Check if required skill is loaded
        state: SkillAwareState = runtime.state
        skills_loaded = state.get("skills_loaded", [])

        if required_skill not in skills_loaded:
            error_msg = (
                f"This tool requires the '{required_skill}' skill to be loaded first. "
                f"Please use load_skill('{required_skill}') before using this tool."
            )
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=error_msg,
                            tool_call_id=runtime.tool_call_id,
                        )
                    ],
                },
            )

        # Skill is loaded, execute the tool
        # Pass runtime if the original function accepts it
        import inspect
        sig = inspect.signature(tool_func)
        if "runtime" in sig.parameters:
            return tool_func(*args, runtime=runtime, **kwargs)
        return tool_func(*args, **kwargs)

    # Apply @tool decorator
    name = tool_name or tool_func.__name__
    description = tool_description or tool_func.__doc__ or ""

    return tool(gated_wrapper, name=name, description=description)


def is_skill_loaded(state: SkillAwareState, skill_id: str) -> bool:
    """Check if a skill is loaded in the current state.

    Helper function for use in tools that need to check skill state.

    Args:
        state: The current agent state (from runtime.state)
        skill_id: The skill ID to check

    Returns:
        True if the skill is loaded, False otherwise
    """
    return skill_id in state.get("skills_loaded", [])


def skill_not_loaded_error(
    skill_id: str,
    tool_call_id: str,
) -> Command:
    """Create a Command response for when a required skill is not loaded.

    Helper function for use in gated tools.

    Args:
        skill_id: The required skill that is not loaded
        tool_call_id: The tool call ID from runtime

    Returns:
        A Command with an error message
    """
    error_msg = (
        f"This tool requires the '{skill_id}' skill to be loaded first. "
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


def create_skill_detail_tool(registry: SkillRegistry):
    """Create a tool for loading skill detail resources (Level 3).

    Args:
        registry: The skill registry

    Returns:
        A tool function for loading skill details
    """

    @tool
    def load_skill_detail(
        skill_id: str,
        resource: str,
        runtime: ToolRuntime,
    ) -> str:
        """Load additional detail resources for a skill.

        Use this to get examples, patterns, or other detailed information
        after loading a skill.

        Args:
            skill_id: The skill ID (must be already loaded)
            resource: The resource name (e.g., "examples", "patterns")

        Returns:
            The detail resource content
        """
        # Check if skill is loaded
        state: SkillAwareState = runtime.state
        if not is_skill_loaded(state, skill_id):
            return (
                f"Skill '{skill_id}' is not loaded. "
                f"Please load it first with load_skill('{skill_id}')."
            )

        # Get skill and load detail
        skill = registry.get(skill_id)
        if not skill:
            return f"Skill not found: {skill_id}"

        return skill.get_detail(resource)

    return load_skill_detail
