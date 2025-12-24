"""Schemas for multi-agent API endpoints."""

from typing import Optional

from pydantic import BaseModel, Field


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
