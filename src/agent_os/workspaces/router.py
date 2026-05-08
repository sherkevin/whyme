"""PRD10 B-17 multi-workspace permission API."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User
from agent_os.common import ApiErrorCode, error_json_response, success_json_response
from agent_os.db.base import get_db
from agent_os.items.models import Workspace
from agent_os.workspaces.models import WorkspaceMember

router = APIRouter(prefix="/api/v1/workspaces", tags=["Workspaces"])

WorkspaceRole = Literal["owner", "admin", "editor", "viewer"]

ROLE_RANK: dict[str, int] = {
    "viewer": 10,
    "editor": 20,
    "admin": 30,
    "owner": 40,
}


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class WorkspaceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class WorkspaceMemberUpsertRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    role: WorkspaceRole = "viewer"


class WorkspaceMemberUpdateRequest(BaseModel):
    role: WorkspaceRole


def _workspace_payload(workspace: Workspace, role: str) -> dict:
    return {
        "id": str(workspace.id),
        "name": workspace.name,
        "description": workspace.description,
        "owner_id": str(workspace.owner_id),
        "role": role,
        "created_at": workspace.created_at.isoformat() if workspace.created_at else None,
        "updated_at": workspace.updated_at.isoformat() if workspace.updated_at else None,
    }


def _member_payload(member: WorkspaceMember, user: User | None = None) -> dict:
    user_obj = user or member.user
    return {
        "id": str(member.id),
        "workspace_id": str(member.workspace_id),
        "user_id": str(member.user_id),
        "email": user_obj.email if user_obj else None,
        "username": user_obj.username if user_obj else None,
        "role": member.role,
        "status": member.status,
        "created_at": member.created_at.isoformat() if member.created_at else None,
        "updated_at": member.updated_at.isoformat() if member.updated_at else None,
    }


async def _get_workspace(db: AsyncSession, workspace_id: uuid.UUID) -> Workspace | None:
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    return result.scalar_one_or_none()


async def _get_member(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> WorkspaceMember | None:
    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.status == "active",
        )
    )
    return result.scalar_one_or_none()


async def _effective_role(
    db: AsyncSession,
    workspace: Workspace,
    user_id: uuid.UUID,
) -> str | None:
    if workspace.owner_id == user_id:
        return "owner"
    member = await _get_member(db, workspace.id, user_id)
    return member.role if member else None


async def _require_workspace_role(
    request: Request,
    db: AsyncSession,
    workspace_id: uuid.UUID,
    user: User,
    minimum_role: WorkspaceRole,
) -> tuple[Workspace, str] | None:
    workspace = await _get_workspace(db, workspace_id)
    if workspace is None:
        return None
    role = await _effective_role(db, workspace, user.id)
    if role is None or ROLE_RANK[role] < ROLE_RANK[minimum_role]:
        return None
    return workspace, role


@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_workspace(
    payload: WorkspaceCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workspace = Workspace(
        name=payload.name,
        description=payload.description,
        owner_id=current_user.id,
    )
    db.add(workspace)
    await db.flush()
    db.add(
        WorkspaceMember(
            workspace_id=workspace.id,
            user_id=current_user.id,
            role="owner",
            status="active",
            invited_by_id=current_user.id,
        )
    )
    await db.commit()
    await db.refresh(workspace)
    return success_json_response(
        _workspace_payload(workspace, "owner"),
        request=request,
        status_code=status.HTTP_201_CREATED,
    )


@router.get("")
@router.get("/")
async def list_workspaces(
    request: Request,
    include_disabled: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    member_workspace_ids = select(WorkspaceMember.workspace_id).where(
        WorkspaceMember.user_id == current_user.id,
    )
    if not include_disabled:
        member_workspace_ids = member_workspace_ids.where(
            WorkspaceMember.status == "active",
        )
    result = await db.execute(
        select(Workspace)
        .where(
            or_(
                Workspace.owner_id == current_user.id,
                Workspace.id.in_(member_workspace_ids),
            )
        )
        .order_by(Workspace.updated_at.desc(), Workspace.created_at.desc())
    )
    workspaces = result.scalars().unique().all()
    items = []
    for workspace in workspaces:
        role = await _effective_role(db, workspace, current_user.id)
        if role:
            items.append(_workspace_payload(workspace, role))
    return success_json_response({"items": items}, request=request)


@router.get("/{workspace_id}")
async def get_workspace(
    workspace_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workspace = await _get_workspace(db, workspace_id)
    if workspace is None:
        return error_json_response(
            ApiErrorCode.NOT_FOUND,
            "Workspace not found",
            request=request,
            status_code=status.HTTP_404_NOT_FOUND,
        )
    role = await _effective_role(db, workspace, current_user.id)
    if role is None:
        return error_json_response(
            ApiErrorCode.FORBIDDEN,
            "You do not have access to this workspace",
            request=request,
            status_code=status.HTTP_403_FORBIDDEN,
        )
    return success_json_response(_workspace_payload(workspace, role), request=request)


@router.patch("/{workspace_id}")
async def update_workspace(
    workspace_id: uuid.UUID,
    payload: WorkspaceUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workspace = await _get_workspace(db, workspace_id)
    if workspace is None:
        return error_json_response(
            ApiErrorCode.NOT_FOUND,
            "Workspace not found",
            request=request,
            status_code=status.HTTP_404_NOT_FOUND,
        )
    role = await _effective_role(db, workspace, current_user.id)
    if role is None or ROLE_RANK[role] < ROLE_RANK["admin"]:
        return error_json_response(
            ApiErrorCode.FORBIDDEN,
            "Workspace admin permission required",
            request=request,
            status_code=status.HTTP_403_FORBIDDEN,
        )
    if payload.name is not None:
        workspace.name = payload.name
    if payload.description is not None:
        workspace.description = payload.description
    await db.commit()
    await db.refresh(workspace)
    return success_json_response(_workspace_payload(workspace, role), request=request)


@router.get("/{workspace_id}/members")
async def list_workspace_members(
    workspace_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    allowed = await _require_workspace_role(
        request, db, workspace_id, current_user, "viewer"
    )
    if allowed is None:
        workspace = await _get_workspace(db, workspace_id)
        return error_json_response(
            ApiErrorCode.NOT_FOUND if workspace is None else ApiErrorCode.FORBIDDEN,
            "Workspace not found" if workspace is None else "Workspace access required",
            request=request,
            status_code=status.HTTP_404_NOT_FOUND
            if workspace is None
            else status.HTTP_403_FORBIDDEN,
        )
    result = await db.execute(
        select(WorkspaceMember, User)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(WorkspaceMember.workspace_id == workspace_id)
        .order_by(WorkspaceMember.created_at.asc())
    )
    items = [_member_payload(member, user) for member, user in result.all()]
    return success_json_response({"items": items}, request=request)


@router.post("/{workspace_id}/members", status_code=status.HTTP_201_CREATED)
async def upsert_workspace_member(
    workspace_id: uuid.UUID,
    payload: WorkspaceMemberUpsertRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    allowed = await _require_workspace_role(
        request, db, workspace_id, current_user, "admin"
    )
    if allowed is None:
        workspace = await _get_workspace(db, workspace_id)
        return error_json_response(
            ApiErrorCode.NOT_FOUND if workspace is None else ApiErrorCode.FORBIDDEN,
            "Workspace not found" if workspace is None else "Workspace admin permission required",
            request=request,
            status_code=status.HTTP_404_NOT_FOUND
            if workspace is None
            else status.HTTP_403_FORBIDDEN,
        )
    workspace, _role = allowed
    user_result = await db.execute(select(User).where(User.email == payload.email))
    target_user = user_result.scalar_one_or_none()
    if target_user is None:
        return error_json_response(
            ApiErrorCode.NOT_FOUND,
            "User not found",
            request=request,
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if target_user.id == workspace.owner_id and payload.role != "owner":
        return error_json_response(
            ApiErrorCode.VALIDATION_ERROR,
            "Workspace owner role cannot be downgraded",
            request=request,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    member = await _get_member(db, workspace_id, target_user.id)
    if member is None:
        member = WorkspaceMember(
            workspace_id=workspace_id,
            user_id=target_user.id,
            role=payload.role,
            status="active",
            invited_by_id=current_user.id,
        )
        db.add(member)
    else:
        member.role = payload.role
        member.status = "active"
    await db.commit()
    await db.refresh(member)
    return success_json_response(
        _member_payload(member, target_user),
        request=request,
        status_code=status.HTTP_201_CREATED,
    )


@router.patch("/{workspace_id}/members/{user_id}")
async def update_workspace_member(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: WorkspaceMemberUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    allowed = await _require_workspace_role(
        request, db, workspace_id, current_user, "admin"
    )
    if allowed is None:
        workspace = await _get_workspace(db, workspace_id)
        return error_json_response(
            ApiErrorCode.NOT_FOUND if workspace is None else ApiErrorCode.FORBIDDEN,
            "Workspace not found" if workspace is None else "Workspace admin permission required",
            request=request,
            status_code=status.HTTP_404_NOT_FOUND
            if workspace is None
            else status.HTTP_403_FORBIDDEN,
        )
    workspace, _role = allowed
    if user_id == workspace.owner_id and payload.role != "owner":
        return error_json_response(
            ApiErrorCode.VALIDATION_ERROR,
            "Workspace owner role cannot be downgraded",
            request=request,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    result = await db.execute(
        select(WorkspaceMember, User)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    row = result.one_or_none()
    if row is None:
        return error_json_response(
            ApiErrorCode.NOT_FOUND,
            "Workspace member not found",
            request=request,
            status_code=status.HTTP_404_NOT_FOUND,
        )
    member, target_user = row
    member.role = payload.role
    member.status = "active"
    await db.commit()
    await db.refresh(member)
    return success_json_response(_member_payload(member, target_user), request=request)


@router.delete("/{workspace_id}/members/{user_id}")
async def remove_workspace_member(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    allowed = await _require_workspace_role(
        request, db, workspace_id, current_user, "admin"
    )
    if allowed is None:
        workspace = await _get_workspace(db, workspace_id)
        return error_json_response(
            ApiErrorCode.NOT_FOUND if workspace is None else ApiErrorCode.FORBIDDEN,
            "Workspace not found" if workspace is None else "Workspace admin permission required",
            request=request,
            status_code=status.HTTP_404_NOT_FOUND
            if workspace is None
            else status.HTTP_403_FORBIDDEN,
        )
    workspace, _role = allowed
    if user_id == workspace.owner_id:
        return error_json_response(
            ApiErrorCode.VALIDATION_ERROR,
            "Workspace owner cannot be removed",
            request=request,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    member = await _get_member(db, workspace_id, user_id)
    if member is None:
        return error_json_response(
            ApiErrorCode.NOT_FOUND,
            "Workspace member not found",
            request=request,
            status_code=status.HTTP_404_NOT_FOUND,
        )
    member.status = "disabled"
    await db.commit()
    return success_json_response({"removed": True}, request=request)
