"""Pydantic schemas for the loan module."""
from __future__ import annotations

from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


class LoanEligibilityResponse(BaseModel):
    max_eligible_amount: str
    interest_rate: str
    max_tenure_months: int


class LoanSimulateRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Loan principal in INR")
    tenure_months: int = Field(..., ge=1, le=24, description="Tenure in months (1–24)")


class LoanSimulateResponse(BaseModel):
    amount: str
    tenure_months: int
    interest_rate: str
    emi_amount: str
    total_payable: str


class LoanBookRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Loan principal in INR")
    tenure_months: int = Field(..., ge=1, le=24, description="Tenure in months (1–24)")


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


class LoanPayResponse(BaseModel):
    loan_id: str
    amount_paid: str
    outstanding_after: str
    loan_status: str
