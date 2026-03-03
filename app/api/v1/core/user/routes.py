"""User API v1 routes (dashboard, account, transactions, profile)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.core.auth.dependencies import AuthContext, get_current_user
from app.repository.session import get_db
from app.schemas.user import UpdateProfileRequest
from app.services.core.user_service.service import UserService

router = APIRouter()


def _request_id(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    return str(rid) if rid else ""


def _ok(request: Request, message: str, data: dict | None = None) -> dict:
    return {
        "success": True,
        "message": message,
        "data": data,
        "request_id": _request_id(request),
    }


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
    return _ok(request, "Dashboard retrieved successfully.", data=data)


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
    return _ok(request, "Account details retrieved successfully.", data=data)


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
    return _ok(request, "Transactions retrieved successfully.", data=data)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

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
        address=payload.address,
    )
    return _ok(request, "Profile updated successfully.")
