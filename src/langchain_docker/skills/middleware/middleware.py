"""Skill middleware for LangChain agents.

This module implements SkillMiddleware which:
1. Automatically injects skill descriptions into system prompts
2. Manages skill-aware state
3. Provides tools for loading skills and listing loaded skills
4. Enables tool gating based on loaded skills
"""

import logging
from typing import Any, Callable, Optional

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import SystemMessage

from langchain_docker.skills.middleware.registry import SkillRegistry
from langchain_docker.skills.middleware.state import SkillAwareState
from langchain_docker.skills.middleware.tools import (
    create_load_skill_tool,
    create_list_loaded_skills_tool,
)

logger = logging.getLogger(__name__)


# Default system prompt section for skills
DEFAULT_SKILL_PROMPT_TEMPLATE = """
## Available Skills

You have access to specialized skills that provide domain-specific knowledge and tools.
Before using domain-specific tools, you should load the relevant skill first.

{skill_descriptions}

To load a skill, use the `load_skill` tool with the skill ID.
You can check which skills are currently loaded with `list_loaded_skills`.
"""


class SkillMiddleware(AgentMiddleware[SkillAwareState]):
    """Middleware that manages skills for an agent.

    SkillMiddleware provides:
    1. Automatic skill description injection into the system prompt
    2. State tracking for loaded skills (prevents duplicate loading)
    3. Tools for loading skills and checking loaded skills
    4. Foundation for tool gating (domain tools can check state)

    The middleware uses the wrap_model_call hook to intercept model requests
    and inject skill information into the system prompt dynamically.

    Attributes:
        state_schema: SkillAwareState - extends AgentState with skill tracking
        tools: List of skill management tools (load_skill, list_loaded_skills)

    Example:
        from langchain_docker.skills.middleware import SkillMiddleware, SkillRegistry

        registry = SkillRegistry()
        registry.register(sql_skill)
        registry.register(jira_skill)

        middleware = SkillMiddleware(registry)

        agent = create_agent(
            model=model,
            middleware=[middleware],
            tools=[sql_query, jira_search],  # Domain tools
        )

        # The agent now:
        # - Sees skill descriptions in its system prompt
        # - Can load skills with load_skill("write_sql")
        # - Tracks loaded skills in state
    """

    state_schema = SkillAwareState

    def __init__(
        self,
        registry: SkillRegistry,
        prompt_template: str = DEFAULT_SKILL_PROMPT_TEMPLATE,
        description_format: str = "list",
        auto_refresh_skills: bool = False,
    ):
        """Initialize the skill middleware.

        Args:
            registry: The skill registry containing available skills
            prompt_template: Template for the skill section in system prompt.
                Must contain {skill_descriptions} placeholder.
            description_format: Format for skill descriptions ("list" or "table")
            auto_refresh_skills: If True, refresh skill descriptions on each
                model call (useful if skills can change during conversation)
        """
        self.registry = registry
        self.prompt_template = prompt_template
        self.description_format = description_format
        self.auto_refresh_skills = auto_refresh_skills

        # Cache skill descriptions (unless auto-refresh is enabled)
        self._cached_descriptions: Optional[str] = None

        # Build the tools list
        self.tools = [
            create_load_skill_tool(registry),
            create_list_loaded_skills_tool(),
        ]

    def _get_skill_descriptions(self) -> str:
        """Get formatted skill descriptions, using cache if available.

        Returns:
            Formatted skill descriptions string
        """
        if self._cached_descriptions is None or self.auto_refresh_skills:
            self._cached_descriptions = self.registry.get_descriptions(
                format=self.description_format
            )
        return self._cached_descriptions

    def _build_skill_prompt_section(self) -> str:
        """Build the skill section to inject into system prompt.

        Returns:
            Formatted skill prompt section
        """
        descriptions = self._get_skill_descriptions()
        return self.prompt_template.format(skill_descriptions=descriptions)

    def before_agent(
        self,
        state: SkillAwareState,
        runtime,
    ) -> dict[str, Any] | None:
        """Initialize skill-aware state before agent starts.

        This hook ensures the state has the required skill tracking fields
        initialized when the agent starts.

        Args:
            state: The current agent state
            runtime: The LangGraph runtime

        Returns:
            State updates to initialize skill tracking, or None
        """
        updates = {}

        # Initialize skills_loaded if not present
        if "skills_loaded" not in state:
            updates["skills_loaded"] = []

        # Initialize skill_load_count if not present
        if "skill_load_count" not in state:
            updates["skill_load_count"] = {}

        return updates if updates else None

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Wrap model calls to inject skill descriptions into system prompt.

        This hook intercepts each model call and:
        1. Checks if skill descriptions need to be injected
        2. Modifies the system prompt to include available skills
        3. Uses the loaded skills info from the last before_model call

        Args:
            request: The model request containing messages and config
            handler: The next handler in the middleware chain

        Returns:
            The model response from the handler
        """
        # Get the current messages
        messages = list(request.messages)

        # Find or create the system message
        system_message_idx = None
        system_content = ""

        for i, msg in enumerate(messages):
            if isinstance(msg, SystemMessage):
                system_message_idx = i
                system_content = msg.content
                break

        # Build skill section
        skill_section = self._build_skill_prompt_section()

        # Get currently loaded skills from the cached value (set in before_model)
        # Note: We can't access state directly from request.runtime in current LangChain
        # The before_model hook sets self._current_loaded_skills from the state
        loaded_skills = getattr(self, "_current_loaded_skills", [])

        # Add loaded skills info if any
        if loaded_skills:
            skill_section += f"\n\n**Currently loaded skills**: {', '.join(loaded_skills)}"

        # Inject skill section into system prompt
        if system_message_idx is not None:
            # Append to existing system message
            new_content = f"{system_content}\n\n{skill_section}"
            messages[system_message_idx] = SystemMessage(content=new_content)
        else:
            # Prepend new system message
            messages.insert(0, SystemMessage(content=skill_section))

        # Create modified request using the override() method
        modified_request = request.override(messages=messages)

        # Call the handler with modified request
        return handler(modified_request)

    def before_model(
        self,
        state: SkillAwareState,
        runtime,
    ) -> dict[str, Any] | None:
        """Hook that runs before each model call.

        Caches loaded skills for use in wrap_model_call, which doesn't
        have direct access to state.

        Args:
            state: The current agent state
            runtime: The LangGraph runtime

        Returns:
            State updates or None
        """
        # Cache loaded skills for use in wrap_model_call
        # This is a workaround since wrap_model_call doesn't have direct state access
        loaded = state.get("skills_loaded", [])
        self._current_loaded_skills = loaded

        if loaded:
            logger.debug(f"Model call with loaded skills: {loaded}")
        return None

    def refresh_skills(self) -> None:
        """Force refresh of cached skill descriptions.

        Call this if skills have been added/removed from the registry
        and you want the changes reflected immediately.
        """
        self._cached_descriptions = None
