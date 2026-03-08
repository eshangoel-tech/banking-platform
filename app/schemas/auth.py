"""Pydantic schemas for auth module (v1)."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=150)
    email: EmailStr
    phone: str = Field(..., min_length=6, max_length=20)
    password: str = Field(..., min_length=8, max_length=128)
    salary: Optional[Decimal] = Field(
        None, ge=0, description="Monthly salary in INR (used for loan eligibility)"
    )


class RegisterResponse(BaseModel):
    user_id: str
    status: str


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6)


class VerifyEmailResponse(BaseModel):
    user_id: str
    status: str
    account_id: str
    account_number: str


class StandardResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    request_id: str



# ---------------------------------------------------------------------------
# Login (step 1 — password check)
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    identifier: str = Field(..., min_length=1, max_length=150, description="Email, phone, or customer_id")
    password: str = Field(..., min_length=1, max_length=128)


# ---------------------------------------------------------------------------
# Login (step 2 — OTP verification)
# ---------------------------------------------------------------------------

class VerifyLoginOTPRequest(BaseModel):
    identifier: str = Field(..., min_length=1, max_length=150)
    otp: str = Field(..., min_length=6, max_length=6)


class VerifyLoginOTPResponse(BaseModel):
    access_token: str
    token_type: str
    session_id: str


# ---------------------------------------------------------------------------
# Forgot password
# ---------------------------------------------------------------------------

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


# ---------------------------------------------------------------------------
# Reset password
# ---------------------------------------------------------------------------

class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)
