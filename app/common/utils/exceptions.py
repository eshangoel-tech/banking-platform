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


# ---------------------------------------------------------------------------
# Transfer
# ---------------------------------------------------------------------------

def insufficient_balance(message: str = "Insufficient balance to complete the transfer") -> AppException:
    return AppException(code="INSUFFICIENT_BALANCE", message=message, http_status=422)


def self_transfer_not_allowed(message: str = "Cannot transfer to your own account") -> AppException:
    return AppException(code="SELF_TRANSFER_NOT_ALLOWED", message=message, http_status=400)


def account_not_active(message: str = "Account is not active") -> AppException:
    return AppException(code="ACCOUNT_NOT_ACTIVE", message=message, http_status=400)


def transfer_not_found(message: str = "Transfer not found") -> AppException:
    return AppException(code="TRANSFER_NOT_FOUND", message=message, http_status=404)


def transfer_already_completed(message: str = "Transfer has already been processed") -> AppException:
    return AppException(code="TRANSFER_ALREADY_COMPLETED", message=message, http_status=409)


# ---------------------------------------------------------------------------
# Wallet / Add-money
# ---------------------------------------------------------------------------

def payment_limit_exceeded(message: str = "Amount exceeds the maximum allowed limit") -> AppException:
    return AppException(code="PAYMENT_LIMIT_EXCEEDED", message=message, http_status=400)


def topup_not_found(message: str = "Top-up request not found or has expired") -> AppException:
    return AppException(code="TOPUP_NOT_FOUND", message=message, http_status=404)


# ---------------------------------------------------------------------------
# Loans
# ---------------------------------------------------------------------------

def loan_not_eligible(message: str = "You are not eligible for a loan") -> AppException:
    return AppException(code="LOAN_NOT_ELIGIBLE", message=message, http_status=400)


def loan_not_found(message: str = "Loan not found") -> AppException:
    return AppException(code="LOAN_NOT_FOUND", message=message, http_status=404)


def loan_not_active(message: str = "Loan is not active and cannot accept payments") -> AppException:
    return AppException(code="LOAN_NOT_ACTIVE", message=message, http_status=400)


def loan_booking_expired(
    message: str = "Loan booking has expired. Please start a new booking.",
) -> AppException:
    return AppException(code="LOAN_BOOKING_EXPIRED", message=message, http_status=410)


# ---------------------------------------------------------------------------
# AI Assistant
# ---------------------------------------------------------------------------

def chat_session_not_found(
    message: str = "Chat session not found",
) -> AppException:
    return AppException(code="CHAT_SESSION_NOT_FOUND", message=message, http_status=404)


def chat_session_expired(
    message: str = "Chat session has expired. Please start a new session.",
) -> AppException:
    return AppException(code="CHAT_SESSION_EXPIRED", message=message, http_status=410)


def chat_session_closed(
    message: str = "Chat session is already closed",
) -> AppException:
    return AppException(code="CHAT_SESSION_CLOSED", message=message, http_status=409)
