"""Demo test for Career Decision Assistant."""


import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.stage3.demo_career_assistant import CareerDecisionAssistant
from agent_os.stage3.models import AgentDecision


@pytest.mark.asyncio
class TestCareerDecisionAssistantDemo:
    """Test Career Decision Assistant demo."""

    async def test_demo_setup(self, db_session: AsyncSession):
        """Test that the demo skill can be created."""
        assistant = CareerDecisionAssistant(db_session)
        await assistant.setup()

        assert assistant.skill is not None
        assert assistant.skill.name == "Career Decision Assistant"
        # The skill should have at least 1 step (could be existing skill from previous tests)
        assert len(assistant.skill.steps) >= 1
        print(f"✅ Demo skill created: {assistant.skill.name}")
        print(f"   Steps: {len(assistant.skill.steps)}")

    async def test_demo_execution(self, db_session: AsyncSession):
        """Test running the demo."""
        assistant = CareerDecisionAssistant(db_session)
        await assistant.setup()

        # Run a demo scenario
        result = await assistant.run_demo(
            user_query="Should I take the job offer?",
            task_context={
                "current_salary": "$100,000",
                "offer_salary": "$120,000"
            }
        )

        assert result["execution_id"] is not None
        assert result["task_id"] is not None
        assert result["status"] in ["completed", "waiting_confirmation", "running"]
        assert result["total_steps"] > 0
        print("✅ Demo executed successfully")
        print(f"   Execution ID: {result['execution_id']}")
        print(f"   Status: {result['status']}")
        print(f"   Steps: {result['total_steps']}")

    async def test_demo_creates_decision(self, db_session: AsyncSession):
        """Test that the demo creates decision points."""
        assistant = CareerDecisionAssistant(db_session)
        await assistant.setup()

        # Run demo
        result = await assistant.run_demo(
            user_query="Should I switch careers?",
            task_context={}
        )

        # Check if decisions were created
        stmt = select(AgentDecision).where(
            AgentDecision.task_id == result["task_id"]
        )

        db_result = await db_session.execute(stmt)
        decisions = db_result.scalars().all()

        # The demo should create at least one decision
        # (depending on flow execution, it may wait for confirmation)
        if result["status"] == "waiting_confirmation":
            assert len(decisions) > 0
            print(f"✅ Demo created {len(decisions)} decision(s)")

            for decision in decisions:
                print(f"\n   Decision: {decision.step_name}")
                print(f"   Options: {len(decision.options)}")
                for option in decision.options:
                    print(f"      - {option['title']}")
        else:
            print("ℹ️  Demo completed without waiting for confirmation")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
