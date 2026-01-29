"""
Test suite for Skills system.

Tests the SkillManager, SkillParser, and skill application functionality.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from agent_os.skills import SkillManager, SkillParser
from agent_os.skills.models import Skill, SkillCategory


class TestSkillParser:
    """Test suite for SkillParser."""

    @pytest.fixture
    def parser(self) -> SkillParser:
        """Create a parser instance."""
        return SkillParser()

    @pytest.fixture
    def sample_skill_content(self) -> str:
        """Sample skill content for testing."""
        return """---
name: "test_skill"
description: "A test skill"
category: "coding"
version: "1.0.0"
author: "Test Author"
tags:
  - test
  - example
tools:
  - read_file
  - write_file
temperature: 0.5
max_tokens: 2000
---
# Role
You are a test assistant.

# Constraints
- Always be helpful
- Follow best practices
"""

    @pytest.fixture
    def sample_skill_file(
        self, tmp_path: Path, sample_skill_content: str
    ) -> Path:
        """Create a temporary skill file."""
        skill_file = tmp_path / "test_skill.md"
        skill_file.write_text(sample_skill_content, encoding="utf-8")
        return skill_file

    def test_parse_valid_skill(
        self, parser: SkillParser, sample_skill_content: str
    ) -> None:
        """Test parsing a valid skill from content string."""
        skill = parser.parse_content(sample_skill_content)

        assert skill.name == "test_skill"
        assert skill.description == "A test skill"
        assert skill.category == SkillCategory.CODING
        assert skill.version == "1.0.0"
        assert skill.author == "Test Author"
        assert "test" in skill.tags
        assert "example" in skill.tags
        assert "read_file" in skill.tools
        assert "write_file" in skill.tools
        assert skill.temperature == 0.5
        assert skill.max_tokens == 2000

    def test_parse_from_file(
        self, parser: SkillParser, sample_skill_file: Path
    ) -> None:
        """Test parsing a skill from a file."""
        skill = parser.parse_file(sample_skill_file)

        assert skill.name == "test_skill"
        assert skill.source_file == str(sample_skill_file)

    def test_parse_extract_constraints(
        self, parser: SkillParser, sample_skill_content: str
    ) -> None:
        """Test that constraints are extracted correctly."""
        skill = parser.parse_content(sample_skill_content)

        assert len(skill.constraints) == 2
        assert "Always be helpful" in skill.constraints
        assert "Follow best practices" in skill.constraints

    def test_parse_missing_frontmatter(self, parser: SkillParser) -> None:
        """Test error when frontmatter is missing."""
        content = "# Role\nNo frontmatter here"

        with pytest.raises(Exception) as exc_info:
            parser.parse_content(content)

        assert "Missing YAML frontmatter" in str(exc_info.value)

    def test_parse_missing_name(self, parser: SkillParser) -> None:
        """Test error when required 'name' field is missing."""
        content = """---
description: "No name"
---
# Role
Test
"""

        with pytest.raises(Exception) as exc_info:
            parser.parse_content(content)

        assert "name is required" in str(exc_info.value)

    def test_parse_nonexistent_file(self, parser: SkillParser, tmp_path: Path) -> None:
        """Test error when file doesn't exist."""
        nonexistent = tmp_path / "nonexistent.md"

        with pytest.raises(Exception) as exc_info:
            parser.parse_file(nonexistent)

        assert "File not found" in str(exc_info.value)

    def test_parse_with_chinese_frontmatter(self, parser: SkillParser) -> None:
        """Test parsing skill with Chinese frontmatter."""
        content = """---
name: "数据分析专家"
description: "专业的数据分析技能"
category: "data_analysis"
---
# 角色
你是一名数据分析专家

# 约束
- 仔细检查数据
- 验证结果
"""
        skill = parser.parse_content(content)

        assert skill.name == "数据分析专家"
        assert skill.category == SkillCategory.DATA_ANALYSIS
        assert len(skill.constraints) == 2


