"""Pydantic schemas for the transfer module."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class TransferInitiateRequest(BaseModel):
    receiver_account_number: str = Field(..., min_length=1, max_length=32)
    amount: Decimal = Field(..., gt=0, decimal_places=2)

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Transfer amount must be greater than zero")
        return v


class TransferInitiateResponse(BaseModel):
    transfer_id: str


class TransferConfirmRequest(BaseModel):
    transfer_id: UUID
    otp: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class TransferConfirmResponse(BaseModel):
    success: bool
    message: str
