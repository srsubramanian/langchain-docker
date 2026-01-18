"""Schemas for Approval API endpoints.

These schemas define the request/response models for the HITL (Human-in-the-Loop)
approval system.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ApprovalConfigSchema(BaseModel):
    """Configuration for HITL approval on a tool."""

    message: str = Field(
        "Approve this action?",
        description="Message shown to the user when requesting approval",
    )
    show_args: bool = Field(
        True,
        description="Whether to show tool arguments in the approval UI",
    )
    timeout_seconds: int = Field(
        300,
        description="Auto-reject after this many seconds (0 = no timeout)",
        ge=0,
        le=3600,
    )
    require_reason_on_reject: bool = Field(
        False,
        description="Whether to require a reason when rejecting",
    )


class ApprovalRequestInfo(BaseModel):
    """Information about an approval request."""

    id: str = Field(..., description="Unique approval request ID")
    tool_call_id: str = Field(..., description="LangGraph tool call ID")
    session_id: str = Field(..., description="Chat session ID")
    thread_id: str = Field(..., description="LangGraph thread ID")
    tool_name: str = Field(..., description="Name of the tool requiring approval")
    tool_args: dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments passed to the tool",
    )
    message: str = Field(..., description="Human-readable description of the action")
    impact_summary: Optional[str] = Field(
        None,
        description="Optional summary of the action's impact",
    )
    status: str = Field(..., description="Current status: pending, approved, rejected, expired, cancelled")
    created_at: datetime = Field(..., description="When the request was created")
    expires_at: Optional[datetime] = Field(
        None,
        description="When the request will auto-expire",
    )
    resolved_at: Optional[datetime] = Field(
        None,
        description="When the request was resolved",
    )
    resolved_by: Optional[str] = Field(
        None,
        description="User who approved/rejected the request",
    )
    rejection_reason: Optional[str] = Field(
        None,
        description="Reason for rejection (if rejected)",
    )


class ApprovalListResponse(BaseModel):
    """Response listing pending approvals."""

    approvals: list[ApprovalRequestInfo] = Field(
        ...,
        description="List of pending approval requests",
    )
    total: int = Field(..., description="Total number of pending approvals")


class ApproveRequest(BaseModel):
    """Request to approve a pending action."""

    reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional reason for approval",
    )


class RejectRequest(BaseModel):
    """Request to reject a pending action."""

    reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Reason for rejection",
    )


class ApprovalResponse(BaseModel):
    """Response after approving or rejecting."""

    approval_id: str = Field(..., description="The approval request ID")
    status: str = Field(..., description="New status: approved or rejected")
    message: str = Field(..., description="Confirmation message")


class ApprovalEventData(BaseModel):
    """Data sent in SSE approval_request event."""

    approval_id: str = Field(..., description="Unique approval request ID")
    tool_name: str = Field(..., description="Name of the tool requiring approval")
    tool_args: Optional[dict[str, Any]] = Field(
        None,
        description="Tool arguments (if show_args is enabled)",
    )
    message: str = Field(..., description="Human-readable description")
    impact_summary: Optional[str] = Field(
        None,
        description="Impact summary if available",
    )
    expires_at: Optional[str] = Field(
        None,
        description="ISO timestamp when request expires",
    )
    config: ApprovalConfigSchema = Field(
        default_factory=ApprovalConfigSchema,
        description="Approval configuration",
    )
