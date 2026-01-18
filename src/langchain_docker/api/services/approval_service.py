"""Approval service for Human-in-the-Loop (HITL) tool execution.

This module manages approval requests for tools that require human confirmation
before execution. Approvals are stored in Redis (with in-memory fallback) and
integrate with LangGraph's interrupt/resume mechanism.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ApprovalStatus(str, Enum):
    """Status of an approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class ApprovalRequest:
    """A request for human approval before tool execution.

    Created when a HITL-enabled tool is called. The tool execution
    is paused until the human approves or rejects the request.
    """

    id: str
    tool_call_id: str  # LangGraph tool call ID
    session_id: str  # Chat session ID
    thread_id: str  # LangGraph thread ID for resuming
    tool_name: str  # e.g., "sql_delete"
    tool_args: dict[str, Any]  # Arguments passed to tool
    message: str  # Human-readable description
    impact_summary: Optional[str] = None  # Optional: "5,000 rows affected"
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None  # Auto-reject after this time
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None  # User who approved/rejected
    rejection_reason: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "tool_call_id": self.tool_call_id,
            "session_id": self.session_id,
            "thread_id": self.thread_id,
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "message": self.message,
            "impact_summary": self.impact_summary,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by": self.resolved_by,
            "rejection_reason": self.rejection_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ApprovalRequest":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            tool_call_id=data["tool_call_id"],
            session_id=data["session_id"],
            thread_id=data["thread_id"],
            tool_name=data["tool_name"],
            tool_args=data.get("tool_args", {}),
            message=data["message"],
            impact_summary=data.get("impact_summary"),
            status=ApprovalStatus(data.get("status", "pending")),
            created_at=datetime.fromisoformat(data["created_at"])
            if isinstance(data.get("created_at"), str)
            else data.get("created_at", datetime.utcnow()),
            expires_at=datetime.fromisoformat(data["expires_at"])
            if data.get("expires_at")
            else None,
            resolved_at=datetime.fromisoformat(data["resolved_at"])
            if data.get("resolved_at")
            else None,
            resolved_by=data.get("resolved_by"),
            rejection_reason=data.get("rejection_reason"),
        )


@dataclass
class ApprovalConfig:
    """Configuration for HITL approval on a tool.

    Can be defined in SKILL.md frontmatter or ToolTemplate.
    """

    message: str = "Approve this action?"  # Message shown to user
    show_args: bool = True  # Whether to show tool arguments in UI
    timeout_seconds: int = 300  # Auto-reject after this time (default 5 min)
    require_reason_on_reject: bool = False  # Require rejection reason

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "message": self.message,
            "show_args": self.show_args,
            "timeout_seconds": self.timeout_seconds,
            "require_reason_on_reject": self.require_reason_on_reject,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ApprovalConfig":
        """Create from dictionary."""
        return cls(
            message=data.get("message", "Approve this action?"),
            show_args=data.get("show_args", True),
            timeout_seconds=data.get("timeout_seconds", 300),
            require_reason_on_reject=data.get("require_reason_on_reject", False),
        )


