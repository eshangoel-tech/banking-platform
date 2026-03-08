"""Auth v1 routes (view layer)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.repository.session import get_db
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    VerifyEmailRequest,
    VerifyEmailResponse,
    VerifyLoginOTPRequest,
    VerifyLoginOTPResponse,
)
from app.common.responses import ok_response
from app.services.core.auth_service.service import AuthService

router = APIRouter()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

@router.post("/register")
async def register(
    request: Request,
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService()
    user_id = await service.register_user(
        db,
        full_name=payload.full_name,
        email=str(payload.email),
        phone=payload.phone,
        password=payload.password,
        salary=payload.salary,
    )
    data = RegisterResponse(user_id=user_id, status="INACTIVE").model_dump()
    return ok_response(request, "Registration successful. OTP sent for email verification.", data=data)


@router.post("/verify-email")
async def verify_email(
    request: Request,
    payload: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService()
    out = await service.verify_email(db, email=str(payload.email), otp=payload.otp)
    data = VerifyEmailResponse(**out).model_dump()
    return ok_response(request, "Email verified successfully.", data=data)


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@router.post("/login")
async def login(
    request: Request,
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService()
    await service.login_user(db, identifier=payload.identifier, password=payload.password)
    return ok_response(request, "Login OTP sent to registered email.")


@router.post("/verify-login-otp")
async def verify_login_otp(
    request: Request,
    payload: VerifyLoginOTPRequest,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService()
    out = await service.verify_login_otp(
        db,
        identifier=payload.identifier,
        otp=payload.otp,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    data = VerifyLoginOTPResponse(**out).model_dump()
    return ok_response(request, "Login successful.", data=data)


# ---------------------------------------------------------------------------
# Password management
# ---------------------------------------------------------------------------

@router.post("/forgot-password")
async def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService()
    await service.forgot_password(db, email=str(payload.email))
    return ok_response(request, "If that email is registered, a reset link has been sent.")


@router.post("/reset-password")
async def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService()
    await service.reset_password(db, token=payload.token, new_password=payload.new_password)
    return ok_response(request, "Password reset successfully. Please log in with your new password.")
