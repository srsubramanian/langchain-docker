"""Dependency injection for FastAPI."""

from functools import lru_cache

from fastapi import Depends, Header

from langchain_docker.api.services.agent_service import AgentService
from langchain_docker.api.services.chat_service import ChatService
from langchain_docker.api.services.mcp_server_manager import MCPServerManager
from langchain_docker.api.services.mcp_tool_service import MCPToolService
from langchain_docker.api.services.memory_service import MemoryService
from langchain_docker.api.services.model_service import ModelService
from langchain_docker.api.services.session_service import SessionService
from langchain_docker.api.services.skill_registry import SkillRegistry
from langchain_docker.core.config import Config


@lru_cache
def get_session_service() -> SessionService:
    """Get singleton session service instance.

    Returns:
        SessionService instance
    """
    return SessionService()


@lru_cache
def get_model_service() -> ModelService:
    """Get singleton model service instance.

    Returns:
        ModelService instance
    """
    return ModelService()


@lru_cache
def get_memory_service(
    model_service: ModelService = Depends(get_model_service),
) -> MemoryService:
    """Get singleton memory service instance.

    Args:
        model_service: Model service (injected)

    Returns:
        MemoryService instance
    """
    config = Config.from_env()
    return MemoryService(config, model_service)


# Singleton for MCP server manager
_mcp_server_manager: MCPServerManager | None = None


def get_mcp_server_manager() -> MCPServerManager:
    """Get singleton MCP server manager instance.

    The MCPServerManager handles subprocess lifecycle for MCP servers
    and JSON-RPC communication over stdin/stdout.

    Returns:
        MCPServerManager instance
    """
    global _mcp_server_manager
    if _mcp_server_manager is None:
        _mcp_server_manager = MCPServerManager()
    return _mcp_server_manager


# Singleton for MCP tool service
_mcp_tool_service: MCPToolService | None = None


def get_mcp_tool_service(
    server_manager: MCPServerManager = Depends(get_mcp_server_manager),
) -> MCPToolService:
    """Get singleton MCP tool service instance.

    The MCPToolService handles tool discovery and LangChain integration
    for MCP servers.

    Args:
        server_manager: MCP server manager (injected)

    Returns:
        MCPToolService instance
    """
    global _mcp_tool_service
    if _mcp_tool_service is None:
        _mcp_tool_service = MCPToolService(server_manager)
    return _mcp_tool_service


def get_chat_service(
    session_service: SessionService = Depends(get_session_service),
    model_service: ModelService = Depends(get_model_service),
    memory_service: MemoryService = Depends(get_memory_service),
    mcp_tool_service: MCPToolService = Depends(get_mcp_tool_service),
) -> ChatService:
    """Get chat service instance.

    Args:
        session_service: Session service (injected)
        model_service: Model service (injected)
        memory_service: Memory service (injected)
        mcp_tool_service: MCP tool service (injected)

    Returns:
        ChatService instance
    """
    return ChatService(session_service, model_service, memory_service, mcp_tool_service)


# Singleton for skill registry
_skill_registry: SkillRegistry | None = None


def get_skill_registry() -> SkillRegistry:
    """Get singleton skill registry instance.

    The SkillRegistry manages all available skills (SQL, etc.)
    using progressive disclosure pattern.

    Returns:
        SkillRegistry instance
    """
    global _skill_registry
    if _skill_registry is None:
        _skill_registry = SkillRegistry()
    return _skill_registry


# Singleton for agent service
_agent_service: AgentService | None = None


def get_agent_service(
    model_service: ModelService = Depends(get_model_service),
    skill_registry: SkillRegistry = Depends(get_skill_registry),
) -> AgentService:
    """Get agent service instance.

    Args:
        model_service: Model service (injected)
        skill_registry: Skill registry (injected)

    Returns:
        AgentService instance
    """
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService(model_service, skill_registry)
    return _agent_service


# Default user ID when header is not provided
DEFAULT_USER_ID = "default"


def get_current_user_id(
    x_user_id: str | None = Header(None, alias="X-User-ID"),
) -> str:
    """Extract current user ID from request header.

    Args:
        x_user_id: User ID from X-User-ID header

    Returns:
        User ID string, defaults to "default" if not provided
    """
    return x_user_id or DEFAULT_USER_ID
