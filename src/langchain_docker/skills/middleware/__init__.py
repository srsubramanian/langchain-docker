"""Middleware-based skills implementation for LangChain agents.

This module implements the skills architecture using LangChain's AgentMiddleware
pattern, enabling:
- Automatic skill description injection into system prompts
- State tracking for loaded skills
- Tool gating based on skill requirements
- Prevention of duplicate skill loading

Architecture:
    SkillRegistry -> SkillMiddleware -> Agent
         |              |
         v              v
    Skills dict    SkillAwareState
                        |
                        v
                   Tools (with ToolRuntime)

Usage:
    from langchain_docker.skills.middleware import (
        SkillRegistry,
        SkillMiddleware,
        SkillAwareState,
    )

    # Create registry with skills
    registry = SkillRegistry()
    registry.register("write_sql", SQLSkillDefinition(...))

    # Create middleware
    middleware = SkillMiddleware(registry)

    # Create agent with middleware
    agent = create_agent(
        model=model,
        middleware=[middleware],
        tools=[...domain_tools...],
    )
"""

from langchain_docker.skills.middleware.registry import SkillRegistry, SkillDefinition
from langchain_docker.skills.middleware.state import SkillAwareState
from langchain_docker.skills.middleware.middleware import SkillMiddleware
from langchain_docker.skills.middleware.tools import (
    create_load_skill_tool,
    create_list_loaded_skills_tool,
    create_gated_tool,
    create_skill_detail_tool,
    is_skill_loaded,
    skill_not_loaded_error,
)
from langchain_docker.skills.middleware.gated_domain_tools import (
    create_gated_sql_query_tool,
    create_gated_sql_list_tables_tool,
    create_gated_sql_get_samples_tool,
    create_gated_jira_search_tool,
    create_gated_jira_get_issue_tool,
    create_gated_jira_list_projects_tool,
    create_gated_jira_get_sprints_tool,
    create_gated_jira_get_changelog_tool,
    create_gated_jira_jql_reference_tool,
    create_gated_tools_for_skill,
)

__all__ = [
    # Core classes
    "SkillRegistry",
    "SkillDefinition",
    "SkillAwareState",
    "SkillMiddleware",
    # Skill management tools
    "create_load_skill_tool",
    "create_list_loaded_skills_tool",
    "create_gated_tool",
    "create_skill_detail_tool",
    # Helper functions
    "is_skill_loaded",
    "skill_not_loaded_error",
    # Gated SQL tools
    "create_gated_sql_query_tool",
    "create_gated_sql_list_tables_tool",
    "create_gated_sql_get_samples_tool",
    # Gated Jira tools
    "create_gated_jira_search_tool",
    "create_gated_jira_get_issue_tool",
    "create_gated_jira_list_projects_tool",
    "create_gated_jira_get_sprints_tool",
    "create_gated_jira_get_changelog_tool",
    "create_gated_jira_jql_reference_tool",
    # Factory function
    "create_gated_tools_for_skill",
]
