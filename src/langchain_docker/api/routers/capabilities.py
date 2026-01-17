"""Capabilities API router for unified tools and skills.

Replaces the separate /skills and tools endpoints with a unified
/capabilities endpoint for the Agent Builder.
"""

from fastapi import APIRouter, Depends, HTTPException

from langchain_docker.api.dependencies import get_capability_registry
from langchain_docker.api.schemas.capabilities import (
    CapabilityDetailResponse,
    CapabilityInfo,
    CapabilityListResponse,
    CapabilityLoadResponse,
    CapabilityParameter,
)
from langchain_docker.api.services.capability_registry import CapabilityRegistry

router = APIRouter(prefix="/capabilities", tags=["capabilities"])


def _capability_to_info(cap) -> CapabilityInfo:
    """Convert Capability object to CapabilityInfo response."""
    return CapabilityInfo(
        id=cap.id,
        name=cap.name,
        description=cap.description,
        category=cap.category,
        type=cap.type,
        tools_provided=cap.tools_provided,
        parameters=[
            CapabilityParameter(
                name=p.name,
                type=p.type,
                description=p.description,
                default=p.default,
                required=p.required,
            )
            for p in cap.parameters
        ],
    )


@router.get("", response_model=CapabilityListResponse)
async def list_capabilities(
    capability_registry: CapabilityRegistry = Depends(get_capability_registry),
) -> CapabilityListResponse:
    """List all available capabilities.

    Returns all capabilities (both tools and skill bundles) for the Agent Builder.
    Users select from this unified list when configuring agents.
    """
    capabilities = capability_registry.list_all()
    cap_infos = [_capability_to_info(cap) for cap in capabilities]
    return CapabilityListResponse(capabilities=cap_infos, total=len(cap_infos))


@router.get("/categories")
async def list_categories(
    capability_registry: CapabilityRegistry = Depends(get_capability_registry),
) -> dict:
    """List all capability categories.

    Returns unique category names for filtering in the UI.
    """
    categories = capability_registry.get_categories()
    return {"categories": categories}


@router.get("/category/{category}", response_model=CapabilityListResponse)
async def list_capabilities_by_category(
    category: str,
    capability_registry: CapabilityRegistry = Depends(get_capability_registry),
) -> CapabilityListResponse:
    """List capabilities in a specific category.

    Args:
        category: Category name (e.g., "math", "database", "project_management")
    """
    capabilities = capability_registry.list_by_category(category)
    cap_infos = [_capability_to_info(cap) for cap in capabilities]
    return CapabilityListResponse(capabilities=cap_infos, total=len(cap_infos))


@router.get("/{capability_id}", response_model=CapabilityInfo)
async def get_capability(
    capability_id: str,
    capability_registry: CapabilityRegistry = Depends(get_capability_registry),
) -> CapabilityInfo:
    """Get detailed information about a capability.

    Args:
        capability_id: Capability identifier
    """
    capability = capability_registry.get(capability_id)
    if not capability:
        raise HTTPException(status_code=404, detail=f"Capability not found: {capability_id}")

    return _capability_to_info(capability)


@router.get("/{capability_id}/load", response_model=CapabilityLoadResponse)
async def load_capability(
    capability_id: str,
    capability_registry: CapabilityRegistry = Depends(get_capability_registry),
) -> CapabilityLoadResponse:
    """Load capability content (for skill bundles).

    For skill_bundle capabilities, this loads the core content (Level 2).
    For simple tools, returns a description of the tool.

    Args:
        capability_id: Capability identifier
    """
    capability = capability_registry.get(capability_id)
    if not capability:
        raise HTTPException(status_code=404, detail=f"Capability not found: {capability_id}")

    if capability.type == "skill_bundle" and capability.load_core:
        content = capability.load_core()
    else:
        # For simple tools, return the description
        content = f"## {capability.name}\n\n{capability.description}\n\nTools provided: {', '.join(capability.tools_provided)}"

    return CapabilityLoadResponse(
        capability_id=capability_id,
        name=capability.name,
        content=content,
    )


@router.get("/{capability_id}/details/{resource_name}", response_model=CapabilityDetailResponse)
async def load_capability_details(
    capability_id: str,
    resource_name: str,
    capability_registry: CapabilityRegistry = Depends(get_capability_registry),
) -> CapabilityDetailResponse:
    """Load detailed resource from a skill bundle capability.

    Args:
        capability_id: Capability identifier
        resource_name: Resource name (e.g., "samples", "examples")
    """
    capability = capability_registry.get(capability_id)
    if not capability:
        raise HTTPException(status_code=404, detail=f"Capability not found: {capability_id}")

    if capability.type != "skill_bundle" or not capability.load_details:
        raise HTTPException(
            status_code=400,
            detail=f"Capability {capability_id} does not support detailed resources"
        )

    content = capability.load_details(resource_name)
    return CapabilityDetailResponse(
        capability_id=capability_id,
        resource_name=resource_name,
        content=content,
    )
