"""FastAPI router for Stage 3 - Multi-step Agent Flows."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.db.base import get_db
from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User

# Import services
from agent_os.stage3.flow_engine import FlowEngine
from agent_os.stage3.skill_service import SkillService

# Import schemas
from agent_os.stage3.schema import (
    # Decision schemas
    DecisionResponse,
    DecisionConfirm,
    # Skill schemas
    SkillCreate,
    SkillUpdate,
    SkillResponse,
    SkillRecommendRequest,
    SkillRecommendation,
    # Flow schemas
    FlowStartRequest,
    FlowStartResponse,
    FlowStatusResponse,
    FlowContinueRequest,
    FlowPauseResponse,
    FlowResumeResponse,
    # Log schemas
    ExecutionLogResponse
)

# Import models
from agent_os.stage3.models import AgentDecision, TaskExecutionLog
from sqlalchemy import select

# =============================================================================
# Router Setup
# =============================================================================

router = APIRouter(prefix="/api/v1/agent", tags=["agent-flows"])


# =============================================================================
# Flow Execution Endpoints
# =============================================================================

@router.post("/flow/start", response_model=FlowStartResponse, status_code=status.HTTP_201_CREATED)
async def start_flow(
    request: FlowStartRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Start executing an Agent Flow.

    Args:
        request: Flow start request
        db: Database session
        current_user: Authenticated user

    Returns:
        Flow execution info
    """
    engine = FlowEngine(db)

    try:
        execution = await engine.start_flow(
            task_id=request.task_id,
            skill_id=request.skill_id,
            initial_context=request.initial_context
        )

        return FlowStartResponse(
            execution_id=execution.execution_id,
            task_id=execution.task_id,
            skill_id=request.skill_id,
            status=execution.status,
            current_step=execution.current_step
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start flow: {str(e)}")


@router.get("/flow/{execution_id}/status", response_model=FlowStatusResponse)
async def get_flow_status(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get current flow execution status.

    Args:
        execution_id: Execution UUID
        db: Database session
        current_user: Authenticated user

    Returns:
        Flow status
    """
    engine = FlowEngine(db)

    status_data = await engine.get_execution_status(execution_id)

    if not status_data:
        raise HTTPException(status_code=404, detail="Execution not found")

    return FlowStatusResponse(**status_data)


@router.post("/flow/{execution_id}/continue", response_model=FlowStatusResponse)
async def continue_flow(
    execution_id: str,
    request: FlowContinueRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Continue flow execution after decision confirmation.

    Args:
        execution_id: Execution UUID
        request: Continue request with decision
        db: Database session
        current_user: Authenticated user

    Returns:
        Updated flow status
    """
    engine = FlowEngine(db)

    try:
        execution = await engine.continue_after_decision(
            execution_id=execution_id,
            decision_id=request.decision_id,
            selected_option_id=request.selected_option_id
        )

        # Get updated status
        status_data = await engine.get_execution_status(execution_id)
        return FlowStatusResponse(**status_data)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to continue flow: {str(e)}")


@router.post("/flow/{execution_id}/pause", response_model=FlowPauseResponse)
async def pause_flow(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Pause a running flow.

    Args:
        execution_id: Execution UUID
        db: Database session
        current_user: Authenticated user

    Returns:
        Pause confirmation
    """
    engine = FlowEngine(db)

    try:
        result = await engine.pause_flow(execution_id)
        if result:
            return FlowPauseResponse(
                execution_id=execution_id,
                status="paused",
                message="Flow paused successfully"
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to pause flow: {str(e)}")


@router.post("/flow/{execution_id}/resume", response_model=FlowResumeResponse)
async def resume_flow(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Resume a paused flow.

    Args:
        execution_id: Execution UUID
        db: Database session
        current_user: Authenticated user

    Returns:
        Resume confirmation
    """
    engine = FlowEngine(db)

    try:
        execution = await engine.resume_flow(execution_id)
        return FlowResumeResponse(
            execution_id=execution_id,
            status="running",
            message="Flow resumed successfully"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resume flow: {str(e)}")


# =============================================================================
# Decision Endpoints
# =============================================================================

@router.get("/decisions/{decision_id}", response_model=DecisionResponse)
async def get_decision(
    decision_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a decision by ID.

    Args:
        decision_id: Decision UUID
        db: Database session
        current_user: Authenticated user

    Returns:
        Decision details
    """
    import uuid as uuid_pkg

    stmt = select(AgentDecision).where(
        AgentDecision.id == uuid_pkg.UUID(decision_id)
    )

    result = await db.execute(stmt)
    decision = result.scalar_one_or_none()

    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    return DecisionResponse.model_validate(decision)


@router.post("/decisions/{decision_id}/confirm", response_model=DecisionResponse)
async def confirm_decision(
    decision_id: str,
    request: DecisionConfirm,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Confirm a decision.

    Args:
        decision_id: Decision UUID
        request: Confirmation data
        db: Database session
        current_user: Authenticated user

    Returns:
        Updated decision
    """
    import uuid as uuid_pkg
    from datetime import datetime

    stmt = select(AgentDecision).where(
        AgentDecision.id == uuid_pkg.UUID(decision_id)
    )

    result = await db.execute(stmt)
    decision = result.scalar_one_or_none()

    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    # Update decision
    decision.selected_option_id = request.selected_option_id
    decision.confirmed_by = request.confirmed_by or str(current_user.id)
    decision.confirmed_at = datetime.utcnow()

    await db.commit()
    await db.refresh(decision)

    return DecisionResponse.model_validate(decision)


@router.get("/tasks/{task_id}/decisions", response_model=List[DecisionResponse])
async def get_task_decisions(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all decisions for a task.

    Args:
        task_id: Task ID
        db: Database session
        current_user: Authenticated user

    Returns:
        List of decisions
    """
    stmt = select(AgentDecision).where(
        AgentDecision.task_id == task_id
    ).order_by(AgentDecision.created_at.desc())

    result = await db.execute(stmt)
    decisions = result.scalars().all()

    return [DecisionResponse.model_validate(d) for d in decisions]


# =============================================================================
# Skill Endpoints
# =============================================================================

@router.post("/skills", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
async def create_skill(
    request: SkillCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new Skill.

    Args:
        request: Skill creation data
        db: Database session
        current_user: Authenticated user

    Returns:
        Created skill
    """
    service = SkillService(db)

    # Convert steps to dict format
    steps_dict = [step.model_dump() for step in request.steps]

    skill = await service.create_skill(
        name=request.name,
        description=request.description,
        category=request.category,
        steps=steps_dict,
        created_by=str(current_user.id),
        applicable_item_types=request.applicable_item_types,
        required_tags=request.required_tags,
        version=request.version
    )

    return SkillResponse.model_validate(skill)


@router.get("/skills", response_model=List[SkillResponse])
async def list_skills(
    category: str = Query(None, description="Filter by category"),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all active Skills.

    Args:
        category: Optional category filter
        limit: Max results
        offset: Pagination offset
        db: Database session
        current_user: Authenticated user

    Returns:
        List of skills
    """
    service = SkillService(db)

    skills = await service.list_skills(
        category=category,
        is_active=True,
        limit=limit,
        offset=offset
    )

    return [SkillResponse.model_validate(s) for s in skills]


@router.get("/skills/{skill_id}", response_model=SkillResponse)
async def get_skill(
    skill_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a Skill by ID.

    Args:
        skill_id: Skill UUID
        db: Database session
        current_user: Authenticated user

    Returns:
        Skill details
    """
    service = SkillService(db)

    skill = await service.get_skill(skill_id)

    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    return SkillResponse.model_validate(skill)


@router.put("/skills/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: str,
    request: SkillUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a Skill.

    Args:
        skill_id: Skill UUID
        request: Update data
        db: Database session
        current_user: Authenticated user

    Returns:
        Updated skill
    """
    service = SkillService(db)

    # Build update dict
    updates = request.model_dump(exclude_unset=True)

    # Convert steps to dict if present
    if "steps" in updates and updates["steps"]:
        updates["steps"] = [step.model_dump() for step in updates["steps"]]

    skill = await service.update_skill(skill_id, **updates)

    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    return SkillResponse.model_validate(skill)


@router.delete("/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(
    skill_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a Skill (soft delete).

    Args:
        skill_id: Skill UUID
        db: Database session
        current_user: Authenticated user

    Returns:
        204 No Content
    """
    service = SkillService(db)

    result = await service.delete_skill(skill_id)

    if not result:
        raise HTTPException(status_code=404, detail="Skill not found")


@router.post("/skills/recommend", response_model=List[SkillRecommendation])
async def recommend_skills(
    request: SkillRecommendRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get recommended Skills for a task.

    Args:
        request: Recommendation request
        db: Database session
        current_user: Authenticated user

    Returns:
        List of skill recommendations with scores
    """
    service = SkillService(db)

    recommendations = await service.recommend_skills(
        task_type=request.task_type,
        task_tags=request.task_tags,
        task_content=request.task_content,
        limit=request.limit
    )

    # Convert to response format
    result = []
    for rec in recommendations:
        result.append(SkillRecommendation(
            skill=SkillResponse.model_validate(rec["skill"]),
            score=rec["score"],
            match_reason=rec["match_reason"]
        ))

    return result


# =============================================================================
# Execution Log Endpoints
# =============================================================================

@router.get("/tasks/{task_id}/execution-logs", response_model=List[ExecutionLogResponse])
async def get_execution_logs(
    task_id: str,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get execution logs for a task.

    Args:
        task_id: Task ID
        limit: Max results
        db: Database session
        current_user: Authenticated user

    Returns:
        List of execution logs
    """
    stmt = select(TaskExecutionLog).where(
        TaskExecutionLog.task_id == task_id
    ).order_by(
        TaskExecutionLog.step_order.asc()
    ).limit(limit)

    result = await db.execute(stmt)
    logs = result.scalars().all()

    return [ExecutionLogResponse.model_validate(log) for log in logs]
