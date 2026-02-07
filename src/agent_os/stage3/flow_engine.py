"""Agent Flow Execution Engine.

This module implements the core execution engine for multi-step Agent workflows.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from agent_os.stage3.models import AgentDecision, Skill, TaskExecutionLog

logger = logging.getLogger(__name__)


class FlowExecution:
    """Represents a single execution of an Agent Flow."""

    def __init__(
        self,
        execution_id: str,
        task_id: str,
        skill_id: str,
        context: Dict[str, Any]
    ):
        self.execution_id = execution_id
        self.task_id = task_id
        self.skill_id = skill_id
        self.context = context
        self.current_step = 0
        self.status = "not_started"
        self.logs: List[TaskExecutionLog] = []


class FlowEngine:
    """Agent Flow Execution Engine.

    Manages the execution of multi-step Agent workflows defined by Skills.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def start_flow(
        self,
        task_id: str,
        skill_id: str,
        initial_context: Dict[str, Any]
    ) -> FlowExecution:
        """Start executing an Agent Flow.

        Args:
            task_id: Task UUID
            skill_id: Skill UUID
            initial_context: Initial context data

        Returns:
            FlowExecution object
        """
        # Load skill definition
        skill = await self._load_skill(skill_id)
        if not skill:
            raise ValueError(f"Skill {skill_id} not found")

        # Create execution
        execution_id = str(uuid.uuid4())
        # Store skill_id in context for later retrieval
        context_with_skill = {
            "skill_id": skill_id,
            **initial_context
        }
        execution = FlowExecution(
            execution_id=execution_id,
            task_id=task_id,
            skill_id=skill_id,
            context=context_with_skill
        )

        execution.status = "running"
        logger.info(f"Started Agent Flow {execution_id} for task {task_id}")

        # Execute steps until completion or waiting for confirmation
        while execution.status == "running":
            await self._execute_next_step(execution, skill)

            # If step requires confirmation, stop and wait
            if execution.status == "waiting_confirmation":
                logger.info(f"Flow {execution_id} waiting for user confirmation at step {execution.current_step}")
                break

            # If completed or failed, stop
            if execution.status in ["completed", "failed"]:
                break

        return execution

    async def get_execution_status(
        self,
        execution_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get current execution status.

        Args:
            execution_id: Execution UUID

        Returns:
            Execution status dict or None
        """
        # Query latest log
        stmt = select(TaskExecutionLog).where(
            TaskExecutionLog.task_id == execution_id
        ).order_by(TaskExecutionLog.step_order.desc())

        result = await self.db.execute(stmt)
        logs = result.scalars().all()

        if not logs:
            return None

        latest_log = logs[0]

        # Check if waiting for decision
        if latest_log.status == "waiting_confirmation":
            decision = await self._load_decision(latest_log.decision_id)
            return {
                "execution_id": execution_id,
                "status": "waiting_confirmation",
                "current_step": latest_log.step_order,
                "decision": {
                    "decision_id": str(latest_log.decision_id),
                    "options": decision.options if decision else None
                }
            }

        return {
            "execution_id": execution_id,
            "status": latest_log.status,
            "current_step": latest_log.step_order,
            "total_steps": len(logs)
        }

    async def pause_flow(
        self,
        execution_id: str
    ) -> bool:
        """Pause a running flow execution.

        Args:
            execution_id: Execution UUID

        Returns:
            True if paused successfully
        """
        # Get current execution log
        stmt = select(TaskExecutionLog).where(
            TaskExecutionLog.task_id == execution_id
        ).order_by(TaskExecutionLog.step_order.desc())

        result = await self.db.execute(stmt)
        logs = result.scalars().all()

        if not logs:
            raise ValueError(f"Execution {execution_id} not found")

        latest_log = logs[0]

        if latest_log.status not in ["running", "pending"]:
            raise ValueError(f"Cannot pause flow in status: {latest_log.status}")

        # Update log status
        latest_log.status = "paused"
        await self.db.commit()

        logger.info(f"Flow {execution_id} paused")
        return True

    async def resume_flow(
        self,
        execution_id: str
    ) -> FlowExecution:
        """Resume a paused flow execution.

        Args:
            execution_id: Execution UUID

        Returns:
            Updated FlowExecution
        """
        # Get current execution log
        stmt = select(TaskExecutionLog).where(
            TaskExecutionLog.task_id == execution_id
        ).order_by(TaskExecutionLog.step_order.desc())

        result = await self.db.execute(stmt)
        logs = result.scalars().all()

        if not logs:
            raise ValueError(f"Execution {execution_id} not found")

        latest_log = logs[0]

        if latest_log.status != "paused":
            raise ValueError(f"Cannot resume flow in status: {latest_log.status}")

        # Get skill from context (need to store skill_id in execution)
        # For now, we'll query the first log to get context
        first_log = logs[-1]

        # Recreate execution
        execution = FlowExecution(
            execution_id=execution_id,
            task_id=execution_id,
            skill_id="",  # Will need to be stored/persisted
            context=latest_log.input_data or {}
        )
        execution.current_step = latest_log.step_order

        # Load skill (simplified - in production, load from stored skill_id)
        # For now, we need to find the skill from the first log
        # This is a limitation of the current implementation

        # Update log status
        latest_log.status = "running"
        await self.db.commit()

        logger.info(f"Flow {execution_id} resumed")

        # Note: In production, we would:
        # 1. Store skill_id with the execution
        # 2. Load the skill and continue execution
        # 3. Call _execute_next_step to continue

        return execution

    async def continue_after_decision(
        self,
        execution_id: str,
        decision_id: str,
        selected_option_id: str
    ) -> FlowExecution:
        """Continue execution after user confirms a decision.

        Args:
            execution_id: Execution UUID
            decision_id: Decision UUID
            selected_option_id: Selected option ID

        Returns:
            Updated FlowExecution
        """
        # Confirm decision
        decision = await self._load_decision(decision_id)
        if not decision:
            raise ValueError(f"Decision {decision_id} not found")

        decision.selected_option_id = selected_option_id
        decision.confirmed_at = datetime.utcnow()
        await self.db.commit()

        logger.info(f"Decision {decision_id} confirmed: {selected_option_id}")

        # Get the execution log that's waiting for this decision
        stmt = select(TaskExecutionLog).where(
            TaskExecutionLog.task_id == execution_id,
            TaskExecutionLog.decision_id == uuid.UUID(decision_id)
        )

        result = await self.db.execute(stmt)
        log = result.scalar_one_or_none()

        if not log:
            raise ValueError(f"Execution log for decision {decision_id} not found")

        # Update log status
        log.status = "completed"
        log.completed_at = datetime.utcnow()

        # Get all logs to determine current step and find skill_id from context
        stmt = select(TaskExecutionLog).where(
            TaskExecutionLog.task_id == execution_id
        ).order_by(TaskExecutionLog.step_order.asc())

        result = await self.db.execute(stmt)
        all_logs = result.scalars().all()

        # Get skill_id from the first log's input_data
        skill_id = None
        if all_logs:
            first_log = all_logs[0]
            if first_log.input_data and "skill_id" in first_log.input_data:
                skill_id = first_log.input_data["skill_id"]

        if not skill_id:
            raise ValueError(f"Cannot find skill_id for execution {execution_id}")

        # Load skill
        skill = await self._load_skill(skill_id)
        if not skill:
            raise ValueError(f"Skill {skill_id} not found")

        # Recreate execution with proper context
        execution = FlowExecution(
            execution_id=execution_id,
            task_id=decision.task_id,
            skill_id=skill_id,
            context=log.input_data or {}
        )
        execution.current_step = log.step_order
        execution.status = "running"

        await self.db.commit()

        logger.info(f"Flow {execution_id} continued after decision, executing remaining steps")

        # Continue executing remaining steps
        while execution.status == "running":
            await self._execute_next_step(execution, skill)

            # If step requires confirmation, stop and wait
            if execution.status == "waiting_confirmation":
                logger.info(f"Flow {execution_id} waiting for user confirmation at step {execution.current_step}")
                break

            # If completed or failed, stop
            if execution.status in ["completed", "failed"]:
                break

        return execution

    async def _load_skill(self, skill_id) -> Optional[Skill]:
        """Load skill from database.

        Args:
            skill_id: Skill UUID (str or UUID object)

        Returns:
            Skill object or None
        """
        # Handle both str and UUID types
        if isinstance(skill_id, str):
            skill_uuid = uuid.UUID(skill_id)
        else:
            skill_uuid = skill_id

        stmt = select(Skill).where(Skill.id == skill_uuid)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _load_decision(self, decision_id) -> Optional[AgentDecision]:
        """Load decision from database.

        Args:
            decision_id: Decision UUID (str or UUID object)

        Returns:
            AgentDecision object or None
        """
        # Handle both str and UUID types
        if isinstance(decision_id, str):
            decision_uuid = uuid.UUID(decision_id)
        else:
            decision_uuid = decision_id

        stmt = select(AgentDecision).where(AgentDecision.id == decision_uuid)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _execute_next_step(
        self,
        execution: FlowExecution,
        skill: Skill
    ):
        """Execute the next step in the workflow.

        Args:
            execution: FlowExecution object
            skill: Skill definition
        """
        steps = sorted(skill.steps, key=lambda x: x["order"])

        if execution.current_step >= len(steps):
            execution.status = "completed"
            logger.info(f"Flow {execution.execution_id} completed")
            return

        step = steps[execution.current_step]
        step_name = step["name"]
        requires_confirmation = step.get("requires_confirmation", False)
        agent_action = step.get("agent_action", "")

        logger.info(f"Executing step {step_name} (order={step['order']})")

        # Create execution log
        log = TaskExecutionLog(
            id=uuid.uuid4(),
            task_id=execution.task_id,
            step_name=step_name,
            step_order=step["order"],
            status="running",
            started_at=datetime.utcnow(),
            agent_action=agent_action,
            input_data=execution.context  # Store context (including skill_id)
        )

        # Execute the step (simplified - in production, dispatch to actual agent)
        try:
            result = await self._execute_agent_action(agent_action, execution.context)

            log.status = "completed"
            log.completed_at = datetime.utcnow()
            log.duration_ms = int((log.completed_at - log.started_at).total_seconds() * 1000)
            log.output_data = result

            # Check if confirmation needed
            if requires_confirmation and "options" in result:
                # Create decision point
                decision = await self._create_decision(
                    execution.task_id,
                    step_name,
                    result["options"]
                )

                log.status = "waiting_confirmation"
                log.decision_id = decision.id

                execution.status = "waiting_confirmation"
                # Move to next step index (will execute after confirmation)
                execution.current_step += 1
                execution.context.update(result)

            else:
                # Continue to next step
                execution.current_step += 1
                execution.context.update(result)

        except Exception as e:
            log.status = "failed"
            log.error_message = str(e)
            logger.error(f"Step {step_name} failed: {e}", exc_info=True)

        self.db.add(log)
        await self.db.commit()

        execution.logs.append(log)

    async def _execute_agent_action(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute an Agent action.

        Args:
            action: Action name
            context: Execution context

        Returns:
            Action result
        """
        # Placeholder for actual agent execution
        # In production, this would dispatch to specific agent modules

        if action == "generate_decision_options":
            return await self._generate_decision_options(context)
        elif action == "classify_and_summarize":
            return await self._classify_and_summarize(context)
        else:
            return {"status": "ok", "message": f"Executed {action}"}

    async def _generate_decision_options(
        self,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate decision options (simplified implementation).

        Args:
            context: Execution context

        Returns:
            Dict with options list
        """
        # Simplified decision generation
        # In production, this would use more sophisticated logic

        options = [
            {
                "id": "option_a",
                "title": "Option A: Proceed",
                "description": "Continue with the current approach",
                "rationale": "Based on current context",
                "risks": ["Risk 1", "Risk 2"],
                "confidence": 0.8
            },
            {
                "id": "option_b",
                "title": "Option B: Alternative",
                "description": "Consider alternative approach",
                "rationale": "Provides different perspective",
                "risks": ["Alternative risk"],
                "confidence": 0.7
            },
            {
                "id": "option_c",
                "title": "Option C: Defer",
                "description": "Defer decision to later",
                "rationale": "Need more information",
                "risks": ["Delay risk"],
                "confidence": 0.6
            }
        ]

        return {"options": options, "recommended_option_id": "option_a"}

    async def _classify_and_summarize(
        self,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Classify and summarize context (simplified implementation).

        Args:
            context: Execution context

        Returns:
            Classification result
        """
        # Simplified classification
        return {
            "context_type": "decision",
            "priority": "medium",
            "complexity": "high",
            "summary": "Context analyzed"
        }

    async def _create_decision(
        self,
        task_id: str,
        step_name: str,
        options: List[Dict[str, Any]]
    ) -> AgentDecision:
        """Create a decision point.

        Args:
            task_id: Task ID
            step_name: Step name
            options: Options list

        Returns:
            AgentDecision object
        """
        decision = AgentDecision(
            task_id=task_id,
            step_name=step_name,
            options=options
        )

        self.db.add(decision)
        await self.db.commit()
        await self.db.refresh(decision)

        return decision
