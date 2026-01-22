"""Agent serialization utilities for Redis storage.

Provides functions to serialize and deserialize CustomAgent and ScheduleConfig
dataclasses to/from JSON for Redis storage.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from langchain_docker.api.services.agent_service import CustomAgent, ScheduleConfig


def serialize_schedule(schedule: Optional[ScheduleConfig]) -> Optional[dict]:
    """Serialize a ScheduleConfig to JSON-compatible dict.

    Args:
        schedule: ScheduleConfig instance or None

    Returns:
        Dictionary with schedule fields or None
    """
    if schedule is None:
        return None
    return {
        "enabled": schedule.enabled,
        "cron_expression": schedule.cron_expression,
        "trigger_prompt": schedule.trigger_prompt,
        "timezone": schedule.timezone,
    }


def deserialize_schedule(data: Optional[dict]) -> Optional[ScheduleConfig]:
    """Deserialize a dict to ScheduleConfig.

    Args:
        data: Dictionary with schedule fields or None

    Returns:
        ScheduleConfig instance or None
    """
    if data is None:
        return None

    # Import here to avoid circular imports
    from langchain_docker.api.services.agent_service import ScheduleConfig

    return ScheduleConfig(
        enabled=data["enabled"],
        cron_expression=data["cron_expression"],
        trigger_prompt=data["trigger_prompt"],
        timezone=data.get("timezone", "UTC"),
    )


def serialize_agent(agent: CustomAgent) -> str:
    """Serialize entire CustomAgent to JSON string.

    Args:
        agent: CustomAgent dataclass instance

    Returns:
        JSON string representation of the agent
    """
    return json.dumps({
        "id": agent.id,
        "name": agent.name,
        "system_prompt": agent.system_prompt,
        "tool_configs": agent.tool_configs,
        "created_at": agent.created_at.isoformat(),
        "skill_ids": agent.skill_ids,
        "schedule": serialize_schedule(agent.schedule),
        "starter_prompts": agent.starter_prompts,
        "metadata": agent.metadata,
        "provider": agent.provider,
        "model": agent.model,
        "temperature": agent.temperature,
    })


def deserialize_agent(data: str) -> CustomAgent:
    """Deserialize JSON string to CustomAgent object.

    Args:
        data: JSON string representation of agent

    Returns:
        CustomAgent dataclass instance
    """
    # Import here to avoid circular imports
    from langchain_docker.api.services.agent_service import CustomAgent

    obj = json.loads(data)
    return CustomAgent(
        id=obj["id"],
        name=obj["name"],
        system_prompt=obj["system_prompt"],
        tool_configs=obj["tool_configs"],
        created_at=datetime.fromisoformat(obj["created_at"]),
        skill_ids=obj.get("skill_ids", []),
        schedule=deserialize_schedule(obj.get("schedule")),
        starter_prompts=obj.get("starter_prompts"),
        metadata=obj.get("metadata", {}),
        provider=obj.get("provider", "openai"),
        model=obj.get("model"),
        temperature=obj.get("temperature", 0.7),
    )
