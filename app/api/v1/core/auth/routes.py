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
from app.services.core.auth_service.service import AuthService

router = APIRouter()


def _request_id(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    return str(rid) if rid else ""


def _ok(request: Request, message: str, data: dict | None = None) -> dict:
    return {
        "success": True,
        "message": message,
        "data": data,
        "request_id": _request_id(request),
    }


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
    )
    data = RegisterResponse(user_id=user_id, status="INACTIVE").model_dump()
    return _ok(request, "Registration successful. OTP sent for email verification.", data=data)


@router.post("/verify-email")
async def verify_email(
    request: Request,
    payload: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService()
    out = await service.verify_email(db, email=str(payload.email), otp=payload.otp)
    data = VerifyEmailResponse(**out).model_dump()
    return _ok(request, "Email verified successfully.", data=data)


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
    return _ok(request, "Login OTP sent to registered email.")


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
    return _ok(request, "Login successful.", data=data)


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
    return _ok(request, "If that email is registered, a reset link has been sent.")


@router.post("/reset-password")
async def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService()
    await service.reset_password(db, token=payload.token, new_password=payload.new_password)
    return _ok(request, "Password reset successfully. Please log in with your new password.")
