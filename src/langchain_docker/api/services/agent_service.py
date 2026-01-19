"""Multi-agent orchestration service using LangGraph Supervisor."""

import logging
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langgraph_supervisor import create_supervisor

# Context variable for current session ID (used by HITL tools)
_current_session_id: ContextVar[str] = ContextVar("current_session_id", default="")

from langchain_docker.api.services.capability_registry import CapabilityRegistry
from langchain_docker.api.services.model_service import ModelService
from langchain_docker.api.services.tool_registry import ToolRegistry
from langchain_docker.api.services.session_service import SessionService
from langchain_docker.api.services.hitl_tool_wrapper import HITLConfig
from langchain_docker.core.tracing import trace_operation, get_tracer

# Import middleware-based skills components
from langchain_docker.skills.middleware import (
    SkillRegistry as MiddlewareSkillRegistry,
    SkillMiddleware,
    SkillAwareState,
    create_load_skill_tool,
    create_gated_tools_for_skill,
)

logger = logging.getLogger(__name__)


@dataclass
class ScheduleConfig:
    """Schedule configuration for an agent."""

    enabled: bool
    cron_expression: str
    trigger_prompt: str
    timezone: str = "UTC"


@dataclass
class CustomAgent:
    """Custom agent definition created by users."""

    id: str
    name: str
    system_prompt: str
    tool_configs: list[dict]  # [{"tool_id": str, "config": dict}, ...]
    created_at: datetime
    skill_ids: list[str] = field(default_factory=list)  # Skills to include
    schedule: Optional[ScheduleConfig] = None  # Schedule configuration
    metadata: dict = field(default_factory=dict)
    provider: str = "openai"  # Model provider (openai, anthropic, google, bedrock)
    model: Optional[str] = None  # Specific model name (uses provider default if None)
    temperature: float = 0.7  # Temperature for responses


# Agent configurations - tools are referenced by ID and resolved via ToolRegistry
# Note: sql_expert is created dynamically in AgentService using SkillRegistry
BUILTIN_AGENTS = {
    # Built-in agents can be added here if needed
    # Example:
    # "example_agent": {
    #     "name": "example_agent",
    #     "tool_ids": ["tool1", "tool2"],
    #     "prompt": "You are an example agent...",
    # },
}

DEFAULT_SUPERVISOR_PROMPT = """You are a team supervisor managing a group of specialized agents.
Your job is to:
1. Understand the user's request
2. Delegate tasks to the appropriate specialist agent(s)
3. Synthesize their responses into a coherent answer

Available specialists:
{agent_descriptions}

Always delegate to the most appropriate specialist. If a task requires multiple specialists, coordinate their work."""


