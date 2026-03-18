"""Pydantic schemas for the transfer module."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class TransferInitiateRequest(BaseModel):
    to_account_number: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=32,
        description="Receiver's ADX Bank account number (e.g. ADX0000012)",
    )
    to_phone: Optional[str] = Field(
        default=None,
        description="Receiver's registered phone number (10 digits)",
    )
    amount: Decimal = Field(..., gt=0, decimal_places=2)

    @model_validator(mode="after")
    def exactly_one_identifier(self) -> "TransferInitiateRequest":
        has_account = bool(self.to_account_number)
        has_phone = bool(self.to_phone)
        if has_account and has_phone:
            raise ValueError("Provide only one of to_account_number or to_phone, not both")
        if not has_account and not has_phone:
            raise ValueError("Provide either to_account_number or to_phone")
        return self

    @field_validator("to_phone")
    @classmethod
    def phone_format(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            digits = v.strip().lstrip("+").lstrip("91")
            if not digits.isdigit() or len(digits) != 10:
                raise ValueError("Phone number must be 10 digits (e.g. 9876543210)")
            return digits
        return v

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Transfer amount must be greater than zero")
        return v


class TransferInitiateResponse(BaseModel):
    transfer_id: str
    receiver_name: str
    receiver_account: str   # masked, e.g. ADX****210
    amount: str


class TransferConfirmRequest(BaseModel):
    transfer_id: UUID
    otp: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class TransferConfirmResponse(BaseModel):
    success: bool
    message: str
