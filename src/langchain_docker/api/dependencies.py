"""Dependency injection for FastAPI."""

from functools import lru_cache

from fastapi import Depends

from langchain_docker.api.services.agent_service import AgentService
from langchain_docker.api.services.chat_service import ChatService
from langchain_docker.api.services.memory_service import MemoryService
from langchain_docker.api.services.model_service import ModelService
from langchain_docker.api.services.session_service import SessionService
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


def get_chat_service(
    session_service: SessionService = Depends(get_session_service),
    model_service: ModelService = Depends(get_model_service),
    memory_service: MemoryService = Depends(get_memory_service),
) -> ChatService:
    """Get chat service instance.

    Args:
        session_service: Session service (injected)
        model_service: Model service (injected)
        memory_service: Memory service (injected)

    Returns:
        ChatService instance
    """
    return ChatService(session_service, model_service, memory_service)


# Singleton for agent service
_agent_service: AgentService | None = None


def get_agent_service(
    model_service: ModelService = Depends(get_model_service),
) -> AgentService:
    """Get agent service instance.

    Args:
        model_service: Model service (injected)

    Returns:
        AgentService instance
    """
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService(model_service)
    return _agent_service
