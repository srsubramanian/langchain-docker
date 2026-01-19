"""Schemas for multi-agent API endpoints."""

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from langchain_docker.api.schemas.chat import MemoryMetadata


# Schedule Schemas


class ScheduleConfig(BaseModel):
    """Configuration for scheduled agent execution."""

    enabled: bool = Field(
        default=False,
        description="Whether the schedule is active",
    )
    cron_expression: str = Field(
        ...,
        description="Cron expression (e.g., '0 9 * * *' for daily at 9am)",
    )
    trigger_prompt: str = Field(
        ...,
        description="The prompt/message to send when the schedule triggers",
        min_length=1,
    )
    timezone: str = Field(
        default="UTC",
        description="Timezone for the schedule (e.g., 'America/New_York')",
    )

    @field_validator("cron_expression")
    @classmethod
    def validate_cron(cls, v: str) -> str:
        """Validate cron expression format."""
        parts = v.strip().split()
        if len(parts) != 5:
            raise ValueError(
                "Cron expression must have 5 parts: minute hour day month weekday"
            )
        return v


# Tool Registry Schemas


class ToolParameterSchema(BaseModel):
    """Schema for a tool parameter."""

    name: str = Field(..., description="Parameter name")
    type: str = Field(..., description="Parameter type (string, number, boolean)")
    description: str = Field(..., description="Parameter description")
    default: Any = Field(None, description="Default value")
    required: bool = Field(False, description="Whether parameter is required")


class ToolTemplateSchema(BaseModel):
    """Schema for a tool template."""

    id: str = Field(..., description="Unique tool identifier")
    name: str = Field(..., description="Human-readable tool name")
    description: str = Field(..., description="Tool description")
    category: str = Field(..., description="Tool category (math, weather, etc.)")
    parameters: list[ToolParameterSchema] = Field(
        default_factory=list,
        description="Configurable parameters for this tool",
    )


# Custom Agent Schemas


class ToolConfigRequest(BaseModel):
    """Tool configuration for a custom agent."""

    tool_id: str = Field(..., description="Tool template ID from registry")
    config: dict = Field(
        default_factory=dict,
        description="Tool-specific configuration parameters",
    )


class CustomAgentCreateRequest(BaseModel):
    """Request to create a custom agent."""

    agent_id: Optional[str] = Field(
        None,
        description="Custom ID (auto-generated UUID if not provided)",
    )
    name: str = Field(
        ...,
        description="Agent name",
        min_length=1,
        max_length=50,
    )
    system_prompt: str = Field(
        ...,
        description="System prompt defining the agent's behavior and personality",
        min_length=10,
    )
    tools: list[ToolConfigRequest] = Field(
        default_factory=list,
        description="Tools to equip the agent with",
    )
    skills: list[str] = Field(
        default_factory=list,
        description="Skill IDs to include (skills add their tools to the agent)",
    )
    schedule: Optional[ScheduleConfig] = Field(
        None,
        description="Optional schedule configuration for automated execution",
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Optional metadata for the agent",
    )
    provider: str = Field(
        "openai",
        description="Model provider to use (openai, anthropic, google, bedrock)",
    )
    model: Optional[str] = Field(
        None,
        description="Model name (uses provider default if not specified)",
    )
    temperature: float = Field(
        0.7,
        ge=0.0,
        le=2.0,
        description="Temperature for model responses (0.0-2.0)",
    )


class ScheduleInfo(BaseModel):
    """Schedule information for display."""

    enabled: bool = Field(..., description="Whether the schedule is active")
    cron_expression: str = Field(..., description="Cron expression")
    trigger_prompt: str = Field(..., description="Prompt to run on trigger")
    timezone: str = Field(..., description="Timezone")
    next_run: Optional[str] = Field(None, description="Next scheduled run time (ISO format)")


class CustomAgentInfo(BaseModel):
    """Information about a custom agent."""

    id: str = Field(..., description="Agent ID")
    name: str = Field(..., description="Agent name")
    tools: list[str] = Field(..., description="Tool IDs equipped on this agent")
    skills: list[str] = Field(default_factory=list, description="Skill IDs included")
    description: str = Field(..., description="Truncated system prompt")
    schedule: Optional[ScheduleInfo] = Field(None, description="Schedule configuration")
    created_at: str = Field(..., description="Creation timestamp (ISO format)")
    provider: str = Field("openai", description="Model provider")
    model: Optional[str] = Field(None, description="Model name")
    temperature: float = Field(0.7, description="Temperature setting")


class CustomAgentCreateResponse(BaseModel):
    """Response after creating a custom agent."""

    agent_id: str = Field(..., description="Created agent ID")
    name: str = Field(..., description="Agent name")
    tools: list[str] = Field(..., description="Tool IDs")
    schedule_enabled: bool = Field(default=False, description="Whether schedule is active")
    message: str = Field(..., description="Status message")


class CustomAgentUpdateRequest(BaseModel):
    """Request to update a custom agent. All fields are optional for partial updates."""

    name: Optional[str] = Field(
        None,
        description="Agent name",
        min_length=1,
        max_length=50,
    )
    system_prompt: Optional[str] = Field(
        None,
        description="System prompt defining the agent's behavior and personality",
        min_length=10,
    )
    tools: Optional[list[ToolConfigRequest]] = Field(
        None,
        description="Tools to equip the agent with",
    )
    skills: Optional[list[str]] = Field(
        None,
        description="Skill IDs to include",
    )
    schedule: Optional[ScheduleConfig] = Field(
        None,
        description="Schedule configuration for automated execution",
    )
    metadata: Optional[dict] = Field(
        None,
        description="Optional metadata for the agent",
    )
    provider: Optional[str] = Field(
        None,
        description="Model provider to use (openai, anthropic, google, bedrock)",
    )
    model: Optional[str] = Field(
        None,
        description="Model name (uses provider default if not specified)",
    )
    temperature: Optional[float] = Field(
        None,
        ge=0.0,
        le=2.0,
        description="Temperature for model responses (0.0-2.0)",
    )


