"""Transfer API v1 routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.core.auth.dependencies import AuthContext, get_current_user
from app.repository.session import get_db
from app.schemas.transfer import TransferConfirmRequest, TransferInitiateRequest
from app.services.core.transfer_service.service import TransferService

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
# Initiate transfer
# ---------------------------------------------------------------------------

@router.post("/initiate")
async def initiate_transfer(
    request: Request,
    payload: TransferInitiateRequest,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = TransferService()
    data = await service.initiate_transfer(
        db,
        user=auth.user,
        session_id=auth.session_id,
        receiver_account_number=payload.receiver_account_number,
        amount=payload.amount,
    )
    return _ok(request, "OTP sent for transfer confirmation.", data=data)


# ---------------------------------------------------------------------------
# Confirm transfer
# ---------------------------------------------------------------------------

@router.post("/confirm")
async def confirm_transfer(
    request: Request,
    payload: TransferConfirmRequest,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = TransferService()
    await service.confirm_transfer(
        db,
        user=auth.user,
        session_id=auth.session_id,
        transfer_id=payload.transfer_id,
        otp=payload.otp,
    )
    return _ok(request, "Transfer completed successfully.")
