"""
Skill data models for the Skills system.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SkillCategory(str, Enum):
    """Categories of skills."""

    CODING = "coding"
    DATA_ANALYSIS = "data_analysis"
    WRITING = "writing"
    RESEARCH = "research"
    DESIGN = "design"
    MANAGEMENT = "management"
    GENERAL = "general"


class Skill(BaseModel):
    """A skill definition with metadata and configuration.

    Skills are loaded from Markdown files with YAML Frontmatter and
    can be dynamically applied to change agent behavior.
    """

    # Core identification
    name: str = Field(..., description="Unique skill identifier")
    description: str = Field(..., description="Human-readable description")
    version: str = Field(default="1.0.0", description="Skill version")

    # Categorization
    category: SkillCategory = Field(
        default=SkillCategory.GENERAL, description="Skill category"
    )
    tags: list[str] = Field(default_factory=list, description="Skill tags for filtering")

    # Capabilities
    system_prompt: str = Field(..., description="System prompt to use when skill is active")
    tools: list[str] = Field(
        default_factory=list, description="Required tool IDs for this skill"
    )
    constraints: list[str] = Field(
        default_factory=list, description="Constraints or guidelines"
    )

    # Metadata
    author: str | None = Field(default=None, description="Skill author")
    source_file: str | None = Field(default=None, description="Source file path")
    created_at: str | None = Field(default=None, description="Creation timestamp")

    # Advanced settings
    temperature: float | None = Field(
        default=None, description="Custom temperature for this skill"
    )
    max_tokens: int | None = Field(
        default=None, description="Custom max tokens for this skill"
    )
    model: str | None = Field(default=None, description="Custom model for this skill")

    class Config:
        """Pydantic config."""

        use_enum_values = True


class SkillContext(BaseModel):
    """Runtime context for skill execution."""

    active_skill: Skill | None = None
    available_tools: list[str] = Field(default_factory=list)
    conversation_history: list[dict[str, Any]] = Field(default_factory=list)

    # Skill state
    skill_start_time: str | None = None
    messages_with_skill: int = 0


class SkillApplicationResult(BaseModel):
    """Result of applying a skill to an agent."""

    success: bool
    skill_name: str
    modified_prompt: str | None = None
    filtered_tools: list[str] = Field(default_factory=list)
    error_message: str | None = None


__all__ = [
    "Skill",
    "SkillCategory",
    "SkillContext",
    "SkillApplicationResult",
]
