"""Manual test for Skills system."""

import tempfile
from pathlib import Path

from agent_os.skills import SkillManager, SkillParser
from agent_os.skills.models import Skill, SkillCategory


def test_parser():
    """Test the skill parser."""
    print("=== Testing SkillParser ===")

    parser = SkillParser()

    # Test 1: Parse from content
    content = """---
name: "test_skill"
description: "A test skill"
category: "coding"
version: "1.0.0"
tags:
  - test
  - example
tools:
  - read_file
  - write_file
temperature: 0.5
---
# Role
You are a test assistant.

# Constraints
- Always be helpful
- Follow best practices
"""

    skill = parser.parse_content(content)
    print(f"[OK] Parsed skill: {skill.name}")
    print(f"  Description: {skill.description}")
    print(f"  Category: {skill.category}")
    print(f"  Tags: {skill.tags}")
    print(f"  Tools: {skill.tools}")
    print(f"  Constraints: {skill.constraints}")
    print()


def test_manager():
    """Test the skill manager."""
    print("=== Testing SkillManager ===")

    # Create temporary directory with skills
    with tempfile.TemporaryDirectory() as tmp_dir:
        dir_path = Path(tmp_dir)

        # Create skill files
        skill1 = dir_path / "coder.md"
        skill1.write_text(
            """---
name: "python_expert"
description: "Python expert"
category: "coding"
tags: ["python"]
tools: ["read_file", "write_file", "run_python"]
---
# Role
You are a Python expert.

# Constraints
- Follow PEP 8
""",
            encoding="utf-8",
        )

        skill2 = dir_path / "analyst.md"
        skill2.write_text(
            """---
name: "data_analyst"
description: "Data analyst"
category: "data_analysis"
tags: ["data"]
tools: ["read_file", "analyze"]
---
# Role
You are a data analyst.
""",
            encoding="utf-8",
        )

        # Load skills
        manager = SkillManager()
        loaded = manager.load_skills_from_directory(tmp_dir)

        print(f"[OK] Loaded {len(loaded)} skills:")
        for name, skill in loaded.items():
            print(f"  - {name}: {skill.description}")

        # Test list skills
        all_skills = manager.list_skills()
        print(f"\n[OK] Listed {len(all_skills)} skills")

        # Test filter by category
        coding_skills = manager.list_skills(category=SkillCategory.CODING)
        print(f"[OK] Found {len(coding_skills)} coding skills")

        # Test apply skill
        agent_state = {}
        available_tools = ["read_file", "write_file", "run_python", "run_command"]
        result = manager.apply_skill(
            agent_state=agent_state,
            skill_name="python_expert",
            available_tools=available_tools,
        )

        print(f"\n[OK] Applied skill:")
        print(f"  Success: {result.success}")
        print(f"  Skill: {result.skill_name}")
        print(f"  Filtered tools: {result.filtered_tools}")
        print(f"  Agent state updated: {'system_prompt' in agent_state}")

        # Test get skill
        skill = manager.get_skill("python_expert")
        print(f"\n[OK] Retrieved skill: {skill.name if skill else 'None'}")

        # Test clear skill
        manager.clear_skill(agent_state)
        print(f"\n[OK] Cleared skill: {'active_skill' not in agent_state}")

    print()


def test_agent_integration():
    """Test Agent with skills."""
    print("=== Testing Agent Integration ===")

    from agent_os.core.config import load_config
    from agent_os.agent import Agent

    # Create agent
    try:
        config = load_config("config.yaml")
        agent = Agent(config)

        # Initialize skills
        agent.initialize_skills()

        # List skills
        skills = agent.list_skills()
        print(f"[OK] Agent has {len(skills)} skills:")
        for skill in skills:
            print(f"  - {skill['name']}: {skill['description']}")

        # Apply a skill
        result = agent.apply_skill("default_coder")
        print(f"\n[OK] Applied skill to agent:")
        print(f"  Success: {result['success']}")
        print(f"  Active skill: {agent.get_active_skill()}")

        # Clear skill
        agent.clear_skill()
        print(f"\n[OK] Cleared skill: {agent.get_active_skill() is None}")

    except Exception as e:
        print(f"[ERROR] Error: {e}")
        import traceback

        traceback.print_exc()

    print()


if __name__ == "__main__":
    test_parser()
    test_manager()
    test_agent_integration()
    print("=== All tests completed ===")
