"""Data classes for versioned skill management.

Provides dataclasses for storing skill versions with immutable history
and usage metrics tracking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SkillVersionResource:
    """Resource file bundled with a skill version."""

    name: str
    description: str
    content: str = ""


@dataclass
class SkillVersionScript:
    """Executable script bundled with a skill version."""

    name: str
    description: str
    language: str = "python"
    content: str = ""


@dataclass
class SkillVersion:
    """Immutable snapshot of a skill at a specific version.

    Each update to a skill creates a new SkillVersion with an
    auto-incremented version_number. Versions are immutable once created.
    """

    version_number: int  # Auto-increment (1, 2, 3...)
    semantic_version: str  # User-facing ("1.0.0", "1.1.0")
    name: str
    description: str
    category: str
    author: str | None
    core_content: str
    resources: list[SkillVersionResource] = field(default_factory=list)
    scripts: list[SkillVersionScript] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    change_summary: str | None = None  # What changed in this version

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "version_number": self.version_number,
            "semantic_version": self.semantic_version,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "author": self.author,
            "core_content": self.core_content,
            "resources": [
                {"name": r.name, "description": r.description, "content": r.content}
                for r in self.resources
            ],
            "scripts": [
                {
                    "name": s.name,
                    "description": s.description,
                    "language": s.language,
                    "content": s.content,
                }
                for s in self.scripts
            ],
            "created_at": self.created_at.isoformat(),
            "change_summary": self.change_summary,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillVersion:
        """Create from dictionary representation."""
        resources = [
            SkillVersionResource(
                name=r["name"],
                description=r.get("description", ""),
                content=r.get("content", ""),
            )
            for r in data.get("resources", [])
        ]
        scripts = [
            SkillVersionScript(
                name=s["name"],
                description=s.get("description", ""),
                language=s.get("language", "python"),
                content=s.get("content", ""),
            )
            for s in data.get("scripts", [])
        ]

        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.utcnow()

        return cls(
            version_number=data["version_number"],
            semantic_version=data.get("semantic_version", "1.0.0"),
            name=data["name"],
            description=data["description"],
            category=data.get("category", "general"),
            author=data.get("author"),
            core_content=data.get("core_content", ""),
            resources=resources,
            scripts=scripts,
            created_at=created_at,
            change_summary=data.get("change_summary"),
        )


@dataclass
class SkillUsageMetrics:
    """Usage metrics for a skill.

    Tracks load counts and unique sessions to help understand
    skill popularity and usage patterns.
    """

    skill_id: str
    total_loads: int = 0
    unique_sessions: int = 0
    last_loaded_at: datetime | None = None
    loads_by_version: dict[int, int] = field(default_factory=dict)  # version_number → count

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "skill_id": self.skill_id,
            "total_loads": self.total_loads,
            "unique_sessions": self.unique_sessions,
            "last_loaded_at": self.last_loaded_at.isoformat() if self.last_loaded_at else None,
            "loads_by_version": self.loads_by_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillUsageMetrics:
        """Create from dictionary representation."""
        last_loaded_at = data.get("last_loaded_at")
        if isinstance(last_loaded_at, str):
            last_loaded_at = datetime.fromisoformat(last_loaded_at)

        # Convert string keys to int for loads_by_version
        loads_by_version = {}
        for k, v in data.get("loads_by_version", {}).items():
            loads_by_version[int(k)] = v

        return cls(
            skill_id=data["skill_id"],
            total_loads=data.get("total_loads", 0),
            unique_sessions=data.get("unique_sessions", 0),
            last_loaded_at=last_loaded_at,
            loads_by_version=loads_by_version,
        )


@dataclass
class VersionedSkill:
    """A skill with full version history and metrics.

    Combines the active version pointer with the complete
    version history and usage metrics.
    """

    id: str
    is_builtin: bool
    active_version: int
    versions: list[SkillVersion] = field(default_factory=list)
    metrics: SkillUsageMetrics | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def active_version_data(self) -> SkillVersion | None:
        """Get the currently active version."""
        for v in self.versions:
            if v.version_number == self.active_version:
                return v
        return None

    @property
    def version_count(self) -> int:
        """Get the number of versions."""
        return len(self.versions)

    @property
    def name(self) -> str:
        """Get the name from the active version."""
        active = self.active_version_data
        return active.name if active else ""

    @property
    def description(self) -> str:
        """Get the description from the active version."""
        active = self.active_version_data
        return active.description if active else ""

    @property
    def category(self) -> str:
        """Get the category from the active version."""
        active = self.active_version_data
        return active.category if active else "general"

    @property
    def semantic_version(self) -> str:
        """Get the semantic version from the active version."""
        active = self.active_version_data
        return active.semantic_version if active else "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "is_builtin": self.is_builtin,
            "active_version": self.active_version,
            "versions": [v.to_dict() for v in self.versions],
            "metrics": self.metrics.to_dict() if self.metrics else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VersionedSkill:
        """Create from dictionary representation."""
        versions = [SkillVersion.from_dict(v) for v in data.get("versions", [])]

        metrics = None
        if data.get("metrics"):
            metrics = SkillUsageMetrics.from_dict(data["metrics"])

        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.utcnow()

        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        elif updated_at is None:
            updated_at = datetime.utcnow()

        return cls(
            id=data["id"],
            is_builtin=data.get("is_builtin", False),
            active_version=data.get("active_version", 1),
            versions=versions,
            metrics=metrics,
            created_at=created_at,
            updated_at=updated_at,
        )
