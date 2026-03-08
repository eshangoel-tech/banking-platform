"""Pydantic schemas for the wallet / add-money module (OTP-based)."""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class AddMoneyInitiateRequest(BaseModel):
    amount: Decimal = Field(
        ...,
        gt=0,
        le=50_000,
        decimal_places=2,
        description="Amount in INR to add (min ₹1, max ₹50,000)",
    )


class AddMoneyInitiateResponse(BaseModel):
    """Returned after initiating an OTP-based top-up."""
    topup_id: str
    amount: str
    message: str


class AddMoneyConfirmRequest(BaseModel):
    topup_id: str = Field(..., min_length=36, max_length=36, description="UUID returned from initiate")
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit OTP sent to registered email")


class AddMoneyConfirmResponse(BaseModel):
    amount_credited: str
    new_balance: str
    currency: str = "INR"