class TestSkillManager:
    """Test suite for SkillManager."""

    @pytest.fixture
    def temp_skills_dir(self) -> tempfile.TemporaryDirectory:
        """Create a temporary directory for skills."""
        return tempfile.TemporaryDirectory()

    @pytest.fixture
    def sample_skills(self, temp_skills_dir: tempfile.TemporaryDirectory) -> list[str]:
        """Create sample skill files."""
        dir_path = Path(temp_skills_dir.name)

        # Skill 1: Python Expert
        skill1 = dir_path / "python_expert.md"
        skill1.write_text(
            """---
name: "python_expert"
description: "Python programming expert"
category: "coding"
tags: ["python", "development"]
tools: ["read_file", "write_file", "run_python"]
---
# Role
You are a Python expert.

# Constraints
- Follow PEP 8
- Write docstrings
""",
            encoding="utf-8",
        )

        # Skill 2: Data Analyst
        skill2 = dir_path / "data_analyst.md"
        skill2.write_text(
            """---
name: "data_analyst"
description: "Data analysis specialist"
category: "data_analysis"
tags: ["data", "analysis"]
tools: ["read_file", "analyze_data"]
---
# Role
You are a data analyst.

# Constraints
- Always inspect data first
- Visualize results
""",
            encoding="utf-8",
        )

        # Skill 3: Invalid file (should be skipped)
        invalid = dir_path / "invalid.txt"
        invalid.write_text("Not a markdown file", encoding="utf-8")

        return [str(skill1), str(skill2)]

    def test_load_skills_from_directory(
        self, temp_skills_dir: tempfile.TemporaryDirectory, sample_skills: list[str]
    ) -> None:
        """Test loading skills from a directory."""
        manager = SkillManager()
        loaded = manager.load_skills_from_directory(temp_skills_dir.name)

        # Should load 2 valid skills (skip .txt file)
        assert len(loaded) == 2
        assert "python_expert" in loaded
        assert "data_analyst" in loaded

    def test_skill_count(self, temp_skills_dir: tempfile.TemporaryDirectory) -> None:
        """Test skill_count property."""
        manager = SkillManager()  # Don't pass directory to avoid auto-loading
        assert manager.skill_count == 0  # Will load when accessed

    def test_get_skill(
        self, temp_skills_dir: tempfile.TemporaryDirectory, sample_skills: list[str]
    ) -> None:
        """Test retrieving a skill by name."""
        manager = SkillManager()  # Don't pass directory to avoid auto-loading
        manager.load_skills_from_directory(temp_skills_dir.name)

        skill = manager.get_skill("python_expert")
        assert skill is not None
        assert skill.name == "python_expert"
        assert skill.category == SkillCategory.CODING

    def test_get_nonexistent_skill(
        self, temp_skills_dir: tempfile.TemporaryDirectory, sample_skills: list[str]
    ) -> None:
        """Test retrieving a non-existent skill."""
        manager = SkillManager()  # Don't pass directory to avoid auto-loading
        manager.load_skills_from_directory(temp_skills_dir.name)

        skill = manager.get_skill("nonexistent")
        assert skill is None

    def test_list_skills_no_filter(
        self, temp_skills_dir: tempfile.TemporaryDirectory, sample_skills: list[str]
    ) -> None:
        """Test listing all skills without filters."""
        manager = SkillManager()  # Don't pass directory to avoid auto-loading
        manager.load_skills_from_directory(temp_skills_dir.name)

        skills = manager.list_skills()
        assert len(skills) == 2

    def test_list_skills_by_category(
        self, temp_skills_dir: tempfile.TemporaryDirectory, sample_skills: list[str]
    ) -> None:
        """Test filtering skills by category."""
        manager = SkillManager()  # Don't pass directory to avoid auto-loading
        manager.load_skills_from_directory(temp_skills_dir.name)

        coding_skills = manager.list_skills(category=SkillCategory.CODING)
        assert len(coding_skills) == 1
        assert coding_skills[0].name == "python_expert"

        data_skills = manager.list_skills(category=SkillCategory.DATA_ANALYSIS)
        assert len(data_skills) == 1
        assert data_skills[0].name == "data_analyst"

    def test_list_skills_by_tag(
        self, temp_skills_dir: tempfile.TemporaryDirectory, sample_skills: list[str]
    ) -> None:
        """Test filtering skills by tag."""
        manager = SkillManager()  # Don't pass directory to avoid auto-loading
        manager.load_skills_from_directory(temp_skills_dir.name)

        python_skills = manager.list_skills(tag="python")
        assert len(python_skills) == 1
        assert python_skills[0].name == "python_expert"

    def test_apply_skill_success(
        self, temp_skills_dir: tempfile.TemporaryDirectory, sample_skills: list[str]
    ) -> None:
        """Test successfully applying a skill."""
        manager = SkillManager()  # Don't pass directory to avoid auto-loading
        manager.load_skills_from_directory(temp_skills_dir.name)

        agent_state = {}
        available_tools = ["read_file", "write_file", "run_python", "run_command"]

        result = manager.apply_skill(
            agent_state=agent_state,
            skill_name="python_expert",
            available_tools=available_tools,
        )

        assert result.success is True
        assert result.skill_name == "python_expert"
        assert result.modified_prompt is not None
        assert "read_file" in result.filtered_tools
        assert "write_file" in result.filtered_tools
        assert "run_python" in result.filtered_tools

    def test_apply_skill_not_found(
        self, temp_skills_dir: tempfile.TemporaryDirectory, sample_skills: list[str]
    ) -> None:
        """Test applying a non-existent skill."""
        manager = SkillManager()  # Don't pass directory to avoid auto-loading
        manager.load_skills_from_directory(temp_skills_dir.name)

        agent_state = {}
        available_tools = []

        result = manager.apply_skill(
            agent_state=agent_state,
            skill_name="nonexistent",
            available_tools=available_tools,
        )

        assert result.success is False
        assert "not found" in result.error_message.lower()

    def test_apply_skill_updates_agent_state(
        self, temp_skills_dir: tempfile.TemporaryDirectory, sample_skills: list[str]
    ) -> None:
        """Test that applying a skill updates agent state."""
        manager = SkillManager()  # Don't pass directory to avoid auto-loading
        manager.load_skills_from_directory(temp_skills_dir.name)

        agent_state = {}
        available_tools = ["read_file", "write_file"]

        result = manager.apply_skill(
            agent_state=agent_state,
            skill_name="python_expert",
            available_tools=available_tools,
        )

        assert "system_prompt" in agent_state
        assert "active_skill" in agent_state
        assert agent_state["active_skill"] == "python_expert"

    def test_clear_skill(self, temp_skills_dir: tempfile.TemporaryDirectory, sample_skills: list[str]) -> None:
        """Test clearing the active skill."""
        manager = SkillManager()  # Don't pass directory to avoid auto-loading
        manager.load_skills_from_directory(temp_skills_dir.name)

        agent_state = {}
        available_tools = ["read_file", "write_file"]

        # Apply a skill
        manager.apply_skill(
            agent_state=agent_state,
            skill_name="python_expert",
            available_tools=available_tools,
        )

        assert "active_skill" in agent_state

        # Clear the skill
        manager.clear_skill(agent_state)

        assert "active_skill" not in agent_state

    def test_tool_filtering_with_skill_requirements(
        self, temp_skills_dir: tempfile.TemporaryDirectory, sample_skills: list[str]
    ) -> None:
        """Test that tools are filtered based on skill requirements."""
        manager = SkillManager()  # Don't pass directory to avoid auto-loading
        manager.load_skills_from_directory(temp_skills_dir.name)

        agent_state = {}
        # Skill requires read_file, write_file, run_python
        all_tools = ["read_file", "write_file", "run_python", "run_command", "analyze_data"]

        result = manager.apply_skill(
            agent_state=agent_state,
            skill_name="python_expert",
            available_tools=all_tools,
        )

        # Should only include tools required by skill
        assert len(result.filtered_tools) == 3
        assert "run_command" not in result.filtered_tools
        assert "analyze_data" not in result.filtered_tools

    def test_get_context(self, temp_skills_dir: tempfile.TemporaryDirectory, sample_skills: list[str]) -> None:
        """Test getting the skill context."""
        manager = SkillManager()  # Don't pass directory to avoid auto-loading
        manager.load_skills_from_directory(temp_skills_dir.name)

        context = manager.get_context()
        assert context is not None
        assert context.active_skill is None

        # Apply a skill
        agent_state = {}
        manager.apply_skill(
            agent_state=agent_state,
            skill_name="python_expert",
            available_tools=["read_file", "write_file"],
        )

        # Check context is updated
        context = manager.get_context()
        assert context.active_skill is not None
        assert context.active_skill.name == "python_expert"


