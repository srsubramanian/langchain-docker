"""Session management API endpoints."""

from fastapi import APIRouter, Depends, Query

from langchain_docker.api.dependencies import get_session_service
from langchain_docker.api.schemas.sessions import (
    DeleteResponse,
    SessionCreate,
    SessionList,
    SessionResponse,
)
from langchain_docker.api.services.session_service import SessionService

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse, status_code=201)
def create_session(
    request: SessionCreate,
    session_service: SessionService = Depends(get_session_service),
):
    """Create a new conversation session.

    Args:
        request: Session creation request with optional metadata

    Returns:
        Created session details
    """
    session = session_service.create(metadata=request.metadata)
    return session_service.to_response(session)


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: str,
    session_service: SessionService = Depends(get_session_service),
):
    """Get session details including full message history.

    Args:
        session_id: Session ID

    Returns:
        Session details with messages
    """
    session = session_service.get(session_id)
    return session_service.to_response(session)


@router.get("", response_model=SessionList)
def list_sessions(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session_service: SessionService = Depends(get_session_service),
):
    """List all sessions with pagination.

    Args:
        limit: Maximum number of sessions to return (1-100)
        offset: Number of sessions to skip

    Returns:
        Paginated list of sessions
    """
    sessions, total = session_service.list(limit=limit, offset=offset)
    summaries = [session_service.to_summary(s) for s in sessions]

    return SessionList(
        sessions=summaries,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.delete("/{session_id}", status_code=204)
def delete_session(
    session_id: str,
    session_service: SessionService = Depends(get_session_service),
):
    """Delete a specific session.

    Args:
        session_id: Session ID

    Returns:
        No content (204)
    """
    session_service.delete(session_id)


@router.delete("", response_model=DeleteResponse)
def clear_all_sessions(
    session_service: SessionService = Depends(get_session_service),
):
    """Clear all sessions.

    Returns:
        Number of sessions deleted
    """
    count = session_service.clear()
    return DeleteResponse(
        deleted_count=count,
        message=f"Cleared {count} session(s)",
    )
