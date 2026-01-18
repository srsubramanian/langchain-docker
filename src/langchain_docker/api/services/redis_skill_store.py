"""Redis-backed versioned skill storage.

Provides persistent storage for skills with immutable version history
and usage metrics tracking. Skills survive server restarts and can be
shared across multiple API instances.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional

import redis

from langchain_docker.api.services.skill_serializer import (
    deserialize_metrics,
    deserialize_skill_meta,
    deserialize_skill_version,
    serialize_metrics,
    serialize_skill_meta,
    serialize_skill_version,
)
from langchain_docker.api.services.versioned_skill import (
    SkillUsageMetrics,
    SkillVersion,
    VersionedSkill,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class SkillNotFoundError(Exception):
    """Raised when a skill is not found in storage."""

    def __init__(self, skill_id: str):
        self.skill_id = skill_id
        super().__init__(f"Skill not found: {skill_id}")


class VersionNotFoundError(Exception):
    """Raised when a skill version is not found."""

    def __init__(self, skill_id: str, version_number: int):
        self.skill_id = skill_id
        self.version_number = version_number
        super().__init__(f"Version {version_number} not found for skill: {skill_id}")


class RedisSkillStore:
    """Redis-backed storage for versioned skills.

    Stores skill versions immutably in Redis with the following key structure:
    - skill:meta:{skill_id}                    → JSON (active_version, is_builtin, timestamps)
    - skill:version:{skill_id}:{version_num}   → JSON (immutable version snapshot)
    - skill:versions:{skill_id}                → ZSET (version_num → timestamp for ordering)
    - skill:metrics:{skill_id}                 → JSON (load counts, unique sessions)
    - skill:sessions:{skill_id}                → SET (session IDs for unique count, 7-day TTL)
    - skills:custom:index                      → SET (all custom skill IDs)
    """

    # Redis key prefixes
    KEY_PREFIX_META = "skill:meta:"
    KEY_PREFIX_VERSION = "skill:version:"
    KEY_PREFIX_VERSIONS = "skill:versions:"
    KEY_PREFIX_METRICS = "skill:metrics:"
    KEY_PREFIX_SESSIONS = "skill:sessions:"
    KEY_CUSTOM_INDEX = "skills:custom:index"

    # Session tracking TTL (7 days)
    SESSION_TTL_SECONDS = 7 * 24 * 60 * 60

    def __init__(self, redis_url: str):
        """Initialize Redis connection.

        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379/0)
        """
        self._redis = redis.from_url(redis_url, decode_responses=True)
        logger.info(f"RedisSkillStore initialized with URL: {redis_url}")

    def _meta_key(self, skill_id: str) -> str:
        """Generate Redis key for skill metadata."""
        return f"{self.KEY_PREFIX_META}{skill_id}"

    def _version_key(self, skill_id: str, version_number: int) -> str:
        """Generate Redis key for a specific version."""
        return f"{self.KEY_PREFIX_VERSION}{skill_id}:{version_number}"

    def _versions_key(self, skill_id: str) -> str:
        """Generate Redis key for version index (sorted set)."""
        return f"{self.KEY_PREFIX_VERSIONS}{skill_id}"

    def _metrics_key(self, skill_id: str) -> str:
        """Generate Redis key for metrics."""
        return f"{self.KEY_PREFIX_METRICS}{skill_id}"

    def _sessions_key(self, skill_id: str) -> str:
        """Generate Redis key for session tracking."""
        return f"{self.KEY_PREFIX_SESSIONS}{skill_id}"

    def save_new_version(
        self,
        skill_id: str,
        version: SkillVersion,
        set_active: bool = True,
        is_builtin: bool = False,
    ) -> int:
        """Save a new skill version.

        Creates the skill if it doesn't exist, otherwise appends a new version.
        Versions are immutable once created.

        Args:
            skill_id: Skill identifier
            version: SkillVersion to save
            set_active: Whether to set this as the active version
            is_builtin: Whether this is a built-in skill

        Returns:
            The version number that was saved
        """
        now = datetime.utcnow()
        now_iso = now.isoformat()

        meta_key = self._meta_key(skill_id)
        version_key = self._version_key(skill_id, version.version_number)
        versions_key = self._versions_key(skill_id)

        # Use pipeline for atomic operations
        pipe = self._redis.pipeline()

        # Save the version data
        pipe.set(version_key, serialize_skill_version(version))

        # Add to versions sorted set (score = timestamp for ordering)
        pipe.zadd(versions_key, {str(version.version_number): now.timestamp()})

        # Get or create metadata
        existing_meta = self._redis.get(meta_key)
        if existing_meta:
            meta = deserialize_skill_meta(existing_meta)
            if set_active:
                meta["active_version"] = version.version_number
            meta["updated_at"] = now_iso
        else:
            meta = {
                "skill_id": skill_id,
                "is_builtin": is_builtin,
                "active_version": version.version_number,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
            # Add to custom skills index if not builtin
            if not is_builtin:
                pipe.sadd(self.KEY_CUSTOM_INDEX, skill_id)

        pipe.set(
            meta_key,
            serialize_skill_meta(
                skill_id=skill_id,
                is_builtin=meta["is_builtin"],
                active_version=meta["active_version"],
                created_at=meta["created_at"],
                updated_at=meta["updated_at"],
            ),
        )

        pipe.execute()
        logger.debug(f"Saved version {version.version_number} for skill: {skill_id}")
        return version.version_number

    def get_skill(self, skill_id: str) -> Optional[VersionedSkill]:
        """Get a skill with all its versions and metrics.

        Args:
            skill_id: Skill identifier

        Returns:
            VersionedSkill or None if not found
        """
        meta_data = self._redis.get(self._meta_key(skill_id))
        if not meta_data:
            return None

        meta = deserialize_skill_meta(meta_data)

        # Get all versions
        versions_key = self._versions_key(skill_id)
        version_numbers = self._redis.zrange(versions_key, 0, -1)
        versions = []
        for vn in version_numbers:
            version_data = self._redis.get(self._version_key(skill_id, int(vn)))
            if version_data:
                versions.append(deserialize_skill_version(version_data))

        # Sort by version number
        versions.sort(key=lambda v: v.version_number)

        # Get metrics
        metrics = self.get_metrics(skill_id)

        return VersionedSkill(
            id=skill_id,
            is_builtin=meta.get("is_builtin", False),
            active_version=meta.get("active_version", 1),
            versions=versions,
            metrics=metrics,
            created_at=datetime.fromisoformat(meta["created_at"]),
            updated_at=datetime.fromisoformat(meta["updated_at"]),
        )

    def get_version(self, skill_id: str, version_number: int) -> Optional[SkillVersion]:
        """Get a specific version of a skill.

        Args:
            skill_id: Skill identifier
            version_number: Version number to retrieve

        Returns:
            SkillVersion or None if not found
        """
        version_data = self._redis.get(self._version_key(skill_id, version_number))
        if not version_data:
            return None
        return deserialize_skill_version(version_data)

    def get_active_version(self, skill_id: str) -> Optional[SkillVersion]:
        """Get the active version of a skill.

        Args:
            skill_id: Skill identifier

        Returns:
            Active SkillVersion or None if not found
        """
        meta_data = self._redis.get(self._meta_key(skill_id))
        if not meta_data:
            return None

        meta = deserialize_skill_meta(meta_data)
        return self.get_version(skill_id, meta["active_version"])

    def list_versions(
        self,
        skill_id: str,
        limit: int = 20,
        offset: int = 0,
        reverse: bool = True,
    ) -> list[SkillVersion]:
        """List versions of a skill with pagination.

        Args:
            skill_id: Skill identifier
            limit: Maximum number of versions to return
            offset: Offset for pagination
            reverse: If True, return newest first

        Returns:
            List of SkillVersion objects
        """
        versions_key = self._versions_key(skill_id)

        # Get version numbers from sorted set
        if reverse:
            # Newest first (highest score = most recent)
            version_numbers = self._redis.zrevrange(
                versions_key, offset, offset + limit - 1
            )
        else:
            version_numbers = self._redis.zrange(
                versions_key, offset, offset + limit - 1
            )

        versions = []
        for vn in version_numbers:
            version_data = self._redis.get(self._version_key(skill_id, int(vn)))
            if version_data:
                versions.append(deserialize_skill_version(version_data))

        return versions

    def get_version_count(self, skill_id: str) -> int:
        """Get the number of versions for a skill.

        Args:
            skill_id: Skill identifier

        Returns:
            Number of versions
        """
        return self._redis.zcard(self._versions_key(skill_id))

    def set_active_version(self, skill_id: str, version_number: int) -> bool:
        """Set the active version for a skill.

        Args:
            skill_id: Skill identifier
            version_number: Version number to activate

        Returns:
            True if successful, False if version doesn't exist

        Raises:
            SkillNotFoundError: If skill not found
        """
        meta_data = self._redis.get(self._meta_key(skill_id))
        if not meta_data:
            raise SkillNotFoundError(skill_id)

        # Verify version exists
        if not self._redis.exists(self._version_key(skill_id, version_number)):
            return False

        meta = deserialize_skill_meta(meta_data)
        meta["active_version"] = version_number
        meta["updated_at"] = datetime.utcnow().isoformat()

        self._redis.set(
            self._meta_key(skill_id),
            serialize_skill_meta(
                skill_id=skill_id,
                is_builtin=meta["is_builtin"],
                active_version=meta["active_version"],
                created_at=meta["created_at"],
                updated_at=meta["updated_at"],
            ),
        )

        logger.debug(f"Set active version to {version_number} for skill: {skill_id}")
        return True

    def delete_skill(self, skill_id: str) -> bool:
        """Delete a skill and all its versions.

        Args:
            skill_id: Skill identifier

        Returns:
            True if deleted, False if not found
        """
        meta_data = self._redis.get(self._meta_key(skill_id))
        if not meta_data:
            return False

        # Get all version numbers
        versions_key = self._versions_key(skill_id)
        version_numbers = self._redis.zrange(versions_key, 0, -1)

        pipe = self._redis.pipeline()

        # Delete all version data
        for vn in version_numbers:
            pipe.delete(self._version_key(skill_id, int(vn)))

        # Delete versions index
        pipe.delete(versions_key)

        # Delete metadata
        pipe.delete(self._meta_key(skill_id))

        # Delete metrics
        pipe.delete(self._metrics_key(skill_id))

        # Delete sessions tracking
        pipe.delete(self._sessions_key(skill_id))

        # Remove from custom index
        pipe.srem(self.KEY_CUSTOM_INDEX, skill_id)

        pipe.execute()
        logger.debug(f"Deleted skill: {skill_id}")
        return True

    def exists(self, skill_id: str) -> bool:
        """Check if a skill exists.

        Args:
            skill_id: Skill identifier

        Returns:
            True if skill exists
        """
        return self._redis.exists(self._meta_key(skill_id)) > 0

    def list_custom_skill_ids(self) -> list[str]:
        """List all custom skill IDs.

        Returns:
            List of skill IDs
        """
        return list(self._redis.smembers(self.KEY_CUSTOM_INDEX))

    def record_skill_load(
        self,
        skill_id: str,
        session_id: Optional[str] = None,
        version_number: Optional[int] = None,
    ) -> None:
        """Record a skill load for metrics tracking.

        Args:
            skill_id: Skill identifier
            session_id: Optional session ID for unique count
            version_number: Optional version number that was loaded
        """
        now = datetime.utcnow()
        metrics_key = self._metrics_key(skill_id)

        # Get or create metrics
        metrics_data = self._redis.get(metrics_key)
        if metrics_data:
            metrics = deserialize_metrics(metrics_data)
        else:
            metrics = SkillUsageMetrics(skill_id=skill_id)

        # Increment total loads
        metrics.total_loads += 1
        metrics.last_loaded_at = now

        # Track version-specific loads
        if version_number is not None:
            metrics.loads_by_version[version_number] = (
                metrics.loads_by_version.get(version_number, 0) + 1
            )

        # Track unique sessions
        if session_id:
            sessions_key = self._sessions_key(skill_id)
            # Add session to set (with TTL refresh)
            added = self._redis.sadd(sessions_key, session_id)
            if added:
                metrics.unique_sessions += 1
            # Refresh TTL on the sessions set
            self._redis.expire(sessions_key, self.SESSION_TTL_SECONDS)

        # Save metrics
        self._redis.set(metrics_key, serialize_metrics(metrics))

    def get_metrics(self, skill_id: str) -> Optional[SkillUsageMetrics]:
        """Get usage metrics for a skill.

        Args:
            skill_id: Skill identifier

        Returns:
            SkillUsageMetrics or None if not found
        """
        metrics_data = self._redis.get(self._metrics_key(skill_id))
        if not metrics_data:
            return None
        return deserialize_metrics(metrics_data)

    def get_skill_meta(self, skill_id: str) -> Optional[dict]:
        """Get skill metadata only (for quick lookups).

        Args:
            skill_id: Skill identifier

        Returns:
            Metadata dict or None if not found
        """
        meta_data = self._redis.get(self._meta_key(skill_id))
        if not meta_data:
            return None
        return deserialize_skill_meta(meta_data)

    def clear_all(self) -> int:
        """Clear all skills from Redis.

        Returns:
            Number of skills deleted
        """
        skill_ids = list(self._redis.smembers(self.KEY_CUSTOM_INDEX))
        count = 0
        for skill_id in skill_ids:
            if self.delete_skill(skill_id):
                count += 1
        return count

    def shutdown(self) -> None:
        """Close Redis connection."""
        self._redis.close()
