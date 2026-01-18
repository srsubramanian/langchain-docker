"""Skills API router implementing progressive disclosure pattern.

Based on Anthropic's Agent Skills architecture.
Reference: https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from langchain_docker.api.dependencies import get_skill_registry
from langchain_docker.api.schemas.skills import (
    SkillCreateRequest,
    SkillCreateResponse,
    SkillDeleteResponse,
    SkillDiffField,
    SkillDiffResponse,
    SkillInfo,
    SkillListResponse,
    SkillLoadResponse,
    SkillMetadata,
    SkillResource,
    SkillResourceLoadResponse,
    SkillScript,
    SkillUpdateRequest,
    SkillUsageMetricsResponse,
    SkillVersionDetail,
    SkillVersionInfo,
    SkillVersionListResponse,
    VersionedSkillInfo,
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
        has_custom_content=skill_data.get("has_custom_content"),
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
    """Update an existing skill (custom or built-in).

    For custom skills: Full update of all fields is supported.
    For built-in skills: Only core_content and resources can be updated.
                         Requires Redis for persistence.

    When Redis is configured, this creates a new immutable version.
    """
    skill = skill_registry.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")

    try:
        if getattr(skill, "is_builtin", False):
            # Built-in skill: only update content and resources
            updated_skill = skill_registry.update_builtin_skill(
                skill_id=skill_id,
                core_content=request.core_content,
                resources=_resources_to_dicts(request.resources),
                change_summary=request.change_summary,
            )
            skill_data = skill_registry.get_skill_full(skill_id)
            return _skill_data_to_info(skill_data)
        else:
            # Custom skill: full update
            updated_skill = skill_registry.update_custom_skill(
                skill_id=skill_id,
                name=request.name,
                description=request.description,
                core_content=request.core_content,
                category=request.category,
                version=request.version,
                author=request.author,
                resources=_resources_to_dicts(request.resources),
                scripts=_scripts_to_dicts(request.scripts),
                change_summary=request.change_summary,
            )
            return _skill_data_to_info(updated_skill.to_dict())
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


@router.post("/{skill_id}/reset", response_model=SkillInfo)
async def reset_skill(
    skill_id: str,
    skill_registry: SkillRegistry = Depends(get_skill_registry),
) -> SkillInfo:
    """Reset a built-in skill to its original file-based content.

    This clears all custom versions from Redis and reverts the skill
    to using the original SKILL.md file content.

    Only built-in skills can be reset. Custom skills should be deleted instead.
    """
    try:
        skill = skill_registry.reset_builtin_skill(skill_id)
        skill_data = skill_registry.get_skill_full(skill_id)
        return _skill_data_to_info(skill_data)
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


# ============================================================================
# Versioning Endpoints
# ============================================================================


@router.get("/{skill_id}/versions", response_model=SkillVersionListResponse)
async def list_skill_versions(
    skill_id: str,
    limit: int = Query(20, ge=1, le=100, description="Maximum versions to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    skill_registry: SkillRegistry = Depends(get_skill_registry),
) -> SkillVersionListResponse:
    """List all versions of a skill with pagination.

    Returns versions newest first. Requires Redis for versioning support.
    """
    versions, total, active_version = skill_registry.list_versions(
        skill_id, limit=limit, offset=offset
    )

    if versions is None:
        raise HTTPException(
            status_code=404,
            detail=f"Skill not found or versioning not available: {skill_id}",
        )

    version_infos = [
        SkillVersionInfo(
            version_number=v.version_number,
            semantic_version=v.semantic_version,
            change_summary=v.change_summary,
            created_at=v.created_at.isoformat(),
            author=v.author,
            is_active=(v.version_number == active_version),
        )
        for v in versions
    ]

    return SkillVersionListResponse(
        skill_id=skill_id,
        versions=version_infos,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{skill_id}/versions/{version_number}", response_model=SkillVersionDetail)
async def get_skill_version(
    skill_id: str,
    version_number: int,
    skill_registry: SkillRegistry = Depends(get_skill_registry),
) -> SkillVersionDetail:
    """Get full content of a specific version.

    Returns the complete version data including core content.
    """
    version, active_version = skill_registry.get_version(skill_id, version_number)

    if version is None:
        raise HTTPException(
            status_code=404,
            detail=f"Version {version_number} not found for skill: {skill_id}",
        )

    return SkillVersionDetail(
        version_number=version.version_number,
        semantic_version=version.semantic_version,
        change_summary=version.change_summary,
        created_at=version.created_at.isoformat(),
        author=version.author,
        is_active=(version.version_number == active_version),
        name=version.name,
        description=version.description,
        category=version.category,
        core_content=version.core_content,
        resources=[
            SkillResource(
                name=r.name,
                description=r.description,
                content=r.content,
            )
            for r in version.resources
        ],
        scripts=[
            SkillScript(
                name=s.name,
                description=s.description,
                language=s.language,
                content=s.content,
            )
            for s in version.scripts
        ],
    )


@router.post("/{skill_id}/versions/{version_number}/activate")
async def activate_version(
    skill_id: str,
    version_number: int,
    skill_registry: SkillRegistry = Depends(get_skill_registry),
) -> dict:
    """Set a version as active (rollback to previous version).

    This allows rolling back to a previous version of the skill.
    """
    success = skill_registry.set_active_version(skill_id, version_number)

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Version {version_number} not found for skill: {skill_id}",
        )

    return {
        "skill_id": skill_id,
        "active_version": version_number,
        "message": f"Version {version_number} is now active",
    }


@router.get("/{skill_id}/versions/diff", response_model=SkillDiffResponse)
async def diff_versions(
    skill_id: str,
    from_version: int = Query(..., description="Source version number"),
    to_version: int = Query(..., description="Target version number"),
    skill_registry: SkillRegistry = Depends(get_skill_registry),
) -> SkillDiffResponse:
    """Compare two versions of a skill.

    Returns a list of field-level changes between the versions.
    """
    from_v, _ = skill_registry.get_version(skill_id, from_version)
    to_v, _ = skill_registry.get_version(skill_id, to_version)

    if from_v is None:
        raise HTTPException(
            status_code=404,
            detail=f"Version {from_version} not found for skill: {skill_id}",
        )

    if to_v is None:
        raise HTTPException(
            status_code=404,
            detail=f"Version {to_version} not found for skill: {skill_id}",
        )

    # Calculate differences
    changes = []

    if from_v.name != to_v.name:
        changes.append(SkillDiffField(field="name", from_value=from_v.name, to_value=to_v.name))

    if from_v.description != to_v.description:
        changes.append(SkillDiffField(
            field="description",
            from_value=from_v.description,
            to_value=to_v.description,
        ))

    if from_v.category != to_v.category:
        changes.append(SkillDiffField(
            field="category",
            from_value=from_v.category,
            to_value=to_v.category,
        ))

    if from_v.semantic_version != to_v.semantic_version:
        changes.append(SkillDiffField(
            field="version",
            from_value=from_v.semantic_version,
            to_value=to_v.semantic_version,
        ))

    if from_v.author != to_v.author:
        changes.append(SkillDiffField(
            field="author",
            from_value=from_v.author,
            to_value=to_v.author,
        ))

    if from_v.core_content != to_v.core_content:
        # Truncate long content for the diff view
        from_preview = from_v.core_content[:500] + "..." if len(from_v.core_content) > 500 else from_v.core_content
        to_preview = to_v.core_content[:500] + "..." if len(to_v.core_content) > 500 else to_v.core_content
        changes.append(SkillDiffField(
            field="core_content",
            from_value=from_preview,
            to_value=to_preview,
        ))

    # Check resources
    from_resources = {r.name for r in from_v.resources}
    to_resources = {r.name for r in to_v.resources}

    if from_resources != to_resources:
        changes.append(SkillDiffField(
            field="resources",
            from_value=", ".join(sorted(from_resources)) or "(none)",
            to_value=", ".join(sorted(to_resources)) or "(none)",
        ))

    # Check scripts
    from_scripts = {s.name for s in from_v.scripts}
    to_scripts = {s.name for s in to_v.scripts}

    if from_scripts != to_scripts:
        changes.append(SkillDiffField(
            field="scripts",
            from_value=", ".join(sorted(from_scripts)) or "(none)",
            to_value=", ".join(sorted(to_scripts)) or "(none)",
        ))

    return SkillDiffResponse(
        skill_id=skill_id,
        from_version=from_version,
        to_version=to_version,
        changes=changes,
    )


@router.get("/{skill_id}/metrics", response_model=SkillUsageMetricsResponse)
async def get_skill_metrics(
    skill_id: str,
    skill_registry: SkillRegistry = Depends(get_skill_registry),
) -> SkillUsageMetricsResponse:
    """Get usage metrics for a skill.

    Returns load counts, unique sessions, and per-version statistics.
    Requires Redis for metrics tracking.
    """
    metrics = skill_registry.get_metrics(skill_id)

    if metrics is None:
        # Return empty metrics if Redis is not configured or no data
        return SkillUsageMetricsResponse(
            total_loads=0,
            unique_sessions=0,
            last_loaded_at=None,
            loads_by_version={},
        )

    return SkillUsageMetricsResponse(
        total_loads=metrics.total_loads,
        unique_sessions=metrics.unique_sessions,
        last_loaded_at=metrics.last_loaded_at.isoformat() if metrics.last_loaded_at else None,
        loads_by_version=metrics.loads_by_version,
    )


@router.get("/{skill_id}/versioned", response_model=VersionedSkillInfo)
async def get_versioned_skill(
    skill_id: str,
    skill_registry: SkillRegistry = Depends(get_skill_registry),
) -> VersionedSkillInfo:
    """Get full skill information with version history.

    Returns skill data along with version summary and metrics.
    """
    skill_data = skill_registry.get_skill_full(skill_id)
    if not skill_data:
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")

    # Get version info
    versions, total, active_version = skill_registry.list_versions(
        skill_id, limit=10, offset=0
    )

    version_infos = []
    if versions:
        version_infos = [
            SkillVersionInfo(
                version_number=v.version_number,
                semantic_version=v.semantic_version,
                change_summary=v.change_summary,
                created_at=v.created_at.isoformat(),
                author=v.author,
                is_active=(v.version_number == active_version),
            )
            for v in versions
        ]

    # Get metrics
    metrics = skill_registry.get_metrics(skill_id)
    metrics_response = None
    if metrics:
        metrics_response = SkillUsageMetricsResponse(
            total_loads=metrics.total_loads,
            unique_sessions=metrics.unique_sessions,
            last_loaded_at=metrics.last_loaded_at.isoformat() if metrics.last_loaded_at else None,
            loads_by_version=metrics.loads_by_version,
        )

    return VersionedSkillInfo(
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
        active_version=active_version or 1,
        version_count=total or 1,
        versions=version_infos,
        metrics=metrics_response,
    )
