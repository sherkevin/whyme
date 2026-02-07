"""Demo: Career Decision Assistant

This module provides a complete demo of the Stage 3 multi-step Agent Flow system
using a Career Decision scenario.

The Career Decision Assistant helps users make career-related decisions through
a structured 8-step process:
1. Context Classification
2. Information Extraction
3. Option Generation
4. Impact Analysis
5. User Confirmation
6. Decision Recording
7. Action Plan Generation
8. Summary and Next Steps
"""

import asyncio
import uuid
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select

from agent_os.stage3.models import Skill, AgentDecision, TaskExecutionLog
from agent_os.stage3.skill_service import SkillService
from agent_os.stage3.flow_engine import FlowEngine


class CareerDecisionAssistant:
    """Career Decision Assistant Demo."""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.skill_service = SkillService(db_session)
        self.flow_engine = FlowEngine(db_session)
        self.skill: Skill = None

    async def setup(self) -> None:
        """Setup the Career Decision Assistant skill."""
        # Check if skill already exists
        skills = await self.skill_service.list_skills(
            category="decision",
            limit=100
        )

        existing = next((s for s in skills if s.name == "Career Decision Assistant"), None)

        if existing:
            print(f"✅ Using existing skill: {existing.name} (v{existing.version})")
            self.skill = existing
            return

        # Create the skill
        self.skill = await self.skill_service.create_skill(
            name="Career Decision Assistant",
            description="Helps users make career-related decisions through a structured 8-step process",
            category="decision",
            steps=[
                {
                    "order": 1,
                    "name": "classify_context",
                    "description": "Classify the career decision context (e.g., job change, promotion, industry switch)",
                    "agent_action": "classify_and_summarize",
                    "requires_confirmation": False
                },
                {
                    "order": 2,
                    "name": "extract_information",
                    "description": "Extract key information from user's input (current role, goals, constraints)",
                    "agent_action": "classify_and_summarize",
                    "requires_confirmation": False
                },
                {
                    "order": 3,
                    "name": "generate_options",
                    "description": "Generate 3-4 career options based on context and constraints",
                    "agent_action": "generate_decision_options",
                    "requires_confirmation": True
                },
                {
                    "order": 4,
                    "name": "analyze_impacts",
                    "description": "Analyze impacts of each option (salary, work-life balance, growth)",
                    "agent_action": "classify_and_summarize",
                    "requires_confirmation": False
                },
                {
                    "order": 5,
                    "name": "await_user_selection",
                    "description": "Wait for user to select preferred option",
                    "agent_action": "generate_decision_options",
                    "requires_confirmation": True
                },
                {
                    "order": 6,
                    "name": "record_decision",
                    "description": "Record the user's decision with rationale",
                    "agent_action": "classify_and_summarize",
                    "requires_confirmation": False
                },
                {
                    "order": 7,
                    "name": "generate_action_plan",
                    "description": "Generate actionable next steps for the chosen path",
                    "agent_action": "classify_and_summarize",
                    "requires_confirmation": False
                },
                {
                    "order": 8,
                    "name": "provide_summary",
                    "description": "Provide final summary and resources",
                    "agent_action": "classify_and_summarize",
                    "requires_confirmation": False
                }
            ],
            created_by="system",
            applicable_item_types=["task", "decision_point"],
            required_tags=["career", "decision"],
            version="1.0"
        )

        print(f"✅ Created skill: {self.skill.name} (v{self.skill.version})")

    async def run_demo(
        self,
        user_query: str,
        task_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run the Career Decision Assistant demo.

        Args:
            user_query: User's career question
            task_context: Additional context (current role, salary, etc.)

        Returns:
            Demo execution results
        """
        print("\n" + "="*80)
        print("🎯 CAREER DECISION ASSISTANT DEMO")
        print("="*80)
        print(f"\n👤 User Query: {user_query}")
        print(f"📊 Context: {task_context}")
        print("\n" + "-"*80)

        # Create a task ID for this demo
        task_id = str(uuid.uuid4())

        # Start the flow
        print("\n🚀 Starting Agent Flow...")
        execution = await self.flow_engine.start_flow(
            task_id=task_id,
            skill_id=str(self.skill.id),
            initial_context={
                "query": user_query,
                **task_context
            }
        )

        print(f"✅ Flow started: {execution.execution_id}")
        print(f"   Status: {execution.status}")
        print(f"   Current Step: {execution.current_step}")

        # Get execution status
        print("\n📊 Checking execution status...")
        status = await self.flow_engine.get_execution_status(task_id)
        print(f"✅ Status: {status['status']}")
        print(f"   Current Step: {status.get('current_step', 'N/A')}")
        print(f"   Total Steps: {status.get('total_steps', 'N/A')}")

        # Check if waiting for decision
        if status['status'] == 'waiting_confirmation':
            print("\n⏸️  Flow is waiting for user confirmation...")

            if 'decision' in status and status['decision']:
                decision_data = status['decision']
                print(f"   Decision ID: {decision_data['decision_id']}")

                # Load full decision
                stmt = select(AgentDecision).where(
                    AgentDecision.id == uuid.UUID(decision_data['decision_id'])
                )
                result = await self.db.execute(stmt)
                decision = result.scalar_one_or_none()

                if decision:
                    print(f"\n📋 Generated Options:")
                    for i, option in enumerate(decision.options, 1):
                        print(f"\n   Option {i}: {option['title']}")
                        print(f"   └─ Description: {option['description']}")
                        print(f"   └─ Rationale: {option['rationale']}")
                        print(f"   └─ Confidence: {option['confidence']:.1%}")
                        if option.get('risks'):
                            print(f"   └─ Risks: {', '.join(option['risks'])}")

                    # Simulate user selecting an option
                    selected = decision.options[0]
                    print(f"\n✅ User selected: {selected['title']}")

                    # Continue after decision
                    print("\n▶️  Continuing flow after user selection...")
                    await self.flow_engine.continue_after_decision(
                        execution_id=task_id,
                        decision_id=str(decision.id),
                        selected_option_id=selected['id']
                    )

        # Get execution logs
        print("\n📝 Execution Logs:")
        stmt = select(TaskExecutionLog).where(
            TaskExecutionLog.task_id == task_id
        ).order_by(TaskExecutionLog.step_order.asc())

        result = await self.db.execute(stmt)
        logs = result.scalars().all()

        for log in logs:
            print(f"\n   Step {log.step_order}: {log.step_name}")
            print(f"   └─ Status: {log.status}")
            print(f"   └─ Action: {log.agent_action or 'N/A'}")
            if log.started_at:
                print(f"   └─ Started: {log.started_at.strftime('%H:%M:%S')}")
            if log.completed_at:
                print(f"   └─ Completed: {log.completed_at.strftime('%H:%M:%S')}")
            if log.duration_ms:
                print(f"   └─ Duration: {log.duration_ms}ms")
            if log.error_message:
                print(f"   └─ Error: {log.error_message}")

        print("\n" + "="*80)
        print("✅ DEMO COMPLETED")
        print("="*80)

        return {
            "execution_id": execution.execution_id,
            "task_id": task_id,
            "status": status['status'],
            "total_steps": len(logs),
            "skill_version": self.skill.version
        }


async def main():
    """Run the Career Decision Assistant demo."""
    import os

    # Create database session
    database_url = os.getenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./agent_os.db"
    )

    engine = create_async_engine(
        database_url,
        echo=False
    )

    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session_maker() as session:
        # Initialize the assistant
        assistant = CareerDecisionAssistant(session)
        await assistant.setup()

        # Run demo scenarios
        print("\n\n" + "🌟"*40)
        print("SCENARIO 1: Job Offer Decision")
        print("🌟"*40)

        result1 = await assistant.run_demo(
            user_query="I received a job offer from a startup. Should I take it?",
            task_context={
                "current_role": "Software Engineer",
                "current_salary": "$120,000",
                "offer_salary": "$140,000 + 0.5% equity",
                "concerns": ["Risk", "Work-life balance", "Career growth"]
            }
        )

        print("\n\n" + "🌟"*40)
        print("SCENARIO 2: Career Change Decision")
        print("🌟"*40)

        result2 = await assistant.run_demo(
            user_query="Should I switch from backend engineering to ML engineering?",
            task_context={
                "current_role": "Backend Engineer",
                "experience": "5 years",
                "ml_background": "Completed ML specialization",
                "concerns": ["Salary impact", "Learning curve", "Job market"]
            }
        )

        print("\n\n" + "🌟"*40)
        print("SCENARIO 3: Promotion Decision")
        print("🌟"*40)

        result3 = await assistant.run_demo(
            user_query="Should I accept the staff engineer promotion?",
            task_context={
                "current_role": "Senior Engineer",
                "pros": ["Higher salary", "Leadership opportunity"],
                "cons": ["Less coding", "More meetings"]
            }
        )

        # Summary
        print("\n\n" + "="*80)
        print("📊 DEMO SUMMARY")
        print("="*80)
        print(f"\n✅ Completed 3 scenarios")
        print(f"✅ Skill Version: {assistant.skill.version}")
        print(f"✅ Total Steps in Flow: {len(assistant.skill.steps)}")
        print("\n💡 This demonstrates the complete Stage 3 multi-step Agent Flow system:")
        print("   - Skill definition with 8 steps")
        print("   - Flow execution with status tracking")
        print("   - Decision point generation")
        print("   - User confirmation workflow")
        print("   - Complete execution logging")
        print("   - Pause/resume capabilities")
        print("\n" + "="*80)


if __name__ == "__main__":
    asyncio.run(main())
