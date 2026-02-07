"""Unit tests for Stage 3 models."""

import pytest
import uuid
from datetime import datetime
from sqlalchemy import select

from agent_os.stage3.models import AgentDecision, Skill, TaskExecutionLog


@pytest.mark.asyncio
class TestAgentDecisionModel:
    """Test AgentDecision model."""

    async def test_create_decision(self, db_session):
        """Test creating an agent decision."""
        task_id = str(uuid.uuid4())

        decision = AgentDecision(
            task_id=task_id,
            step_name="step_2_generate_options",
            options=[
                {
                    "id": "option_a",
                    "title": "Accept Project",
                    "description": "High ROI and manageable risk",
                    "rationale": "ROI > 50%",
                    "risks": ["Requires 20 person-months"],
                    "confidence": 0.85
                }
            ]
        )

        db_session.add(decision)
        await db_session.commit()
        await db_session.refresh(decision)

        assert decision.id is not None
        assert decision.task_id == task_id
        assert len(decision.options) == 1
        print(f"✅ Created AgentDecision: {decision.id}")


@pytest.mark.asyncio
class TestSkillModel:
    """Test Skill model."""

    async def test_create_skill(self, db_session):
        """Test creating a skill."""
        user_id = str(uuid.uuid4())

        skill = Skill(
            name="Career Decision Assistant",
            description="Help users make career-related decisions",
            category="decision",
            steps=[
                {
                    "order": 1,
                    "name": "analyze_context",
                    "agent_action": "classify_and_summarize",
                    "requires_confirmation": False
                }
            ],
            applicable_item_types=["task"],
            version="1.0",
            created_by=user_id
        )

        db_session.add(skill)
        await db_session.commit()
        await db_session.refresh(skill)

        assert skill.id is not None
        assert skill.name == "Career Decision Assistant"
        assert len(skill.steps) == 1
        print(f"✅ Created Skill: {skill.name} (v{skill.version})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
