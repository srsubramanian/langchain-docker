"""Session management service."""

import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from langchain_core.messages import BaseMessage

from langchain_docker.api.schemas.chat import MessageSchema
from langchain_docker.api.schemas.sessions import SessionResponse, SessionSummary
from langchain_docker.utils.errors import SessionNotFoundError


@dataclass
class Session:
    """In-memory session data structure."""

    session_id: str
    user_id: str = "default"
    messages: list[BaseMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)
    conversation_summary: str | None = None
    summary_message_count: int = 0
    last_summarized_at: datetime | None = None


class SessionService:
    """Service for managing conversation sessions.

    Provides in-memory storage with TTL cleanup and thread-safe access.
    """

    def __init__(self, ttl_hours: int = 24):
        """Initialize session service.

        Args:
            ttl_hours: Time-to-live for sessions in hours
        """
        self._sessions: OrderedDict[str, Session] = OrderedDict()
        self._lock = threading.Lock()
        self._ttl_seconds = ttl_hours * 3600
        self._cleanup_thread: Optional[threading.Thread] = None
        self._stop_cleanup = threading.Event()

        # Start background cleanup thread
        self._start_cleanup_thread()

    def _start_cleanup_thread(self) -> None:
        """Start background thread for session cleanup."""

        def cleanup_loop():
            while not self._stop_cleanup.is_set():
                self._cleanup_expired()
                time.sleep(300)  # Check every 5 minutes

        self._cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        self._cleanup_thread.start()

    def _cleanup_expired(self) -> None:
        """Remove sessions older than TTL."""
        now = datetime.utcnow()
        with self._lock:
            expired = [
                sid
                for sid, session in self._sessions.items()
                if (now - session.updated_at).total_seconds() > self._ttl_seconds
            ]
            for sid in expired:
                del self._sessions[sid]

    def create(self, user_id: str = "default", metadata: Optional[dict] = None) -> Session:
        """Create a new session.

        Args:
            user_id: User ID who owns this session
            metadata: Optional metadata for the session

        Returns:
            Created session
        """
        session = Session(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            metadata=metadata or {},
        )

        with self._lock:
            self._sessions[session.session_id] = session

        return session

    def get(self, session_id: str) -> Session:
        """Get a session by ID.

        Args:
            session_id: Session ID

        Returns:
            Session object

        Raises:
            SessionNotFoundError: If session not found
        """
        with self._lock:
            if session_id not in self._sessions:
                raise SessionNotFoundError(session_id)
            return self._sessions[session_id]

    def get_or_create(
        self,
        session_id: Optional[str] = None,
        user_id: str = "default",
        metadata: Optional[dict] = None,
    ) -> Session:
        """Get existing session or create new one.

        Args:
            session_id: Optional session ID
            user_id: User ID for new sessions
            metadata: Optional metadata for new sessions

        Returns:
            Existing or new session
        """
        if session_id:
            try:
                return self.get(session_id)
            except SessionNotFoundError:
                # Session ID provided but not found, create new with that ID
                session = Session(
                    session_id=session_id,
                    user_id=user_id,
                    metadata=metadata or {},
                )
                with self._lock:
                    self._sessions[session_id] = session
                return session
        else:
            return self.create(user_id=user_id, metadata=metadata)

    def list(
        self,
        limit: int = 10,
        offset: int = 0,
        user_id: Optional[str] = None,
    ) -> tuple[list[Session], int]:
        """List sessions with pagination, optionally filtered by user.

        Args:
            limit: Maximum number of sessions to return
            offset: Number of sessions to skip
            user_id: Optional user ID to filter by

        Returns:
            Tuple of (sessions list, total count)
        """
        with self._lock:
            sessions = list(self._sessions.values())
            # Filter by user if specified
            if user_id:
                sessions = [s for s in sessions if s.user_id == user_id]
            total = len(sessions)
            # Return most recently updated first
            sessions.sort(key=lambda s: s.updated_at, reverse=True)
            return sessions[offset : offset + limit], total

    def delete(self, session_id: str) -> None:
        """Delete a session.

        Args:
            session_id: Session ID

        Raises:
            SessionNotFoundError: If session not found
        """
        with self._lock:
            if session_id not in self._sessions:
                raise SessionNotFoundError(session_id)
            del self._sessions[session_id]

    def clear(self) -> int:
        """Clear all sessions.

        Returns:
            Number of sessions deleted
        """
        with self._lock:
            count = len(self._sessions)
            self._sessions.clear()
            return count

    def update_timestamp(self, session_id: str) -> None:
        """Update session's updated_at timestamp.

        Args:
            session_id: Session ID

        Raises:
            SessionNotFoundError: If session not found
        """
        session = self.get(session_id)
        session.updated_at = datetime.utcnow()

    def to_response(self, session: Session) -> SessionResponse:
        """Convert session to response schema.

        Args:
            session: Session object

        Returns:
            SessionResponse schema
        """
        return SessionResponse(
            session_id=session.session_id,
            created_at=session.created_at,
            updated_at=session.updated_at,
            message_count=len(session.messages),
            messages=[MessageSchema.from_langchain(msg) for msg in session.messages],
            metadata=session.metadata,
        )

    def to_summary(self, session: Session) -> SessionSummary:
        """Convert session to summary schema.

        Args:
            session: Session object

        Returns:
            SessionSummary schema
        """
        last_message = None
        if session.messages:
            last_message = session.messages[-1].content[:100]  # First 100 chars

        return SessionSummary(
            session_id=session.session_id,
            created_at=session.created_at,
            updated_at=session.updated_at,
            message_count=len(session.messages),
            last_message=last_message,
            metadata=session.metadata,
        )

    def shutdown(self) -> None:
        """Shutdown the service and cleanup thread."""
        self._stop_cleanup.set()
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=1)
