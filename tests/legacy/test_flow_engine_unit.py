"""Unit tests for Agent Flow Execution Engine."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.stage3.flow_engine import FlowEngine
from agent_os.stage3.models import AgentDecision, Skill, TaskExecutionLog


@pytest.mark.asyncio
class TestFlowEngine:
    """Test FlowEngine core functionality."""

    async def test_start_flow(self, db_session: AsyncSession):
        """Test starting an Agent Flow."""
        # Create a skill
        skill = Skill(
            name="Test Skill",
            description="Test skill for flow execution",
            category="decision",
            steps=[
                {
                    "order": 1,
                    "name": "step1_analyze",
                    "description": "First step",
                    "agent_action": "classify_and_summarize",
                    "requires_confirmation": False
                }
            ],
            version="1.0"
        )

        db_session.add(skill)
        await db_session.commit()
        await db_session.refresh(skill)

        # Start flow
        engine = FlowEngine(db_session)
        task_id = str(uuid.uuid4())

        execution = await engine.start_flow(
            task_id=task_id,
            skill_id=str(skill.id),
            initial_context={"content": "Test input"}
        )

        assert execution.execution_id is not None
        assert execution.task_id == task_id
        print(f"✅ Flow started: {execution.execution_id}")
        print(f"   Status: {execution.status}")

    async def test_flow_creates_execution_logs(self, db_session: AsyncSession):
        """Test that flow execution creates logs."""
        # Create skill
        skill = Skill(
            name="Test Skill",
            description="Test skill",
            category="decision",
            steps=[
                {
                    "order": 1,
                    "name": "step1",
                    "agent_action": "classify_and_summarize",
                    "requires_confirmation": False
                }
            ],
            version="1.0"
        )

        db_session.add(skill)
        await db_session.commit()

        # Start flow
        engine = FlowEngine(db_session)
        task_id = str(uuid.uuid4())

        execution = await engine.start_flow(
            task_id=task_id,
            skill_id=str(skill.id),
            initial_context={"test": "data"}
        )

        # Check logs were created
        stmt = select(TaskExecutionLog).where(
            TaskExecutionLog.task_id == task_id
        )
        result = await db_session.execute(stmt)
        logs = result.scalars().all()

        assert len(logs) > 0
        print(f"✅ Created {len(logs)} execution logs")

    async def test_flow_creates_decision_when_confirmation_needed(self, db_session: AsyncSession):
        """Test that flow creates decision when confirmation is required."""
        # Create skill with confirmation required
        skill = Skill(
            name="Decision Skill",
            description="Skill with confirmation",
            category="decision",
            steps=[
                {
                    "order": 1,
                    "name": "generate_options",
                    "agent_action": "generate_decision_options",
                    "requires_confirmation": True
                }
            ],
            version="1.0"
        )

        db_session.add(skill)
        await db_session.commit()

        # Start flow
        engine = FlowEngine(db_session)
        task_id = str(uuid.uuid4())

        execution = await engine.start_flow(
            task_id=task_id,
            skill_id=str(skill.id),
            initial_context={"query": "What should I do?"}
        )

        # Check status
        assert execution.status == "waiting_confirmation"

        # Check decision was created
        stmt = select(AgentDecision).where(
            AgentDecision.task_id == task_id
        )
        result = await db_session.execute(stmt)
        decision = result.scalar_one_or_none()

        assert decision is not None
        assert len(decision.options) > 0
        print(f"✅ Decision created: {decision.id}")
        print(f"   Options: {len(decision.options)}")

    async def test_pause_and_resume_flow(self, db_session: AsyncSession):
        """Test pausing and resuming a flow."""
        # Create a skill that waits for confirmation
        skill = Skill(
            name="Multi-step Skill",
            description="Skill with confirmation step",
            category="decision",
            steps=[
                {
                    "order": 1,
                    "name": "generate_options",
                    "agent_action": "generate_decision_options",
                    "requires_confirmation": True
                }
            ],
            version="1.0"
        )

        db_session.add(skill)
        await db_session.commit()

        # Start flow - will be waiting for confirmation
        engine = FlowEngine(db_session)
        task_id = str(uuid.uuid4())

        execution = await engine.start_flow(
            task_id=task_id,
            skill_id=str(skill.id),
            initial_context={"test": "data"}
        )

        # Get the latest log (should be waiting_confirmation)
        stmt = select(TaskExecutionLog).where(
            TaskExecutionLog.task_id == task_id
        ).order_by(TaskExecutionLog.step_order.desc())
        result = await db_session.execute(stmt)
        latest_log = result.scalar_one()

        # Manually set status to "running" to test pause
        # In real scenario, we'd pause during execution
        latest_log.status = "running"
        await db_session.commit()

        # Pause the flow
        paused = await engine.pause_flow(task_id)
        assert paused is True

        # Verify status
        await db_session.refresh(latest_log)
        assert latest_log.status == "paused"
        print(f"✅ Flow paused: {task_id}")

        # Resume the flow
        resumed_execution = await engine.resume_flow(task_id)
        assert resumed_execution is not None
        print(f"✅ Flow resumed: {task_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
