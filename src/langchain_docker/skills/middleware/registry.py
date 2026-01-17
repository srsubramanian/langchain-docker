"""Skill registry for middleware-based skills.

This module provides a central registry for skill definitions that can be
used by SkillMiddleware to inject skill descriptions and manage skill loading.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class SkillDefinition:
    """Definition of a skill that can be loaded by an agent.

    A skill represents a specialized capability that provides context,
    guidelines, and potentially tools to the agent.

    Attributes:
        id: Unique identifier for the skill (e.g., "write_sql", "jira")
        name: Human-readable name (e.g., "SQL Query Expert")
        description: Brief description shown in skill list (Level 1)
        category: Category for grouping (e.g., "database", "project_management")
        core_content: Main skill content loaded on-demand (Level 2).
            This can be a string or a callable that returns content dynamically.
        detail_resources: Additional resources loaded on request (Level 3).
            Maps resource names to content or callables.
        required_by_tools: List of tool names that require this skill to be loaded.
            Used for automatic tool gating.
        version: Skill version for tracking updates

    Example:
        sql_skill = SkillDefinition(
            id="write_sql",
            name="SQL Query Expert",
            description="Write SQL queries against databases",
            category="database",
            core_content=lambda: f"Schema: {get_db_schema()}",
            detail_resources={
                "samples": lambda: get_sample_rows(),
                "patterns": "Common SQL patterns...",
            },
            required_by_tools=["sql_query", "sql_list_tables"],
        )
    """

    id: str
    name: str
    description: str
    category: str
    core_content: str | Callable[[], str]
    detail_resources: dict[str, str | Callable[[], str]] = field(default_factory=dict)
    required_by_tools: list[str] = field(default_factory=list)
    version: str = "1.0.0"

    def get_core_content(self) -> str:
        """Get the core content, calling if it's a callable.

        Returns:
            The core skill content (Level 2)
        """
        if callable(self.core_content):
            return self.core_content()
        return self.core_content

    def get_detail(self, resource: str) -> str:
        """Get a detail resource, calling if it's a callable.

        Args:
            resource: The resource name to retrieve

        Returns:
            The resource content (Level 3) or error message if not found
        """
        if resource not in self.detail_resources:
            available = ", ".join(self.detail_resources.keys())
            return f"Unknown resource: {resource}. Available: {available}"

        content = self.detail_resources[resource]
        if callable(content):
            return content()
        return content


class SkillRegistry:
    """Central registry for skill definitions.

    The SkillRegistry provides:
    1. A single source of truth for all available skills
    2. Methods to get skill descriptions for system prompt injection
    3. Skill lookup by ID for loading
    4. Tool-to-skill mapping for automatic gating

    The registry supports loading skills from:
    - Direct registration via register()
    - SKILL.md files via load_from_directory()
    - The existing skill_registry.py skills via load_from_legacy()

    Example:
        registry = SkillRegistry()

        # Register skills
        registry.register(sql_skill_definition)
        registry.register(jira_skill_definition)

        # Get descriptions for system prompt
        descriptions = registry.get_descriptions()
        # Returns: "- write_sql: SQL Query Expert - Write SQL queries..."

        # Check which skill a tool requires
        required_skill = registry.get_required_skill("sql_query")
        # Returns: "write_sql"
    """

    def __init__(self):
        """Initialize an empty registry."""
        self._skills: dict[str, SkillDefinition] = {}
        self._tool_to_skill: dict[str, str] = {}

    def register(self, skill: SkillDefinition) -> None:
        """Register a skill definition.

        Args:
            skill: The skill definition to register

        Raises:
            ValueError: If a skill with the same ID is already registered
        """
        if skill.id in self._skills:
            logger.warning(f"Overwriting existing skill: {skill.id}")

        self._skills[skill.id] = skill

        # Build tool-to-skill mapping
        for tool_name in skill.required_by_tools:
            self._tool_to_skill[tool_name] = skill.id

        logger.info(f"Registered skill: {skill.id} ({skill.name})")

    def unregister(self, skill_id: str) -> bool:
        """Unregister a skill.

        Args:
            skill_id: The skill ID to unregister

        Returns:
            True if the skill was removed, False if not found
        """
        if skill_id not in self._skills:
            return False

        skill = self._skills.pop(skill_id)

        # Remove tool mappings
        for tool_name in skill.required_by_tools:
            self._tool_to_skill.pop(tool_name, None)

        logger.info(f"Unregistered skill: {skill_id}")
        return True

    def get(self, skill_id: str) -> Optional[SkillDefinition]:
        """Get a skill by ID.

        Args:
            skill_id: The skill ID to retrieve

        Returns:
            The skill definition or None if not found
        """
        return self._skills.get(skill_id)

    def list_skills(self) -> list[SkillDefinition]:
        """Get all registered skills.

        Returns:
            List of all skill definitions
        """
        return list(self._skills.values())

    def get_descriptions(self, format: str = "list") -> str:
        """Get formatted descriptions of all skills for system prompt injection.

        Args:
            format: Output format - "list" for bullet points, "table" for markdown table

        Returns:
            Formatted string of skill descriptions
        """
        if not self._skills:
            return "No skills available."

        if format == "table":
            lines = ["| Skill | Description |", "|-------|-------------|"]
            for skill in self._skills.values():
                lines.append(f"| {skill.id} | {skill.description} |")
            return "\n".join(lines)

        # Default: list format
        lines = []
        for skill in self._skills.values():
            lines.append(f"- {skill.id}: {skill.name} - {skill.description}")
        return "\n".join(lines)

    def get_required_skill(self, tool_name: str) -> Optional[str]:
        """Get the skill required by a tool.

        Args:
            tool_name: The tool name to check

        Returns:
            The skill ID required by the tool, or None if no requirement
        """
        return self._tool_to_skill.get(tool_name)

    def get_tools_requiring_skill(self, skill_id: str) -> list[str]:
        """Get all tools that require a specific skill.

        Args:
            skill_id: The skill ID to check

        Returns:
            List of tool names that require this skill
        """
        skill = self._skills.get(skill_id)
        if skill:
            return skill.required_by_tools.copy()
        return []

    def load_from_directory(self, directory: Path) -> int:
        """Load skills from SKILL.md files in a directory.

        Expected structure:
            directory/
            ├── skill_name/
            │   ├── SKILL.md      # Contains frontmatter + core content
            │   ├── examples.md   # Detail resource
            │   └── patterns.md   # Detail resource

        Args:
            directory: Path to the skills directory

        Returns:
            Number of skills loaded
        """
        if not directory.exists():
            logger.warning(f"Skills directory does not exist: {directory}")
            return 0

        count = 0
        for skill_dir in directory.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            try:
                skill = self._parse_skill_md(skill_md, skill_dir)
                self.register(skill)
                count += 1
            except Exception as e:
                logger.error(f"Failed to load skill from {skill_md}: {e}")

        return count

    def _parse_skill_md(self, skill_md: Path, skill_dir: Path) -> SkillDefinition:
        """Parse a SKILL.md file into a SkillDefinition.

        Args:
            skill_md: Path to the SKILL.md file
            skill_dir: Path to the skill directory

        Returns:
            Parsed SkillDefinition
        """
        content = skill_md.read_text(encoding="utf-8")

        # Parse YAML frontmatter
        metadata = {}
        core_content = content

        if content.startswith("---"):
            lines = content.split("\n")
            end_idx = None
            for i, line in enumerate(lines[1:], 1):
                if line.strip() == "---":
                    end_idx = i
                    break

            if end_idx:
                import yaml
                frontmatter = "\n".join(lines[1:end_idx])
                metadata = yaml.safe_load(frontmatter) or {}
                core_content = "\n".join(lines[end_idx + 1:]).strip()

        # Load detail resources from other .md files
        detail_resources = {}
        for md_file in skill_dir.glob("*.md"):
            if md_file.name == "SKILL.md":
                continue
            resource_name = md_file.stem
            # Use lazy loading
            detail_resources[resource_name] = lambda f=md_file: f.read_text(encoding="utf-8")

        return SkillDefinition(
            id=metadata.get("id", skill_dir.name),
            name=metadata.get("name", skill_dir.name.replace("_", " ").title()),
            description=metadata.get("description", ""),
            category=metadata.get("category", "general"),
            core_content=core_content,
            detail_resources=detail_resources,
            required_by_tools=metadata.get("required_by_tools", []),
            version=metadata.get("version", "1.0.0"),
        )

    def load_from_legacy(self, legacy_registry) -> int:
        """Load skills from the existing SkillRegistry.

        This method bridges the gap between the old skill_registry.py
        implementation and the new middleware-based approach.

        Args:
            legacy_registry: Instance of the legacy SkillRegistry

        Returns:
            Number of skills loaded
        """
        # Mapping of skill IDs to their required tools and detail resources
        SKILL_METADATA: dict[str, dict] = {
            "write_sql": {
                "required_by_tools": ["sql_query", "sql_list_tables", "sql_get_samples"],
                "detail_resources": ["samples"],
            },
            "jira": {
                "required_by_tools": [
                    "jira_search", "jira_get_issue", "jira_list_projects",
                    "jira_get_sprints", "jira_get_changelog"
                ],
                "detail_resources": ["jql_reference"],
            },
            "xlsx": {
                "required_by_tools": [],
                "detail_resources": ["examples", "formatting"],
            },
        }

        count = 0
        for skill in legacy_registry.list_skills():
            # Get metadata for this skill, or use defaults
            metadata = SKILL_METADATA.get(skill.id, {})
            required_tools = metadata.get("required_by_tools", [])
            resource_names = metadata.get("detail_resources", [])

            # Build detail_resources dict with lazy loading lambdas
            detail_resources = {}
            for resource_name in resource_names:
                # Capture skill and resource_name in closure
                detail_resources[resource_name] = (
                    lambda s=skill, r=resource_name: s.load_details(r)
                )

            definition = SkillDefinition(
                id=skill.id,
                name=skill.name,
                description=skill.description,
                category=skill.category,
                core_content=skill.load_core,  # Pass the method as callable
                detail_resources=detail_resources,
                required_by_tools=required_tools,
                version=getattr(skill, "version", "1.0.0"),
            )
            self.register(definition)
            count += 1

        return count
