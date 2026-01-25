"""Dependency injection for FastAPI."""

import logging
from functools import lru_cache

from fastapi import Depends, Header
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

from langchain_docker.api.services.agent_service import AgentService
from langchain_docker.api.services.approval_service import ApprovalService
from langchain_docker.api.services.chat_service import ChatService
from langchain_docker.api.services.embedding_service import EmbeddingService
from langchain_docker.api.services.knowledge_base_service import KnowledgeBaseService
from langchain_docker.api.services.mcp_server_manager import MCPServerManager
from langchain_docker.api.services.mcp_tool_service import MCPToolService
from langchain_docker.api.services.memory_service import MemoryService
from langchain_docker.api.services.model_service import ModelService
from langchain_docker.api.services.opensearch_store import OpenSearchStore
from langchain_docker.api.services.session_service import SessionService
from langchain_docker.api.services.capability_registry import CapabilityRegistry
from langchain_docker.api.services.skill_registry import SkillRegistry
from langchain_docker.api.services.workspace_service import WorkspaceService
from langchain_docker.core.config import (
    Config,
    get_redis_url,
    get_session_ttl_hours,
    is_graph_rag_enabled,
    is_neo4j_configured,
    is_opensearch_configured,
)

logger = logging.getLogger(__name__)


@lru_cache
def get_session_service() -> SessionService:
    """Get singleton session service instance.

    Uses Redis for persistent storage if REDIS_URL is configured,
    otherwise falls back to in-memory storage.

    Returns:
        SessionService instance
    """
    redis_url = get_redis_url()
    ttl_hours = get_session_ttl_hours()
    return SessionService(ttl_hours=ttl_hours, redis_url=redis_url)


# Singleton for checkpointer
_checkpointer: BaseCheckpointSaver | None = None


def get_checkpointer() -> BaseCheckpointSaver:
    """Get singleton checkpointer for LangGraph agent persistence.

    Uses RedisSaver if REDIS_URL is configured for production persistence,
    otherwise falls back to InMemorySaver for development/testing.

    The checkpointer enables:
    - Conversation persistence across agent invocations
    - Skill loading state tracking via SkillMiddleware
    - Human-in-the-loop workflows (future)

    Returns:
        BaseCheckpointSaver instance (RedisSaver or InMemorySaver)
    """
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    redis_url = get_redis_url()
    if redis_url:
        try:
            from langgraph.checkpoint.redis import RedisSaver

            # Create RedisSaver directly with URL (from_conn_string is a context manager)
            _checkpointer = RedisSaver(redis_url=redis_url)
            _checkpointer.setup()
            logger.info(f"LangGraph checkpointer using Redis: {redis_url}")
        except Exception as e:
            logger.warning(f"Failed to create RedisSaver, falling back to InMemorySaver: {e}")
            _checkpointer = InMemorySaver()
    else:
        _checkpointer = InMemorySaver()
        logger.info("LangGraph checkpointer using InMemorySaver (no Redis URL configured)")

    return _checkpointer


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


# Singleton for approval service (must be before get_chat_service)
_approval_service: ApprovalService | None = None


def get_approval_service() -> ApprovalService:
    """Get singleton approval service instance.

    The ApprovalService manages Human-in-the-Loop (HITL) approval requests
    for tools that require human confirmation before execution.

    Uses Redis for persistent storage if REDIS_URL is configured,
    otherwise falls back to in-memory storage.

    Returns:
        ApprovalService instance
    """
    global _approval_service
    if _approval_service is None:
        redis_url = get_redis_url()
        _approval_service = ApprovalService(redis_url=redis_url)
    return _approval_service


def get_chat_service(
    session_service: SessionService = Depends(get_session_service),
    model_service: ModelService = Depends(get_model_service),
    memory_service: MemoryService = Depends(get_memory_service),
    mcp_tool_service: MCPToolService = Depends(get_mcp_tool_service),
    approval_service: ApprovalService = Depends(get_approval_service),
) -> ChatService:
    """Get chat service instance.

    Args:
        session_service: Session service (injected)
        model_service: Model service (injected)
        memory_service: Memory service (injected)
        mcp_tool_service: MCP tool service (injected)
        approval_service: Approval service for HITL tools (injected)

    Returns:
        ChatService instance
    """
    # Get knowledge base service for RAG (optional)
    kb_service = get_knowledge_base_service()

    return ChatService(
        session_service,
        model_service,
        memory_service,
        mcp_tool_service,
        approval_service,
        kb_service,
    )


# Singleton for skill registry
_skill_registry: SkillRegistry | None = None


def get_skill_registry() -> SkillRegistry:
    """Get singleton skill registry instance.

    The SkillRegistry manages all available skills (SQL, etc.)
    using progressive disclosure pattern.

    When REDIS_URL is configured, skills are persisted with
    immutable version history and usage metrics tracking.

    Returns:
        SkillRegistry instance

    Note:
        This is kept for backward compatibility. New code should use
        get_capability_registry() instead.
    """
    global _skill_registry
    if _skill_registry is None:
        redis_url = get_redis_url()
        _skill_registry = SkillRegistry(redis_url=redis_url)
    return _skill_registry


# Singleton for capability registry
_capability_registry: CapabilityRegistry | None = None


def get_capability_registry() -> CapabilityRegistry:
    """Get singleton capability registry instance.

    The CapabilityRegistry is the unified registry for all agent capabilities,
    replacing the separate skill_registry and tool_registry. It provides:
    - Simple tools (math, weather, search, stock prices)
    - Skill bundles (SQL database, Jira integration, XLSX spreadsheets)

    Returns:
        CapabilityRegistry instance
    """
    global _capability_registry
    if _capability_registry is None:
        _capability_registry = CapabilityRegistry()
    return _capability_registry


