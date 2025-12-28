"""Schemas for Skills API endpoints.

Based on Anthropic's Agent Skills pattern with progressive disclosure.
Reference: https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class SkillMetadata(BaseModel):
    """Level 1: Skill metadata (always visible in agent prompt)."""

    id: str = Field(..., description="Unique skill identifier")
    name: str = Field(..., description="Human-readable skill name")
    description: str = Field(..., description="What the skill does")
    category: str = Field(..., description="Skill category (database, document, etc.)")
    version: str = Field("1.0.0", description="Skill version")
    author: Optional[str] = Field(None, description="Skill author")


class SkillResource(BaseModel):
    """Additional resource file bundled with a skill."""

    name: str = Field(..., description="Resource filename (e.g., 'forms.md')")
    description: str = Field(..., description="What this resource contains")
    content: Optional[str] = Field(None, description="Resource content (if loaded)")


class SkillScript(BaseModel):
    """Executable script bundled with a skill."""

    name: str = Field(..., description="Script filename (e.g., 'extract.py')")
    description: str = Field(..., description="What this script does")
    language: str = Field("python", description="Script language")
    content: Optional[str] = Field(None, description="Script content (if loaded)")


class SkillCreateRequest(BaseModel):
    """Request to create a new skill (SKILL.md format)."""

    id: Optional[str] = Field(
        None,
        description="Custom ID (auto-generated from name if not provided)",
    )
    name: str = Field(
        ...,
        description="Skill name",
        min_length=1,
        max_length=100,
    )
    description: str = Field(
        ...,
        description="Brief description of what the skill does",
        min_length=10,
        max_length=500,
    )
    category: str = Field(
        "general",
        description="Skill category",
    )
    version: str = Field("1.0.0", description="Skill version")
    author: Optional[str] = Field(None, description="Skill author")

    # Level 2: Core content (body of SKILL.md)
    core_content: str = Field(
        ...,
        description="Main skill instructions (markdown format)",
        min_length=10,
    )

    # Level 3: Additional resources
    resources: list[SkillResource] = Field(
        default_factory=list,
        description="Additional resource files",
    )

    # Optional: Bundled scripts
    scripts: list[SkillScript] = Field(
        default_factory=list,
        description="Executable scripts",
    )


class SkillUpdateRequest(BaseModel):
    """Request to update an existing skill."""

    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    category: Optional[str] = Field(None)
    version: Optional[str] = Field(None)
    author: Optional[str] = Field(None)
    core_content: Optional[str] = Field(None)
    resources: Optional[list[SkillResource]] = Field(None)
    scripts: Optional[list[SkillScript]] = Field(None)


class SkillInfo(BaseModel):
    """Full skill information."""

    id: str = Field(..., description="Skill ID")
    name: str = Field(..., description="Skill name")
    description: str = Field(..., description="Skill description")
    category: str = Field(..., description="Skill category")
    version: str = Field(..., description="Skill version")
    author: Optional[str] = Field(None, description="Skill author")
    is_builtin: bool = Field(..., description="Whether this is a built-in skill")
    core_content: Optional[str] = Field(None, description="Core content (Level 2)")
    resources: list[SkillResource] = Field(
        default_factory=list,
        description="Additional resources",
    )
    scripts: list[SkillScript] = Field(
        default_factory=list,
        description="Bundled scripts",
    )
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")


class SkillListResponse(BaseModel):
    """Response listing all skills (Level 1 metadata only)."""

    skills: list[SkillMetadata] = Field(..., description="List of skill metadata")
    total: int = Field(..., description="Total number of skills")


class SkillCreateResponse(BaseModel):
    """Response after creating a skill."""

    skill_id: str = Field(..., description="Created skill ID")
    name: str = Field(..., description="Skill name")
    message: str = Field(..., description="Status message")


class SkillDeleteResponse(BaseModel):
    """Response after deleting a skill."""

    skill_id: str = Field(..., description="Deleted skill ID")
    deleted: bool = Field(..., description="Whether the skill was deleted")


class SkillLoadResponse(BaseModel):
    """Response when loading skill content (Level 2)."""

    skill_id: str = Field(..., description="Skill ID")
    name: str = Field(..., description="Skill name")
    content: str = Field(..., description="Loaded skill content")


class SkillResourceLoadResponse(BaseModel):
    """Response when loading a skill resource (Level 3)."""

    skill_id: str = Field(..., description="Skill ID")
    resource_name: str = Field(..., description="Resource name")
    content: str = Field(..., description="Resource content")


class SkillScriptExecuteRequest(BaseModel):
    """Request to execute a skill script."""

    script_name: str = Field(..., description="Script name to execute")
    args: dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments to pass to the script",
    )


class SkillScriptExecuteResponse(BaseModel):
    """Response from executing a skill script."""

    skill_id: str = Field(..., description="Skill ID")
    script_name: str = Field(..., description="Executed script name")
    output: str = Field(..., description="Script output")
    success: bool = Field(..., description="Whether execution succeeded")
