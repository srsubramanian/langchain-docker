"""Approval API router for Human-in-the-Loop (HITL) tool execution.

Provides endpoints for managing approval requests that block tool execution
until a human approves or rejects the action.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from langchain_docker.api.dependencies import get_approval_service
from langchain_docker.api.schemas.approvals import (
    ApprovalListResponse,
    ApprovalRequestInfo,
    ApprovalResponse,
    ApproveRequest,
    RejectRequest,
)
from langchain_docker.api.services.approval_service import (
    ApprovalService,
    ApprovalStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/approvals", tags=["approvals"])


def _approval_to_info(approval) -> ApprovalRequestInfo:
    """Convert ApprovalRequest to ApprovalRequestInfo schema."""
    return ApprovalRequestInfo(
        id=approval.id,
        tool_call_id=approval.tool_call_id,
        session_id=approval.session_id,
        thread_id=approval.thread_id,
        tool_name=approval.tool_name,
        tool_args=approval.tool_args,
        message=approval.message,
        impact_summary=approval.impact_summary,
        status=approval.status.value,
        created_at=approval.created_at,
        expires_at=approval.expires_at,
        resolved_at=approval.resolved_at,
        resolved_by=approval.resolved_by,
        rejection_reason=approval.rejection_reason,
    )


@router.get("/pending", response_model=ApprovalListResponse)
async def list_pending_approvals(
    session_id: str = Query(..., description="Chat session ID"),
    approval_service: ApprovalService = Depends(get_approval_service),
) -> ApprovalListResponse:
    """List all pending approval requests for a session.

    Returns approvals that are waiting for human decision, sorted by
    creation time (newest first).
    """
    approvals = approval_service.list_pending(session_id)
    return ApprovalListResponse(
        approvals=[_approval_to_info(a) for a in approvals],
        total=len(approvals),
    )


@router.get("/{approval_id}", response_model=ApprovalRequestInfo)
async def get_approval(
    approval_id: str,
    approval_service: ApprovalService = Depends(get_approval_service),
) -> ApprovalRequestInfo:
    """Get details of a specific approval request."""
    approval = approval_service.get(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail=f"Approval not found: {approval_id}")
    return _approval_to_info(approval)


@router.post("/{approval_id}/approve", response_model=ApprovalResponse)
async def approve_request(
    approval_id: str,
    request: Optional[ApproveRequest] = None,
    user_id: Optional[str] = Query(None, description="User who approved"),
    approval_service: ApprovalService = Depends(get_approval_service),
) -> ApprovalResponse:
    """Approve a pending action.

    This unblocks the tool execution and allows it to proceed.
    """
    approval = approval_service.get(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail=f"Approval not found: {approval_id}")

    if approval.status != ApprovalStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Approval is not pending: {approval.status.value}",
        )

    updated = approval_service.approve(approval_id, approved_by=user_id)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to approve request")

    logger.info(f"Approved: {approval_id} for tool {updated.tool_name}")

    return ApprovalResponse(
        approval_id=approval_id,
        status="approved",
        message=f"Approved execution of {updated.tool_name}",
    )


@router.post("/{approval_id}/reject", response_model=ApprovalResponse)
async def reject_request(
    approval_id: str,
    request: Optional[RejectRequest] = None,
    user_id: Optional[str] = Query(None, description="User who rejected"),
    approval_service: ApprovalService = Depends(get_approval_service),
) -> ApprovalResponse:
    """Reject a pending action.

    This cancels the tool execution and the agent will be notified.
    """
    approval = approval_service.get(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail=f"Approval not found: {approval_id}")

    if approval.status != ApprovalStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Approval is not pending: {approval.status.value}",
        )

    reason = request.reason if request else None
    updated = approval_service.reject(approval_id, reason=reason, rejected_by=user_id)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to reject request")

    logger.info(f"Rejected: {approval_id} for tool {updated.tool_name}: {reason}")

    return ApprovalResponse(
        approval_id=approval_id,
        status="rejected",
        message=f"Rejected execution of {updated.tool_name}"
        + (f": {reason}" if reason else ""),
    )


@router.post("/{approval_id}/cancel", response_model=ApprovalResponse)
async def cancel_request(
    approval_id: str,
    approval_service: ApprovalService = Depends(get_approval_service),
) -> ApprovalResponse:
    """Cancel a pending approval request.

    Used when a session ends or the request is no longer needed.
    """
    approval = approval_service.get(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail=f"Approval not found: {approval_id}")

    if approval.status != ApprovalStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Approval is not pending: {approval.status.value}",
        )

    updated = approval_service.cancel(approval_id)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to cancel request")

    return ApprovalResponse(
        approval_id=approval_id,
        status="cancelled",
        message=f"Cancelled approval for {updated.tool_name}",
    )
