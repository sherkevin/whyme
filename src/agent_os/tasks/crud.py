"""CRUD operations for Task management."""

from datetime import UTC, date, datetime
from typing import List, Optional, Tuple

from sqlalchemy import and_, asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.tasks.models import Task
from agent_os.tasks.schema import TaskCreate, TaskStatusUpdate, TaskUpdate

# =============================================================================
# Task CRUD Operations
# =============================================================================

async def create_task(
    db: AsyncSession,
    *,
    task_in: TaskCreate,
    user_id: int
) -> Task:
    """Create a new task.

    Args:
        db: Async database session
        task_in: Task creation data
        user_id: ID of the user creating the task

    Returns:
        Created task object
    """
    db_task = Task(
        **task_in.model_dump(),
        user_id=user_id
    )
    db.add(db_task)
    await db.commit()
    await db.refresh(db_task)
    return db_task


async def get_task_by_id(
    db: AsyncSession,
    *,
    task_id: int,
    user_id: int
) -> Task | None:
    """Get a task by ID.

    Args:
        db: Async database session
        task_id: ID of the task to retrieve
        user_id: ID of the user (for access control)

    Returns:
        Task object if found, None otherwise
    """
    stmt = select(Task).where(
        and_(
            Task.id == task_id,
            Task.user_id == user_id
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_tasks(
    db: AsyncSession,
    *,
    user_id: int,
    status: str | None = None,
    task_type: str | None = None,
    priority_min: int | None = None,
    priority_max: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    scheduled_date: date | None = None,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc"
) -> tuple[list[Task], int]:
    """List tasks with filtering and pagination.

    Args:
        db: Async database session
        user_id: ID of the user
        status: Filter by status
        task_type: Filter by type
        priority_min: Minimum priority
        priority_max: Maximum priority
        date_from: Filter by scheduled date from
        date_to: Filter by scheduled date to
        scheduled_date: Filter by exact scheduled date
        skip: Number of records to skip
        limit: Maximum number of records to return
        sort_by: Field to sort by
        sort_order: Sort order (asc or desc)

    Returns:
        Tuple of (list of tasks, total count)
    """
    # Build query conditions
    conditions = [Task.user_id == user_id]

    if status:
        conditions.append(Task.status == status)
    if task_type:
        conditions.append(Task.type == task_type)
    if priority_min is not None:
        conditions.append(Task.priority >= priority_min)
    if priority_max is not None:
        conditions.append(Task.priority <= priority_max)
    if scheduled_date:
        conditions.append(Task.scheduled_date == scheduled_date)
    else:
        if date_from:
            conditions.append(Task.scheduled_date >= date_from)
        if date_to:
            conditions.append(Task.scheduled_date <= date_to)

    # Count query
    count_stmt = select(func.count(Task.id)).where(and_(*conditions))
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Data query with sorting
    sort_column = getattr(Task, sort_by)
    sort_func = desc if sort_order == "desc" else asc

    stmt = (
        select(Task)
        .where(and_(*conditions))
        .order_by(sort_func(sort_column))
        .offset(skip)
        .limit(limit)
    )

    result = await db.execute(stmt)
    tasks = result.scalars().all()

    return list(tasks), total


async def update_task(
    db: AsyncSession,
    *,
    db_task: Task,
    task_in: TaskUpdate | TaskStatusUpdate
) -> Task:
    """Update a task.

    Args:
        db: Async database session
        db_task: Existing task object
        task_in: Task update data

    Returns:
        Updated task object
    """
    update_data = task_in.model_dump(exclude_unset=True)

    # Auto-set completed_at when status changes to completed
    if isinstance(task_in, TaskStatusUpdate) and task_in.status == "completed":
        if not update_data.get("completed_at"):
            update_data["completed_at"] = datetime.now(UTC)

    for field, value in update_data.items():
        setattr(db_task, field, value)

    db.add(db_task)
    await db.commit()
    await db.refresh(db_task)
    return db_task


async def delete_task(
    db: AsyncSession,
    *,
    task_id: int,
    user_id: int
) -> bool:
    """Delete a task.

    Args:
        db: Async database session
        task_id: ID of the task to delete
        user_id: ID of the user (for access control)

    Returns:
        True if deleted, False if not found
    """
    stmt = select(Task).where(
        and_(
            Task.id == task_id,
            Task.user_id == user_id
        )
    )
    result = await db.execute(stmt)
    db_task = result.scalar_one_or_none()

    if db_task:
        await db.delete(db_task)
        await db.commit()
        return True

    return False


async def get_tasks_for_today(
    db: AsyncSession,
    *,
    user_id: int,
    today: date
) -> list[Task]:
    """Get all tasks for today.

    Args:
        db: Async database session
        user_id: ID of the user
        today: Today's date

    Returns:
        List of tasks for today
    """
    stmt = select(Task).where(
        and_(
            Task.user_id == user_id,
            or_(
                Task.scheduled_date == today,
                and_(
                    Task.scheduled_date.is_(None),
                    func.date(Task.created_at) == today
                )
            )
        )
    ).order_by(desc(Task.priority), Task.created_at)

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_task_stats(
    db: AsyncSession,
    *,
    user_id: int,
    today: date | None = None
) -> dict:
    """Get task statistics.

    Args:
        db: Async database session
        user_id: ID of the user
        today: Optional date filter for today's stats

    Returns:
        Dictionary with task statistics
    """
    conditions = [Task.user_id == user_id]

    if today:
        conditions.append(
            or_(
                Task.scheduled_date == today,
                and_(
                    Task.scheduled_date.is_(None),
                    func.date(Task.created_at) == today
                )
            )
        )

    # Total count
    total_stmt = select(func.count(Task.id)).where(and_(*conditions))
    total_result = await db.execute(total_stmt)
    total = total_result.scalar() or 0

    # Count by status
    status_stats = {}
    for status in ["pending", "in_progress", "completed"]:
        status_stmt = select(func.count(Task.id)).where(
            and_(*conditions, Task.status == status)
        )
        status_result = await db.execute(status_stmt)
        status_stats[status] = status_result.scalar() or 0

    # Count by priority
    priority_stmt = select(
        Task.priority,
        func.count(Task.id)
    ).where(
        and_(*conditions)
    ).group_by(Task.priority)

    priority_result = await db.execute(priority_stmt)
    by_priority = {str(prio): count for prio, count in priority_result.all()}

    # Count by type
    type_stmt = select(
        Task.type,
        func.count(Task.id)
    ).where(
        and_(*conditions)
    ).group_by(Task.type)

    type_result = await db.execute(type_stmt)
    by_type = {t: count for t, count in type_result.all()}

    return {
        "total": total,
        "pending": status_stats.get("pending", 0),
        "in_progress": status_stats.get("in_progress", 0),
        "completed": status_stats.get("completed", 0),
        "by_priority": by_priority,
        "by_type": by_type
    }


# =============================================================================
# Batch Operations
# =============================================================================

async def create_tasks_batch(
    db: AsyncSession,
    *,
    tasks_data: list[TaskCreate],
    user_id: int
) -> list[Task]:
    """Create multiple tasks in batch.

    Args:
        db: Async database session
        tasks_data: List of task creation data
        user_id: ID of the user creating the tasks

    Returns:
        List of created task objects
    """
    db_tasks = [
        Task(**task_data.model_dump(), user_id=user_id)
        for task_data in tasks_data
    ]

    db.add_all(db_tasks)
    await db.commit()

    # Refresh all tasks
    for task in db_tasks:
        await db.refresh(task)

    return db_tasks


async def update_tasks_batch(
    db: AsyncSession,
    *,
    task_ids: list[int],
    user_id: int,
    updates: TaskUpdate
) -> int:
    """Update multiple tasks in batch.

    Args:
        db: Async database session
        task_ids: List of task IDs to update
        user_id: ID of the user (for access control)
        updates: Update data to apply to all tasks

    Returns:
        Number of tasks updated
    """
    # Get all tasks that belong to the user
    stmt = select(Task).where(
        and_(
            Task.id.in_(task_ids),
            Task.user_id == user_id
        )
    )
    result = await db.execute(stmt)
    tasks = result.scalars().all()

    update_data = updates.model_dump(exclude_unset=True)

    for task in tasks:
        for field, value in update_data.items():
            setattr(task, field, value)

    db.add_all(tasks)
    await db.commit()

    return len(tasks)


async def delete_tasks_batch(
    db: AsyncSession,
    *,
    task_ids: list[int],
    user_id: int
) -> int:
    """Delete multiple tasks in batch.

    Args:
        db: Async database session
        task_ids: List of task IDs to delete
        user_id: ID of the user (for access control)

    Returns:
        Number of tasks deleted
    """
    stmt = select(Task).where(
        and_(
            Task.id.in_(task_ids),
            Task.user_id == user_id
        )
    )
    result = await db.execute(stmt)
    tasks = result.scalars().all()

    for task in tasks:
        await db.delete(task)

    await db.commit()

    return len(tasks)