class TestSkillIntegration:
    """Integration tests for the complete skills system."""

    def test_skill_lifecycle(self) -> None:
        """Test the complete skill lifecycle: load -> apply -> clear."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create a skill file
            skill_file = Path(tmp_dir) / "test_skill.md"
            skill_file.write_text(
                """---
name: "lifecycle_test"
description: "Test skill for lifecycle"
category: "coding"
tools: ["read_file"]
---
# Role
Test role
""",
                encoding="utf-8",
            )

            # Load
            manager = SkillManager()
            manager.load_skills_from_directory(tmp_dir)

            # Verify loaded
            skill = manager.get_skill("lifecycle_test")
            assert skill is not None

            # Apply
            agent_state = {}
            result = manager.apply_skill(
                agent_state=agent_state,
                skill_name="lifecycle_test",
                available_tools=["read_file", "write_file"],
            )
            assert result.success

            # Clear
            manager.clear_skill(agent_state)
            assert "active_skill" not in agent_state

    def test_multiple_skills_same_category(self) -> None:
        """Test loading and managing multiple skills in the same category."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            dir_path = Path(tmp_dir)

            # Create multiple coding skills
            for i in range(3):
                skill_file = dir_path / f"coder_{i}.md"
                skill_file.write_text(
                    f"""---
name: "coder_{i}"
description: "Coder variant {i}"
category: "coding"
---
# Role
Coder {i}
""",
                    encoding="utf-8",
                )

            manager = SkillManager()
            manager.load_skills_from_directory(tmp_dir)

            coding_skills = manager.list_skills(category=SkillCategory.CODING)
            assert len(coding_skills) == 3


