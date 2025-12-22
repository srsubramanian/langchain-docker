"""Session-related Pydantic schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from langchain_docker.api.schemas.chat import MessageSchema


class SessionCreate(BaseModel):
    """Request schema for creating a session."""

    metadata: dict[str, Any] = Field(default_factory=dict, description="Optional session metadata")


class SessionResponse(BaseModel):
    """Response schema for session details."""

    session_id: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    messages: list[MessageSchema] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionSummary(BaseModel):
    """Summary of a session (for list endpoints)."""

    session_id: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    last_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionList(BaseModel):
    """Response schema for listing sessions."""

    sessions: list[SessionSummary]
    total: int
    limit: int
    offset: int


class DeleteResponse(BaseModel):
    """Response schema for delete operations."""

    deleted_count: int
    message: str
