"""Pydantic schemas for user-related APIs."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# Existing schemas (registration / profile display)
# ---------------------------------------------------------------------------

class AddressSchema(BaseModel):
    """Generic JSON address container."""

    line1: Optional[str] = None
    line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None


class UserRegisterRequest(BaseModel):
    """Payload for user registration."""

    full_name: str = Field(..., min_length=1, max_length=150)
    email: EmailStr
    phone: str = Field(..., min_length=6, max_length=20)
    password: str = Field(..., min_length=8, max_length=128)
    salary: Optional[Decimal] = None
    address: Optional[AddressSchema] = None


class UserResponse(BaseModel):
    """Shape of user data returned to clients."""

    id: str
    customer_id: str
    full_name: str
    email: EmailStr
    phone: str
    status: str

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Module 3: Dashboard, Account, Transactions, Profile
# ---------------------------------------------------------------------------

class DashboardUserInfo(BaseModel):
    full_name: str
    email: str
    phone: str


class DashboardAccountInfo(BaseModel):
    account_number_masked: str
    balance: str
    account_type: str
    currency: str
    status: str


class TransactionItem(BaseModel):
    id: str
    entry_type: str
    amount: str
    balance_after: str
    reference_type: Optional[str]
    description: Optional[str]
    created_at: str


class DashboardSummaryResponse(BaseModel):
    user: DashboardUserInfo
    account: DashboardAccountInfo
    recent_transactions: List[TransactionItem]


class AccountDetailsResponse(BaseModel):
    account_number: str
    account_type: str
    balance: str
    currency: str
    status: str
    created_at: str


class TransactionListResponse(BaseModel):
    total_records: int
    page: int
    limit: int
    transactions: List[TransactionItem]


class UpdateProfileRequest(BaseModel):
    address: Optional[str] = None
    phone: Optional[str] = Field(None, min_length=6, max_length=20)


class UpdateProfileResponse(BaseModel):
    success: bool
    message: str
