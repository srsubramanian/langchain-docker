"""Redis-backed session storage.

Provides persistent session storage using Redis with automatic TTL expiration.
Sessions survive server restarts and can be shared across multiple API instances.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import redis

from langchain_docker.api.services.session_serializer import (
    deserialize_session,
    serialize_session,
)
from langchain_docker.utils.errors import SessionNotFoundError

if TYPE_CHECKING:
    from langchain_docker.api.services.session_service import Session


class RedisSessionStore:
    """Redis-backed session storage with TTL support.

    Uses Redis SETEX for automatic session expiration and maintains
    secondary indexes for user-based session filtering.
    """

    KEY_PREFIX = "session:"
    USER_INDEX_PREFIX = "user:"

    def __init__(self, redis_url: str, ttl_hours: int = 24):
        """Initialize Redis connection.

        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379/0)
            ttl_hours: Session TTL in hours (default: 24)
        """
        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._ttl_seconds = ttl_hours * 3600

    def _session_key(self, session_id: str) -> str:
        """Generate Redis key for session."""
        return f"{self.KEY_PREFIX}{session_id}"

    def _user_sessions_key(self, user_id: str) -> str:
        """Generate Redis key for user's session index."""
        return f"{self.USER_INDEX_PREFIX}{user_id}:sessions"

    def create(
        self,
        user_id: str = "default",
        metadata: Optional[dict] = None,
    ) -> Session:
        """Create a new session in Redis.

        Args:
            user_id: User ID who owns this session
            metadata: Optional metadata for the session

        Returns:
            Created session
        """
        # Import here to avoid circular imports
        from langchain_docker.api.services.session_service import Session

        session = Session(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            metadata=metadata or {},
        )
        self._save(session)
        return session

    def get(self, session_id: str) -> Session:
        """Get session by ID from Redis.

        Args:
            session_id: Session ID

        Returns:
            Session object

        Raises:
            SessionNotFoundError: If session not found or expired
        """
        data = self._redis.get(self._session_key(session_id))
        if not data:
            raise SessionNotFoundError(session_id)
        return deserialize_session(data)

    def get_or_create(
        self,
        session_id: Optional[str] = None,
        user_id: str = "default",
        metadata: Optional[dict] = None,
    ) -> Session:
        """Get existing session or create new one.

        Args:
            session_id: Optional session ID to look up
            user_id: User ID for new sessions
            metadata: Optional metadata for new sessions

        Returns:
            Existing or new session
        """
        if session_id:
            try:
                return self.get(session_id)
            except SessionNotFoundError:
                # Session ID provided but not found, create with that ID
                from langchain_docker.api.services.session_service import Session

                session = Session(
                    session_id=session_id,
                    user_id=user_id,
                    metadata=metadata or {},
                )
                self._save(session)
                return session
        return self.create(user_id=user_id, metadata=metadata)

    def save(self, session: Session) -> None:
        """Save session to Redis.

        Args:
            session: Session to save
        """
        self._save(session)

    def _save(self, session: Session) -> None:
        """Internal save with TTL and index maintenance.

        Args:
            session: Session to save
        """
        key = self._session_key(session.session_id)
        # Use SETEX for automatic TTL expiration
        self._redis.setex(key, self._ttl_seconds, serialize_session(session))
        # Add to user's session index
        self._redis.sadd(self._user_sessions_key(session.user_id), session.session_id)

    def list(
        self,
        limit: int = 10,
        offset: int = 0,
        user_id: Optional[str] = None,
    ) -> tuple[list[Session], int]:
        """List sessions with pagination.

        Args:
            limit: Maximum number of sessions to return
            offset: Number of sessions to skip
            user_id: Optional user ID to filter by

        Returns:
            Tuple of (sessions list, total count)
        """
        if user_id:
            # Get sessions for specific user from index
            session_ids = self._redis.smembers(self._user_sessions_key(user_id))
        else:
            # Get all sessions by scanning keys
            session_ids = set()
            for key in self._redis.scan_iter(f"{self.KEY_PREFIX}*"):
                session_ids.add(key.replace(self.KEY_PREFIX, ""))

        sessions = []
        expired_ids = []

        for sid in session_ids:
            try:
                sessions.append(self.get(sid))
            except SessionNotFoundError:
                # Session expired, mark for removal from index
                expired_ids.append(sid)

        # Clean up expired session IDs from user indexes
        for sid in expired_ids:
            if user_id:
                self._redis.srem(self._user_sessions_key(user_id), sid)

        # Sort by updated_at descending
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        total = len(sessions)
        return sessions[offset:offset + limit], total

    def delete(self, session_id: str) -> None:
        """Delete a session from Redis.

        Args:
            session_id: Session ID to delete

        Raises:
            SessionNotFoundError: If session not found
        """
        session = self.get(session_id)  # Raises if not found
        self._redis.delete(self._session_key(session_id))
        self._redis.srem(self._user_sessions_key(session.user_id), session_id)

    def clear(self) -> int:
        """Clear all sessions from Redis.

        Returns:
            Number of sessions deleted
        """
        # Get all session keys
        keys = list(self._redis.scan_iter(f"{self.KEY_PREFIX}*"))
        count = len(keys)

        if keys:
            self._redis.delete(*keys)

        # Clear all user indexes
        for key in self._redis.scan_iter(f"{self.USER_INDEX_PREFIX}*:sessions"):
            self._redis.delete(key)

        return count

    def update_timestamp(self, session_id: str) -> None:
        """Update session timestamp and refresh TTL.

        Args:
            session_id: Session ID

        Raises:
            SessionNotFoundError: If session not found
        """
        session = self.get(session_id)
        session.updated_at = datetime.utcnow()
        self._save(session)

    def shutdown(self) -> None:
        """Close Redis connection."""
        self._redis.close()
