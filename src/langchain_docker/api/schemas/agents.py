"""Schemas for multi-agent API endpoints."""

from typing import Any, Optional

from pydantic import BaseModel, Field


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
    metadata: dict = Field(
        default_factory=dict,
        description="Optional metadata for the agent",
    )


class CustomAgentInfo(BaseModel):
    """Information about a custom agent."""

    id: str = Field(..., description="Agent ID")
    name: str = Field(..., description="Agent name")
    tools: list[str] = Field(..., description="Tool IDs equipped on this agent")
    skills: list[str] = Field(default_factory=list, description="Skill IDs included")
    description: str = Field(..., description="Truncated system prompt")
    created_at: str = Field(..., description="Creation timestamp (ISO format)")


class CustomAgentCreateResponse(BaseModel):
    """Response after creating a custom agent."""

    agent_id: str = Field(..., description="Created agent ID")
    name: str = Field(..., description="Agent name")
    tools: list[str] = Field(..., description="Tool IDs")
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
    session_id: Optional[str] = Field(
        None,
        description="Session ID for tracing",
    )


class WorkflowInvokeResponse(BaseModel):
    """Response from invoking a workflow."""

    workflow_id: str = Field(..., description="Workflow ID")
    agents: list[str] = Field(..., description="Agents that participated")
    response: str = Field(..., description="Final response from the workflow")
    message_count: int = Field(..., description="Number of messages in the conversation")


class WorkflowDeleteResponse(BaseModel):
    """Response after deleting a workflow."""

    workflow_id: str = Field(..., description="Deleted workflow ID")
    deleted: bool = Field(..., description="Whether the workflow was deleted")
