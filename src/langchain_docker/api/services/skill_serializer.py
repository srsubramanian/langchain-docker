"""Skill serialization utilities for Redis storage.

Provides functions to serialize and deserialize SkillVersion and SkillUsageMetrics
dataclasses to/from JSON for Redis storage.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_docker.api.services.versioned_skill import (
        SkillUsageMetrics,
        SkillVersion,
        VersionedSkill,
    )


def serialize_skill_version(version: SkillVersion) -> str:
    """Serialize a SkillVersion to JSON string.

    Args:
        version: SkillVersion instance

    Returns:
        JSON string representation
    """
    return json.dumps(version.to_dict())


def deserialize_skill_version(data: str) -> SkillVersion:
    """Deserialize JSON string to SkillVersion.

    Args:
        data: JSON string representation

    Returns:
        SkillVersion instance
    """
    from langchain_docker.api.services.versioned_skill import SkillVersion

    return SkillVersion.from_dict(json.loads(data))


def serialize_metrics(metrics: SkillUsageMetrics) -> str:
    """Serialize SkillUsageMetrics to JSON string.

    Args:
        metrics: SkillUsageMetrics instance

    Returns:
        JSON string representation
    """
    return json.dumps(metrics.to_dict())


def deserialize_metrics(data: str) -> SkillUsageMetrics:
    """Deserialize JSON string to SkillUsageMetrics.

    Args:
        data: JSON string representation

    Returns:
        SkillUsageMetrics instance
    """
    from langchain_docker.api.services.versioned_skill import SkillUsageMetrics

    return SkillUsageMetrics.from_dict(json.loads(data))


def serialize_skill_meta(
    skill_id: str,
    is_builtin: bool,
    active_version: int,
    created_at: str,
    updated_at: str,
) -> str:
    """Serialize skill metadata to JSON string.

    Args:
        skill_id: Skill identifier
        is_builtin: Whether the skill is built-in
        active_version: Currently active version number
        created_at: Creation timestamp (ISO format)
        updated_at: Last update timestamp (ISO format)

    Returns:
        JSON string representation
    """
    return json.dumps({
        "skill_id": skill_id,
        "is_builtin": is_builtin,
        "active_version": active_version,
        "created_at": created_at,
        "updated_at": updated_at,
    })


def deserialize_skill_meta(data: str) -> dict:
    """Deserialize skill metadata from JSON string.

    Args:
        data: JSON string representation

    Returns:
        Dictionary with skill metadata
    """
    return json.loads(data)


def serialize_versioned_skill(skill: VersionedSkill) -> str:
    """Serialize a complete VersionedSkill to JSON string.

    Args:
        skill: VersionedSkill instance

    Returns:
        JSON string representation
    """
    return json.dumps(skill.to_dict())


def deserialize_versioned_skill(data: str) -> VersionedSkill:
    """Deserialize JSON string to VersionedSkill.

    Args:
        data: JSON string representation

    Returns:
        VersionedSkill instance
    """
    from langchain_docker.api.services.versioned_skill import VersionedSkill

    return VersionedSkill.from_dict(json.loads(data))
