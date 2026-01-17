"""Skills API router implementing progressive disclosure pattern.

Based on Anthropic's Agent Skills architecture.
Reference: https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
"""

from fastapi import APIRouter, Depends, HTTPException

from langchain_docker.api.dependencies import get_skill_registry
from langchain_docker.api.schemas.skills import (
    SkillCreateRequest,
    SkillCreateResponse,
    SkillDeleteResponse,
    SkillInfo,
    SkillListResponse,
    SkillLoadResponse,
    SkillMetadata,
    SkillResource,
    SkillResourceLoadResponse,
    SkillScript,
    SkillUpdateRequest,
)
from langchain_docker.api.services.skill_registry import SkillRegistry

router = APIRouter(prefix="/skills", tags=["skills"])


def _resources_to_dicts(resources: list | None) -> list[dict] | None:
    """Convert SkillResource list to dicts for registry."""
    if not resources:
        return None
    return [
        {"name": r.name, "description": r.description, "content": r.content or ""}
        for r in resources
    ]


def _scripts_to_dicts(scripts: list | None) -> list[dict] | None:
    """Convert SkillScript list to dicts for registry."""
    if not scripts:
        return None
    return [
        {"name": s.name, "description": s.description, "language": s.language, "content": s.content or ""}
        for s in scripts
    ]


def _skill_data_to_info(skill_data: dict) -> SkillInfo:
    """Convert skill data dict to SkillInfo response."""
    return SkillInfo(
        id=skill_data["id"],
        name=skill_data["name"],
        description=skill_data["description"],
        category=skill_data["category"],
        version=skill_data.get("version", "1.0.0"),
        author=skill_data.get("author"),
        is_builtin=skill_data.get("is_builtin", False),
        core_content=skill_data.get("core_content"),
        resources=[
            SkillResource(
                name=r["name"],
                description=r.get("description", ""),
                content=r.get("content"),
            )
            for r in skill_data.get("resources", [])
        ],
        scripts=[
            SkillScript(
                name=s["name"],
                description=s.get("description", ""),
                language=s.get("language", "python"),
                content=s.get("content"),
            )
            for s in skill_data.get("scripts", [])
        ],
        created_at=skill_data.get("created_at"),
        updated_at=skill_data.get("updated_at"),
    )


@router.get("", response_model=SkillListResponse)
async def list_skills(
    skill_registry: SkillRegistry = Depends(get_skill_registry),
) -> SkillListResponse:
    """List all available skills (Level 1 metadata only).

    Returns skill metadata for agent system prompts.
    This is the minimal context that's always loaded.
    """
    skills = skill_registry.list_skills_full()
    metadata = [
        SkillMetadata(
            id=s["id"],
            name=s["name"],
            description=s["description"],
            category=s["category"],
            version=s.get("version", "1.0.0"),
            author=s.get("author"),
        )
        for s in skills
    ]
    return SkillListResponse(skills=metadata, total=len(metadata))


@router.get("/{skill_id}", response_model=SkillInfo)
async def get_skill(
    skill_id: str,
    skill_registry: SkillRegistry = Depends(get_skill_registry),
) -> SkillInfo:
    """Get full skill information including content.

    Returns complete skill data for editing or viewing.
    """
    skill_data = skill_registry.get_skill_full(skill_id)
    if not skill_data:
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")

    return _skill_data_to_info(skill_data)


@router.post("", response_model=SkillCreateResponse)
async def create_skill(
    request: SkillCreateRequest,
    skill_registry: SkillRegistry = Depends(get_skill_registry),
) -> SkillCreateResponse:
    """Create a new custom skill.

    Creates a skill following the SKILL.md format with:
    - YAML frontmatter (name, description, category)
    - Markdown body (core instructions)
    - Optional resources and scripts
    """
    try:
        skill = skill_registry.create_custom_skill(
            name=request.name,
            description=request.description,
            core_content=request.core_content,
            skill_id=request.id,
            category=request.category,
            version=request.version,
            author=request.author,
            resources=_resources_to_dicts(request.resources),
            scripts=_scripts_to_dicts(request.scripts),
        )

        return SkillCreateResponse(
            skill_id=skill.id,
            name=skill.name,
            message=f"Skill '{skill.name}' created successfully",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{skill_id}", response_model=SkillInfo)
async def update_skill(
    skill_id: str,
    request: SkillUpdateRequest,
    skill_registry: SkillRegistry = Depends(get_skill_registry),
) -> SkillInfo:
    """Update an existing custom skill.

    Only custom skills can be updated. Built-in skills are read-only.
    """
    try:
        skill = skill_registry.update_custom_skill(
            skill_id=skill_id,
            name=request.name,
            description=request.description,
            core_content=request.core_content,
            category=request.category,
            version=request.version,
            author=request.author,
            resources=_resources_to_dicts(request.resources),
            scripts=_scripts_to_dicts(request.scripts),
        )

        return _skill_data_to_info(skill.to_dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{skill_id}", response_model=SkillDeleteResponse)
async def delete_skill(
    skill_id: str,
    skill_registry: SkillRegistry = Depends(get_skill_registry),
) -> SkillDeleteResponse:
    """Delete a custom skill.

    Only custom skills can be deleted. Built-in skills cannot be removed.
    """
    try:
        skill_registry.delete_custom_skill(skill_id)
        return SkillDeleteResponse(skill_id=skill_id, deleted=True)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{skill_id}/load", response_model=SkillLoadResponse)
async def load_skill(
    skill_id: str,
    skill_registry: SkillRegistry = Depends(get_skill_registry),
) -> SkillLoadResponse:
    """Load skill core content (Level 2).

    This is called by agents when they trigger a skill.
    Returns the main skill instructions.
    """
    skill = skill_registry.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")

    content = skill_registry.load_skill(skill_id)
    return SkillLoadResponse(
        skill_id=skill_id,
        name=skill.name,
        content=content,
    )


@router.get("/{skill_id}/resources/{resource_name}", response_model=SkillResourceLoadResponse)
async def load_skill_resource(
    skill_id: str,
    resource_name: str,
    skill_registry: SkillRegistry = Depends(get_skill_registry),
) -> SkillResourceLoadResponse:
    """Load a specific skill resource (Level 3).

    This is called by agents when they need additional details.
    Returns the content of a specific resource file.
    """
    skill = skill_registry.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")

    content = skill_registry.load_skill_details(skill_id, resource_name)
    return SkillResourceLoadResponse(
        skill_id=skill_id,
        resource_name=resource_name,
        content=content,
    )


@router.get("/{skill_id}/export")
async def export_skill(
    skill_id: str,
    skill_registry: SkillRegistry = Depends(get_skill_registry),
) -> dict:
    """Export skill as SKILL.md format.

    Returns the skill in portable SKILL.md format with YAML frontmatter.
    """
    try:
        content = skill_registry.export_skill_md(skill_id)
        return {
            "skill_id": skill_id,
            "format": "skill.md",
            "content": content,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/import")
async def import_skill(
    content: str,
    skill_registry: SkillRegistry = Depends(get_skill_registry),
) -> SkillCreateResponse:
    """Import a skill from SKILL.md format.

    Parses YAML frontmatter and creates a new skill.
    """
    try:
        skill = skill_registry.import_skill_md(content)
        return SkillCreateResponse(
            skill_id=skill.id,
            name=skill.name,
            message=f"Skill '{skill.name}' imported successfully",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
