"""Application-wide exception base class and factory helpers."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AppException(Exception):
    """Structured exception that maps to an HTTP error response."""
    code: str
    message: str
    http_status: int = 400


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def user_already_exists(message: str = "User already exists") -> AppException:
    return AppException(code="USER_ALREADY_EXISTS", message=message, http_status=409)


def user_not_found(message: str = "User not found") -> AppException:
    return AppException(code="USER_NOT_FOUND", message=message, http_status=404)


def invalid_credentials(message: str = "Invalid email or password") -> AppException:
    return AppException(code="INVALID_CREDENTIALS", message=message, http_status=401)


def account_locked(message: str = "Account is locked due to too many failed attempts") -> AppException:
    return AppException(code="ACCOUNT_LOCKED", message=message, http_status=403)


def user_blocked(message: str = "Account is temporarily blocked. Try again later.") -> AppException:
    return AppException(code="USER_BLOCKED", message=message, http_status=403)


# ---------------------------------------------------------------------------
# OTP
# ---------------------------------------------------------------------------

def invalid_otp(message: str = "Invalid OTP") -> AppException:
    return AppException(code="INVALID_OTP", message=message, http_status=400)


def otp_expired(message: str = "OTP has expired") -> AppException:
    return AppException(code="OTP_EXPIRED", message=message, http_status=400)


def max_otp_attempts(message: str = "Maximum OTP attempts exceeded") -> AppException:
    return AppException(code="MAX_OTP_ATTEMPTS", message=message, http_status=429)


# ---------------------------------------------------------------------------
# Token
# ---------------------------------------------------------------------------

def token_expired(message: str = "Token has expired") -> AppException:
    return AppException(code="TOKEN_EXPIRED", message=message, http_status=401)


def token_invalid(message: str = "Invalid token") -> AppException:
    return AppException(code="TOKEN_INVALID", message=message, http_status=401)


# ---------------------------------------------------------------------------
# Generic
# ---------------------------------------------------------------------------

def forbidden(message: str = "You do not have permission to perform this action") -> AppException:
    return AppException(code="FORBIDDEN", message=message, http_status=403)


def not_found(resource: str = "Resource") -> AppException:
    return AppException(code="NOT_FOUND", message=f"{resource} not found", http_status=404)
