"""Redis-backed custom agent storage.

Provides persistent storage for custom agents using Redis.
Agents survive server restarts and can be shared across multiple API instances.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

import redis

from langchain_docker.api.services.agent_serializer import (
    deserialize_agent,
    serialize_agent,
)

if TYPE_CHECKING:
    from langchain_docker.api.services.agent_service import CustomAgent

logger = logging.getLogger(__name__)


class AgentNotFoundError(Exception):
    """Raised when an agent is not found in storage."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        super().__init__(f"Agent not found: {agent_id}")


class RedisAgentStore:
    """Redis-backed storage for custom agents.

    Stores custom agent definitions persistently in Redis, allowing them
    to survive server restarts and be shared across multiple instances.
    """

    KEY_PREFIX = "agent:"

    def __init__(self, redis_url: str):
        """Initialize Redis connection.

        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379/0)
        """
        self._redis = redis.from_url(redis_url, decode_responses=True)
        logger.info(f"RedisAgentStore initialized with URL: {redis_url}")

    def _agent_key(self, agent_id: str) -> str:
        """Generate Redis key for agent."""
        return f"{self.KEY_PREFIX}{agent_id}"

    def save(self, agent: CustomAgent) -> None:
        """Save a custom agent to Redis.

        Args:
            agent: CustomAgent to save
        """
        key = self._agent_key(agent.id)
        self._redis.set(key, serialize_agent(agent))
        logger.debug(f"Saved agent to Redis: {agent.id}")

    def get(self, agent_id: str) -> CustomAgent:
        """Get a custom agent by ID from Redis.

        Args:
            agent_id: Agent ID

        Returns:
            CustomAgent object

        Raises:
            AgentNotFoundError: If agent not found
        """
        data = self._redis.get(self._agent_key(agent_id))
        if not data:
            raise AgentNotFoundError(agent_id)
        return deserialize_agent(data)

    def get_optional(self, agent_id: str) -> Optional[CustomAgent]:
        """Get a custom agent by ID, returning None if not found.

        Args:
            agent_id: Agent ID

        Returns:
            CustomAgent object or None if not found
        """
        try:
            return self.get(agent_id)
        except AgentNotFoundError:
            return None

    def delete(self, agent_id: str) -> bool:
        """Delete a custom agent from Redis.

        Args:
            agent_id: Agent ID to delete

        Returns:
            True if deleted, False if not found
        """
        key = self._agent_key(agent_id)
        result = self._redis.delete(key)
        if result:
            logger.debug(f"Deleted agent from Redis: {agent_id}")
        return result > 0

    def list_all(self) -> list[CustomAgent]:
        """List all custom agents from Redis.

        Returns:
            List of all CustomAgent objects
        """
        agents = []
        for key in self._redis.scan_iter(f"{self.KEY_PREFIX}*"):
            data = self._redis.get(key)
            if data:
                try:
                    agents.append(deserialize_agent(data))
                except Exception as e:
                    logger.warning(f"Failed to deserialize agent {key}: {e}")
        return agents

    def exists(self, agent_id: str) -> bool:
        """Check if an agent exists in Redis.

        Args:
            agent_id: Agent ID

        Returns:
            True if agent exists
        """
        return self._redis.exists(self._agent_key(agent_id)) > 0

    def clear(self) -> int:
        """Clear all custom agents from Redis.

        Returns:
            Number of agents deleted
        """
        keys = list(self._redis.scan_iter(f"{self.KEY_PREFIX}*"))
        count = len(keys)
        if keys:
            self._redis.delete(*keys)
        logger.info(f"Cleared {count} agents from Redis")
        return count

    def shutdown(self) -> None:
        """Close Redis connection."""
        self._redis.close()
