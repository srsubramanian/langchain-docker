"""Custom state schema for skill-aware agents.

This module defines SkillAwareState which extends AgentState to track
which skills have been loaded during a conversation.
"""

from typing import Any
from typing_extensions import NotRequired

from langchain.agents import AgentState


class SkillAwareState(AgentState):
    """Extended agent state that tracks skill loading.

    This state schema is used by SkillMiddleware to:
    1. Track which skills have been loaded in the current conversation
    2. Count how many times each skill has been loaded (to prevent duplicates)
    3. Store skill-specific context that tools might need

    Attributes:
        skills_loaded: List of skill IDs that have been loaded in this conversation.
            Tools can check this to ensure required skills are loaded before executing.
        skill_load_count: Dictionary mapping skill_id -> load count.
            Used to detect and prevent duplicate skill loading.
        skill_context: Optional dictionary for skill-specific runtime context.
            Skills can store additional data here if needed.

    Example:
        # Initial state when conversation starts
        state = {
            "messages": [],
            "skills_loaded": [],
            "skill_load_count": {},
        }

        # After loading "write_sql" skill
        state = {
            "messages": [...],
            "skills_loaded": ["write_sql"],
            "skill_load_count": {"write_sql": 1},
        }
    """

    # List of skill IDs loaded in this conversation
    skills_loaded: NotRequired[list[str]]

    # Track load counts to prevent duplicate loading
    skill_load_count: NotRequired[dict[str, int]]

    # Track which version of each skill was loaded (for versioned skills)
    skills_version_loaded: NotRequired[dict[str, int]]

    # Optional skill-specific context
    skill_context: NotRequired[dict[str, Any]]


def get_loaded_skills(state: SkillAwareState) -> list[str]:
    """Get list of skills loaded in the current conversation.

    Args:
        state: The current agent state

    Returns:
        List of skill IDs that have been loaded
    """
    return state.get("skills_loaded", [])


def is_skill_loaded(state: SkillAwareState, skill_id: str) -> bool:
    """Check if a specific skill has been loaded.

    Args:
        state: The current agent state
        skill_id: The skill ID to check

    Returns:
        True if the skill has been loaded, False otherwise
    """
    return skill_id in state.get("skills_loaded", [])


def get_skill_load_count(state: SkillAwareState, skill_id: str) -> int:
    """Get how many times a skill has been loaded.

    Args:
        state: The current agent state
        skill_id: The skill ID to check

    Returns:
        Number of times the skill has been loaded (0 if never loaded)
    """
    return state.get("skill_load_count", {}).get(skill_id, 0)
