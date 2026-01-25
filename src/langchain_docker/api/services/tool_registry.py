"""Tool registry service for exposing tools as discoverable templates.

This module provides a centralized registry for tool templates that can be used
to build custom agents. Tools are organized by domain-specific providers.
"""

import logging
from typing import Any

from langchain_docker.api.services.tools.base import (
    ToolFunc,
    ToolParameter,
    ToolTemplate,
)
from langchain_docker.api.services.tools.chrome_perf_tools import ChromePerfToolProvider
from langchain_docker.api.services.tools.jira_tools import JiraToolProvider
from langchain_docker.api.services.tools.kb_tools import KBToolProvider, KBIngestToolProvider
from langchain_docker.api.services.tools.lighthouse_tools import LighthouseToolProvider
from langchain_docker.api.services.tools.sql_tools import SQLToolProvider
from langchain_docker.api.services.tools.web_perf_tools import WebPerformanceToolProvider
from langchain_docker.api.services.tools.workspace_tools import WorkspaceToolProvider

logger = logging.getLogger(__name__)

# Re-export for backwards compatibility
__all__ = [
    "ToolParameter",
    "ToolTemplate",
    "ToolRegistry",
    "ToolFunc",
]


class ToolRegistry:
    """Registry of available tool templates.

    Provides a discoverable catalog of tools that can be used to build
    custom agents. Tools are loaded from domain-specific providers.

    Example:
        registry = ToolRegistry()
        tools = registry.list_tools()
        sql_tools = registry.list_by_category("database")
        tool = registry.create_tool_instance("sql_query")
    """

    def __init__(self, workspace_service=None):
        """Initialize tool registry and load tools from providers.

        Args:
            workspace_service: Optional WorkspaceService for providers that need file access
        """
        self._tools: dict[str, ToolTemplate] = {}
        self._providers = []
        self._workspace_service = workspace_service
        self._load_providers(workspace_service=workspace_service)

    def _load_providers(self, workspace_service=None) -> None:
        """Load all tool providers and register their tools.

        Args:
            workspace_service: Optional WorkspaceService for providers that need file access
        """
        # Lazy import to avoid circular dependency
        from langchain_docker.api.services.skill_registry import SkillRegistry

        skill_registry = SkillRegistry()

        # Session ID getter that uses the context variable (set by AgentService)
        def get_session_id() -> str:
            from langchain_docker.api.services.agent_service import _current_session_id
            return _current_session_id.get()

        # Register all providers
        self._providers = [
            SQLToolProvider(skill_registry),
            JiraToolProvider(skill_registry),
            KBToolProvider(skill_registry),
            KBIngestToolProvider(skill_registry),
            WebPerformanceToolProvider(skill_registry),
            LighthouseToolProvider(skill_registry),
            # ChromePerfToolProvider needs workspace_service for file access
            ChromePerfToolProvider(skill_registry, workspace_service=workspace_service),
            # WorkspaceToolProvider for session file operations
            WorkspaceToolProvider(workspace_service, get_session_id) if workspace_service else None,
            # Add new providers here as they are created:
            # GithubToolProvider(skill_registry),
            # SlackToolProvider(skill_registry),
        ]
        # Filter out None providers (when workspace_service is not available)
        self._providers = [p for p in self._providers if p is not None]

        # Load tools from each provider
        for provider in self._providers:
            for template in provider.get_templates():
                self.register(template)
                logger.debug(f"Registered tool: {template.id} from {provider.__class__.__name__}")

        logger.info(f"ToolRegistry loaded {len(self._tools)} tools from {len(self._providers)} providers")

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
