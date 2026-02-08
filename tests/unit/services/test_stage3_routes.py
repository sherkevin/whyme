"""Unit tests for Stage 3 router components (without full integration)."""

import pytest
import uuid
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.stage3.router import router
from agent_os.stage3.models import Skill
from agent_os.auth.models import User
from agent_os.auth.security import create_access_token


# Create a test app with the Stage 3 router
test_app = FastAPI()
test_app.include_router(router)


@pytest.mark.asyncio
class TestStage3RouterSetup:
    """Test that router is properly configured."""

    def test_router_routes_defined(self):
        """Test that all expected routes are defined."""
        routes = [route.path for route in router.routes]

        # Flow execution routes
        assert "/api/v1/agent/flow/start" in routes
        assert "/api/v1/agent/flow/{execution_id}/status" in routes
        assert "/api/v1/agent/flow/{execution_id}/continue" in routes
        assert "/api/v1/agent/flow/{execution_id}/pause" in routes
        assert "/api/v1/agent/flow/{execution_id}/resume" in routes

        # Decision routes
        assert "/api/v1/agent/decisions/{decision_id}" in routes
        assert "/api/v1/agent/decisions/{decision_id}/confirm" in routes
        assert "/api/v1/agent/tasks/{task_id}/decisions" in routes

        # Skill routes
        assert "/api/v1/agent/skills" in routes
        assert "/api/v1/agent/skills/{skill_id}" in routes
        assert "/api/v1/agent/skills/recommend" in routes

        # Execution log routes
        assert "/api/v1/agent/tasks/{task_id}/execution-logs" in routes

        print(f"✅ All {len(routes)} Stage 3 routes defined")


@pytest.mark.asyncio
class TestSkillServiceDirect:
    """Test Skill Service directly without API layer."""

    async def test_skill_service_workflow(self, db_session: AsyncSession):
        """Test complete skill service workflow."""
        from agent_os.stage3.skill_service import SkillService

        service = SkillService(db_session)
        user_id = str(uuid.uuid4())

        # Create skill
        skill = await service.create_skill(
            name="Workflow Test Skill",
            description="Testing complete workflow",
            category="decision",
            steps=[
                {"order": 1, "name": "step1", "agent_action": "action1", "requires_confirmation": False},
                {"order": 2, "name": "step2", "agent_action": "action2", "requires_confirmation": True}
            ],
            created_by=user_id,
            applicable_item_types=["task"],
            required_tags=["important"]
        )

        assert skill.id is not None
        print(f"✅ Step 1: Created skill {skill.name}")

        # Get skill
        retrieved = await service.get_skill(str(skill.id))
        assert retrieved is not None
        assert retrieved.name == "Workflow Test Skill"
        print(f"✅ Step 2: Retrieved skill")

        # List skills
        skills = await service.list_skills(category="decision")
        assert len(skills) >= 1
        print(f"✅ Step 3: Listed {len(skills)} skills")

        # Update skill
        updated = await service.update_skill(
            str(skill.id),
            description="Updated description"
        )
        assert updated.description == "Updated description"
        print(f"✅ Step 4: Updated skill")

        # Recommend skills
        recommendations = await service.recommend_skills(
            task_type="task",
            task_tags=["important"],
            limit=5
        )
        assert len(recommendations) > 0
        assert any(r["skill"].id == skill.id for r in recommendations)
        print(f"✅ Step 5: Got {len(recommendations)} recommendations")

        # Get stats
        stats = await service.get_skill_stats(str(skill.id))
        assert stats is not None
        assert stats["name"] == "Workflow Test Skill"
        print(f"✅ Step 6: Got skill stats")

        # Create version
        v2 = await service.create_skill_version(
            parent_skill_id=str(skill.id),
            changes={"description": "Version 2"},
            created_by=user_id
        )
        assert v2 is not None
        assert v2.version == "1.1"
        assert v2.parent_skill_id == skill.id
        print(f"✅ Step 7: Created version {v2.version}")

        # Get versions
        versions = await service.get_skill_versions(str(skill.id))
        assert len(versions) >= 2
        print(f"✅ Step 8: Retrieved {len(versions)} versions")

        # Delete (soft delete)
        deleted = await service.delete_skill(str(skill.id))
        assert deleted is True
        print(f"✅ Step 9: Soft deleted skill")

        # Verify it's deleted
        retrieved_after = await service.get_skill(str(skill.id))
        assert retrieved_after is None  # Should not return inactive skills
        print(f"✅ Step 10: Verified soft delete")


@pytest.mark.asyncio
class TestFlowEngineDirect:
    """Test Flow Engine directly without API layer."""

    async def test_flow_engine_workflow(self, db_session: AsyncSession):
        """Test complete flow engine workflow."""
        from agent_os.stage3.flow_engine import FlowEngine

        # Create skill
        skill = Skill(
            name="Engine Test Skill",
            description="Testing flow engine",
            category="decision",
            steps=[
                {
                    "order": 1,
                    "name": "step1",
                    "agent_action": "classify_and_summarize",
                    "requires_confirmation": False
                },
                {
                    "order": 2,
                    "name": "step2",
                    "agent_action": "generate_decision_options",
                    "requires_confirmation": True
                }
            ],
            created_by=str(uuid.uuid4()),
            version="1.0"
        )
        db_session.add(skill)
        await db_session.commit()
        await db_session.refresh(skill)

        engine = FlowEngine(db_session)
        task_id = str(uuid.uuid4())

        # Start flow
        execution = await engine.start_flow(
            task_id=task_id,
            skill_id=str(skill.id),
            initial_context={"test": "data"}
        )
        assert execution.execution_id is not None
        print(f"✅ Step 1: Started flow {execution.execution_id}")

        # Get status
        status = await engine.get_execution_status(task_id)
        assert status is not None
        assert "status" in status
        print(f"✅ Step 2: Got flow status: {status['status']}")

        # Pause if running
        if status["status"] in ["running", "completed"]:
            # Get latest log and manually set to running for pause test
            from sqlalchemy import select
            from agent_os.stage3.models import TaskExecutionLog

            stmt = select(TaskExecutionLog).where(
                TaskExecutionLog.task_id == task_id
            ).order_by(TaskExecutionLog.step_order.desc())

            result = await db_session.execute(stmt)
            latest_log = result.scalar_one_or_none()

            if latest_log:
                latest_log.status = "running"
                await db_session.commit()

                # Pause
                paused = await engine.pause_flow(task_id)
                assert paused is True
                print(f"✅ Step 3: Paused flow")

                # Resume
                resumed = await engine.resume_flow(task_id)
                assert resumed is not None
                print(f"✅ Step 4: Resumed flow")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
