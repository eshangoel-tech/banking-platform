"""Pydantic schemas for the wallet / add-money module."""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class AddMoneyInitiateRequest(BaseModel):
    amount: Decimal = Field(
        ...,
        gt=0,
        le=20_000,
        decimal_places=2,
        description="Amount in INR to add (min 1, max 20 000)",
    )


class AddMoneyInitiateResponse(BaseModel):
    """Payload returned after creating a Razorpay order."""

    order_id: str
    razorpay_key_id: str
    amount: str
    currency: str


class WebhookResponse(BaseModel):
    """Minimal 200-OK ack sent back to Razorpay."""

    status: str = "ok"