class TestSkillModels:
    """Test suite for Skill data models."""

    def test_skill_creation(self) -> None:
        """Test creating a Skill model."""
        skill = Skill(
            name="test",
            description="Test skill",
            system_prompt="You are a test assistant",
            tools=["read_file"],
            constraints=["Be helpful"],
        )

        assert skill.name == "test"
        assert skill.description == "Test skill"
        assert skill.category == SkillCategory.GENERAL  # Default

    def test_skill_with_all_fields(self) -> None:
        """Test creating a skill with all optional fields."""
        skill = Skill(
            name="complete_skill",
            description="A complete skill definition",
            version="2.0.0",
            category=SkillCategory.CODING,
            tags=["test", "complete"],
            system_prompt="Complete prompt",
            tools=["tool1", "tool2"],
            constraints=["constraint1", "constraint2"],
            author="Test Author",
            temperature=0.7,
            max_tokens=3000,
            model="gpt-4",
        )

        assert skill.version == "2.0.0"
        assert skill.temperature == 0.7
        assert skill.max_tokens == 3000
        assert skill.model == "gpt-4"

    def test_skill_category_enum(self) -> None:
        """Test SkillCategory enum values."""
        assert SkillCategory.CODING == "coding"
        assert SkillCategory.DATA_ANALYSIS == "data_analysis"
        assert SkillCategory.WRITING == "writing"
        assert SkillCategory.RESEARCH == "research"
        assert SkillCategory.DESIGN == "design"
        assert SkillCategory.MANAGEMENT == "management"
        assert SkillCategory.GENERAL == "general"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
