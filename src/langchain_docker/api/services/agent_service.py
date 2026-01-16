"""Multi-agent orchestration service using LangGraph Supervisor."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langgraph_supervisor import create_supervisor

from langchain_docker.api.services.model_service import ModelService
from langchain_docker.api.services.tool_registry import ToolRegistry
from langchain_docker.core.tracing import trace_session

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


# Built-in tools for demo agents
def add(a: float, b: float) -> float:
    """Add two numbers together."""
    return a + b


def subtract(a: float, b: float) -> float:
    """Subtract b from a."""
    return a - b


def multiply(a: float, b: float) -> float:
    """Multiply two numbers together."""
    return a * b


def divide(a: float, b: float) -> float:
    """Divide a by b. Returns error if b is zero."""
    if b == 0:
        return float("inf")
    return a / b


def get_current_weather(location: str) -> str:
    """Get the current weather for a location (demo - returns mock data)."""
    # Mock weather data for demo
    weather_data = {
        "san francisco": "Sunny, 68°F (20°C), light breeze",
        "new york": "Cloudy, 55°F (13°C), chance of rain",
        "london": "Rainy, 50°F (10°C), overcast",
        "tokyo": "Clear, 72°F (22°C), humid",
        "paris": "Partly cloudy, 62°F (17°C), pleasant",
    }
    location_lower = location.lower()
    for city, weather in weather_data.items():
        if city in location_lower:
            return f"Weather in {location}: {weather}"
    return f"Weather in {location}: Sunny, 70°F (21°C), clear skies (default)"


def search_web(query: str) -> str:
    """Search the web for information (demo - returns mock data)."""
    # Mock search results for demo
    return f"Search results for '{query}': This is a demo search result. In production, integrate with a real search API like Tavily, SerpAPI, or DuckDuckGo."


def get_stock_price(symbol: str) -> str:
    """Get the current stock price for a symbol (demo - returns mock data)."""
    # Mock stock data for demo
    mock_prices = {
        "AAPL": 178.50,
        "GOOGL": 141.25,
        "MSFT": 378.90,
        "AMZN": 178.25,
        "META": 505.75,
    }
    symbol_upper = symbol.upper()
    if symbol_upper in mock_prices:
        return f"{symbol_upper}: ${mock_prices[symbol_upper]:.2f}"
    return f"{symbol_upper}: $100.00 (demo price)"


# SQL tools will be created dynamically using SkillRegistry
# See AgentService._create_sql_tools() for implementation


# Agent configurations
BUILTIN_AGENTS = {
    "math_expert": {
        "name": "math_expert",
        "tools": [add, subtract, multiply, divide],
        "prompt": "You are a math expert. Use the provided tools to solve mathematical problems. Always show your work step by step.",
    },
    "weather_expert": {
        "name": "weather_expert",
        "tools": [get_current_weather],
        "prompt": "You are a weather expert. Use the weather tool to get current conditions for any location.",
    },
    "research_expert": {
        "name": "research_expert",
        "tools": [search_web],
        "prompt": "You are a research expert with web search capabilities. Search for information to answer questions accurately.",
    },
    "finance_expert": {
        "name": "finance_expert",
        "tools": [get_stock_price],
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
    """

    def __init__(self, model_service: ModelService, skill_registry=None, scheduler_service=None):
        """Initialize agent service.

        Args:
            model_service: Model service for LLM access
            skill_registry: Skill registry for progressive disclosure skills
            scheduler_service: Scheduler service for cron-based execution
        """
        self.model_service = model_service
        self._workflows: dict[str, Any] = {}
        self._custom_agents: dict[str, CustomAgent] = {}
        self._direct_sessions: dict[str, dict] = {}  # For direct agent invocation (no supervisor)
        self._tool_registry = ToolRegistry()

        # Import SkillRegistry here to avoid circular imports if not provided
        if skill_registry is None:
            from langchain_docker.api.services.skill_registry import SkillRegistry
            skill_registry = SkillRegistry()
        self._skill_registry = skill_registry

        # Setup scheduler service
        if scheduler_service is None:
            from langchain_docker.api.services.scheduler_service import SchedulerService
            scheduler_service = SchedulerService()
        self._scheduler_service = scheduler_service
        self._scheduler_service.set_execution_callback(self._execute_scheduled_agent)
        self._scheduler_service.start()

        # Create dynamic agents from skill registry
        self._dynamic_agents = self._create_skill_based_agents()

    def _create_skill_based_agents(self) -> dict:
        """Create agents from registered skills.

        Returns:
            Dictionary of skill-based agent configurations
        """
        agents = {}

        # Get SQL skill if available
        from langchain_docker.api.services.skill_registry import SQLSkill
        skill = self._skill_registry.get_skill("write_sql")
        if skill and isinstance(skill, SQLSkill):
            sql_skill: SQLSkill = skill  # Type hint for IDE
            # Create tool functions that use the skill
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
            }

        return agents

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
        return [
            {
                "name": config["name"],
                "tools": [t.__name__ for t in config["tools"]],
                "description": config["prompt"][:100] + "...",
            }
            for config in all_agents.values()
        ]

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
                available = [s.id for s in self._skill_registry.list_skills()]
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
                    config={"metadata": {"agent_id": agent_id, "scheduled": True}},
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
            logger.info(f"Deleted custom agent: {agent_id}")
            return True
        return False

    def _sanitize_agent_name(self, name: str) -> str:
        """Sanitize agent name for OpenAI compatibility.

        OpenAI requires names to match pattern: ^[^\s<|\\/>]+
        (no spaces or special characters like <, |, \, /, >)

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

    def _build_agent_from_custom(self, agent_id: str, llm) -> Any:
        """Build a LangChain agent from a custom agent definition.

        Args:
            agent_id: Custom agent ID
            llm: Language model to use

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

        # Build system prompt with skills (progressive disclosure Level 2)
        system_prompt = custom.system_prompt

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

        # Sanitize name for OpenAI compatibility
        safe_name = self._sanitize_agent_name(custom.name)

        return create_agent(
            model=llm,
            tools=tools,
            name=safe_name,
            system_prompt=system_prompt,
        )

    def invoke_agent_direct(
        self,
        agent_id: str,
        message: str,
        session_id: Optional[str] = None,
        provider: str = "openai",
        model: Optional[str] = None,
    ) -> dict:
        """Invoke a custom agent directly without supervisor.

        This allows the agent to interact directly with the user for
        human-in-the-loop scenarios (e.g., asking for confirmation).

        Args:
            agent_id: Custom agent ID
            message: User message
            session_id: Session ID for conversation continuity
            provider: Model provider
            model: Model name (optional)

        Returns:
            Agent response with conversation state

        Raises:
            ValueError: If agent not found
        """
        if agent_id not in self._custom_agents:
            raise ValueError(f"Custom agent not found: {agent_id}")

        custom = self._custom_agents[agent_id]

        # Use session_id or create one based on agent_id
        sess_key = session_id or f"direct-{agent_id}"

        # Get or create session
        if sess_key not in self._direct_sessions:
            # Get model - use agent's configured provider/model if available
            agent_provider = custom.provider if hasattr(custom, 'provider') else provider
            agent_model = custom.model if hasattr(custom, 'model') else model

            llm = self.model_service.get_or_create(
                provider=agent_provider,
                model=agent_model,
                temperature=custom.temperature if hasattr(custom, 'temperature') else 0.7,
            )

            # Build the agent
            agent = self._build_agent_from_custom(agent_id, llm)
            # create_agent returns a compiled graph, so only compile if needed
            compiled = agent.compile() if hasattr(agent, 'compile') else agent

            self._direct_sessions[sess_key] = {
                "app": compiled,
                "agent_id": agent_id,
                "messages": [],
            }

        session_data = self._direct_sessions[sess_key]
        app = session_data["app"]

        # Get conversation history
        history = session_data.get("messages", [])

        # Debug: Log history before adding new message
        logger.info(f"[HITL Debug] Session {sess_key} - History before new message: {len(history)} messages")
        for i, msg in enumerate(history):
            msg_type = type(msg).__name__
            content_preview = str(msg.content)[:100] if hasattr(msg, 'content') else 'N/A'
            logger.info(f"[HITL Debug]   History[{i}] {msg_type}: {content_preview}")

        # Add user message
        user_msg = HumanMessage(content=message)
        history.append(user_msg)
        logger.info(f"[HITL Debug] Added user message: {message[:100]}")

        # Invoke agent directly
        with trace_session(sess_key):
            result = app.invoke(
                {"messages": history},
                config={"metadata": {"session_id": sess_key, "agent_id": agent_id}},
            )

        # Extract and store messages
        messages = result.get("messages", [])
        session_data["messages"] = messages

        # Debug: Log all messages to trace the flow
        logger.info(f"[HITL Debug] Direct invocation for {agent_id} - Total messages: {len(messages)}")
        for i, msg in enumerate(messages):
            msg_type = type(msg).__name__
            content_preview = str(msg.content)[:200] if hasattr(msg, 'content') else 'N/A'
            logger.info(f"[HITL Debug]   [{i}] {msg_type}: {content_preview}")

        # Find last AI message with text content
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
                logger.info(f"[HITL Debug] Selected response from {msg_type}: {text[:100]}...")
                break

        if not response_content:
            logger.warning(f"[HITL Debug] No text content found in any AI message!")

        return {
            "agent_id": agent_id,
            "session_id": sess_key,
            "response": response_content,
            "message_count": len(messages),
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
                agent = create_agent(
                    model=llm,
                    tools=config["tools"],
                    name=config["name"],
                    system_prompt=config["prompt"],
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
    ) -> dict:
        """Invoke a multi-agent workflow.

        Supports human-in-the-loop by preserving conversation history.

        Args:
            workflow_id: Workflow to invoke
            message: User message
            session_id: Optional session ID for tracing

        Returns:
            Workflow result with agent responses

        Raises:
            ValueError: If workflow not found
        """
        if workflow_id not in self._workflows:
            raise ValueError(f"Workflow not found: {workflow_id}")

        workflow_data = self._workflows[workflow_id]
        app = workflow_data["app"]

        # Get existing conversation history for human-in-the-loop support
        history = workflow_data.get("messages", [])

        # Add new user message to history
        user_msg = HumanMessage(content=message)
        history.append(user_msg)

        # Invoke with full conversation history
        with trace_session(session_id or workflow_id):
            result = app.invoke(
                {"messages": history},
                config={"metadata": {"session_id": session_id, "workflow_id": workflow_id}},
            )

        # Extract response messages and update stored history
        messages = result.get("messages", [])
        workflow_data["messages"] = messages  # Store full conversation

        # Find the last AI message with actual text content
        # (The last message might be a tool call without text)
        response_content = ""
        for msg in reversed(messages):
            # Skip non-AI messages (HumanMessage, ToolMessage, etc.)
            msg_type = type(msg).__name__
            if msg_type not in ("AIMessage", "AIMessageChunk"):
                continue

            content = msg.content
            text = ""

            if isinstance(content, str) and content.strip():
                text = content
            elif isinstance(content, list):
                # Join text parts from content blocks
                text = "".join(
                    block if isinstance(block, str) else block.get("text", "")
                    for block in content
                    if isinstance(block, str) or (isinstance(block, dict) and block.get("type") == "text")
                ).strip()

            if text:
                response_content = text
                break

        return {
            "workflow_id": workflow_id,
            "agents": workflow_data["agents"],
            "response": response_content,
            "message_count": len(messages),
        }

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
