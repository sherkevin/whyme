"""Skill Service - Manages Skill CRUD operations and recommendations.

This module provides functionality for:
- Creating, reading, updating, and deleting Skills
- Recommending Skills based on Task characteristics
- Skill versioning and matching
"""

import uuid
import logging
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime

from agent_os.stage3.models import Skill

logger = logging.getLogger(__name__)


class SkillService:
    """Service for managing Skills."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    async def create_skill(
        self,
        name: str,
        description: str,
        category: str,
        steps: List[Dict[str, Any]],
        created_by: str,
        applicable_item_types: Optional[List[str]] = None,
        required_tags: Optional[List[str]] = None,
        version: str = "1.0",
        parent_skill_id: Optional[str] = None
    ) -> Skill:
        """Create a new Skill.

        Args:
            name: Skill name
            description: Skill description
            category: Skill category (e.g., 'decision', 'analysis', 'automation')
            steps: List of step definitions
            created_by: User ID who created this skill
            applicable_item_types: Item types this skill applies to
            required_tags: Tags required for this skill to apply
            version: Skill version
            parent_skill_id: Parent skill ID if this is a version

        Returns:
            Created Skill object
        """
        skill = Skill(
            name=name,
            description=description,
            category=category,
            steps=steps,
            created_by=created_by,
            applicable_item_types=applicable_item_types or [],
            required_tags=required_tags or [],
            version=version,
            parent_skill_id=uuid.UUID(parent_skill_id) if parent_skill_id else None
        )

        self.db.add(skill)
        await self.db.commit()
        await self.db.refresh(skill)

        logger.info(f"Created Skill: {skill.name} (v{skill.version})")
        return skill

    async def get_skill(self, skill_id: str) -> Optional[Skill]:
        """Get a Skill by ID.

        Args:
            skill_id: Skill UUID

        Returns:
            Skill object or None
        """
        stmt = select(Skill).where(
            and_(
                Skill.id == uuid.UUID(skill_id),
                Skill.is_active == True
            )
        )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_skills(
        self,
        category: Optional[str] = None,
        created_by: Optional[str] = None,
        is_active: bool = True,
        limit: int = 100,
        offset: int = 0
    ) -> List[Skill]:
        """List Skills with optional filters.

        Args:
            category: Filter by category
            created_by: Filter by creator
            is_active: Only active skills
            limit: Max results
            offset: Pagination offset

        Returns:
            List of Skill objects
        """
        conditions = [Skill.is_active == is_active]

        if category:
            conditions.append(Skill.category == category)
        if created_by:
            conditions.append(Skill.created_by == created_by)

        stmt = select(Skill).where(
            and_(*conditions)
        ).order_by(
            Skill.created_at.desc()
        ).limit(limit).offset(offset)

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def update_skill(
        self,
        skill_id: str,
        **updates
    ) -> Optional[Skill]:
        """Update a Skill.

        Args:
            skill_id: Skill UUID
            **updates: Fields to update

        Returns:
            Updated Skill or None
        """
        skill = await self.get_skill(skill_id)
        if not skill:
            return None

        # Update allowed fields
        allowed_fields = {
            'name', 'description', 'category', 'steps',
            'applicable_item_types', 'required_tags', 'is_active'
        }

        for field, value in updates.items():
            if field in allowed_fields and hasattr(skill, field):
                setattr(skill, field, value)

        skill.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(skill)

        logger.info(f"Updated Skill: {skill.name}")
        return skill

    async def delete_skill(self, skill_id: str) -> bool:
        """Soft delete a Skill.

        Args:
            skill_id: Skill UUID

        Returns:
            True if deleted
        """
        skill = await self.get_skill(skill_id)
        if not skill:
            return False

        skill.is_active = False
        skill.updated_at = datetime.utcnow()
        await self.db.commit()

        logger.info(f"Deleted Skill: {skill.name}")
        return True

    async def create_skill_version(
        self,
        parent_skill_id: str,
        changes: Dict[str, Any],
        created_by: str
    ) -> Optional[Skill]:
        """Create a new version of an existing Skill.

        Args:
            parent_skill_id: Parent Skill UUID
            changes: Changes to apply (steps, description, etc.)
            created_by: User ID creating new version

        Returns:
            New Skill version or None
        """
        parent = await self.get_skill(parent_skill_id)
        if not parent:
            return None

        # Increment version
        version_parts = parent.version.split('.')
        if len(version_parts) == 2:
            major, minor = version_parts
            new_version = f"{major}.{int(minor) + 1}"
        else:
            new_version = "2.0"

        # Create new version
        new_skill = Skill(
            name=parent.name,
            description=changes.get('description', parent.description),
            category=parent.category,
            steps=changes.get('steps', parent.steps),
            applicable_item_types=changes.get(
                'applicable_item_types',
                parent.applicable_item_types
            ),
            required_tags=changes.get('required_tags', parent.required_tags),
            version=new_version,
            parent_skill_id=uuid.UUID(parent_skill_id),
            created_by=created_by
        )

        self.db.add(new_skill)
        await self.db.commit()
        await self.db.refresh(new_skill)

        logger.info(f"Created Skill version {new_version} from {parent.version}")
        return new_skill

    # =========================================================================
    # Skill Recommendation
    # =========================================================================

    async def recommend_skills(
        self,
        task_type: str,
        task_tags: Optional[List[str]] = None,
        task_content: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Recommend Skills for a given Task.

        Args:
            task_type: Task item type
            task_tags: Task tags
            task_content: Task content for semantic matching
            limit: Max recommendations

        Returns:
            List of (Skill, score) tuples
        """
        # Get all active skills
        skills = await self.list_skills(is_active=True, limit=100)

        recommendations = []

        for skill in skills:
            score = 0.0

            # Match by item type (highest weight)
            if skill.applicable_item_types:
                if task_type in skill.applicable_item_types:
                    score += 0.5

            # Match by tags (medium weight)
            if skill.required_tags and task_tags:
                matching_tags = set(skill.required_tags) & set(task_tags)
                if matching_tags:
                    score += 0.3 * (len(matching_tags) / len(skill.required_tags))

            # Simple content matching (basic keyword matching)
            # In production, this would use embeddings/vector search
            if task_content and skill.description:
                content_lower = task_content.lower()
                desc_lower = skill.description.lower()

                # Extract keywords from description
                desc_words = set(desc_lower.split())
                content_words = set(content_lower.split())

                matching_words = desc_words & content_words
                if matching_words:
                    score += 0.2 * (len(matching_words) / len(desc_words))

            # Only include if there's some relevance
            if score > 0:
                recommendations.append({
                    "skill": skill,
                    "score": score,
                    "match_reason": self._get_match_reason(skill, task_type, task_tags)
                })

        # Sort by score and limit
        recommendations.sort(key=lambda x: x["score"], reverse=True)
        return recommendations[:limit]

    def _get_match_reason(
        self,
        skill: Skill,
        task_type: str,
        task_tags: Optional[List[str]]
    ) -> str:
        """Generate explanation for why a skill was recommended."""
        reasons = []

        if skill.applicable_item_types and task_type in skill.applicable_item_types:
            reasons.append(f"matches type '{task_type}'")

        if skill.required_tags and task_tags:
            matching = set(skill.required_tags) & set(task_tags)
            if matching:
                reasons.append(f"matches tags: {', '.join(matching)}")

        return "; ".join(reasons) if reasons else "general match"

    # =========================================================================
    # Skill Analytics
    # =========================================================================

    async def get_skill_versions(self, skill_id: str) -> List[Skill]:
        """Get all versions of a Skill.

        Args:
            skill_id: Skill UUID (any version)

        Returns:
            List of Skill versions (oldest first)
        """
        # First, get the root skill (or the skill itself if it's the root)
        skill = await self.get_skill(skill_id)
        if not skill:
            return []

        # If this is a child, find the root
        if skill.parent_skill_id:
            root_id = skill.parent_skill_id
            while root_id:
                parent_stmt = select(Skill).where(Skill.id == root_id)
                result = await self.db.execute(parent_stmt)
                parent = result.scalar_one_or_none()
                if parent and parent.parent_skill_id:
                    root_id = parent.parent_skill_id
                else:
                    root_id = None
        else:
            # This is the root
            root_id = skill.id

        # Get all versions
        if skill.parent_skill_id:
            # Use the original parent_skill_id to start
            stmt = select(Skill).where(
                Skill.parent_skill_id == skill.parent_skill_id
            )
        else:
            stmt = select(Skill).where(
                Skill.parent_skill_id == skill.id
            )

        result = await self.db.execute(stmt)
        versions = result.scalars().all()

        # Include the root skill if applicable
        if not skill.parent_skill_id:
            versions = [skill] + list(versions)

        return sorted(versions, key=lambda x: x.created_at)

    async def get_skill_stats(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """Get usage statistics for a Skill.

        Args:
            skill_id: Skill UUID

        Returns:
            Statistics dict or None
        """
        skill = await self.get_skill(skill_id)
        if not skill:
            return None

        # In production, this would query execution logs
        # For now, return basic info
        versions = await self.get_skill_versions(skill_id)

        return {
            "skill_id": str(skill.id),
            "name": skill.name,
            "version": skill.version,
            "total_versions": len(versions),
            "created_at": skill.created_at,
            "is_active": skill.is_active,
            "applicable_item_types": skill.applicable_item_types,
            "category": skill.category
        }
