"""User API v1 routes (dashboard, account, transactions, profile)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.core.auth_dependency import AuthContext, get_current_user
from app.repository.session import get_db
from app.schemas.user import UpdateProfileRequest
from app.common.responses import ok_response
from app.services.core.user_service.service import UserService

router = APIRouter()


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.get("/dashboard/summary")
async def dashboard_summary(
    request: Request,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = UserService()
    data = await service.get_dashboard_summary(
        db, user=auth.user, session_id=auth.session_id
    )
    return ok_response(request, "Dashboard retrieved successfully.", data=data)


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------

@router.get("/account/details")
async def account_details(
    request: Request,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = UserService()
    data = await service.get_account_details(
        db, user_id=auth.user.id, session_id=auth.session_id
    )
    return ok_response(request, "Account details retrieved successfully.", data=data)


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

@router.get("/transactions")
async def list_transactions(
    request: Request,
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    limit: int = Query(10, ge=1, le=50, description="Records per page (max 50)"),
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = UserService()
    data = await service.get_transactions(
        db,
        user_id=auth.user.id,
        session_id=auth.session_id,
        page=page,
        limit=limit,
    )
    return ok_response(request, "Transactions retrieved successfully.", data=data)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@router.get("/user/profile")
async def get_profile(
    request: Request,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the authenticated user's current profile for pre-filling the edit form."""
    service = UserService()
    data = await service.get_profile(auth.user)
    return ok_response(request, "Profile retrieved successfully.", data=data)


@router.put("/user/profile")
async def update_profile(
    request: Request,
    payload: UpdateProfileRequest,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = UserService()
    await service.update_profile(
        db,
        user=auth.user,
        session_id=auth.session_id,
        phone=payload.phone,
        address=payload.address.model_dump(exclude_none=True) if payload.address else None,
    )
    return ok_response(request, "Profile updated successfully.")
