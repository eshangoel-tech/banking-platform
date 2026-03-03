"""Wallet API v1 routes — add-money (Razorpay)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.core.auth.dependencies import AuthContext, get_current_user
from app.repository.session import get_db
from app.schemas.wallet import AddMoneyInitiateRequest
from app.services.core.wallet_service.service import WalletService

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
# Initiate add-money  (requires JWT)
# ---------------------------------------------------------------------------

@router.post("/add-money/initiate")
async def initiate_add_money(
    request: Request,
    payload: AddMoneyInitiateRequest,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a Razorpay order for adding money to the wallet.

    Returns the order details needed by the frontend Razorpay Checkout widget:
      - order_id       → pass to Razorpay SDK as `order_id`
      - razorpay_key_id → pass to Razorpay SDK as `key`
      - amount         → display to user (INR)
      - currency       → "INR"
    """
    service = WalletService()
    data = await service.initiate_add_money(
        db,
        user=auth.user,
        session_id=auth.session_id,
        amount=payload.amount,
    )
    return _ok(request, "Payment order created.", data=data)


# ---------------------------------------------------------------------------
# Razorpay webhook  (PUBLIC — no JWT)
# ---------------------------------------------------------------------------

@router.post(
    "/add-money/webhook",
    # Exclude from OpenAPI security schemes — this endpoint is public
    include_in_schema=True,
)
async def add_money_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_razorpay_signature: str = Header(
        default="",
        alias="x-razorpay-signature",
        description="HMAC-SHA256 signature sent by Razorpay",
    ),
):
    """
    Razorpay webhook endpoint.

    Security:  Every request is verified via HMAC-SHA256 before any DB
               access.  This endpoint MUST return 200 quickly; Razorpay
               retries on non-200 with exponential back-off.

    Idempotent: Duplicate delivery of the same event is silently ignored.

    Configure in Razorpay Dashboard → Settings → Webhooks:
      URL    : https://<host>/api/v1/wallet/add-money/webhook
      Events : payment.captured, payment.failed
      Secret : value of RAZORPAY_WEBHOOK_SECRET env var
    """
    # Read raw body — must be read BEFORE any middleware or Pydantic touches it
    body = await request.body()

    service = WalletService()
    await service.process_webhook(db, body=body, signature=x_razorpay_signature)

    # Razorpay expects a plain 200 with minimal body
    return JSONResponse(status_code=200, content={"status": "ok"})
