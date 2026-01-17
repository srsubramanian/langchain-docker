"""Tests for the skills middleware module.

This module tests:
- SkillDefinition dataclass
- SkillRegistry for managing skills
- SkillAwareState for tracking loaded skills
- SkillMiddleware for system prompt injection
- load_skill and list_loaded_skills tools
- Gated domain tools
"""

import pytest
from unittest.mock import MagicMock, patch

from langchain_docker.skills.middleware import (
    SkillRegistry,
    SkillDefinition,
    SkillAwareState,
    SkillMiddleware,
    create_load_skill_tool,
    create_list_loaded_skills_tool,
    is_skill_loaded,
    skill_not_loaded_error,
)
from langchain_docker.skills.middleware.state import (
    get_loaded_skills,
    get_skill_load_count,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_skill():
    """Create a sample skill definition for testing."""
    return SkillDefinition(
        id="test_skill",
        name="Test Skill",
        description="A skill for testing purposes",
        category="testing",
        core_content="This is the core content of the test skill.",
        detail_resources={
            "examples": "Example 1\nExample 2",
            "patterns": "Pattern A\nPattern B",
        },
        required_by_tools=["test_tool_1", "test_tool_2"],
    )


@pytest.fixture
def callable_skill():
    """Create a skill with callable content for testing lazy loading."""
    call_count = {"core": 0, "examples": 0}

    def get_core():
        call_count["core"] += 1
        return f"Core content (loaded {call_count['core']} times)"

    def get_examples():
        call_count["examples"] += 1
        return f"Examples (loaded {call_count['examples']} times)"

    skill = SkillDefinition(
        id="callable_skill",
        name="Callable Skill",
        description="A skill with callable content",
        category="testing",
        core_content=get_core,
        detail_resources={"examples": get_examples},
        required_by_tools=["callable_tool"],
    )
    return skill, call_count


@pytest.fixture
def skill_registry(sample_skill):
    """Create a skill registry with a sample skill."""
    registry = SkillRegistry()
    registry.register(sample_skill)
    return registry


@pytest.fixture
def skill_middleware(skill_registry):
    """Create a skill middleware instance."""
    return SkillMiddleware(registry=skill_registry)


# =============================================================================
# SkillDefinition Tests
# =============================================================================

class TestSkillDefinition:
    """Tests for SkillDefinition dataclass."""

    def test_create_with_string_content(self, sample_skill):
        """Test creating a skill with string content."""
        assert sample_skill.id == "test_skill"
        assert sample_skill.name == "Test Skill"
        assert sample_skill.description == "A skill for testing purposes"
        assert sample_skill.category == "testing"
        assert sample_skill.version == "1.0.0"

    def test_get_core_content_string(self, sample_skill):
        """Test getting core content when it's a string."""
        content = sample_skill.get_core_content()
        assert content == "This is the core content of the test skill."

    def test_get_core_content_callable(self, callable_skill):
        """Test getting core content when it's a callable."""
        skill, call_count = callable_skill
        assert call_count["core"] == 0

        content = skill.get_core_content()
        assert "Core content" in content
        assert call_count["core"] == 1

        # Calling again should invoke the callable again
        content2 = skill.get_core_content()
        assert call_count["core"] == 2

    def test_get_detail_existing_resource(self, sample_skill):
        """Test getting an existing detail resource."""
        content = sample_skill.get_detail("examples")
        assert content == "Example 1\nExample 2"

    def test_get_detail_nonexistent_resource(self, sample_skill):
        """Test getting a nonexistent detail resource."""
        content = sample_skill.get_detail("nonexistent")
        assert "Unknown resource" in content
        assert "examples" in content  # Should list available resources

    def test_get_detail_callable_resource(self, callable_skill):
        """Test getting a callable detail resource."""
        skill, call_count = callable_skill
        assert call_count["examples"] == 0

        content = skill.get_detail("examples")
        assert "Examples" in content
        assert call_count["examples"] == 1


# =============================================================================
# SkillRegistry Tests
# =============================================================================

class TestSkillRegistry:
    """Tests for SkillRegistry."""

    def test_register_skill(self, sample_skill):
        """Test registering a skill."""
        registry = SkillRegistry()
        registry.register(sample_skill)

        assert registry.get("test_skill") == sample_skill

    def test_register_duplicate_skill_warning(self, sample_skill, caplog):
        """Test that registering a duplicate skill logs a warning."""
        registry = SkillRegistry()
        registry.register(sample_skill)
        registry.register(sample_skill)

        assert "Overwriting existing skill" in caplog.text

    def test_unregister_skill(self, skill_registry, sample_skill):
        """Test unregistering a skill."""
        result = skill_registry.unregister("test_skill")
        assert result is True
        assert skill_registry.get("test_skill") is None

    def test_unregister_nonexistent_skill(self, skill_registry):
        """Test unregistering a nonexistent skill."""
        result = skill_registry.unregister("nonexistent")
        assert result is False

    def test_list_skills(self, skill_registry, sample_skill):
        """Test listing all skills."""
        skills = skill_registry.list_skills()
        assert len(skills) == 1
        assert skills[0] == sample_skill

    def test_get_descriptions_list_format(self, skill_registry):
        """Test getting skill descriptions in list format."""
        descriptions = skill_registry.get_descriptions(format="list")
        assert "test_skill" in descriptions
        assert "Test Skill" in descriptions
        assert "A skill for testing purposes" in descriptions

    def test_get_descriptions_table_format(self, skill_registry):
        """Test getting skill descriptions in table format."""
        descriptions = skill_registry.get_descriptions(format="table")
        assert "| Skill | Description |" in descriptions
        assert "test_skill" in descriptions

    def test_get_descriptions_empty_registry(self):
        """Test getting descriptions from an empty registry."""
        registry = SkillRegistry()
        descriptions = registry.get_descriptions()
        assert "No skills available" in descriptions

    def test_get_required_skill(self, skill_registry):
        """Test getting the required skill for a tool."""
        skill_id = skill_registry.get_required_skill("test_tool_1")
        assert skill_id == "test_skill"

    def test_get_required_skill_unknown_tool(self, skill_registry):
        """Test getting required skill for an unknown tool."""
        skill_id = skill_registry.get_required_skill("unknown_tool")
        assert skill_id is None

    def test_get_tools_requiring_skill(self, skill_registry):
        """Test getting tools that require a skill."""
        tools = skill_registry.get_tools_requiring_skill("test_skill")
        assert "test_tool_1" in tools
        assert "test_tool_2" in tools

    def test_get_tools_requiring_nonexistent_skill(self, skill_registry):
        """Test getting tools for a nonexistent skill."""
        tools = skill_registry.get_tools_requiring_skill("nonexistent")
        assert tools == []


# =============================================================================
# SkillAwareState Tests
# =============================================================================

class TestSkillAwareState:
    """Tests for SkillAwareState and helper functions."""

    def test_get_loaded_skills_empty(self):
        """Test getting loaded skills from empty state."""
        state: SkillAwareState = {"messages": []}
        skills = get_loaded_skills(state)
        assert skills == []

    def test_get_loaded_skills_with_skills(self):
        """Test getting loaded skills when skills are present."""
        state: SkillAwareState = {
            "messages": [],
            "skills_loaded": ["skill1", "skill2"],
        }
        skills = get_loaded_skills(state)
        assert skills == ["skill1", "skill2"]

    def test_is_skill_loaded_true(self):
        """Test checking if a skill is loaded (true case)."""
        state: SkillAwareState = {
            "messages": [],
            "skills_loaded": ["test_skill"],
        }
        assert is_skill_loaded(state, "test_skill") is True

    def test_is_skill_loaded_false(self):
        """Test checking if a skill is loaded (false case)."""
        state: SkillAwareState = {
            "messages": [],
            "skills_loaded": ["other_skill"],
        }
        assert is_skill_loaded(state, "test_skill") is False

    def test_get_skill_load_count(self):
        """Test getting skill load count."""
        state: SkillAwareState = {
            "messages": [],
            "skill_load_count": {"skill1": 2, "skill2": 1},
        }
        assert get_skill_load_count(state, "skill1") == 2
        assert get_skill_load_count(state, "skill2") == 1
        assert get_skill_load_count(state, "skill3") == 0


# =============================================================================
# SkillMiddleware Tests
# =============================================================================

class TestSkillMiddleware:
    """Tests for SkillMiddleware."""

    def test_middleware_has_state_schema(self, skill_middleware):
        """Test that middleware has the correct state schema."""
        assert skill_middleware.state_schema == SkillAwareState

    def test_middleware_has_tools(self, skill_middleware):
        """Test that middleware provides tools."""
        assert len(skill_middleware.tools) == 2  # load_skill, list_loaded_skills

    def test_build_skill_prompt_section(self, skill_middleware):
        """Test building the skill prompt section."""
        section = skill_middleware._build_skill_prompt_section()
        assert "Available Skills" in section
        assert "test_skill" in section
        assert "load_skill" in section

    def test_get_skill_descriptions_caching(self, skill_middleware):
        """Test that skill descriptions are cached."""
        desc1 = skill_middleware._get_skill_descriptions()
        desc2 = skill_middleware._get_skill_descriptions()
        # Should return same cached value
        assert desc1 == desc2

    def test_refresh_skills(self, skill_middleware):
        """Test refreshing skill descriptions."""
        # Get initial descriptions
        _ = skill_middleware._get_skill_descriptions()
        assert skill_middleware._cached_descriptions is not None

        # Refresh
        skill_middleware.refresh_skills()
        assert skill_middleware._cached_descriptions is None


# =============================================================================
# Helper Function Tests
# =============================================================================

class TestHelperFunctions:
    """Tests for helper functions in the tools module."""

    def test_skill_not_loaded_error(self):
        """Test creating a skill not loaded error Command."""
        from langgraph.types import Command
        from langchain_core.messages import ToolMessage

        error_cmd = skill_not_loaded_error("test_skill", "tool_call_123")

        assert isinstance(error_cmd, Command)
        assert "messages" in error_cmd.update
        messages = error_cmd.update["messages"]
        assert len(messages) == 1
        assert isinstance(messages[0], ToolMessage)
        assert "test_skill" in messages[0].content
        assert "load_skill" in messages[0].content


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for the complete middleware flow."""

    def test_full_skill_registration_and_retrieval(self):
        """Test the full flow of registering and retrieving skills."""
        # Create registry
        registry = SkillRegistry()

        # Create and register multiple skills
        sql_skill = SkillDefinition(
            id="write_sql",
            name="SQL Expert",
            description="Write SQL queries",
            category="database",
            core_content="SQL guidelines here",
            required_by_tools=["sql_query"],
        )

        jira_skill = SkillDefinition(
            id="jira",
            name="Jira Expert",
            description="Manage Jira issues",
            category="project_management",
            core_content="Jira guidelines here",
            required_by_tools=["jira_search"],
        )

        registry.register(sql_skill)
        registry.register(jira_skill)

        # Verify skills are registered
        assert len(registry.list_skills()) == 2
        assert registry.get("write_sql") == sql_skill
        assert registry.get("jira") == jira_skill

        # Verify tool mappings
        assert registry.get_required_skill("sql_query") == "write_sql"
        assert registry.get_required_skill("jira_search") == "jira"

    def test_middleware_with_custom_prompt_template(self, skill_registry):
        """Test middleware with a custom prompt template."""
        custom_template = """
# Skills Available
{skill_descriptions}

Use load_skill() to activate.
"""
        middleware = SkillMiddleware(
            registry=skill_registry,
            prompt_template=custom_template,
        )

        section = middleware._build_skill_prompt_section()
        assert "# Skills Available" in section
        assert "Use load_skill() to activate" in section


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