class CustomAgentUpdateResponse(BaseModel):
    """Response after updating a custom agent."""

    agent_id: str = Field(..., description="Updated agent ID")
    name: str = Field(..., description="Agent name")
    tools: list[str] = Field(..., description="Tool IDs")
    skills: list[str] = Field(default_factory=list, description="Skill IDs")
    provider: str = Field(..., description="Model provider")
    model: Optional[str] = Field(None, description="Model name")
    temperature: float = Field(..., description="Temperature setting")
    message: str = Field(..., description="Status message")


class CustomAgentDeleteResponse(BaseModel):
    """Response after deleting a custom agent."""

    agent_id: str = Field(..., description="Deleted agent ID")
    deleted: bool = Field(..., description="Whether the agent was deleted")


# Built-in Agent Schemas


class AgentInfo(BaseModel):
    """Information about a built-in agent."""

    name: str = Field(..., description="Agent name")
    tools: list[str] = Field(..., description="List of tool names")
    description: str = Field(..., description="Agent description")


class WorkflowCreateRequest(BaseModel):
    """Request to create a multi-agent workflow."""

    workflow_id: Optional[str] = Field(
        None,
        description="Custom workflow ID (auto-generated if not provided)",
    )
    agents: list[str] = Field(
        ...,
        description="List of agent names to include in the workflow",
        min_length=1,
    )
    provider: str = Field(
        "openai",
        description="Model provider to use",
    )
    model: Optional[str] = Field(
        None,
        description="Model name (uses provider default if not specified)",
    )
    supervisor_prompt: Optional[str] = Field(
        None,
        description="Custom supervisor prompt (uses default if not specified)",
    )


class WorkflowInfo(BaseModel):
    """Information about a workflow."""

    workflow_id: str = Field(..., description="Workflow ID")
    agents: list[str] = Field(..., description="Agents in the workflow")
    provider: str = Field(..., description="Model provider")
    model: Optional[str] = Field(None, description="Model name")


class WorkflowCreateResponse(BaseModel):
    """Response after creating a workflow."""

    workflow_id: str = Field(..., description="Created workflow ID")
    agents: list[str] = Field(..., description="Agents in the workflow")
    message: str = Field(..., description="Status message")


class WorkflowInvokeRequest(BaseModel):
    """Request to invoke a workflow."""

    message: str = Field(..., description="User message to process")
    images: Optional[list[str]] = Field(
        None,
        description="Optional list of base64 data URIs for images",
    )
    session_id: Optional[str] = Field(
        None,
        description="Session ID for persistence and conversation continuity",
    )
    # Memory options for unified conversation management
    enable_memory: bool = Field(
        True,
        description="Enable memory management (summarization for long conversations)",
    )
    memory_trigger_count: Optional[int] = Field(
        None,
        gt=0,
        description="Override: Number of messages before triggering summarization",
    )
    memory_keep_recent: Optional[int] = Field(
        None,
        gt=0,
        description="Override: Number of recent messages to keep after summarization",
    )


class WorkflowInvokeResponse(BaseModel):
    """Response from invoking a workflow."""

    workflow_id: str = Field(..., description="Workflow ID")
    agents: list[str] = Field(..., description="Agents that participated")
    response: str = Field(..., description="Final response from the workflow")
    message_count: int = Field(..., description="Number of messages in the conversation")
    session_id: str = Field(..., description="Session ID for conversation persistence")
    memory_metadata: Optional[MemoryMetadata] = Field(
        None,
        description="Metadata about memory management (summarization)",
    )


class WorkflowDeleteResponse(BaseModel):
    """Response after deleting a workflow."""

    workflow_id: str = Field(..., description="Deleted workflow ID")
    deleted: bool = Field(..., description="Whether the workflow was deleted")


# Direct Agent Invocation (no supervisor)


class DirectInvokeRequest(BaseModel):
    """Request to invoke an agent directly (no supervisor)."""

    message: str = Field(..., description="User message")
    images: Optional[list[str]] = Field(
        None,
        description="Optional list of base64 data URIs for images",
    )
    session_id: Optional[str] = Field(
        None,
        description="Session ID for conversation continuity",
    )
    # Provider/model override - allows UI to override agent defaults
    provider: Optional[str] = Field(
        None,
        description="Override model provider (openai, anthropic, google, bedrock)",
    )
    model: Optional[str] = Field(
        None,
        description="Override model name",
    )
    temperature: Optional[float] = Field(
        None,
        ge=0.0,
        le=2.0,
        description="Override temperature for model responses (0.0-2.0)",
    )
    # Memory options for unified conversation management
    enable_memory: bool = Field(
        True,
        description="Enable memory management (summarization for long conversations)",
    )
    memory_trigger_count: Optional[int] = Field(
        None,
        gt=0,
        description="Override: Number of messages before triggering summarization",
    )
    memory_keep_recent: Optional[int] = Field(
        None,
        gt=0,
        description="Override: Number of recent messages to keep after summarization",
    )


class DirectInvokeResponse(BaseModel):
    """Response from direct agent invocation."""

    agent_id: str = Field(..., description="Agent ID")
    session_id: str = Field(..., description="Session ID for follow-up messages")
    response: str = Field(..., description="Agent response")
    message_count: int = Field(..., description="Number of messages in conversation")
    memory_metadata: Optional[MemoryMetadata] = Field(
        None,
        description="Metadata about memory management (summarization)",
    )
