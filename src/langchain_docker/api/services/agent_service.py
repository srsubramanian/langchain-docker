"""Multi-agent orchestration service using LangGraph Supervisor."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langgraph_supervisor import create_supervisor

from langchain_docker.api.services.capability_registry import CapabilityRegistry
from langchain_docker.api.services.model_service import ModelService
from langchain_docker.api.services.tool_registry import ToolRegistry
from langchain_docker.api.services.session_service import SessionService
from langchain_docker.core.tracing import trace_session

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
BUILTIN_AGENTS = {
    "math_expert": {
        "name": "math_expert",
        "tool_ids": ["add", "subtract", "multiply", "divide"],
        "prompt": "You are a math expert. Use the provided tools to solve mathematical problems. Always show your work step by step.",
    },
    "weather_expert": {
        "name": "weather_expert",
        "tool_ids": ["get_weather"],
        "prompt": "You are a weather expert. Use the weather tool to get current conditions for any location.",
    },
    "research_expert": {
        "name": "research_expert",
        "tool_ids": ["search_web"],
        "prompt": "You are a research expert with web search capabilities. Search for information to answer questions accurately.",
    },
    "finance_expert": {
        "name": "finance_expert",
        "tool_ids": ["get_stock_price"],
        "prompt": "You are a finance expert. Use the stock price tool to get current market data and provide financial insights.",
    },
    # sql_expert is created dynamically in AgentService using SkillRegistry
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
        """
        self.model_service = model_service
        self.session_service = session_service
        self.memory_service = memory_service
        self._checkpointer = checkpointer
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

        Returns:
            Compiled agent graph with middleware and checkpointing
        """
        if use_skills:
            # Create agent with skill middleware and optional checkpointing
            # Middleware tools (load_skill, list_loaded_skills) are automatically added
            agent = create_agent(
                model=llm,
                tools=tools,
                name=agent_name,
                system_prompt=system_prompt,
                middleware=[self._skill_middleware],
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

            with trace_session(workflow_id):
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

        # Create tool instances from configurations
        tools = []
        for tc in custom.tool_configs:
            tool = self._tool_registry.create_tool_instance(
                tc["tool_id"],
                tc.get("config", {}),
            )
            tools.append(tool)

        # Build system prompt
        system_prompt = custom.system_prompt

        # Sanitize name for OpenAI compatibility
        safe_name = self._sanitize_agent_name(custom.name)

        if use_middleware and custom.skill_ids:
            # Use middleware pattern: skills are loaded dynamically via load_skill tool
            # The middleware will:
            # 1. Inject skill descriptions into system prompt
            # 2. Track loaded skills in state
            # 3. Provide load_skill and list_loaded_skills tools

            # Add hint about available skills to the prompt
            skill_names = ", ".join(custom.skill_ids)
            system_prompt += f"\n\n# Available Skills\nYou have access to the following skills: {skill_names}\nUse the load_skill tool to load a skill before using its domain tools."

            return self.create_middleware_enabled_agent(
                agent_name=safe_name,
                llm=llm,
                tools=tools,
                system_prompt=system_prompt,
                use_skills=True,
            )
        else:
            # Legacy pattern: directly embed skill content in system prompt
            if custom.skill_ids:
                skill_contexts = []
                for skill_id in custom.skill_ids:
                    skill = self._skill_registry.get_skill(skill_id)
                    if skill:
                        # Load Level 2 content from the skill
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

            # Invoke agent with optimized context
            with trace_session(sess_key):
                result = app.invoke(
                    {"messages": context_messages},
                    config={
                        "configurable": {"thread_id": sess_key},
                        "metadata": {"session_id": sess_key, "agent_id": agent_id},
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

            with trace_session(sess_key):
                result = app.invoke(
                    {"messages": history},
                    config={
                        "configurable": {"thread_id": sess_key},
                        "metadata": {"session_id": sess_key, "agent_id": agent_id},
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
                if "tool_ids" in config:
                    tools = [
                        self._tool_registry.create_tool_instance(tid)
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
            user_msg = HumanMessage(content=message)
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

            # Invoke with optimized context
            with trace_session(sess_id):
                result = app.invoke(
                    {"messages": context_messages},
                    config={
                        "configurable": {"thread_id": sess_id},
                        "metadata": {"session_id": sess_id, "workflow_id": workflow_id},
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
            user_msg = HumanMessage(content=message)
            history.append(user_msg)

            with trace_session(sess_id):
                result = app.invoke(
                    {"messages": history},
                    config={
                        "configurable": {"thread_id": sess_id},
                        "metadata": {"session_id": sess_id, "workflow_id": workflow_id},
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
