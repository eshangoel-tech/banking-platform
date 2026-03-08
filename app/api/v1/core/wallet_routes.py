"""Wallet API v1 routes — OTP-based add-money."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.core.auth_dependency import AuthContext, get_current_user
from app.common.responses import ok_response
from app.repository.session import get_db
from app.schemas.wallet import AddMoneyConfirmRequest, AddMoneyInitiateRequest
from app.services.core.wallet_service.service import WalletService

router = APIRouter()


# ---------------------------------------------------------------------------
# Step 1: initiate add-money  (requires JWT)
# ---------------------------------------------------------------------------

@router.post("/add-money/initiate")
async def initiate_add_money(
    request: Request,
    payload: AddMoneyInitiateRequest,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Initiate an add-money request.

    Validates the amount, generates an OTP, and emails it to the user.
    Returns a `topup_id` that must be passed to `/add-money/confirm`.
    """
    service = WalletService()
    data = await service.initiate_add_money(
        db,
        user=auth.user,
        session_id=auth.session_id,
        amount=payload.amount,
    )
    return ok_response(request, "OTP sent to your registered email.", data=data)


# ---------------------------------------------------------------------------
# Step 2: confirm add-money  (requires JWT)
# ---------------------------------------------------------------------------

@router.post("/add-money/confirm")
async def confirm_add_money(
    request: Request,
    payload: AddMoneyConfirmRequest,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Confirm an add-money request by verifying the OTP.

    On success, the specified amount is credited to the user's account.
    """
    service = WalletService()
    data = await service.confirm_add_money(
        db,
        user=auth.user,
        session_id=auth.session_id,
        topup_id=uuid.UUID(payload.topup_id),
        otp=payload.otp,
    )
    return ok_response(request, "Amount credited successfully.", data=data)
