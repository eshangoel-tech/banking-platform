"""Pydantic schemas for user-related APIs."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional

from pydantic import BaseModel, EmailStr, Field


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