# Singleton for workspace service (must be before agent service)
_workspace_service: WorkspaceService | None = None


def get_workspace_service() -> WorkspaceService:
    """Get singleton workspace service instance.

    The WorkspaceService provides session-specific working folders
    for file uploads, generated outputs, and temporary data.
    Similar to Claude Cowork's "Working Folder" feature.

    Returns:
        WorkspaceService instance
    """
    global _workspace_service
    if _workspace_service is None:
        _workspace_service = WorkspaceService()
        logger.info(f"WorkspaceService initialized with base_path={_workspace_service.base_path}")
    return _workspace_service


# Singleton for agent service
_agent_service: AgentService | None = None


def get_agent_service(
    model_service: ModelService = Depends(get_model_service),
    session_service: SessionService = Depends(get_session_service),
    memory_service: MemoryService = Depends(get_memory_service),
    skill_registry: SkillRegistry = Depends(get_skill_registry),
    approval_service: ApprovalService = Depends(get_approval_service),
    mcp_tool_service: MCPToolService = Depends(get_mcp_tool_service),
    workspace_service: WorkspaceService = Depends(get_workspace_service),
) -> AgentService:
    """Get agent service instance.

    Args:
        model_service: Model service (injected)
        session_service: Session service for unified memory (injected)
        memory_service: Memory service for summarization (injected)
        skill_registry: Skill registry (injected)
        approval_service: Approval service for HITL tool approval (injected)
        mcp_tool_service: MCP tool service for MCP tool integration (injected)
        workspace_service: Workspace service for file operations (injected)

    Returns:
        AgentService instance
    """
    global _agent_service
    if _agent_service is None:
        checkpointer = get_checkpointer()
        redis_url = get_redis_url()
        _agent_service = AgentService(
            model_service=model_service,
            session_service=session_service,
            memory_service=memory_service,
            skill_registry=skill_registry,
            checkpointer=checkpointer,
            redis_url=redis_url,
            approval_service=approval_service,
            mcp_tool_service=mcp_tool_service,
            workspace_service=workspace_service,
        )
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


# Singleton for embedding service
_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Get singleton embedding service instance.

    The EmbeddingService generates vector embeddings for documents
    and queries using OpenAI's text-embedding-3-small model.

    Returns:
        EmbeddingService instance
    """
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


# Singleton for opensearch store
_opensearch_store: OpenSearchStore | None = None


def get_opensearch_store(
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> OpenSearchStore:
    """Get singleton OpenSearch store instance.

    The OpenSearchStore provides vector similarity search for
    the knowledge base using OpenSearch's k-NN plugin.

    Args:
        embedding_service: Embedding service (injected)

    Returns:
        OpenSearchStore instance
    """
    global _opensearch_store
    if _opensearch_store is None:
        _opensearch_store = OpenSearchStore(embedding_service)
    return _opensearch_store


# Singleton for Graph RAG service
_graph_rag_service = None  # Type: GraphRAGService | None


def get_graph_rag_service():
    """Get singleton GraphRAG service instance.

    The GraphRAGService provides entity-aware retrieval using
    LlamaIndex PropertyGraphIndex with Neo4j as the graph store.

    Only initialized if GRAPH_RAG_ENABLED=true and Neo4j is configured.

    Returns:
        GraphRAGService instance or None if not configured
    """
    global _graph_rag_service

    # Only initialize once
    if _graph_rag_service is not None:
        return _graph_rag_service

    # Check if GraphRAG should be enabled
    if not is_graph_rag_enabled():
        logger.info("GraphRAG disabled (GRAPH_RAG_ENABLED=false)")
        return None

    if not is_neo4j_configured():
        logger.warning("GraphRAG enabled but Neo4j not configured (missing NEO4J_URL or NEO4J_PASSWORD)")
        return None

    try:
        from langchain_docker.api.services.graph_rag_service import GraphRAGService

        _graph_rag_service = GraphRAGService()
        if _graph_rag_service.is_available:
            logger.info("GraphRAGService initialized successfully")
        else:
            logger.warning(
                f"GraphRAGService initialization failed: {_graph_rag_service.initialization_error}"
            )
        return _graph_rag_service

    except ImportError as e:
        logger.error(f"Failed to import GraphRAGService (missing dependencies?): {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize GraphRAGService: {e}")
        return None


# Singleton for knowledge base service
_knowledge_base_service: KnowledgeBaseService | None = None


def get_knowledge_base_service() -> KnowledgeBaseService:
    """Get singleton knowledge base service instance.

    The KnowledgeBaseService provides high-level operations for
    document ingestion, search, and management. It orchestrates
    the document processor, embedding service, vector store, and
    optional GraphRAG service for entity-aware retrieval.

    Returns:
        KnowledgeBaseService instance (or None if not configured)
    """
    global _knowledge_base_service
    if _knowledge_base_service is None:
        # Get optional GraphRAG service
        graph_rag = get_graph_rag_service()

        if is_opensearch_configured():
            _knowledge_base_service = KnowledgeBaseService(
                graph_rag_service=graph_rag,
            )
            logger.info(
                f"KnowledgeBaseService initialized "
                f"(graph_rag={'enabled' if graph_rag and graph_rag.is_available else 'disabled'})"
            )
        else:
            logger.warning("OpenSearch not configured, knowledge base disabled")
            # Return a service instance anyway - it will report not available
            _knowledge_base_service = KnowledgeBaseService(
                graph_rag_service=graph_rag,
            )
    return _knowledge_base_service
