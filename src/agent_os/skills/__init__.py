"""
Skills Module - Coze-style Open Skills System

This module implements a flexible skill management system that allows
dynamic role switching and capability extension through Markdown + YAML
Frontmatter skill definitions.
"""

from .manager import SkillManager
from .models import Skill, SkillCategory
from .parser import SkillParser

__all__ = [
    "SkillManager",
    "Skill",
    "SkillCategory",
    "SkillParser",
]
