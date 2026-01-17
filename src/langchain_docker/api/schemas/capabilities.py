"""Schemas for Capabilities API endpoints.

Unified schema for tools and skills as capabilities.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class CapabilityParameter(BaseModel):
    """Parameter definition for a configurable capability."""

    name: str = Field(..., description="Parameter name")
    type: str = Field(..., description="Parameter type (string, number, boolean)")
    description: str = Field(..., description="Parameter description")
    default: Optional[str | int | float | bool] = Field(None, description="Default value")
    required: bool = Field(False, description="Whether parameter is required")


class CapabilityInfo(BaseModel):
    """Full capability information."""

    id: str = Field(..., description="Unique capability identifier")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="What the capability does")
    category: str = Field(..., description="Capability category")
    type: Literal["tool", "skill_bundle"] = Field(
        ..., description="Capability type: simple tool or skill bundle"
    )
    tools_provided: list[str] = Field(
        default_factory=list,
        description="Tools available when this capability is enabled",
    )
    parameters: list[CapabilityParameter] = Field(
        default_factory=list,
        description="Configurable parameters",
    )


class CapabilityListResponse(BaseModel):
    """Response listing all capabilities."""

    capabilities: list[CapabilityInfo] = Field(
        ..., description="List of capabilities"
    )
    total: int = Field(..., description="Total number of capabilities")


class CapabilityLoadResponse(BaseModel):
    """Response when loading skill bundle content."""

    capability_id: str = Field(..., description="Capability ID")
    name: str = Field(..., description="Capability name")
    content: str = Field(..., description="Loaded content")


class CapabilityDetailResponse(BaseModel):
    """Response when loading detailed resource."""

    capability_id: str = Field(..., description="Capability ID")
    resource_name: str = Field(..., description="Resource name")
    content: str = Field(..., description="Resource content")
