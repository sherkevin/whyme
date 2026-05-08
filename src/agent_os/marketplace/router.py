"""PRD10 B-19 Skill Marketplace API."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User
from agent_os.billing.router import _append_credit_entry, _credit_balance, _ensure_subscription
from agent_os.common import ApiErrorCode, error_json_response, paginated_response, success_json_response
from agent_os.db.base import get_db
from agent_os.marketplace.models import SkillInstallation, SkillMarketplaceListing
from agent_os.stage3.models import Skill

router = APIRouter(prefix="/api/v1/skill-marketplace", tags=["Skill Marketplace"])

ListingStatus = Literal["listed", "unlisted", "archived"]


class ListingCreateRequest(BaseModel):
    skill_id: uuid.UUID
    price_credits: int = Field(default=0, ge=0, le=100_000)
    status: ListingStatus = "listed"


class ListingUpdateRequest(BaseModel):
    price_credits: int | None = Field(default=None, ge=0, le=100_000)
    status: ListingStatus | None = None


def _listing_payload(
    listing: SkillMarketplaceListing,
    skill: Skill,
    *,
    is_installed: bool = False,
) -> dict:
    payload = {
        "id": str(listing.id),
        "skill_id": str(listing.skill_id),
        "seller_user_id": str(listing.seller_user_id),
        "status": listing.status,
        "price_credits": listing.price_credits,
        "installs_count": listing.installs_count,
        "purchases_count": listing.purchases_count,
        "is_installed": is_installed,
        "created_at": listing.created_at.isoformat() if listing.created_at else None,
        "updated_at": listing.updated_at.isoformat() if listing.updated_at else None,
    }
    payload["skill"] = skill.to_prd10_dict(is_installed=is_installed)
    return payload


def _installation_payload(installation: SkillInstallation, skill: Skill | None = None) -> dict:
    payload = {
        "id": str(installation.id),
        "user_id": str(installation.user_id),
        "skill_id": str(installation.skill_id),
        "listing_id": str(installation.listing_id) if installation.listing_id else None,
        "status": installation.status,
        "source": installation.source,
        "price_paid_credits": installation.price_paid_credits,
        "installed_at": installation.installed_at.isoformat() if installation.installed_at else None,
        "updated_at": installation.updated_at.isoformat() if installation.updated_at else None,
    }
    if skill is not None:
        payload["skill"] = skill.to_prd10_dict(is_installed=installation.status == "installed")
    return payload


async def _installed_skill_ids(db: AsyncSession, user_id: uuid.UUID) -> set[uuid.UUID]:
    result = await db.execute(
        select(SkillInstallation.skill_id).where(
            SkillInstallation.user_id == user_id,
            SkillInstallation.status == "installed",
        )
    )
    return set(result.scalars().all())


async def _get_listing_with_skill(
    db: AsyncSession,
    listing_id: uuid.UUID,
) -> tuple[SkillMarketplaceListing, Skill] | None:
    result = await db.execute(
        select(SkillMarketplaceListing, Skill)
        .join(Skill, Skill.id == SkillMarketplaceListing.skill_id)
        .where(SkillMarketplaceListing.id == listing_id)
    )
    return result.one_or_none()


@router.get("/listings")
async def list_marketplace_listings(
    request: Request,
    category: str | None = Query(default=None),
    keyword: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base = (
        select(SkillMarketplaceListing, Skill)
        .join(Skill, Skill.id == SkillMarketplaceListing.skill_id)
        .where(
            SkillMarketplaceListing.status == "listed",
            Skill.is_active.is_(True),
            Skill.status == "published",
        )
    )
    if category:
        base = base.where(Skill.category == category)
    keyword = (keyword or "").strip()
    if keyword:
        like = f"%{keyword}%"
        base = base.where(or_(Skill.name.ilike(like), Skill.description.ilike(like)))
    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    rows = (
        await db.execute(
            base.order_by(
                SkillMarketplaceListing.purchases_count.desc(),
                SkillMarketplaceListing.created_at.desc(),
            )
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
    ).all()
    installed_ids = await _installed_skill_ids(db, current_user.id)
    return paginated_response(
        [
            _listing_payload(listing, skill, is_installed=skill.id in installed_ids)
            for listing, skill in rows
        ],
        page=page,
        page_size=page_size,
        total=int(total or 0),
        request=request,
    )


@router.post("/listings", status_code=status.HTTP_201_CREATED)
async def create_or_update_listing(
    payload: ListingCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    skill = (
        await db.execute(
            select(Skill).where(Skill.id == payload.skill_id, Skill.is_active.is_(True))
        )
    ).scalar_one_or_none()
    if skill is None:
        return error_json_response(
            ApiErrorCode.NOT_FOUND,
            "Skill not found",
            request=request,
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if skill.created_by and str(skill.created_by) != str(current_user.id):
        return error_json_response(
            ApiErrorCode.FORBIDDEN,
            "Only the skill creator can list this skill",
            request=request,
            status_code=status.HTTP_403_FORBIDDEN,
        )
    existing = (
        await db.execute(
            select(SkillMarketplaceListing).where(
                SkillMarketplaceListing.skill_id == payload.skill_id
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        listing = SkillMarketplaceListing(
            skill_id=payload.skill_id,
            seller_user_id=current_user.id,
            price_credits=payload.price_credits,
            status=payload.status,
        )
        db.add(listing)
    else:
        if existing.seller_user_id != current_user.id:
            return error_json_response(
                ApiErrorCode.FORBIDDEN,
                "Only the listing seller can update this listing",
                request=request,
                status_code=status.HTTP_403_FORBIDDEN,
            )
        listing = existing
        listing.price_credits = payload.price_credits
        listing.status = payload.status
    await db.commit()
    await db.refresh(listing)
    return success_json_response(
        _listing_payload(listing, skill, is_installed=False),
        request=request,
        status_code=status.HTTP_201_CREATED,
    )


@router.patch("/listings/{listing_id}")
async def update_listing(
    listing_id: uuid.UUID,
    payload: ListingUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await _get_listing_with_skill(db, listing_id)
    if row is None:
        return error_json_response(
            ApiErrorCode.NOT_FOUND,
            "Marketplace listing not found",
            request=request,
            status_code=status.HTTP_404_NOT_FOUND,
        )
    listing, skill = row
    if listing.seller_user_id != current_user.id:
        return error_json_response(
            ApiErrorCode.FORBIDDEN,
            "Only the listing seller can update this listing",
            request=request,
            status_code=status.HTTP_403_FORBIDDEN,
        )
    if payload.price_credits is not None:
        listing.price_credits = payload.price_credits
    if payload.status is not None:
        listing.status = payload.status
    await db.commit()
    await db.refresh(listing)
    return success_json_response(_listing_payload(listing, skill), request=request)


@router.get("/installations")
async def list_installations(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(SkillInstallation, Skill)
            .join(Skill, Skill.id == SkillInstallation.skill_id)
            .where(
                SkillInstallation.user_id == current_user.id,
                SkillInstallation.status == "installed",
            )
            .order_by(SkillInstallation.installed_at.desc())
        )
    ).all()
    return success_json_response(
        {"items": [_installation_payload(installation, skill) for installation, skill in rows]},
        request=request,
    )


@router.post("/listings/{listing_id}/purchase", status_code=status.HTTP_201_CREATED)
async def purchase_listing(
    listing_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await _get_listing_with_skill(db, listing_id)
    if row is None:
        return error_json_response(
            ApiErrorCode.NOT_FOUND,
            "Marketplace listing not found",
            request=request,
            status_code=status.HTTP_404_NOT_FOUND,
        )
    listing, skill = row
    if listing.status != "listed" or not skill.is_active or skill.status != "published":
        return error_json_response(
            ApiErrorCode.VALIDATION_ERROR,
            "Marketplace listing is not available",
            request=request,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if listing.seller_user_id == current_user.id:
        return error_json_response(
            ApiErrorCode.VALIDATION_ERROR,
            "Seller already owns this skill",
            request=request,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    existing = (
        await db.execute(
            select(SkillInstallation).where(
                SkillInstallation.user_id == current_user.id,
                SkillInstallation.skill_id == skill.id,
                SkillInstallation.status == "installed",
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return success_json_response(
            {
                "installation": _installation_payload(existing, skill),
                "charged_credits": 0,
                "already_installed": True,
            },
            request=request,
            status_code=status.HTTP_200_OK,
        )

    await _ensure_subscription(db, current_user, None)
    balance = await _credit_balance(db, current_user.id, None)
    if balance < listing.price_credits:
        return error_json_response(
            ApiErrorCode.VALIDATION_ERROR,
            "Insufficient credit balance",
            details={"balance": balance, "price_credits": listing.price_credits},
            request=request,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if listing.price_credits:
        await _append_credit_entry(
            db,
            user_id=current_user.id,
            workspace_id=None,
            amount=-int(listing.price_credits),
            reason="skill_marketplace_purchase",
            reference_type="skill_marketplace_listing",
            reference_id=str(listing.id),
            note=skill.name,
        )
    installation = SkillInstallation(
        user_id=current_user.id,
        skill_id=skill.id,
        listing_id=listing.id,
        status="installed",
        source="marketplace",
        price_paid_credits=listing.price_credits,
    )
    db.add(installation)
    listing.installs_count = int(listing.installs_count or 0) + 1
    listing.purchases_count = int(listing.purchases_count or 0) + 1
    await db.commit()
    await db.refresh(installation)
    await db.refresh(listing)
    return success_json_response(
        {
            "installation": _installation_payload(installation, skill),
            "listing": _listing_payload(listing, skill, is_installed=True),
            "charged_credits": listing.price_credits,
            "already_installed": False,
        },
        request=request,
        status_code=status.HTTP_201_CREATED,
    )
