"""
Skill Manager - Manages loading, caching, and applying skills.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import (
    Skill,
    SkillApplicationResult,
    SkillCategory,
    SkillContext,
)
from .parser import SkillParseError, SkillParser


class SkillManager:
    """Manager for Coze-style skills system.

    The SkillManager handles:
    - Loading skills from Markdown + YAML files
    - Caching parsed skills
    - Applying skills to agent state
    - Filtering tools based on skill requirements
    - Dynamic skill switching during conversation

    Usage:
        ```python
        manager = SkillManager()
        manager.load_skills_from_directory("./skills/library")

        # Apply a skill
        result = manager.apply_skill(
            agent_state=state,
            skill_name="python_expert",
            available_tools=["read_file", "write_file"]
        )
        ```
    """

    def __init__(self, skills_directory: str | Path | None = None) -> None:
        """Initialize the skill manager.

        Args:
            skills_directory: Optional directory to load skills from
        """
        self.parser = SkillParser()
        self._skills: dict[str, Skill] = {}
        self._context = SkillContext()

        if skills_directory:
            self.load_skills_from_directory(skills_directory)

    def load_skills_from_directory(
        self, directory: str | Path, recursive: bool = False
    ) -> dict[str, Skill]:
        """Load all skill files from a directory.

        Args:
            directory: Path to directory containing .md skill files
            recursive: Whether to recursively search subdirectories

        Returns:
            Dictionary of loaded skills {skill_name: Skill}

        Raises:
            ValueError: If directory doesn't exist
        """
        dir_path = Path(directory)

        if not dir_path.exists():
            raise ValueError(f"Skills directory not found: {directory}")

        if not dir_path.is_dir():
            raise ValueError(f"Not a directory: {directory}")

        # Find all .md files
        pattern = "**/*.md" if recursive else "*.md"
        skill_files = list(dir_path.glob(pattern))

        loaded: dict[str, Skill] = {}

        for skill_file in skill_files:
            try:
                skill = self.parser.parse_file(skill_file)
                self.register_skill(skill)
                loaded[skill.name] = skill
            except SkillParseError as e:
                # Log but don't fail on individual parse errors
                print(f"Warning: {e}")

        print(f"Loaded {len(loaded)} skills from {directory}")
        return loaded

    def register_skill(self, skill: Skill) -> None:
        """Register a skill in the manager.

        Args:
            skill: Skill object to register

        Raises:
            ValueError: If a skill with the same name already exists
        """
        if skill.name in self._skills:
            raise ValueError(f"Skill already registered: {skill.name}")

        self._skills[skill.name] = skill

    def get_skill(self, name: str) -> Skill | None:
        """Get a skill by name.

        Args:
            name: Skill name

        Returns:
            Skill object or None if not found
        """
        return self._skills.get(name)

    def list_skills(
        self,
        category: SkillCategory | None = None,
        tag: str | None = None,
    ) -> list[Skill]:
        """List available skills with optional filtering.

        Args:
            category: Optional category filter
            tag: Optional tag filter

        Returns:
            List of matching skills
        """
        skills = list(self._skills.values())

        if category:
            skills = [s for s in skills if s.category == category]

        if tag:
            skills = [s for s in skills if tag in s.tags]

        return skills

    def apply_skill(
        self,
        agent_state: dict[str, Any],
        skill_name: str,
        available_tools: list[str],
    ) -> SkillApplicationResult:
        """Apply a skill to an agent's state.

        This modifies the agent state by:
        1. Updating the system prompt with the skill's prompt
        2. Filtering available tools to only those required by the skill
        3. Setting skill-specific parameters (temperature, max_tokens, etc.)

        Args:
            agent_state: Current agent state dict
            skill_name: Name of skill to apply
            available_tools: List of currently available tool names

        Returns:
            SkillApplicationResult with success status and modifications
        """
        skill = self.get_skill(skill_name)

        if not skill:
            return SkillApplicationResult(
                success=False,
                skill_name=skill_name,
                error_message=f"Skill not found: {skill_name}",
            )

        try:
            # Modify system prompt
            modified_prompt = self._build_skill_prompt(skill)

            # Filter tools
            filtered_tools = self._filter_tools(skill, available_tools)

            # Update agent state
            agent_state["system_prompt"] = modified_prompt
            agent_state["active_skill"] = skill.name

            # Apply skill-specific parameters
            if skill.temperature is not None:
                agent_state["temperature"] = skill.temperature

            if skill.max_tokens is not None:
                agent_state["max_tokens"] = skill.max_tokens

            if skill.model is not None:
                agent_state["model"] = skill.model

            # Update context
            self._context.active_skill = skill
            self._context.available_tools = filtered_tools

            return SkillApplicationResult(
                success=True,
                skill_name=skill_name,
                modified_prompt=modified_prompt,
                filtered_tools=filtered_tools,
            )

        except Exception as e:
            return SkillApplicationResult(
                success=False,
                skill_name=skill_name,
                error_message=f"Failed to apply skill: {e}",
            )

    def clear_skill(self, agent_state: dict[str, Any]) -> None:
        """Clear the active skill from agent state.

        Args:
            agent_state: Agent state dict to modify
        """
        agent_state.pop("active_skill", None)
        agent_state.pop("system_prompt", None)

        # Restore defaults
        agent_state.pop("temperature", None)
        agent_state.pop("max_tokens", None)
        agent_state.pop("model", None)

        self._context.active_skill = None

    def _build_skill_prompt(self, skill: Skill) -> str:
        """Build the complete system prompt for a skill.

        Args:
            skill: Skill to build prompt for

        Returns:
            Complete system prompt string
        """
        prompt_parts = [
            f"# Role\n{skill.name}",
            f"\n{skill.system_prompt}",
        ]

        # Add constraints if present
        if skill.constraints:
            prompt_parts.append("\n# Constraints")
            for constraint in skill.constraints:
                prompt_parts.append(f"- {constraint}")

        # Add tool usage guidance
        if skill.tools:
            tools_str = ", ".join(skill.tools)
            prompt_parts.append(f"\n# Available Tools\nYou have access to: {tools_str}")

        return "\n".join(prompt_parts)

    def _filter_tools(
        self, skill: Skill, available_tools: list[str]
    ) -> list[str]:
        """Filter available tools based on skill requirements.

        If the skill specifies required tools, only those tools are returned.
        Otherwise, all available tools are returned.

        Args:
            skill: Skill with tool requirements
            available_tools: List of available tool names

        Returns:
            Filtered list of tool names
        """
        if not skill.tools:
            # No specific tool requirements, return all
            return available_tools

        # Filter to only tools that are both required and available
        filtered = [t for t in skill.tools if t in available_tools]

        # Warn if required tools are missing
        missing = set(skill.tools) - set(available_tools)
        if missing:
            print(
                f"Warning: Skill '{skill.name}' requires tools not available: {missing}"
            )

        return filtered

    def get_context(self) -> SkillContext:
        """Get the current skill context.

        Returns:
            Current SkillContext
        """
        return self._context

    @property
    def skill_count(self) -> int:
        """Get the number of registered skills."""
        return len(self._skills)


__all__ = ["SkillManager"]