class AgentService:
    """Service for creating and managing multi-agent workflows.

    Supports both built-in agents and custom user-defined agents.
    Custom agents can be persisted to Redis for durability across restarts.
    """

    def __init__(
        self,
        model_service: ModelService,
        session_service: Optional[SessionService] = None,
        memory_service=None,  # Type: MemoryService (optional to avoid circular import)
        skill_registry=None,
        scheduler_service=None,
        checkpointer=None,  # Type: BaseCheckpointSaver (optional for agent persistence)
        redis_url: Optional[str] = None,  # Redis URL for persistent agent storage
        approval_service=None,  # Type: ApprovalService (optional for HITL support)
    ):
        """Initialize agent service.

        Args:
            model_service: Model service for LLM access
            session_service: Session service for unified memory management
            memory_service: Memory service for conversation summarization
            skill_registry: Skill registry for progressive disclosure skills (legacy)
            scheduler_service: Scheduler service for cron-based execution
            checkpointer: LangGraph checkpointer for agent state persistence
            redis_url: Redis URL for persistent custom agent storage (optional)
            approval_service: Approval service for HITL tool approval (optional)
        """
        self.model_service = model_service
        self.session_service = session_service
        self.memory_service = memory_service
        self._checkpointer = checkpointer
        self._approval_service = approval_service
        self._workflows: dict[str, Any] = {}
        self._custom_agents: dict[str, CustomAgent] = {}
        self._direct_sessions: dict[str, dict] = {}  # Legacy: For backward compatibility
        self._tool_registry = ToolRegistry()
        self._capability_registry = CapabilityRegistry()

        # Initialize Redis agent store if URL provided
        self._agent_store = None
        if redis_url:
            from langchain_docker.api.services.redis_agent_store import RedisAgentStore
            self._agent_store = RedisAgentStore(redis_url)
            self._load_agents_from_redis()

        # Import legacy SkillRegistry for backward compatibility
        if skill_registry is None:
            from langchain_docker.api.services.skill_registry import SkillRegistry
            skill_registry = SkillRegistry()
        self._skill_registry = skill_registry

        # Initialize middleware-based skill registry
        self._middleware_skill_registry = MiddlewareSkillRegistry()
        self._setup_middleware_skills()

        # Create skill middleware for agents
        self._skill_middleware = SkillMiddleware(
            registry=self._middleware_skill_registry,
            description_format="list",
            auto_refresh_skills=False,
        )

        # Setup scheduler service
        if scheduler_service is None:
            from langchain_docker.api.services.scheduler_service import SchedulerService
            scheduler_service = SchedulerService()
        self._scheduler_service = scheduler_service
        self._scheduler_service.set_execution_callback(self._execute_scheduled_agent)
        self._scheduler_service.start()

        # Create dynamic agents from skill registry
        self._dynamic_agents = self._create_skill_based_agents()

    def _setup_middleware_skills(self) -> None:
        """Setup middleware-based skills by converting legacy skills.

        This bridges the legacy SkillRegistry with the new middleware-based
        SkillRegistry using the load_from_legacy() method.
        """
        count = self._middleware_skill_registry.load_from_legacy(self._skill_registry)
        logger.info(f"Initialized {count} middleware skills: {[s.id for s in self._middleware_skill_registry.list_skills()]}")

    def _load_agents_from_redis(self) -> None:
        """Load all custom agents from Redis into memory cache.

        This is called on startup when Redis is configured to restore
        agents from persistent storage.
        """
        if self._agent_store is None:
            return

        try:
            agents = self._agent_store.list_all()
            for agent in agents:
                self._custom_agents[agent.id] = agent
            logger.info(f"Loaded {len(agents)} custom agents from Redis")
        except Exception as e:
            logger.error(f"Failed to load agents from Redis: {e}")

    def _save_agent_to_redis(self, agent: CustomAgent) -> None:
        """Save a custom agent to Redis if store is configured.

        Args:
            agent: CustomAgent to persist
        """
        if self._agent_store is not None:
            try:
                self._agent_store.save(agent)
            except Exception as e:
                logger.error(f"Failed to save agent {agent.id} to Redis: {e}")

    def _delete_agent_from_redis(self, agent_id: str) -> None:
        """Delete a custom agent from Redis if store is configured.

        Args:
            agent_id: Agent ID to delete
        """
        if self._agent_store is not None:
            try:
                self._agent_store.delete(agent_id)
            except Exception as e:
                logger.error(f"Failed to delete agent {agent_id} from Redis: {e}")

    def _create_skill_based_agents(self) -> dict:
        """Create agents from registered skills.

        Returns:
            Dictionary of skill-based agent configurations

        Note:
            This method creates agent configurations. When agents are actually
            built (via _build_agent_from_custom or create_workflow), the
            SkillMiddleware is attached to enable skill state tracking.
        """
        agents = {}

        # Get SQL skill if available
        from langchain_docker.api.services.skill_registry import SQLSkill
        skill = self._skill_registry.get_skill("write_sql")
        if skill and isinstance(skill, SQLSkill):
            sql_skill: SQLSkill = skill  # Type hint for IDE

            # Create tool functions that use the skill
            # Note: These are non-gated tools for backward compatibility
            # When using middleware, gated tools are preferred
            def load_sql_skill() -> str:
                """Load the SQL skill with database schema and guidelines."""
                tracer = get_tracer()
                if tracer:
                    with tracer.start_as_current_span("skill.load_core") as span:
                        span.set_attribute("skill.id", "write_sql")
                        span.set_attribute("skill.name", sql_skill.name)
                        span.set_attribute("skill.category", sql_skill.category)
                        content = sql_skill.load_core()
                        span.set_attribute("content_length", len(content))
                        return content
                return sql_skill.load_core()

            def sql_query(query: str) -> str:
                """Execute a SQL query against the database."""
                return sql_skill.execute_query(query)

            def sql_list_tables() -> str:
                """List all available tables in the database."""
                return sql_skill.list_tables()

            def sql_get_samples() -> str:
                """Get sample rows from database tables."""
                return sql_skill.load_details("samples")

            agents["sql_expert"] = {
                "name": "sql_expert",
                "tools": [load_sql_skill, sql_query, sql_list_tables, sql_get_samples],
                "prompt": f"""You are a SQL expert assistant that helps users query databases.

{self._skill_registry.get_skill_summary()}

When a user asks about data:
1. First call load_sql_skill() to get the database schema
2. Write appropriate SQL queries using sql_query()
3. Explain query results clearly to users

Guidelines:
- Always load the skill first to understand the database schema
- Use sql_list_tables() if you need a quick overview of available tables
- Use sql_get_samples() to see sample data from tables
- Write clean, readable SQL queries with explicit column names
- Explain your queries and results in plain language""",
                "use_middleware": True,  # Flag to enable middleware for this agent
                "required_skill": "write_sql",  # Skill this agent is based on
            }

        return agents

    def create_middleware_enabled_agent(
        self,
        agent_name: str,
        llm,
        tools: list,
        system_prompt: str,
        use_skills: bool = True,
        middleware=None,
    ):
        """Create an agent with SkillMiddleware enabled.

        This method creates agents that:
        1. Have skill descriptions automatically injected into system prompts
        2. Track loaded skills in state (preventing duplicates)
        3. Include load_skill and list_loaded_skills tools
        4. Persist state across invocations via checkpointer (if configured)

        Args:
            agent_name: Name for the agent
            llm: Language model to use
            tools: List of tools for the agent
            system_prompt: System prompt for the agent
            use_skills: Whether to attach SkillMiddleware
            middleware: Optional custom middleware to use. If None, uses default.

        Returns:
            Compiled agent graph with middleware and checkpointing
        """
        if use_skills:
            # Use custom middleware if provided, otherwise use shared default
            skill_middleware = middleware if middleware is not None else self._skill_middleware

            # Create agent with skill middleware and optional checkpointing
            # Middleware tools (load_skill, list_loaded_skills) are automatically added
            agent = create_agent(
                model=llm,
                tools=tools,
                name=agent_name,
                system_prompt=system_prompt,
                middleware=[skill_middleware],
                checkpointer=self._checkpointer,
            )
        else:
            # Create agent without middleware but with checkpointing
            agent = create_agent(
                model=llm,
                tools=tools,
                name=agent_name,
                system_prompt=system_prompt,
                checkpointer=self._checkpointer,
            )

        return agent

    def _get_all_builtin_agents(self) -> dict:
        """Get all builtin agents including dynamic skill-based ones.

        Returns:
            Combined dictionary of static and dynamic agents
        """
        return {**BUILTIN_AGENTS, **self._dynamic_agents}

    def list_builtin_agents(self) -> list[dict]:
        """List all available built-in agents.

        Returns:
            List of agent configurations
        """
        all_agents = self._get_all_builtin_agents()
        result = []
        for config in all_agents.values():
            # Handle both tool_ids (new style) and tools (dynamic agents)
            if "tool_ids" in config:
                tool_names = config["tool_ids"]
            else:
                tool_names = [t.__name__ for t in config["tools"]]
            result.append({
                "name": config["name"],
                "tools": tool_names,
                "description": config["prompt"][:100] + "...",
            })
        return result

    # Tool Registry Methods

    def get_tool_registry(self) -> ToolRegistry:
        """Get the tool registry.

        Returns:
            ToolRegistry instance
        """
        return self._tool_registry

    def list_tool_templates(self) -> list[dict]:
        """List all available tool templates.

        Returns:
            List of tool templates with metadata
        """
        return self._tool_registry.to_dict_list()

    def list_tool_categories(self) -> list[str]:
        """List all tool categories.

        Returns:
            List of category names
        """
        return self._tool_registry.get_categories()

    # Capability Registry Methods

    def get_capability_registry(self) -> CapabilityRegistry:
        """Get the capability registry.

        Returns:
            CapabilityRegistry instance
        """
        return self._capability_registry

    def list_capabilities(self) -> list[dict]:
        """List all available capabilities (unified tools and skills).

        Returns:
            List of capabilities with metadata
        """
        return self._capability_registry.to_dict_list()

    def list_capability_categories(self) -> list[str]:
        """List all capability categories.

        Returns:
            List of category names
        """
        return self._capability_registry.get_categories()

    def get_hitl_config_for_tool(self, tool_id: str):
        """Get HITL configuration for a tool.

        Checks both ToolRegistry and CapabilityRegistry for HITL configs.

        Args:
            tool_id: Tool identifier

        Returns:
            HITLConfig if tool requires approval, None otherwise
        """
        # Check ToolRegistry first
        tool_template = self._tool_registry.get_tool(tool_id)
        if tool_template and tool_template.requires_approval:
            return tool_template.requires_approval

        # Check CapabilityRegistry
        hitl_config = self._capability_registry.get_hitl_config(tool_id)
        if hitl_config:
            return hitl_config

        return None

    def _is_hitl_pending(self, output: str) -> bool:
        """Check if tool output indicates HITL pending status.

        Args:
            output: Tool output string

        Returns:
            True if output contains HITL pending marker
        """
        return isinstance(output, str) and output.startswith("__HITL_PENDING__:")

    def _extract_approval_id(self, output: str) -> Optional[str]:
        """Extract approval ID from HITL pending output.

        Args:
            output: Tool output string

        Returns:
            Approval ID if present, None otherwise
        """
        if not self._is_hitl_pending(output):
            return None
        return output.split(":", 1)[1] if ":" in output else None

    def _create_hitl_aware_tool(
        self,
        tool_func: Callable,
        tool_name: str,
        hitl_config: HITLConfig,
    ) -> Callable:
        """Create an HITL-aware wrapper for a tool.

        The wrapper creates an approval request before executing the tool.
        If not approved, returns a pending marker that triggers approval UI.
        Uses the context variable _current_session_id set at invocation time.

        Args:
            tool_func: Original tool function
            tool_name: Name of the tool
            hitl_config: HITL configuration

        Returns:
            Wrapped tool function that handles HITL flow
        """
        approval_service = self._approval_service

        def hitl_wrapper(*args, **kwargs) -> str:
            if not approval_service:
                # No approval service, execute directly
                return tool_func(*args, **kwargs)

            # Get session_id from context variable
            session_id = _current_session_id.get()
            if not session_id:
                logger.warning(f"No session_id in context for HITL tool {tool_name}, executing directly")
                return tool_func(*args, **kwargs)

            # Build tool args for display
            tool_args = {}
            if args:
                tool_args["args"] = list(args)
            if kwargs:
                tool_args.update(kwargs)

            # Create approval request
            from langchain_docker.api.services.approval_service import ApprovalConfig
            import uuid

            tool_call_id = str(uuid.uuid4())
            approval = approval_service.create(
                tool_call_id=tool_call_id,
                session_id=session_id,
                thread_id=session_id,  # Use session_id as thread_id
                tool_name=tool_name,
                tool_args=tool_args if hitl_config.show_args else {},
                config=ApprovalConfig(
                    message=hitl_config.message,
                    show_args=hitl_config.show_args,
                    timeout_seconds=hitl_config.timeout_seconds,
                    require_reason_on_reject=hitl_config.require_reason_on_reject,
                ),
            )

            logger.info(f"HITL approval requested: {approval.id} for {tool_name} in session {session_id}")
            return f"__HITL_PENDING__:{approval.id}"

        # Copy function metadata
        hitl_wrapper.__name__ = tool_func.__name__
        hitl_wrapper.__doc__ = (tool_func.__doc__ or "") + " [Requires approval]"

        return hitl_wrapper

    def _create_tool_with_hitl_check(
        self,
        tool_id: str,
        tool_config: Optional[dict] = None,
    ) -> Callable:
        """Create a tool instance, wrapping with HITL if needed.

        Checks if the tool has HITL config and wraps it accordingly.
        The HITL wrapper uses the context variable for session_id.

        Args:
            tool_id: Tool identifier
            tool_config: Optional tool configuration

        Returns:
            Tool function (wrapped with HITL if needed)
        """
        # Create the base tool
        tool_func = self._tool_registry.create_tool_instance(tool_id, tool_config)

        # Check for HITL config
        hitl_config = self.get_hitl_config_for_tool(tool_id)
        if hitl_config and hitl_config.enabled:
            # Wrap with HITL
            return self._create_hitl_aware_tool(tool_func, tool_id, hitl_config)

        return tool_func

    def get_tools_for_capabilities(
        self,
        capability_ids: list[str],
        configs: Optional[dict[str, dict]] = None,
    ) -> list[Callable]:
        """Get all tools for a list of capabilities.

        Args:
            capability_ids: List of capability IDs to get tools from
            configs: Optional dict mapping capability_id to config dict

        Returns:
            List of tool functions

        Raises:
            ValueError: If any capability_id is invalid
        """
        configs = configs or {}
        tools = []
        for cap_id in capability_ids:
            cap_tools = self._capability_registry.get_tools_for_capability(
                cap_id,
                configs.get(cap_id),
            )
            tools.extend(cap_tools)
        return tools

    # Custom Agent Methods

    def create_custom_agent(
        self,
        agent_id: str,
        name: str,
        system_prompt: str,
        tool_configs: list[dict],
        skill_ids: Optional[list[str]] = None,
        schedule_config: Optional[dict] = None,
        metadata: Optional[dict] = None,
        provider: str = "openai",
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> CustomAgent:
        """Create a custom agent from tool selections and skills.

        Args:
            agent_id: Unique identifier for the agent
            name: Human-readable agent name
            system_prompt: System prompt defining agent behavior
            tool_configs: List of tool configurations [{"tool_id": str, "config": dict}]
            skill_ids: List of skill IDs to include (their context will be added)
            schedule_config: Optional schedule configuration dict with:
                - enabled: bool
                - cron_expression: str (e.g., "0 9 * * *")
                - trigger_prompt: str
                - timezone: str (default: "UTC")
            metadata: Optional additional metadata
            provider: Model provider to use (openai, anthropic, google, bedrock)
            model: Specific model name (uses provider default if None)
            temperature: Temperature for model responses (0.0-2.0)

        Returns:
            Created CustomAgent

        Raises:
            ValueError: If any tool_id or skill_id is invalid
        """
        # Validate tool configs
        for tc in tool_configs:
            tool_id = tc.get("tool_id")
            if not self._tool_registry.get_tool(tool_id):
                available = [t.id for t in self._tool_registry.list_tools()]
                raise ValueError(f"Unknown tool: {tool_id}. Available: {available}")

        # Validate skill_ids
        skill_ids = skill_ids or []
        for skill_id in skill_ids:
            if not self._skill_registry.get_skill(skill_id):
                available = [s['id'] for s in self._skill_registry.list_skills()]
                raise ValueError(f"Unknown skill: {skill_id}. Available: {available}")

        # Create schedule config if provided
        schedule = None
        if schedule_config:
            schedule = ScheduleConfig(
                enabled=schedule_config.get("enabled", False),
                cron_expression=schedule_config["cron_expression"],
                trigger_prompt=schedule_config["trigger_prompt"],
                timezone=schedule_config.get("timezone", "UTC"),
            )

        agent = CustomAgent(
            id=agent_id,
            name=name,
            system_prompt=system_prompt,
            tool_configs=tool_configs,
            created_at=datetime.utcnow(),
            skill_ids=skill_ids,
            schedule=schedule,
            metadata=metadata or {},
            provider=provider,
            model=model,
            temperature=temperature,
        )
        self._custom_agents[agent_id] = agent

        # Persist to Redis if configured
        self._save_agent_to_redis(agent)

        # Register schedule if provided
        if schedule:
            self._scheduler_service.add_schedule(
                agent_id=agent_id,
                cron_expression=schedule.cron_expression,
                trigger_prompt=schedule.trigger_prompt,
                timezone=schedule.timezone,
                enabled=schedule.enabled,
            )

        logger.info(
            f"Created custom agent: {agent_id} ({name}) with {len(skill_ids)} skills"
            + (f", scheduled: {schedule.cron_expression}" if schedule and schedule.enabled else "")
        )
        return agent

    def _execute_scheduled_agent(self, agent_id: str, trigger_prompt: str) -> None:
        """Execute a scheduled agent with the trigger prompt.

        This is called by the scheduler service when a cron trigger fires.

        Args:
            agent_id: The agent to execute
            trigger_prompt: The prompt to send
        """
        agent = self._custom_agents.get(agent_id)
        if not agent:
            logger.error(f"Scheduled agent not found: {agent_id}")
            return

        try:
            # Create a simple workflow for this agent and invoke it
            workflow_id = f"_scheduled_{agent_id}_{datetime.utcnow().timestamp()}"

            # Build the agent using the agent's configured provider/model/temperature
            llm = self.model_service.get_or_create(
                provider=agent.provider,
                model=agent.model,
                temperature=agent.temperature,
            )

            # Invoke the agent directly
            agent_graph = self._build_agent_from_custom(agent_id, llm)
            compiled = agent_graph.compile() if hasattr(agent_graph, 'compile') else agent_graph

            with trace_operation(
                session_id=workflow_id,
                operation="scheduled_agent",
                metadata={
                    "agent_id": agent_id,
                    "scheduled": True,
                    "provider": agent.provider,
                    "model": agent.model,
                },
                tags=["agent", "scheduled", agent.provider],
            ):
                result = compiled.invoke(
                    {"messages": [HumanMessage(content=trigger_prompt)]},
                    config={
                        "configurable": {"thread_id": workflow_id},
                        "metadata": {"agent_id": agent_id, "scheduled": True},
                    },
                )

            # Log the result
            messages = result.get("messages", [])
            final_response = messages[-1].content if messages else "No response"
            logger.info(f"Scheduled execution completed for {agent_id}: {final_response[:100]}...")

        except Exception as e:
            logger.error(f"Scheduled execution failed for {agent_id}: {e}")

    def get_agent_schedule(self, agent_id: str) -> Optional[dict]:
        """Get schedule info for an agent.

        Args:
            agent_id: Agent ID

        Returns:
            Schedule info dict or None
        """
        return self._scheduler_service.get_schedule(agent_id)

    def update_agent_schedule(
        self,
        agent_id: str,
        enabled: Optional[bool] = None,
        cron_expression: Optional[str] = None,
        trigger_prompt: Optional[str] = None,
        timezone: Optional[str] = None,
    ) -> Optional[dict]:
        """Update schedule for an agent.

        Args:
            agent_id: Agent ID
            enabled: New enabled state
            cron_expression: New cron expression
            trigger_prompt: New trigger prompt
            timezone: New timezone

        Returns:
            Updated schedule info or None if agent not found
        """
        agent = self._custom_agents.get(agent_id)
        if not agent:
            return None

        current = self._scheduler_service.get_schedule(agent_id)

        # Build updated config
        new_config = {
            "enabled": enabled if enabled is not None else (current.get("enabled", False) if current else False),
            "cron_expression": cron_expression or (current.get("cron_expression") if current else None),
            "trigger_prompt": trigger_prompt or (current.get("trigger_prompt") if current else None),
            "timezone": timezone or (current.get("timezone", "UTC") if current else "UTC"),
        }

        if not new_config["cron_expression"] or not new_config["trigger_prompt"]:
            return None

        # Update agent's schedule
        agent.schedule = ScheduleConfig(
            enabled=new_config["enabled"],
            cron_expression=new_config["cron_expression"],
            trigger_prompt=new_config["trigger_prompt"],
            timezone=new_config["timezone"],
        )

        # Update scheduler
        return self._scheduler_service.add_schedule(
            agent_id=agent_id,
            cron_expression=new_config["cron_expression"],
            trigger_prompt=new_config["trigger_prompt"],
            timezone=new_config["timezone"],
            enabled=new_config["enabled"],
        )

    def get_custom_agent(self, agent_id: str) -> Optional[CustomAgent]:
        """Get a custom agent by ID.

        Args:
            agent_id: Agent identifier

        Returns:
            CustomAgent if found, None otherwise
        """
        return self._custom_agents.get(agent_id)

    def list_custom_agents(self) -> list[dict]:
        """List all custom agents.

        Returns:
            List of custom agent info
        """
        result = []
        for a in self._custom_agents.values():
            agent_dict = {
                "id": a.id,
                "name": a.name,
                "tools": [tc["tool_id"] for tc in a.tool_configs],
                "skills": a.skill_ids,
                "description": a.system_prompt[:100] + "..." if len(a.system_prompt) > 100 else a.system_prompt,
                "created_at": a.created_at.isoformat(),
                "schedule": None,
                "provider": a.provider,
                "model": a.model,
                "temperature": a.temperature,
            }
            # Include schedule info if present
            if a.schedule:
                schedule_data = self.get_agent_schedule(a.id)
                agent_dict["schedule"] = {
                    "enabled": a.schedule.enabled,
                    "cron_expression": a.schedule.cron_expression,
                    "trigger_prompt": a.schedule.trigger_prompt,
                    "timezone": a.schedule.timezone,
                    "next_run": schedule_data.get("next_run") if schedule_data else None,
                }
            result.append(agent_dict)
        return result

    def update_custom_agent(
        self,
        agent_id: str,
        name: Optional[str] = None,
        system_prompt: Optional[str] = None,
        tool_configs: Optional[list[dict]] = None,
        skill_ids: Optional[list[str]] = None,
        schedule_config: Optional[dict] = None,
        metadata: Optional[dict] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> CustomAgent:
        """Update an existing custom agent.

        Only provided fields are updated; others remain unchanged.
        Updating the agent clears any cached compiled agent so the
        next invocation uses the new configuration.

        Args:
            agent_id: ID of the agent to update
            name: New agent name
            system_prompt: New system prompt
            tool_configs: New tool configurations [{"tool_id": str, "config": dict}]
            skill_ids: New skill IDs to include
            schedule_config: New schedule configuration
            metadata: New metadata
            provider: New model provider (openai, anthropic, google, bedrock)
            model: New model name
            temperature: New temperature (0.0-2.0)

        Returns:
            Updated CustomAgent

        Raises:
            ValueError: If agent not found or invalid tool_id/skill_id
        """
        if agent_id not in self._custom_agents:
            raise ValueError(f"Custom agent not found: {agent_id}")

        agent = self._custom_agents[agent_id]

        # Validate and update tool configs if provided
        if tool_configs is not None:
            for tc in tool_configs:
                tool_id = tc.get("tool_id")
                if not self._tool_registry.get_tool(tool_id):
                    available = [t.id for t in self._tool_registry.list_tools()]
                    raise ValueError(f"Unknown tool: {tool_id}. Available: {available}")
            agent.tool_configs = tool_configs

        # Validate and update skill_ids if provided
        if skill_ids is not None:
            for skill_id in skill_ids:
                if not self._skill_registry.get_skill(skill_id):
                    available = [s['id'] for s in self._skill_registry.list_skills()]
                    raise ValueError(f"Unknown skill: {skill_id}. Available: {available}")
            agent.skill_ids = skill_ids

        # Update simple fields if provided
        if name is not None:
            agent.name = name
        if system_prompt is not None:
            agent.system_prompt = system_prompt
        if metadata is not None:
            agent.metadata = metadata
        if provider is not None:
            agent.provider = provider
        if model is not None:
            agent.model = model
        if temperature is not None:
            agent.temperature = temperature

        # Handle schedule update
        if schedule_config is not None:
            # Remove old schedule first
            self._scheduler_service.remove_schedule(agent_id)

            if schedule_config:
                agent.schedule = ScheduleConfig(
                    enabled=schedule_config.get("enabled", False),
                    cron_expression=schedule_config["cron_expression"],
                    trigger_prompt=schedule_config["trigger_prompt"],
                    timezone=schedule_config.get("timezone", "UTC"),
                )
                # Register new schedule
                self._scheduler_service.add_schedule(
                    agent_id=agent_id,
                    cron_expression=agent.schedule.cron_expression,
                    trigger_prompt=agent.schedule.trigger_prompt,
                    timezone=agent.schedule.timezone,
                    enabled=agent.schedule.enabled,
                )
            else:
                agent.schedule = None

        # Clear cached compiled agent to force rebuild with new config
        cache_key = f"unified:{agent_id}"
        if cache_key in self._direct_sessions:
            del self._direct_sessions[cache_key]

        # Persist to Redis if configured
        self._save_agent_to_redis(agent)

        logger.info(f"Updated custom agent: {agent_id} ({agent.name})")
        return agent

    def delete_custom_agent(self, agent_id: str) -> bool:
        """Delete a custom agent.

        Args:
            agent_id: Agent to delete

        Returns:
            True if deleted, False if not found
        """
        if agent_id in self._custom_agents:
            # Remove any associated schedule
            self._scheduler_service.remove_schedule(agent_id)
            del self._custom_agents[agent_id]
            # Delete from Redis if configured
            self._delete_agent_from_redis(agent_id)
            logger.info(f"Deleted custom agent: {agent_id}")
            return True
        return False

    def _sanitize_agent_name(self, name: str) -> str:
        """Sanitize agent name for OpenAI compatibility.

        OpenAI requires names to match pattern: ^[^\\s<|\\\\/>]+
        (no spaces or special characters like <, |, \\, /, >)

        Args:
            name: Original agent name

        Returns:
            Sanitized name safe for OpenAI
        """
        import re
        # Replace spaces and hyphens with underscores
        safe_name = name.replace(" ", "_").replace("-", "_")
        # Remove any other problematic characters
        safe_name = re.sub(r'[<|\\/>]', '', safe_name)
        # Remove any consecutive underscores
        safe_name = re.sub(r'_+', '_', safe_name)
        return safe_name.strip("_")

    def _build_agent_from_custom(
        self,
        agent_id: str,
        llm,
        use_middleware: bool = False,
    ) -> Any:
        """Build a LangChain agent from a custom agent definition.

        Args:
            agent_id: Custom agent ID
            llm: Language model to use
            use_middleware: Whether to use SkillMiddleware for skill management.
                If True, skills are managed via middleware (load_skill tool).
                If False, skill content is directly added to system prompt.

        Returns:
            Compiled agent graph

        Raises:
            ValueError: If agent not found
        """
        custom = self._custom_agents.get(agent_id)
        if not custom:
            raise ValueError(f"Custom agent not found: {agent_id}")

        # Create tool instances from configurations, with HITL wrapping if needed
        tools = []
        for tc in custom.tool_configs:
            tool = self._create_tool_with_hitl_check(
                tc["tool_id"],
                tc.get("config", {}),
            )
            tools.append(tool)

        # Build system prompt
        system_prompt = custom.system_prompt

        # Sanitize name for OpenAI compatibility
        safe_name = self._sanitize_agent_name(custom.name)

        # Automatically use middleware when agent has skills
        if custom.skill_ids:
            # Use middleware pattern: skills are loaded dynamically via load_skill tool
            # The middleware will:
            # 1. Inject skill descriptions into system prompt
            # 2. Track loaded skills in state
            # 3. Provide load_skill and list_loaded_skills tools

            # Add domain tools from each skill's capability
            for skill_id in custom.skill_ids:
                try:
                    skill_tools = self._capability_registry.get_tools_for_capability(
                        skill_id, None
                    )
                    tools.extend(skill_tools)
                    tool_names = [getattr(t, '__name__', str(t)) for t in skill_tools]
                    logger.info(f"Added {len(skill_tools)} tools from skill {skill_id}: {tool_names}")
                except Exception as e:
                    logger.warning(f"Failed to get tools for skill {skill_id}: {e}")

            # Add hint about available skills to the prompt
            skill_names = ", ".join(custom.skill_ids)
            system_prompt += f"\n\n# Available Skills\nYou have access to the following skills: {skill_names}\nUse the load_skill tool to load a skill before using its domain tools."

            logger.info(f"Creating agent {custom.name} with {len(tools)} total tools, skills: {custom.skill_ids}")

            # Create per-agent middleware with skill filter to only show assigned skills
            from langchain_docker.skills.middleware import SkillMiddleware
            agent_middleware = SkillMiddleware(
                registry=self._middleware_skill_registry,
                description_format="list",
                auto_refresh_skills=False,
                skill_filter=custom.skill_ids,  # Only show assigned skills
            )

            return self.create_middleware_enabled_agent(
                agent_name=safe_name,
                llm=llm,
                tools=tools,
                system_prompt=system_prompt,
                use_skills=True,
                middleware=agent_middleware,  # Use filtered middleware
            )
        else:
            # Legacy pattern: Add skill tools and context
            if custom.skill_ids:
                skill_contexts = []
                for skill_id in custom.skill_ids:
                    skill = self._skill_registry.get_skill(skill_id)
                    if skill:
                        # Add skill tools based on skill type
                        from langchain_docker.api.services.skill_registry import SQLSkill
                        if isinstance(skill, SQLSkill):
                            sql_skill = skill  # Capture for closures

                            def load_sql_skill() -> str:
                                """Load the SQL skill with database schema and guidelines."""
                                tracer = get_tracer()
                                if tracer:
                                    with tracer.start_as_current_span("skill.load_core") as span:
                                        span.set_attribute("skill.id", "write_sql")
                                        span.set_attribute("skill.name", sql_skill.name)
                                        span.set_attribute("skill.category", sql_skill.category)
                                        content = sql_skill.load_core()
                                        span.set_attribute("content_length", len(content))
                                        return content
                                return sql_skill.load_core()

                            def sql_query(query: str) -> str:
                                """Execute a SQL query against the database."""
                                return sql_skill.execute_query(query)

                            def sql_list_tables() -> str:
                                """List all available tables in the database."""
                                return sql_skill.list_tables()

                            def sql_get_samples() -> str:
                                """Get sample rows from database tables."""
                                return sql_skill.load_details("samples")

                            # Add skill tools
                            tools.extend([load_sql_skill, sql_query, sql_list_tables, sql_get_samples])

                            # Add context about using tools
                            skill_contexts.append(f"""
## {skill.name} Skill

You have access to SQL tools. Follow this workflow:
1. First call load_sql_skill() to get the database schema
2. Use sql_query(query) to execute SQL queries
3. Use sql_list_tables() to see available tables
4. Use sql_get_samples() to see sample data

Always use the tools to interact with the database.""")
                        else:
                            # Generic skill - just add context
                            core_content = skill.load_core()
                            skill_contexts.append(f"\n## {skill.name} Skill\n{core_content}")

                if skill_contexts:
                    system_prompt = system_prompt + "\n\n# Equipped Skills\n" + "\n".join(skill_contexts)

            return create_agent(
                model=llm,
                tools=tools,
                name=safe_name,
                system_prompt=system_prompt,
                checkpointer=self._checkpointer,
            )

    def invoke_agent_direct(
        self,
        agent_id: str,
        message: str,
        session_id: Optional[str] = None,
        user_id: str = "default",
        provider: str = "openai",
        model: Optional[str] = None,
        enable_memory: bool = True,
        memory_trigger_count: Optional[int] = None,
        memory_keep_recent: Optional[int] = None,
    ) -> dict:
        """Invoke a custom agent directly without supervisor.

        This allows the agent to interact directly with the user for
        human-in-the-loop scenarios (e.g., asking for confirmation).
        Uses SessionService for persistence and MemoryService for summarization
        when available.

        Args:
            agent_id: Custom agent ID
            message: User message
            session_id: Session ID for conversation continuity
            user_id: User ID for session scoping
            provider: Model provider
            model: Model name (optional)
            enable_memory: Whether to enable memory summarization
            memory_trigger_count: Override for summarization trigger threshold
            memory_keep_recent: Override for number of recent messages to keep

        Returns:
            Agent response with conversation state, session_id, and memory_metadata

        Raises:
            ValueError: If agent not found
        """
        if agent_id not in self._custom_agents:
            raise ValueError(f"Custom agent not found: {agent_id}")

        custom = self._custom_agents[agent_id]

        # Use session_id or create one based on agent_id and user_id
        sess_key = session_id or f"{user_id}:direct:{agent_id}"

        # Get model - use agent's configured provider/model if available
        agent_provider = custom.provider if hasattr(custom, 'provider') else provider
        agent_model = custom.model if hasattr(custom, 'model') else model
        memory_metadata = None

        # Get or create compiled agent (cached in _direct_sessions for performance)
        if sess_key not in self._direct_sessions:
            llm = self.model_service.get_or_create(
                provider=agent_provider,
                model=agent_model,
                temperature=custom.temperature if hasattr(custom, 'temperature') else 0.7,
            )

            agent = self._build_agent_from_custom(agent_id, llm)
            compiled = agent.compile() if hasattr(agent, 'compile') else agent

            self._direct_sessions[sess_key] = {
                "app": compiled,
                "agent_id": agent_id,
            }

        app = self._direct_sessions[sess_key]["app"]

        # Use SessionService if available for unified memory
        if self.session_service is not None:
            session = self.session_service.get_or_create(
                sess_key,
                user_id=user_id,
                metadata={"agent_id": agent_id, "session_type": "direct_agent"},
            )
            # Update session type if not already set
            if session.session_type == "chat":
                session.session_type = "direct_agent"

            # Add user message to session
            user_msg = HumanMessage(content=message)
            session.messages.append(user_msg)

            logger.debug(f"[Direct Agent] Session {sess_key} - {len(session.messages)} messages")

            # Apply memory summarization if MemoryService is available
            if enable_memory and self.memory_service is not None:
                memory_request = self._create_memory_request(
                    message, agent_provider, agent_model, enable_memory,
                    memory_trigger_count, memory_keep_recent
                )
                context_messages, memory_metadata = self.memory_service.process_conversation(
                    session, memory_request
                )
            else:
                context_messages = session.messages

            # Invoke agent with optimized context and enhanced tracing
            with trace_operation(
                session_id=sess_key,
                user_id=user_id,
                operation="direct_agent",
                metadata={
                    "agent_id": agent_id,
                    "agent_name": custom.name,
                    "provider": agent_provider,
                    "model": agent_model,
                    "message_count": len(context_messages),
                },
                tags=["agent", "direct", agent_provider],
            ):
                result = app.invoke(
                    {"messages": context_messages},
                    config={
                        "configurable": {"thread_id": sess_key},
                        "metadata": {"session_id": sess_key, "agent_id": agent_id, "user_id": user_id},
                    },
                )

            # Extract response messages and update session
            messages = result.get("messages", [])
            session.messages = messages
            session.updated_at = datetime.utcnow()
        else:
            # Fallback: Use legacy _direct_sessions storage
            if "messages" not in self._direct_sessions[sess_key]:
                self._direct_sessions[sess_key]["messages"] = []

            history = self._direct_sessions[sess_key]["messages"]
            user_msg = HumanMessage(content=message)
            history.append(user_msg)

            logger.debug(f"[Direct Agent Legacy] Session {sess_key} - {len(history)} messages")

            with trace_operation(
                session_id=sess_key,
                user_id=user_id,
                operation="direct_agent_legacy",
                metadata={
                    "agent_id": agent_id,
                    "agent_name": custom.name,
                    "provider": agent_provider,
                    "model": agent_model,
                },
                tags=["agent", "direct", "legacy", agent_provider],
            ):
                result = app.invoke(
                    {"messages": history},
                    config={
                        "configurable": {"thread_id": sess_key},
                        "metadata": {"session_id": sess_key, "agent_id": agent_id, "user_id": user_id},
                    },
                )

            messages = result.get("messages", [])
            self._direct_sessions[sess_key]["messages"] = messages

        # Extract response content
        response_content = self._extract_response_content(messages)

        if not response_content:
            logger.warning(f"[Direct Agent] No text content found in any AI message for {agent_id}")

        return {
            "agent_id": agent_id,
            "session_id": sess_key,
            "response": response_content,
            "message_count": len(messages),
            "memory_metadata": memory_metadata,
        }

    def clear_direct_session(self, session_id: str) -> bool:
        """Clear a direct agent session.

        Args:
            session_id: Session to clear

        Returns:
            True if cleared, False if not found
        """
        if session_id in self._direct_sessions:
            del self._direct_sessions[session_id]
            return True
        return False

    async def stream_agent_direct(
        self,
        agent_id: str,
        message: str,
        session_id: Optional[str] = None,
        user_id: str = "default",
        provider: str = "openai",
        model: Optional[str] = None,
        enable_memory: bool = True,
        memory_trigger_count: Optional[int] = None,
        memory_keep_recent: Optional[int] = None,
    ):
        """Stream responses from a custom agent directly without supervisor.

        Yields SSE events for tool calls, tool results, and tokens.

        Args:
            agent_id: Custom agent ID
            message: User message
            session_id: Session ID for conversation continuity
            user_id: User ID for session scoping
            provider: Model provider
            model: Model name (optional)
            enable_memory: Whether to enable memory summarization
            memory_trigger_count: Override for summarization trigger threshold
            memory_keep_recent: Override for number of recent messages to keep

        Yields:
            Dict events: start, tool_call, tool_result, token, done, error

        Raises:
            ValueError: If agent not found
        """
        import json

        if agent_id not in self._custom_agents:
            yield {"event": "error", "data": json.dumps({"error": f"Custom agent not found: {agent_id}"})}
            return

        custom = self._custom_agents[agent_id]

        # Use session_id or create one based on agent_id and user_id
        sess_key = session_id or f"{user_id}:direct:{agent_id}"

        # Get model - use agent's configured provider/model if available
        agent_provider = custom.provider if hasattr(custom, 'provider') else provider
        agent_model = custom.model if hasattr(custom, 'model') else model
        memory_metadata = None

        # Get or create compiled agent (cached in _direct_sessions for performance)
        if sess_key not in self._direct_sessions:
            llm = self.model_service.get_or_create(
                provider=agent_provider,
                model=agent_model,
                temperature=custom.temperature if hasattr(custom, 'temperature') else 0.7,
            )

            agent = self._build_agent_from_custom(agent_id, llm)
            compiled = agent.compile() if hasattr(agent, 'compile') else agent

            self._direct_sessions[sess_key] = {
                "app": compiled,
                "agent_id": agent_id,
            }

        app = self._direct_sessions[sess_key]["app"]

        # Emit start event
        yield {"event": "start", "data": json.dumps({
            "session_id": sess_key,
            "agent_id": agent_id,
            "provider": agent_provider,
            "model": agent_model,
        })}

        # Get or create session and add user message
        if self.session_service is not None:
            session = self.session_service.get_or_create(
                sess_key,
                user_id=user_id,
                metadata={"agent_id": agent_id, "session_type": "direct_agent"},
            )
            if session.session_type == "chat":
                session.session_type = "direct_agent"

            user_msg = HumanMessage(content=message)
            session.messages.append(user_msg)

            # Apply memory summarization if available
            if enable_memory and self.memory_service is not None:
                memory_request = self._create_memory_request(
                    message, agent_provider, agent_model, enable_memory,
                    memory_trigger_count, memory_keep_recent
                )
                context_messages, memory_metadata = self.memory_service.process_conversation(
                    session, memory_request
                )
            else:
                context_messages = session.messages
        else:
            # Fallback: Use legacy storage
            if "messages" not in self._direct_sessions[sess_key]:
                self._direct_sessions[sess_key]["messages"] = []

            history = self._direct_sessions[sess_key]["messages"]
            user_msg = HumanMessage(content=message)
            history.append(user_msg)
            context_messages = history

        # Stream agent response with enhanced tracing
        try:
            with trace_operation(
                session_id=sess_key,
                user_id=user_id,
                operation="stream_agent",
                metadata={
                    "agent_id": agent_id,
                    "agent_name": custom.name,
                    "provider": agent_provider,
                    "model": agent_model,
                    "message_count": len(context_messages),
                },
                tags=["agent", "streaming", agent_provider],
            ):
                final_messages = []
                accumulated_content = ""

                async for event in app.astream_events(
                    {"messages": context_messages},
                    config={
                        "configurable": {"thread_id": sess_key},
                        "metadata": {"session_id": sess_key, "agent_id": agent_id, "user_id": user_id},
                    },
                    version="v2",
                ):
                    kind = event.get("event", "")
                    data = event.get("data", {})

                    # Tool call started
                    if kind == "on_tool_start":
                        tool_name = event.get("name", "unknown")
                        tool_input = data.get("input", {})
                        yield {"event": "tool_call", "data": json.dumps({
                            "tool_name": tool_name,
                            "tool_id": event.get("run_id", ""),
                            "arguments": json.dumps(tool_input) if isinstance(tool_input, dict) else str(tool_input),
                        })}

                    # Tool call completed
                    elif kind == "on_tool_end":
                        tool_name = event.get("name", "unknown")
                        output = data.get("output", "")
                        # Truncate long outputs
                        output_str = str(output)[:500] if output else ""
                        yield {"event": "tool_result", "data": json.dumps({
                            "tool_name": tool_name,
                            "tool_id": event.get("run_id", ""),
                            "result": output_str,
                        })}

                    # Streaming tokens from LLM
                    elif kind == "on_chat_model_stream":
                        chunk = data.get("chunk")
                        if chunk and hasattr(chunk, 'content') and chunk.content:
                            content = chunk.content
                            if isinstance(content, str):
                                accumulated_content += content
                                yield {"event": "token", "data": json.dumps({"content": content})}

                    # Chain/graph end - capture final messages
                    elif kind == "on_chain_end" and event.get("name") == "LangGraph":
                        output = data.get("output", {})
                        if isinstance(output, dict) and "messages" in output:
                            final_messages = output["messages"]

                # Update session with final messages
                if final_messages:
                    if self.session_service is not None:
                        session.messages = final_messages
                        session.updated_at = datetime.utcnow()
                    else:
                        self._direct_sessions[sess_key]["messages"] = final_messages

                # Extract final response
                response_content = self._extract_response_content(final_messages) if final_messages else accumulated_content

                # Emit done event
                yield {"event": "done", "data": json.dumps({
                    "session_id": sess_key,
                    "agent_id": agent_id,
                    "response": response_content,
                    "message_count": len(final_messages) if final_messages else len(context_messages) + 1,
                    "memory_metadata": {
                        "summarized": memory_metadata.summarized if memory_metadata else False,
                        "summary_triggered": memory_metadata.summary_triggered if memory_metadata else False,
                        "total_messages": memory_metadata.total_messages if memory_metadata else 0,
                    } if memory_metadata else None,
                })}

        except Exception as e:
            logger.error(f"[Stream Agent] Error: {e}")
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    async def stream_builtin_agent(
        self,
        agent_id: str,
        message: str,
        session_id: Optional[str] = None,
        user_id: str = "default",
        provider: str = "openai",
        model: Optional[str] = None,
        enable_memory: bool = True,
        memory_trigger_count: Optional[int] = None,
        memory_keep_recent: Optional[int] = None,
    ):
        """Stream responses from a built-in agent directly without supervisor.

        Yields SSE events for tool calls, tool results, and tokens.

        Args:
            agent_id: Built-in agent ID (e.g., 'sql_expert', 'math_expert')
            message: User message
            session_id: Session ID for conversation continuity
            user_id: User ID for session scoping
            provider: Model provider
            model: Model name (optional)
            enable_memory: Whether to enable memory summarization
            memory_trigger_count: Override for summarization trigger threshold
            memory_keep_recent: Override for number of recent messages to keep

        Yields:
            Dict events: start, tool_call, tool_result, token, done, error

        Raises:
            ValueError: If agent not found
        """
        import json

        all_builtin = self._get_all_builtin_agents()
        if agent_id not in all_builtin:
            yield {"event": "error", "data": json.dumps({"error": f"Built-in agent not found: {agent_id}"})}
            return

        agent_config = all_builtin[agent_id]

        # Use session_id or create one based on agent_id and user_id
        sess_key = session_id or f"{user_id}:builtin:{agent_id}"
        memory_metadata = None

        # Cache key for the compiled agent
        cache_key = f"builtin:{agent_id}"

        # Get or create compiled agent (cached for performance)
        if cache_key not in self._direct_sessions:
            llm = self.model_service.get_or_create(
                provider=provider,
                model=model,
                temperature=0.7,
            )

            # Build agent from built-in config (same pattern as create_workflow)
            use_middleware = agent_config.get("use_middleware", False)

            # Get tools - from tool_ids (new style) or tools (dynamic agents)
            # HITL-aware tool creation
            if "tool_ids" in agent_config:
                tools = [
                    self._create_tool_with_hitl_check(tid)
                    for tid in agent_config["tool_ids"]
                ]
            else:
                tools = agent_config["tools"]

            if use_middleware:
                # Create agent with skill middleware for skill-based agents
                agent = self.create_middleware_enabled_agent(
                    agent_name=agent_config["name"],
                    llm=llm,
                    tools=tools,
                    system_prompt=agent_config["prompt"],
                    use_skills=True,
                )
            else:
                # Create standard agent without middleware but with checkpointing
                agent = create_agent(
                    model=llm,
                    tools=tools,
                    name=agent_config["name"],
                    system_prompt=agent_config["prompt"],
                    checkpointer=self._checkpointer,
                )

            compiled = agent.compile() if hasattr(agent, 'compile') else agent

            self._direct_sessions[cache_key] = {
                "app": compiled,
                "agent_id": agent_id,
            }

        app = self._direct_sessions[cache_key]["app"]

        # Emit start event
        yield {"event": "start", "data": json.dumps({
            "session_id": sess_key,
            "agent_id": agent_id,
            "provider": provider,
            "model": model,
        })}

        # Get or create session and add user message
        if self.session_service is not None:
            session = self.session_service.get_or_create(
                sess_key,
                user_id=user_id,
                metadata={"agent_id": agent_id, "session_type": "builtin_agent"},
            )
            if session.session_type == "chat":
                session.session_type = "builtin_agent"

            user_msg = HumanMessage(content=message)
            session.messages.append(user_msg)

            # Apply memory summarization if available
            if enable_memory and self.memory_service is not None:
                memory_request = self._create_memory_request(
                    message, provider, model, enable_memory,
                    memory_trigger_count, memory_keep_recent
                )
                context_messages, memory_metadata = self.memory_service.process_conversation(
                    session, memory_request
                )
            else:
                context_messages = session.messages
        else:
            # Fallback: Use simple message list
            if sess_key not in self._direct_sessions:
                self._direct_sessions[sess_key] = {"messages": []}
            elif "messages" not in self._direct_sessions[sess_key]:
                self._direct_sessions[sess_key]["messages"] = []

            history = self._direct_sessions[sess_key]["messages"]
            user_msg = HumanMessage(content=message)
            history.append(user_msg)
            context_messages = history

        # Stream agent response with enhanced tracing
        try:
            with trace_operation(
                session_id=sess_key,
                user_id=user_id,
                operation="stream_builtin_agent",
                metadata={
                    "agent_id": agent_id,
                    "agent_name": agent_config.get("name", agent_id),
                    "provider": provider,
                    "model": model,
                    "message_count": len(context_messages),
                },
                tags=["agent", "builtin", "streaming", provider],
            ):
                final_messages = []
                accumulated_content = ""

                async for event in app.astream_events(
                    {"messages": context_messages},
                    config={
                        "configurable": {"thread_id": sess_key},
                        "metadata": {"session_id": sess_key, "agent_id": agent_id, "user_id": user_id},
                    },
                    version="v2",
                ):
                    kind = event.get("event", "")
                    data = event.get("data", {})

                    # Tool call started
                    if kind == "on_tool_start":
                        tool_name = event.get("name", "unknown")
                        tool_input = data.get("input", {})
                        yield {"event": "tool_call", "data": json.dumps({
                            "tool_name": tool_name,
                            "tool_id": event.get("run_id", ""),
                            "arguments": json.dumps(tool_input) if isinstance(tool_input, dict) else str(tool_input),
                        })}

                    # Tool call completed
                    elif kind == "on_tool_end":
                        tool_name = event.get("name", "unknown")
                        output = data.get("output", "")
                        # Truncate long outputs
                        output_str = str(output)[:500] if output else ""
                        yield {"event": "tool_result", "data": json.dumps({
                            "tool_name": tool_name,
                            "tool_id": event.get("run_id", ""),
                            "result": output_str,
                        })}

                    # Streaming tokens from LLM
                    elif kind == "on_chat_model_stream":
                        chunk = data.get("chunk")
                        if chunk and hasattr(chunk, 'content') and chunk.content:
                            content = chunk.content
                            if isinstance(content, str):
                                accumulated_content += content
                                yield {"event": "token", "data": json.dumps({"content": content})}

                    # Chain/graph end - capture final messages
                    elif kind == "on_chain_end" and event.get("name") == "LangGraph":
                        output = data.get("output", {})
                        if isinstance(output, dict) and "messages" in output:
                            final_messages = output["messages"]

                # Update session with final messages
                if final_messages:
                    if self.session_service is not None:
                        session.messages = final_messages
                        session.updated_at = datetime.utcnow()
                    else:
                        self._direct_sessions[sess_key]["messages"] = final_messages

                # Extract final response
                response_content = self._extract_response_content(final_messages) if final_messages else accumulated_content

                # Emit done event
                yield {"event": "done", "data": json.dumps({
                    "session_id": sess_key,
                    "agent_id": agent_id,
                    "response": response_content,
                    "message_count": len(final_messages) if final_messages else len(context_messages) + 1,
                    "memory_metadata": {
                        "summarized": memory_metadata.summarized if memory_metadata else False,
                        "summary_triggered": memory_metadata.summary_triggered if memory_metadata else False,
                        "total_messages": memory_metadata.total_messages if memory_metadata else 0,
                    } if memory_metadata else None,
                })}

        except Exception as e:
            logger.error(f"[Stream Builtin Agent] Error: {e}")
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    # =========================================================================
    # UNIFIED AGENT METHODS
    # These methods handle both custom and built-in agents through a single API
    # =========================================================================

    def _get_agent_info(self, agent_id: str) -> tuple[str, dict, Optional[Any]]:
        """Get agent information for any agent type.

        Args:
            agent_id: Agent ID (custom or built-in)

        Returns:
            Tuple of (agent_type, config, custom_agent_obj)
            - agent_type: "custom" or "builtin"
            - config: Agent configuration dict
            - custom_agent_obj: CustomAgent object if custom, None if builtin

        Raises:
            ValueError: If agent not found
        """
        # Check custom agents first
        if agent_id in self._custom_agents:
            custom = self._custom_agents[agent_id]
            return "custom", {
                "name": custom.name,
                "prompt": custom.system_prompt,
                "provider": custom.provider,
                "model": custom.model,
                "temperature": custom.temperature,
                "tool_configs": custom.tool_configs,
                "skill_ids": custom.skill_ids,
            }, custom

        # Check built-in agents
        all_builtin = self._get_all_builtin_agents()
        if agent_id in all_builtin:
            return "builtin", all_builtin[agent_id], None

        # Not found
        available = list(self._custom_agents.keys()) + list(all_builtin.keys())
        raise ValueError(f"Agent not found: {agent_id}. Available: {available}")

    def list_all_agents(self) -> list[dict]:
        """List all agents (both custom and built-in).

        Returns:
            List of agent info dicts with unified schema
        """
        agents = []

        # Add built-in agents
        for config in self._get_all_builtin_agents().values():
            if "tool_ids" in config:
                tool_names = config["tool_ids"]
            else:
                tool_names = [t.__name__ for t in config.get("tools", [])]

            agents.append({
                "id": config["name"],
                "name": config["name"],
                "type": "builtin",
                "tools": tool_names,
                "description": config["prompt"][:100] + "..." if len(config["prompt"]) > 100 else config["prompt"],
            })

        # Add custom agents
        for agent_id, custom in self._custom_agents.items():
            agents.append({
                "id": agent_id,
                "name": custom.name,
                "type": "custom",
                "tools": [tc["tool_id"] for tc in custom.tool_configs],
                "skills": custom.skill_ids,
                "description": custom.system_prompt[:100] + "..." if len(custom.system_prompt) > 100 else custom.system_prompt,
                "provider": custom.provider,
                "model": custom.model,
            })

        return agents

    def invoke_agent(
        self,
        agent_id: str,
        message: str,
        images: Optional[list[str]] = None,
        session_id: Optional[str] = None,
        user_id: str = "default",
        provider: str = "openai",
        model: Optional[str] = None,
        enable_memory: bool = True,
        memory_trigger_count: Optional[int] = None,
        memory_keep_recent: Optional[int] = None,
    ) -> dict:
        """Invoke any agent (custom or built-in) without supervisor.

        This is the unified method for non-streaming agent invocation.

        Args:
            agent_id: Agent ID (custom or built-in)
            message: User message
            images: Optional list of base64 data URIs for images
            session_id: Session ID for conversation continuity
            user_id: User ID for session scoping
            provider: Model provider (overridden by agent config if set)
            model: Model name (overridden by agent config if set)
            enable_memory: Whether to enable memory summarization
            memory_trigger_count: Override for summarization trigger threshold
            memory_keep_recent: Override for number of recent messages to keep

        Returns:
            Agent response with session_id and memory metadata

        Raises:
            ValueError: If agent not found
        """
        agent_type, config, custom = self._get_agent_info(agent_id)

        # Determine provider/model - agent config takes precedence
        agent_provider = config.get("provider", provider)
        agent_model = config.get("model", model)
        agent_temp = config.get("temperature", 0.7)

        # Build session key
        sess_key = session_id or f"{user_id}:agent:{agent_id}"
        memory_metadata = None

        # Cache key for compiled agent
        cache_key = f"unified:{agent_id}"

        # Get or create compiled agent
        if cache_key not in self._direct_sessions:
            llm = self.model_service.get_or_create(
                provider=agent_provider,
                model=agent_model,
                temperature=agent_temp,
            )

            if agent_type == "custom":
                agent = self._build_agent_from_custom(agent_id, llm)
            else:
                # Build from builtin config, with HITL wrapping if needed
                use_middleware = config.get("use_middleware", False)
                if "tool_ids" in config:
                    tools = [self._create_tool_with_hitl_check(tid) for tid in config["tool_ids"]]
                else:
                    tools = config.get("tools", [])

                if use_middleware:
                    agent = self.create_middleware_enabled_agent(
                        agent_name=config["name"],
                        llm=llm,
                        tools=tools,
                        system_prompt=config["prompt"],
                        use_skills=True,
                    )
                else:
                    agent = create_agent(
                        model=llm,
                        tools=tools,
                        name=config["name"],
                        system_prompt=config["prompt"],
                        checkpointer=self._checkpointer,
                    )

            compiled = agent.compile() if hasattr(agent, 'compile') else agent
            self._direct_sessions[cache_key] = {"app": compiled, "agent_id": agent_id}

        app = self._direct_sessions[cache_key]["app"]

        # Session management
        if self.session_service is not None:
            session = self.session_service.get_or_create(
                sess_key,
                user_id=user_id,
                metadata={"agent_id": agent_id, "agent_type": agent_type},
            )
            user_msg = self._build_user_message(message, images, agent_provider)
            session.messages.append(user_msg)

            if enable_memory and self.memory_service is not None:
                memory_request = self._create_memory_request(
                    message, agent_provider, agent_model, enable_memory,
                    memory_trigger_count, memory_keep_recent
                )
                context_messages, memory_metadata = self.memory_service.process_conversation(
                    session, memory_request
                )
            else:
                context_messages = session.messages
        else:
            if cache_key not in self._direct_sessions or "messages" not in self._direct_sessions[cache_key]:
                self._direct_sessions[cache_key]["messages"] = []
            history = self._direct_sessions[cache_key]["messages"]
            user_msg = self._build_user_message(message, images, agent_provider)
            history.append(user_msg)
            context_messages = history

        # Invoke agent with tracing
        with trace_operation(
            session_id=sess_key,
            user_id=user_id,
            operation="invoke_agent",
            metadata={
                "agent_id": agent_id,
                "agent_type": agent_type,
                "agent_name": config.get("name", agent_id),
                "provider": agent_provider,
                "model": agent_model,
                "message_count": len(context_messages),
            },
            tags=["agent", agent_type, agent_provider],
        ):
            result = app.invoke(
                {"messages": context_messages},
                config={
                    "configurable": {"thread_id": sess_key},
                    "metadata": {"session_id": sess_key, "agent_id": agent_id, "user_id": user_id},
                },
            )

        # Update session
        messages = result.get("messages", [])
        if self.session_service is not None:
            session.messages = messages
            session.updated_at = datetime.utcnow()
        else:
            self._direct_sessions[cache_key]["messages"] = messages

        response_content = self._extract_response_content(messages)

        return {
            "agent_id": agent_id,
            "agent_type": agent_type,
            "session_id": sess_key,
            "response": response_content,
            "message_count": len(messages),
            "memory_metadata": memory_metadata,
        }

    async def stream_agent(
        self,
        agent_id: str,
        message: str,
        images: Optional[list[str]] = None,
        session_id: Optional[str] = None,
        user_id: str = "default",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        enable_memory: bool = True,
        memory_trigger_count: Optional[int] = None,
        memory_keep_recent: Optional[int] = None,
    ):
        """Stream responses from any agent (custom or built-in).

        This is the unified method for streaming agent invocation.

        Yields SSE events for tool calls, tool results, and tokens.

        Args:
            agent_id: Agent ID (custom or built-in)
            message: User message
            images: Optional list of base64 data URIs for images
            session_id: Session ID for conversation continuity
            user_id: User ID for session scoping
            provider: Override model provider (None = use agent default)
            model: Override model name (None = use agent default)
            temperature: Override temperature (None = use agent default)
            enable_memory: Whether to enable memory summarization
            memory_trigger_count: Override for summarization trigger threshold
            memory_keep_recent: Override for number of recent messages to keep

        Yields:
            Dict events: start, tool_call, tool_result, token, done, error
        """
        import json

        try:
            agent_type, config, custom = self._get_agent_info(agent_id)
        except ValueError as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)})}
            return

        # Determine provider/model - request override takes precedence over agent config
        # If neither provided, default to openai
        agent_provider = provider or config.get("provider") or "openai"
        agent_model = model or config.get("model")
        agent_temp = temperature if temperature is not None else config.get("temperature", 0.7)

        # Build session key
        sess_key = session_id or f"{user_id}:agent:{agent_id}"
        memory_metadata = None

        # Cache key for compiled agent - includes provider/model so switching works
        cache_key = f"unified:{agent_id}:{agent_provider}:{agent_model or 'default'}"

        # Get or create compiled agent
        try:
            if cache_key not in self._direct_sessions:
                llm = self.model_service.get_or_create(
                    provider=agent_provider,
                    model=agent_model,
                    temperature=agent_temp,
                )

                if agent_type == "custom":
                    agent = self._build_agent_from_custom(agent_id, llm)
                else:
                    # Build from builtin config, with HITL wrapping if needed
                    use_middleware = config.get("use_middleware", False)
                    if "tool_ids" in config:
                        tools = [self._create_tool_with_hitl_check(tid) for tid in config["tool_ids"]]
                    else:
                        tools = config.get("tools", [])

                    if use_middleware:
                        agent = self.create_middleware_enabled_agent(
                            agent_name=config["name"],
                            llm=llm,
                            tools=tools,
                            system_prompt=config["prompt"],
                            use_skills=True,
                        )
                    else:
                        agent = create_agent(
                            model=llm,
                            tools=tools,
                            name=config["name"],
                            system_prompt=config["prompt"],
                            checkpointer=self._checkpointer,
                        )

                compiled = agent.compile() if hasattr(agent, 'compile') else agent
                self._direct_sessions[cache_key] = {"app": compiled, "agent_id": agent_id}

            app = self._direct_sessions[cache_key]["app"]
        except Exception as e:
            logger.error(f"[Stream Agent] Failed to create agent {agent_id} with provider {agent_provider}: {e}")
            yield {"event": "error", "data": json.dumps({"error": f"Failed to initialize {agent_provider} model: {str(e)}"})}
            return

        # Emit start event
        yield {"event": "start", "data": json.dumps({
            "session_id": sess_key,
            "agent_id": agent_id,
            "agent_type": agent_type,
            "provider": agent_provider,
            "model": agent_model,
        })}

        # Session management
        if self.session_service is not None:
            session = self.session_service.get_or_create(
                sess_key,
                user_id=user_id,
                metadata={"agent_id": agent_id, "agent_type": agent_type},
            )
            user_msg = self._build_user_message(message, images, agent_provider)
            session.messages.append(user_msg)

            if enable_memory and self.memory_service is not None:
                memory_request = self._create_memory_request(
                    message, agent_provider, agent_model, enable_memory,
                    memory_trigger_count, memory_keep_recent
                )
                context_messages, memory_metadata = self.memory_service.process_conversation(
                    session, memory_request
                )
            else:
                context_messages = session.messages
        else:
            if "messages" not in self._direct_sessions.get(cache_key, {}):
                self._direct_sessions[cache_key]["messages"] = []
            history = self._direct_sessions[cache_key]["messages"]
            user_msg = self._build_user_message(message, images, agent_provider)
            history.append(user_msg)
            context_messages = history

        # Stream agent response with tracing
        try:
            # Set session context for HITL tools
            token = _current_session_id.set(sess_key)

            with trace_operation(
                session_id=sess_key,
                user_id=user_id,
                operation="stream_agent",
                metadata={
                    "agent_id": agent_id,
                    "agent_type": agent_type,
                    "agent_name": config.get("name", agent_id),
                    "provider": agent_provider,
                    "model": agent_model,
                    "message_count": len(context_messages),
                },
                tags=["agent", "streaming", agent_type, agent_provider],
            ):
                final_messages = []
                accumulated_content = ""

                async for event in app.astream_events(
                    {"messages": context_messages},
                    config={
                        "configurable": {"thread_id": sess_key},
                        "metadata": {"session_id": sess_key, "agent_id": agent_id, "user_id": user_id},
                    },
                    version="v2",
                ):
                    kind = event.get("event", "")
                    data = event.get("data", {})

                    # Debug: log all events from astream_events
                    logger.info(f"[Stream Event] kind={kind}, name={event.get('name')}, data_keys={list(data.keys()) if isinstance(data, dict) else type(data)}")

                    # Tool call started
                    if kind == "on_tool_start":
                        tool_name = event.get("name", "unknown")
                        tool_input = data.get("input", {})
                        yield {"event": "tool_call", "data": json.dumps({
                            "tool_name": tool_name,
                            "tool_id": event.get("run_id", ""),
                            "arguments": json.dumps(tool_input) if isinstance(tool_input, dict) else str(tool_input),
                        })}

                    # Tool call completed
                    elif kind == "on_tool_end":
                        tool_name = event.get("name", "unknown")
                        output = data.get("output", "")
                        # Extract content from tool output (may be object with content attr)
                        if hasattr(output, 'content'):
                            output_str = str(output.content)[:500] if output.content else ""
                        else:
                            output_str = str(output)[:500] if output else ""

                        # Check for HITL pending response
                        if self._is_hitl_pending(output_str):
                            approval_id = self._extract_approval_id(output_str)
                            hitl_config = self.get_hitl_config_for_tool(tool_name)

                            # Get approval details if available
                            approval_data = None
                            if self._approval_service and approval_id:
                                approval_data = self._approval_service.get(approval_id)

                            yield {"event": "approval_request", "data": json.dumps({
                                "approval_id": approval_id,
                                "tool_name": tool_name,
                                "tool_id": event.get("run_id", ""),
                                "message": hitl_config.message if hitl_config else "Approve this action?",
                                "tool_args": approval_data.tool_args if approval_data else {},
                                "expires_at": approval_data.expires_at.isoformat() if approval_data and approval_data.expires_at else None,
                                "config": {
                                    "show_args": hitl_config.show_args if hitl_config else True,
                                    "timeout_seconds": hitl_config.timeout_seconds if hitl_config else 300,
                                    "require_reason_on_reject": hitl_config.require_reason_on_reject if hitl_config else False,
                                },
                            })}
                        else:
                            yield {"event": "tool_result", "data": json.dumps({
                                "tool_name": tool_name,
                                "tool_id": event.get("run_id", ""),
                                "result": output_str,
                            })}

                    # Streaming tokens from LLM
                    elif kind == "on_chat_model_stream":
                        chunk = data.get("chunk")
                        if chunk and hasattr(chunk, 'content') and chunk.content:
                            content = chunk.content
                            if isinstance(content, str):
                                accumulated_content += content
                                yield {"event": "token", "data": json.dumps({"content": content})}

                    # Chain/graph end - capture final messages
                    # Check for agent name (e.g., "sql_expert") or "LangGraph"
                    elif kind == "on_chain_end" and event.get("name") in (config.get("name"), agent_id, "LangGraph"):
                        output = data.get("output", {})
                        if isinstance(output, dict):
                            if "messages" in output:
                                final_messages = output["messages"]
                            # Log output structure for debugging
                            elif not final_messages:
                                logger.info(f"[Stream Event] on_chain_end output keys: {list(output.keys())}")

                    # Capture from on_chat_model_end as fallback (for non-streaming models like Bedrock)
                    elif kind == "on_chat_model_end" and not accumulated_content:
                        output = data.get("output")
                        if output and hasattr(output, 'content'):
                            content = output.content
                            if isinstance(content, str) and content:
                                accumulated_content = content
                                yield {"event": "token", "data": json.dumps({"content": content})}
                            elif isinstance(content, list):
                                # Handle list content (e.g., from Claude/Bedrock models)
                                text_content = "".join(
                                    block.get("text", "") if isinstance(block, dict) else str(block)
                                    for block in content
                                    if isinstance(block, str) or (isinstance(block, dict) and block.get("type") == "text")
                                )
                                if text_content:
                                    accumulated_content = text_content
                                    yield {"event": "token", "data": json.dumps({"content": text_content})}

                # Update session with final messages
                if final_messages:
                    if self.session_service is not None:
                        session.messages = final_messages
                        session.updated_at = datetime.utcnow()
                    else:
                        self._direct_sessions[cache_key]["messages"] = final_messages

                # Extract final response
                response_content = self._extract_response_content(final_messages) if final_messages else accumulated_content

                # Debug: log final content
                logger.info(f"[Stream Agent Done] agent_id={agent_id}, final_messages_count={len(final_messages)}, accumulated_len={len(accumulated_content)}, response_len={len(response_content)}")
                if not response_content:
                    logger.warning(f"[Stream Agent] Empty response! final_messages={final_messages[:2] if final_messages else 'None'}")

                # Emit done event
                yield {"event": "done", "data": json.dumps({
                    "session_id": sess_key,
                    "agent_id": agent_id,
                    "agent_type": agent_type,
                    "response": response_content,
                    "message_count": len(final_messages) if final_messages else len(context_messages) + 1,
                    "memory_metadata": {
                        "summarized": memory_metadata.summarized if memory_metadata else False,
                        "summary_triggered": memory_metadata.summary_triggered if memory_metadata else False,
                        "total_messages": memory_metadata.total_messages if memory_metadata else 0,
                    } if memory_metadata else None,
                })}

        except Exception as e:
            logger.error(f"[Stream Agent] Error for {agent_id}: {e}")
            yield {"event": "error", "data": json.dumps({"error": str(e)})}
        finally:
            # Reset session context
            _current_session_id.reset(token)

    def create_workflow(
        self,
        workflow_id: str,
        agent_names: list[str],
        provider: str = "openai",
        model: Optional[str] = None,
        supervisor_prompt: Optional[str] = None,
    ) -> str:
        """Create a multi-agent workflow with supervisor.

        Supports both built-in agents and custom user-defined agents.

        Args:
            workflow_id: Unique identifier for the workflow
            agent_names: List of agent names (built-in or custom agent IDs)
            provider: Model provider to use
            model: Model name (optional)
            supervisor_prompt: Custom supervisor prompt (optional)

        Returns:
            Workflow ID

        Raises:
            ValueError: If agent name not found
        """
        # Get model
        llm = self.model_service.get_or_create(
            provider=provider,
            model=model,
            temperature=0.0,
        )

        # Create agents - supports both built-in and custom agents
        agents = []
        agent_descriptions = []

        all_builtin = self._get_all_builtin_agents()

        for agent_name in agent_names:
            # Check built-in agents first (including skill-based ones)
            if agent_name in all_builtin:
                config = all_builtin[agent_name]
                use_middleware = config.get("use_middleware", False)

                # Get tools - from tool_ids (new style) or tools (dynamic agents)
                # HITL-aware tool creation
                if "tool_ids" in config:
                    tools = [
                        self._create_tool_with_hitl_check(tid)
                        for tid in config["tool_ids"]
                    ]
                else:
                    tools = config["tools"]

                if use_middleware:
                    # Create agent with skill middleware for skill-based agents
                    agent = self.create_middleware_enabled_agent(
                        agent_name=config["name"],
                        llm=llm,
                        tools=tools,
                        system_prompt=config["prompt"],
                        use_skills=True,
                    )
                else:
                    # Create standard agent without middleware but with checkpointing
                    agent = create_agent(
                        model=llm,
                        tools=tools,
                        name=config["name"],
                        system_prompt=config["prompt"],
                        checkpointer=self._checkpointer,
                    )

                agents.append(agent)
                agent_descriptions.append(
                    f"- {config['name']}: {config['prompt'][:50]}..."
                )
            # Check custom agents
            elif agent_name in self._custom_agents:
                agent = self._build_agent_from_custom(agent_name, llm)
                custom = self._custom_agents[agent_name]
                agents.append(agent)
                agent_descriptions.append(
                    f"- {custom.name}: {custom.system_prompt[:50]}..."
                )
            else:
                available = list(all_builtin.keys()) + list(self._custom_agents.keys())
                raise ValueError(
                    f"Unknown agent: {agent_name}. Available: {available}"
                )

        # Create supervisor prompt
        if supervisor_prompt is None:
            supervisor_prompt = DEFAULT_SUPERVISOR_PROMPT.format(
                agent_descriptions="\n".join(agent_descriptions)
            )

        # Create supervisor workflow
        workflow = create_supervisor(
            agents,
            model=llm,
            prompt=supervisor_prompt,
        )

        # Compile and store
        compiled = workflow.compile()
        self._workflows[workflow_id] = {
            "app": compiled,
            "agents": agent_names,
            "provider": provider,
            "model": model,
            "messages": [],  # Conversation history for human-in-the-loop
        }

        logger.info(f"Created workflow {workflow_id} with agents: {agent_names}")
        return workflow_id

    def invoke_workflow(
        self,
        workflow_id: str,
        message: str,
        images: Optional[list[str]] = None,
        session_id: Optional[str] = None,
        user_id: str = "default",
        enable_memory: bool = True,
        memory_trigger_count: Optional[int] = None,
        memory_keep_recent: Optional[int] = None,
    ) -> dict:
        """Invoke a multi-agent workflow.

        Supports human-in-the-loop by preserving conversation history.
        Uses SessionService for persistence and MemoryService for summarization
        when available.

        Args:
            workflow_id: Workflow to invoke
            message: User message
            images: Optional list of base64 data URIs for images
            session_id: Optional session ID for persistence
            user_id: User ID for session scoping
            enable_memory: Whether to enable memory summarization
            memory_trigger_count: Override for summarization trigger threshold
            memory_keep_recent: Override for number of recent messages to keep

        Returns:
            Workflow result with agent responses, session_id, and memory_metadata

        Raises:
            ValueError: If workflow not found
        """
        if workflow_id not in self._workflows:
            raise ValueError(f"Workflow not found: {workflow_id}")

        workflow_data = self._workflows[workflow_id]
        app = workflow_data["app"]
        provider = workflow_data.get("provider", "openai")
        model = workflow_data.get("model")

        # Determine session ID
        sess_id = session_id or f"{user_id}:workflow:{workflow_id}"
        memory_metadata = None

        # Use SessionService if available for unified memory
        if self.session_service is not None:
            session = self.session_service.get_or_create(
                sess_id,
                user_id=user_id,
                metadata={"workflow_id": workflow_id, "session_type": "workflow"},
            )
            # Update session type if not already set
            if session.session_type == "chat":
                session.session_type = "workflow"

            # Add user message to session
            user_msg = self._build_user_message(message, images, provider)
            session.messages.append(user_msg)

            # Apply memory summarization if MemoryService is available
            if enable_memory and self.memory_service is not None:
                # Create a minimal request object for MemoryService
                memory_request = self._create_memory_request(
                    message, provider, model, enable_memory,
                    memory_trigger_count, memory_keep_recent
                )
                context_messages, memory_metadata = self.memory_service.process_conversation(
                    session, memory_request
                )
            else:
                context_messages = session.messages

            # Invoke with optimized context and enhanced tracing
            with trace_operation(
                session_id=sess_id,
                user_id=user_id,
                operation="workflow",
                metadata={
                    "workflow_id": workflow_id,
                    "agents": workflow_data["agents"],
                    "provider": provider,
                    "model": model,
                    "message_count": len(context_messages),
                },
                tags=["workflow", "multi-agent", provider],
            ):
                result = app.invoke(
                    {"messages": context_messages},
                    config={
                        "configurable": {"thread_id": sess_id},
                        "metadata": {"session_id": sess_id, "workflow_id": workflow_id, "user_id": user_id},
                    },
                )

            # Extract response messages and update session
            messages = result.get("messages", [])
            session.messages = messages
            session.updated_at = datetime.utcnow()

            # Also update legacy workflow storage for backward compatibility
            workflow_data["messages"] = messages
        else:
            # Fallback: Use legacy workflow-based storage
            history = workflow_data.get("messages", [])
            user_msg = self._build_user_message(message, images, provider)
            history.append(user_msg)

            with trace_operation(
                session_id=sess_id,
                user_id=user_id,
                operation="workflow_legacy",
                metadata={
                    "workflow_id": workflow_id,
                    "agents": workflow_data["agents"],
                    "provider": provider,
                    "model": model,
                },
                tags=["workflow", "multi-agent", "legacy", provider],
            ):
                result = app.invoke(
                    {"messages": history},
                    config={
                        "configurable": {"thread_id": sess_id},
                        "metadata": {"session_id": sess_id, "workflow_id": workflow_id, "user_id": user_id},
                    },
                )

            messages = result.get("messages", [])
            workflow_data["messages"] = messages

        # Find the last AI message with actual text content
        response_content = self._extract_response_content(messages)

        return {
            "workflow_id": workflow_id,
            "agents": workflow_data["agents"],
            "response": response_content,
            "message_count": len(messages),
            "session_id": sess_id,
            "memory_metadata": memory_metadata,
        }

    async def stream_workflow(
        self,
        workflow_id: str,
        message: str,
        images: Optional[list[str]] = None,
        session_id: Optional[str] = None,
        user_id: str = "default",
        enable_memory: bool = True,
        memory_trigger_count: Optional[int] = None,
        memory_keep_recent: Optional[int] = None,
    ):
        """Stream responses from a multi-agent workflow.

        Yields SSE events for agent delegation, tool calls, tool results, and tokens.

        Args:
            workflow_id: Workflow to invoke
            message: User message
            images: Optional list of base64 data URIs for images
            session_id: Optional session ID for persistence
            user_id: User ID for session scoping
            enable_memory: Whether to enable memory summarization
            memory_trigger_count: Override for summarization trigger threshold
            memory_keep_recent: Override for number of recent messages to keep

        Yields:
            Dict events: start, agent_start, agent_end, tool_call, tool_result, token, done, error
        """
        import json

        if workflow_id not in self._workflows:
            yield {"event": "error", "data": json.dumps({"error": f"Workflow not found: {workflow_id}"})}
            return

        workflow_data = self._workflows[workflow_id]
        app = workflow_data["app"]
        provider = workflow_data.get("provider", "openai")
        model = workflow_data.get("model")
        agents = workflow_data.get("agents", [])

        # Determine session ID
        sess_id = session_id or f"{user_id}:workflow:{workflow_id}"
        memory_metadata = None

        # Emit start event
        yield {"event": "start", "data": json.dumps({
            "session_id": sess_id,
            "workflow_id": workflow_id,
            "agents": agents,
            "provider": provider,
            "model": model,
        })}

        # Use SessionService if available for unified memory
        if self.session_service is not None:
            session = self.session_service.get_or_create(
                sess_id,
                user_id=user_id,
                metadata={"workflow_id": workflow_id, "session_type": "workflow"},
            )
            if session.session_type == "chat":
                session.session_type = "workflow"

            user_msg = self._build_user_message(message, images, provider)
            session.messages.append(user_msg)

            if enable_memory and self.memory_service is not None:
                memory_request = self._create_memory_request(
                    message, provider, model, enable_memory,
                    memory_trigger_count, memory_keep_recent
                )
                context_messages, memory_metadata = self.memory_service.process_conversation(
                    session, memory_request
                )
            else:
                context_messages = session.messages
        else:
            # Fallback: Use legacy workflow-based storage
            history = workflow_data.get("messages", [])
            user_msg = self._build_user_message(message, images, provider)
            history.append(user_msg)
            context_messages = history

        # Stream workflow response with tracing
        try:
            with trace_operation(
                session_id=sess_id,
                user_id=user_id,
                operation="stream_workflow",
                metadata={
                    "workflow_id": workflow_id,
                    "agents": agents,
                    "provider": provider,
                    "model": model,
                    "message_count": len(context_messages),
                },
                tags=["workflow", "multi-agent", "streaming", provider],
            ):
                final_messages = []
                accumulated_content = ""
                current_agent = None

                async for event in app.astream_events(
                    {"messages": context_messages},
                    config={
                        "configurable": {"thread_id": sess_id},
                        "metadata": {"session_id": sess_id, "workflow_id": workflow_id, "user_id": user_id},
                    },
                    version="v2",
                ):
                    kind = event.get("event", "")
                    data = event.get("data", {})
                    name = event.get("name", "")

                    # Agent node started (subgraph invocation)
                    if kind == "on_chain_start" and name in agents:
                        current_agent = name
                        yield {"event": "agent_start", "data": json.dumps({
                            "agent_name": name,
                            "agent_id": event.get("run_id", ""),
                        })}

                    # Agent node ended
                    elif kind == "on_chain_end" and name in agents:
                        yield {"event": "agent_end", "data": json.dumps({
                            "agent_name": name,
                            "agent_id": event.get("run_id", ""),
                        })}
                        current_agent = None

                    # Tool call started
                    elif kind == "on_tool_start":
                        tool_name = event.get("name", "unknown")
                        tool_input = data.get("input", {})
                        yield {"event": "tool_call", "data": json.dumps({
                            "tool_name": tool_name,
                            "tool_id": event.get("run_id", ""),
                            "agent_name": current_agent,
                            "arguments": json.dumps(tool_input) if isinstance(tool_input, dict) else str(tool_input),
                        })}

                    # Tool call completed
                    elif kind == "on_tool_end":
                        tool_name = event.get("name", "unknown")
                        output = data.get("output", "")
                        # Extract content from tool output (may be object with content attr)
                        if hasattr(output, 'content'):
                            output_str = str(output.content)[:500] if output.content else ""
                        else:
                            output_str = str(output)[:500] if output else ""
                        yield {"event": "tool_result", "data": json.dumps({
                            "tool_name": tool_name,
                            "tool_id": event.get("run_id", ""),
                            "agent_name": current_agent,
                            "result": output_str,
                        })}

                    # Streaming tokens from LLM
                    elif kind == "on_chat_model_stream":
                        chunk = data.get("chunk")
                        if chunk and hasattr(chunk, 'content') and chunk.content:
                            content = chunk.content
                            if isinstance(content, str):
                                accumulated_content += content
                                yield {"event": "token", "data": json.dumps({
                                    "content": content,
                                    "agent_name": current_agent,
                                })}

                    # Chain/graph end - capture final messages
                    elif kind == "on_chain_end" and name == "LangGraph":
                        output = data.get("output", {})
                        if isinstance(output, dict) and "messages" in output:
                            final_messages = output["messages"]

                # Update session with final messages
                if final_messages:
                    if self.session_service is not None:
                        session.messages = final_messages
                        session.updated_at = datetime.utcnow()
                    else:
                        workflow_data["messages"] = final_messages

                # Extract final response
                response_content = self._extract_response_content(final_messages) if final_messages else accumulated_content

                # Emit done event
                yield {"event": "done", "data": json.dumps({
                    "session_id": sess_id,
                    "workflow_id": workflow_id,
                    "agents": agents,
                    "response": response_content,
                    "message_count": len(final_messages) if final_messages else len(context_messages) + 1,
                    "memory_metadata": {
                        "summarized": memory_metadata.summarized if memory_metadata else False,
                        "summary_triggered": memory_metadata.summary_triggered if memory_metadata else False,
                        "total_messages": memory_metadata.total_messages if memory_metadata else 0,
                    } if memory_metadata else None,
                })}

        except Exception as e:
            logger.error(f"[Stream Workflow] Error for {workflow_id}: {e}")
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    def _parse_data_uri(self, uri: str) -> tuple[str, str]:
        """Parse data URI into mime type and base64 data.

        Args:
            uri: Data URI (e.g., 'data:image/png;base64,iVBORw0KGgo...')

        Returns:
            Tuple of (mime_type, base64_data)
        """
        # data:image/png;base64,iVBORw0KGgo...
        header, data = uri.split(",", 1)
        mime_type = header.split(":")[1].split(";")[0]
        return mime_type, data

    def _build_user_message(
        self, text: str, images: Optional[list[str]], provider: str
    ) -> HumanMessage:
        """Build a HumanMessage with optional image content.

        Args:
            text: Text message content
            images: Optional list of base64 data URIs
            provider: Model provider (for format-specific handling)

        Returns:
            HumanMessage with text and/or image content
        """
        if not images:
            return HumanMessage(content=text)

        # Build multimodal content blocks
        content: list[dict] = [{"type": "text", "text": text}]

        for image_uri in images:
            if provider == "anthropic":
                # Anthropic format: base64 with source
                mime_type, data = self._parse_data_uri(image_uri)
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": data
                    }
                })
            else:
                # OpenAI/Google/Bedrock format: image_url
                content.append({
                    "type": "image_url",
                    "image_url": {"url": image_uri}
                })

        return HumanMessage(content=content)

    def _create_memory_request(
        self,
        message: str,
        provider: str,
        model: Optional[str],
        enable_memory: bool,
        memory_trigger_count: Optional[int],
        memory_keep_recent: Optional[int],
    ):
        """Create a minimal request object compatible with MemoryService.

        Args:
            message: User message
            provider: Model provider
            model: Model name
            enable_memory: Whether memory is enabled
            memory_trigger_count: Trigger threshold override
            memory_keep_recent: Keep recent override

        Returns:
            Object with attributes expected by MemoryService
        """
        from types import SimpleNamespace
        return SimpleNamespace(
            message=message,
            provider=provider,
            model=model,
            enable_memory=enable_memory,
            memory_trigger_count=memory_trigger_count,
            memory_keep_recent=memory_keep_recent,
        )

    def _extract_response_content(self, messages: list) -> str:
        """Extract the last AI response content from messages.

        Args:
            messages: List of messages from workflow invocation

        Returns:
            Response text content
        """
        response_content = ""
        for msg in reversed(messages):
            msg_type = type(msg).__name__
            if msg_type not in ("AIMessage", "AIMessageChunk"):
                continue

            content = msg.content
            text = ""

            if isinstance(content, str) and content.strip():
                text = content
            elif isinstance(content, list):
                text = "".join(
                    block if isinstance(block, str) else block.get("text", "")
                    for block in content
                    if isinstance(block, str) or (isinstance(block, dict) and block.get("type") == "text")
                ).strip()

            if text:
                response_content = text
                break

        return response_content

    def delete_workflow(self, workflow_id: str) -> bool:
        """Delete a workflow.

        Args:
            workflow_id: Workflow to delete

        Returns:
            True if deleted, False if not found
        """
        if workflow_id in self._workflows:
            del self._workflows[workflow_id]
            return True
        return False

    def clear_workflow_history(self, workflow_id: str) -> bool:
        """Clear conversation history for a workflow.

        Useful for resetting human-in-the-loop conversations.

        Args:
            workflow_id: Workflow to clear history for

        Returns:
            True if cleared, False if workflow not found
        """
        if workflow_id in self._workflows:
            self._workflows[workflow_id]["messages"] = []
            return True
        return False

    def list_workflows(self) -> list[dict]:
        """List all active workflows.

        Returns:
            List of workflow info
        """
        return [
            {
                "workflow_id": wf_id,
                "agents": data["agents"],
                "provider": data["provider"],
                "model": data["model"],
            }
            for wf_id, data in self._workflows.items()
        ]
