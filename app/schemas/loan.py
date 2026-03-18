"""Pydantic schemas for the loan module."""
from __future__ import annotations

from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.config.bank_rules.bank_rules import (
    LOAN_ALLOWED_TENURES,
    LOAN_MIN_AMOUNT,
)

_ALLOWED_TENURES = LOAN_ALLOWED_TENURES
_DEFAULT_TENURE = _ALLOWED_TENURES[0]  # 6


class LoanEligibilityResponse(BaseModel):
    min_loan_amount: str
    max_eligible_amount: str
    existing_loan_outstanding: str
    available_loan_amount: str
    allowed_tenures: List[int]
    interest_rate: str
    processing_fee_percent: int


class LoanSimulateRequest(BaseModel):
    amount: Decimal = Field(
        default=Decimal(str(LOAN_MIN_AMOUNT)),
        ge=LOAN_MIN_AMOUNT,
        description=f"Loan principal in INR (min ₹{LOAN_MIN_AMOUNT})",
    )
    tenure_months: int = Field(
        default=_DEFAULT_TENURE,
        description=f"Tenure in months — allowed values: {_ALLOWED_TENURES}",
    )

    @field_validator("tenure_months")
    @classmethod
    def tenure_must_be_allowed(cls, v: int) -> int:
        if v not in _ALLOWED_TENURES:
            raise ValueError(f"tenure_months must be one of {_ALLOWED_TENURES}")
        return v


class LoanSimulateResponse(BaseModel):
    amount: str
    tenure_months: int
    interest_rate: str
    emi_amount: str
    total_payable: str


class LoanBookRequest(BaseModel):
    amount: Decimal = Field(
        default=Decimal(str(LOAN_MIN_AMOUNT)),
        ge=LOAN_MIN_AMOUNT,
        description=f"Loan principal in INR (min ₹{LOAN_MIN_AMOUNT})",
    )
    tenure_months: int = Field(
        default=_DEFAULT_TENURE,
        description=f"Tenure in months — allowed values: {_ALLOWED_TENURES}",
    )

    @field_validator("tenure_months")
    @classmethod
    def tenure_must_be_allowed(cls, v: int) -> int:
        if v not in _ALLOWED_TENURES:
            raise ValueError(f"tenure_months must be one of {_ALLOWED_TENURES}")
        return v


class LoanBookResponse(BaseModel):
    booking_id: str
    message: str


class LoanConfirmRequest(BaseModel):
    booking_id: str
    otp: str = Field(..., min_length=6, max_length=6)


class LoanItem(BaseModel):
    id: str
    principal_amount: str
    emi_amount: str
    outstanding_amount: str
    interest_rate: str
    tenure_months: int
    status: str
    created_at: str
    approved_at: Optional[str]


class LoanListResponse(BaseModel):
    loans: List[LoanItem]


class LoanPayInitiateResponse(BaseModel):
    pay_id: str
    emi_amount: str
    outstanding_amount: str
    message: str


class LoanPayConfirmRequest(BaseModel):
    pay_id: str
    otp: str = Field(..., min_length=6, max_length=6)


class LoanPayResponse(BaseModel):
    loan_id: str
    amount_paid: str
    outstanding_after: str
    loan_status: str
