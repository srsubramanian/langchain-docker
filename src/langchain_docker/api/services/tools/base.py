"""Base class for tool providers."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Optional

from langchain_docker.api.services.hitl_tool_wrapper import HITLConfig

if TYPE_CHECKING:
    from langchain_docker.api.services.skill_registry import Skill, SkillRegistry

logger = logging.getLogger(__name__)

# Type aliases for tool function signatures
ToolFunc = Callable[..., str]
ToolFactory = Callable[..., ToolFunc]


@dataclass
class ToolParameter:
    """Parameter definition for a configurable tool."""

    name: str
    type: str  # "string", "int", "boolean"
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
    category: str
    parameters: list[ToolParameter] = field(default_factory=list)
    factory: ToolFactory | None = None
    requires_approval: Optional[HITLConfig] = None


class ToolProvider(ABC):
    """Abstract base class for domain-specific tool providers.

    Each provider is responsible for:
    - Managing tools for a specific domain (SQL, Jira, etc.)
    - Lazy-loading the associated skill
    - Creating tool factories
    - Registering tool templates

    Example:
        class MyToolProvider(ToolProvider):
            def get_skill_id(self) -> str:
                return "my_skill"

            def get_templates(self) -> list[ToolTemplate]:
                return [
                    ToolTemplate(
                        id="my_tool",
                        name="My Tool",
                        description="Does something",
                        category="my_category",
                        factory=self._create_my_tool,
                    ),
                ]

            def _create_my_tool(self) -> Callable[[], str]:
                skill = self.get_skill()
                def my_tool() -> str:
                    return skill.do_something()
                return my_tool
    """

    def __init__(self, skill_registry: "SkillRegistry"):
        """Initialize the tool provider.

        Args:
            skill_registry: Registry for loading skills
        """
        self._skill_registry = skill_registry
        self._skill: Optional["Skill"] = None

    @abstractmethod
    def get_skill_id(self) -> str:
        """Return the ID of the skill this provider uses.

        Returns:
            Skill identifier (e.g., "write_sql", "jira")
        """
        pass

    @abstractmethod
    def get_templates(self) -> list[ToolTemplate]:
        """Return all tool templates for this provider.

        Returns:
            List of ToolTemplate instances
        """
        pass

    def get_skill(self) -> "Skill":
        """Get the associated skill (lazy loaded).

        Returns:
            The skill instance for this provider
        """
        if self._skill is None:
            self._skill = self._skill_registry.get_skill(self.get_skill_id())
            logger.info(f"[{self.__class__.__name__}] Loaded skill: {self.get_skill_id()}")
        return self._skill

    def get_category(self) -> str:
        """Return the default category for tools from this provider.

        Override in subclasses if needed.

        Returns:
            Category name
        """
        skill = self.get_skill()
        return skill.category if skill else "general"