class ApprovalService:
    """Service for managing approval requests.

    Stores approvals in Redis when available, falls back to in-memory storage.
    Integrates with LangGraph's interrupt/resume for blocking tool execution.
    """

    # Redis key prefixes
    APPROVAL_KEY_PREFIX = "approval:"
    SESSION_APPROVALS_PREFIX = "session:approvals:"

    def __init__(self, redis_url: Optional[str] = None):
        """Initialize the approval service.

        Args:
            redis_url: Optional Redis URL for persistent storage.
        """
        self._redis = None
        self._redis_url = redis_url
        self._memory_store: dict[str, ApprovalRequest] = {}
        self._session_index: dict[str, set[str]] = {}  # session_id -> approval_ids

        if redis_url:
            try:
                import redis

                self._redis = redis.from_url(redis_url, decode_responses=True)
                self._redis.ping()
                logger.info("ApprovalService initialized with Redis")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}. Using in-memory storage.")
                self._redis = None

    def create(
        self,
        tool_call_id: str,
        session_id: str,
        thread_id: str,
        tool_name: str,
        tool_args: dict[str, Any],
        config: Optional[ApprovalConfig] = None,
        impact_summary: Optional[str] = None,
    ) -> ApprovalRequest:
        """Create a new approval request.

        Args:
            tool_call_id: LangGraph tool call ID
            session_id: Chat session ID
            thread_id: LangGraph thread ID for resuming
            tool_name: Name of the tool requiring approval
            tool_args: Arguments passed to the tool
            config: Approval configuration
            impact_summary: Optional summary of the action's impact

        Returns:
            The created ApprovalRequest
        """
        config = config or ApprovalConfig()

        approval = ApprovalRequest(
            id=str(uuid.uuid4()),
            tool_call_id=tool_call_id,
            session_id=session_id,
            thread_id=thread_id,
            tool_name=tool_name,
            tool_args=tool_args,
            message=config.message,
            impact_summary=impact_summary,
            status=ApprovalStatus.PENDING,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(seconds=config.timeout_seconds)
            if config.timeout_seconds > 0
            else None,
        )

        self._store(approval)
        logger.info(f"Created approval request: {approval.id} for tool {tool_name}")
        return approval

    def get(self, approval_id: str) -> Optional[ApprovalRequest]:
        """Get an approval request by ID.

        Args:
            approval_id: The approval request ID

        Returns:
            The ApprovalRequest or None if not found
        """
        if self._redis:
            data = self._redis.get(f"{self.APPROVAL_KEY_PREFIX}{approval_id}")
            if data:
                return ApprovalRequest.from_dict(json.loads(data))
            return None
        return self._memory_store.get(approval_id)

    def list_pending(self, session_id: str) -> list[ApprovalRequest]:
        """List all pending approvals for a session.

        Args:
            session_id: The chat session ID

        Returns:
            List of pending ApprovalRequests
        """
        approvals = []

        if self._redis:
            approval_ids = self._redis.smembers(f"{self.SESSION_APPROVALS_PREFIX}{session_id}")
            for approval_id in approval_ids:
                approval = self.get(approval_id)
                if approval and approval.status == ApprovalStatus.PENDING:
                    # Check for expiration
                    if approval.expires_at and datetime.utcnow() > approval.expires_at:
                        self._expire(approval)
                    else:
                        approvals.append(approval)
        else:
            for approval_id in self._session_index.get(session_id, set()):
                approval = self._memory_store.get(approval_id)
                if approval and approval.status == ApprovalStatus.PENDING:
                    if approval.expires_at and datetime.utcnow() > approval.expires_at:
                        self._expire(approval)
                    else:
                        approvals.append(approval)

        return sorted(approvals, key=lambda a: a.created_at, reverse=True)

    def approve(
        self,
        approval_id: str,
        approved_by: Optional[str] = None,
    ) -> Optional[ApprovalRequest]:
        """Approve a pending request.

        Args:
            approval_id: The approval request ID
            approved_by: Optional user identifier

        Returns:
            The updated ApprovalRequest or None if not found
        """
        approval = self.get(approval_id)
        if not approval:
            logger.warning(f"Approval not found: {approval_id}")
            return None

        if approval.status != ApprovalStatus.PENDING:
            logger.warning(f"Approval {approval_id} is not pending: {approval.status}")
            return approval

        approval.status = ApprovalStatus.APPROVED
        approval.resolved_at = datetime.utcnow()
        approval.resolved_by = approved_by

        self._store(approval)
        logger.info(f"Approved: {approval_id} by {approved_by}")
        return approval

    def reject(
        self,
        approval_id: str,
        reason: Optional[str] = None,
        rejected_by: Optional[str] = None,
    ) -> Optional[ApprovalRequest]:
        """Reject a pending request.

        Args:
            approval_id: The approval request ID
            reason: Optional rejection reason
            rejected_by: Optional user identifier

        Returns:
            The updated ApprovalRequest or None if not found
        """
        approval = self.get(approval_id)
        if not approval:
            logger.warning(f"Approval not found: {approval_id}")
            return None

        if approval.status != ApprovalStatus.PENDING:
            logger.warning(f"Approval {approval_id} is not pending: {approval.status}")
            return approval

        approval.status = ApprovalStatus.REJECTED
        approval.resolved_at = datetime.utcnow()
        approval.resolved_by = rejected_by
        approval.rejection_reason = reason

        self._store(approval)
        logger.info(f"Rejected: {approval_id} by {rejected_by}: {reason}")
        return approval

    def cancel(self, approval_id: str) -> Optional[ApprovalRequest]:
        """Cancel a pending request (e.g., if session ends).

        Args:
            approval_id: The approval request ID

        Returns:
            The updated ApprovalRequest or None if not found
        """
        approval = self.get(approval_id)
        if not approval:
            return None

        if approval.status == ApprovalStatus.PENDING:
            approval.status = ApprovalStatus.CANCELLED
            approval.resolved_at = datetime.utcnow()
            self._store(approval)
            logger.info(f"Cancelled: {approval_id}")

        return approval

    def delete(self, approval_id: str) -> bool:
        """Delete an approval request.

        Args:
            approval_id: The approval request ID

        Returns:
            True if deleted
        """
        approval = self.get(approval_id)
        if not approval:
            return False

        if self._redis:
            self._redis.delete(f"{self.APPROVAL_KEY_PREFIX}{approval_id}")
            self._redis.srem(
                f"{self.SESSION_APPROVALS_PREFIX}{approval.session_id}",
                approval_id,
            )
        else:
            self._memory_store.pop(approval_id, None)
            if approval.session_id in self._session_index:
                self._session_index[approval.session_id].discard(approval_id)

        return True

    def _store(self, approval: ApprovalRequest) -> None:
        """Store an approval request."""
        if self._redis:
            # Store the approval
            self._redis.set(
                f"{self.APPROVAL_KEY_PREFIX}{approval.id}",
                json.dumps(approval.to_dict()),
                ex=86400,  # Expire after 24 hours
            )
            # Add to session index
            self._redis.sadd(
                f"{self.SESSION_APPROVALS_PREFIX}{approval.session_id}",
                approval.id,
            )
        else:
            self._memory_store[approval.id] = approval
            if approval.session_id not in self._session_index:
                self._session_index[approval.session_id] = set()
            self._session_index[approval.session_id].add(approval.id)

    def _expire(self, approval: ApprovalRequest) -> None:
        """Mark an approval as expired."""
        approval.status = ApprovalStatus.EXPIRED
        approval.resolved_at = datetime.utcnow()
        self._store(approval)
        logger.info(f"Expired: {approval.id}")
