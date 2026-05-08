"""
Skill parser for loading skills from Markdown + YAML Frontmatter files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .models import Skill, SkillCategory


class SkillParseError(Exception):
    """Raised when skill parsing fails."""

    def __init__(self, file_path: str, message: str) -> None:
        """Initialize error with file context."""
        self.file_path = file_path
        self.message = message
        super().__init__(f"Error parsing {file_path}: {message}")


class SkillParser:
    """Parser for Coze-style Markdown + YAML Frontmatter skill definitions.

    Skills are defined as Markdown files with YAML Frontmatter:

    ```markdown
    ---
    name: "python_expert"
    description: "Expert Python developer"
    category: "coding"
    tools: ["read_file", "write_file", "run_python"]
    tags: ["python", "development"]
    ---
    # Role
    You are an expert Python developer...

    # Constraints
    - Always follow PEP 8
    - Write docstrings for all functions
    ```

    The YAML frontmatter contains metadata, while the Markdown body
    contains the system prompt and constraints.
    """

    def parse_file(self, file_path: str | Path) -> Skill:
        """Parse a skill from a Markdown file.

        Args:
            file_path: Path to the Markdown skill file

        Returns:
            Parsed Skill object

        Raises:
            SkillParseError: If parsing fails
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise SkillParseError(str(file_path), "File not found")

        if not file_path.suffix in [".md", ".markdown"]:
            raise SkillParseError(
                str(file_path), f"Unsupported file type: {file_path.suffix}"
            )

        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            raise SkillParseError(str(file_path), f"Failed to read file: {e}")

        return self.parse_content(content, source_file=str(file_path))

    def parse_content(self, content: str, source_file: str | None = None) -> Skill:
        """Parse a skill from Markdown content string.

        Args:
            content: Markdown content with YAML frontmatter
            source_file: Optional source file path for metadata

        Returns:
            Parsed Skill object

        Raises:
            SkillParseError: If parsing fails
        """
        # Split frontmatter and content
        if not content.startswith("---"):
            raise SkillParseError(
                source_file or "<string>", "Missing YAML frontmatter (must start with '---')"
            )

        # Find end of frontmatter
        try:
            end_marker = content.index("\n---", 4)
        except ValueError:
            raise SkillParseError(
                source_file or "<string>", "Missing end marker for YAML frontmatter"
            )

        frontmatter_text = content[4:end_marker]
        markdown_body = content[end_marker + 5 :].strip()

        # Parse YAML frontmatter
        try:
            frontmatter_data = yaml.safe_load(frontmatter_text)
            if frontmatter_data is None:
                frontmatter_data = {}
        except yaml.YAMLError as e:
            raise SkillParseError(
                source_file or "<string>", f"Invalid YAML frontmatter: {e}"
            )

        # Extract fields from frontmatter
        try:
            metadata = self._extract_metadata(frontmatter_data)
        except (KeyError, TypeError) as e:
            raise SkillParseError(source_file or "<string>", f"Missing required field: {e}")

        # Parse markdown body for prompt and constraints
        prompt, constraints = self._parse_markdown_body(markdown_body)

        # Build skill data
        skill_data: dict[str, Any] = {
            "name": metadata["name"],
            "description": metadata.get("description", ""),
            "system_prompt": prompt,
            "tools": metadata.get("tools", []),
            "tags": metadata.get("tags", []),
            "constraints": constraints,
            "source_file": source_file,
        }

        # Optional fields
        if "version" in metadata:
            skill_data["version"] = metadata["version"]

        if "category" in metadata:
            try:
                skill_data["category"] = SkillCategory(metadata["category"])
            except ValueError:
                # Invalid category, use default
                pass

        if "author" in metadata:
            skill_data["author"] = metadata["author"]

        if "temperature" in metadata:
            skill_data["temperature"] = metadata["temperature"]

        if "max_tokens" in metadata:
            skill_data["max_tokens"] = metadata["max_tokens"]

        if "model" in metadata:
            skill_data["model"] = metadata["model"]

        # Validate and create skill
        try:
            skill = Skill(**skill_data)
        except ValidationError as e:
            raise SkillParseError(source_file or "<string>", f"Validation error: {e}")

        return skill

    def _extract_metadata(self, frontmatter: dict[str, Any]) -> dict[str, Any]:
        """Extract required metadata from frontmatter.

        Args:
            frontmatter: Parsed YAML frontmatter dict

        Returns:
            Extracted metadata dict

        Raises:
            KeyError: If required fields are missing
        """
        if "name" not in frontmatter:
            raise KeyError("name is required in frontmatter")

        return frontmatter

    def _parse_markdown_body(
        self, body: str
    ) -> tuple[str, list[str]]:
        """Parse the markdown body to extract prompt and constraints.

        This method looks for specific sections:
        - "Constraints" or "约束" section for constraints list
        - Everything else becomes the system prompt

        Args:
            body: Markdown body content (without frontmatter)

        Returns:
            Tuple of (system_prompt, constraints_list)
        """
        constraints: list[str] = []

        # Look for constraints section
        lines = body.split("\n")
        in_constraints_section = False
        prompt_lines: list[str] = []

        for line in lines:
            # Check if we're entering a constraints section
            if line.strip().lower() in [
                "# constraints",
                "## constraints",
                "### constraints",
                "# 约束",
                "## 约束",
                "### 约束",
            ]:
                in_constraints_section = True
                continue

            # Check if we're leaving the constraints section
            if in_constraints_section and line.strip().startswith("#"):
                in_constraints_section = False

            # Process line based on section
            if in_constraints_section:
                # Extract constraint from list item
                line_stripped = line.strip()
                if line_stripped.startswith("- ") or line_stripped.startswith("* "):
                    constraint = line_stripped[2:].strip()
                    if constraint:
                        constraints.append(constraint)
                elif line_stripped:
                    # Non-list line in constraints section
                    constraints.append(line_stripped)
            else:
                prompt_lines.append(line)

        # Build prompt
        prompt = "\n".join(prompt_lines).strip()

        return prompt, constraints


__all__ = ["SkillParser", "SkillParseError"]
