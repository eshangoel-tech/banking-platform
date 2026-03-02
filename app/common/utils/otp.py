"""OTP generation, hashing, and SMTP email delivery."""
from __future__ import annotations

import hashlib
import logging
import os
import secrets
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SMTP configuration (loaded from env)
# ---------------------------------------------------------------------------
SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER: str = os.getenv("SMTP_USER", "")
SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "noreply@adxbank.com")
SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "ADX Bank")
FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

# ---------------------------------------------------------------------------
# OTP core utilities
# ---------------------------------------------------------------------------

def generate_otp() -> str:
    """Generate a cryptographically secure 6-digit OTP."""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(otp: str) -> str:
    """Return the SHA-256 hex digest of the OTP (plaintext never stored)."""
    return hashlib.sha256(otp.encode("utf-8")).hexdigest()


def verify_otp_hash(otp: str, stored_hash: str) -> bool:
    """Verify a raw OTP string against its stored SHA-256 hash."""
    return hash_otp(otp) == stored_hash


# ---------------------------------------------------------------------------
# SMTP email delivery
# ---------------------------------------------------------------------------

_OTP_SUBJECTS: dict[str, str] = {
    "EMAIL_VERIFY": "Verify your ADX Bank email",
    "PASSWORD_RESET": "ADX Bank password reset OTP",
    "LOGIN": "ADX Bank login OTP",
}


def _build_otp_email(to_email: str, otp: str, otp_type: str) -> MIMEMultipart:
    """Construct a plain-text + HTML MIME email carrying the OTP."""
    subject = _OTP_SUBJECTS.get(otp_type, "Your ADX Bank OTP")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
    msg["To"] = to_email

    plain = (
        f"Your ADX Bank OTP is: {otp}\n\n"
        "This OTP expires in 5 minutes. Do not share it with anyone.\n"
        "ADX Bank will never ask you for this code."
    )

    html = f"""
    <html>
      <body style="font-family:Arial,sans-serif;background:#f5f5f5;padding:24px;margin:0;">
        <div style="max-width:480px;margin:auto;background:#fff;border-radius:10px;
                    padding:36px;box-shadow:0 2px 8px rgba(0,0,0,0.07);">
          <h2 style="color:#1a3c6e;margin:0 0 4px;">ADX Bank</h2>
          <p style="color:#555;margin-top:0;">Verification Code</p>
          <hr style="border:none;border-top:1px solid #eee;margin:16px 0;">
          <p style="color:#333;">Use the one-time password below to complete your action:</p>
          <div style="font-size:40px;font-weight:700;letter-spacing:10px;color:#1a3c6e;
                      text-align:center;padding:20px 0;background:#f0f4ff;
                      border-radius:8px;margin:16px 0;">{otp}</div>
          <p style="color:#666;font-size:13px;line-height:1.6;">
            This OTP is valid for <strong>5 minutes</strong> and can only be used once.<br>
            <strong>Never share this code</strong> — ADX Bank will never ask for your OTP.
          </p>
          <hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
          <p style="color:#aaa;font-size:11px;text-align:center;">
            &copy; ADX Bank. If you did not request this code, please ignore this email.
          </p>
        </div>
      </body>
    </html>
    """

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))
    return msg


async def send_reset_password_email(to_email: str, reset_token: str) -> None:
    """
    Send a password-reset link to the given email address.

    The raw token is embedded in the link — never log it.
    Raises:
        aiosmtplib.SMTPException: on delivery failure (caller decides how to handle).
    """
    reset_url = f"{FRONTEND_URL}/reset-password?token={reset_token}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Reset your ADX Bank password"
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
    msg["To"] = to_email

    plain = (
        f"You requested a password reset for your ADX Bank account.\n\n"
        f"Click the link below to set a new password (expires in 15 minutes):\n"
        f"{reset_url}\n\n"
        "If you did not request this, please ignore this email."
    )

    html = f"""
    <html>
      <body style="font-family:Arial,sans-serif;background:#f5f5f5;padding:24px;margin:0;">
        <div style="max-width:480px;margin:auto;background:#fff;border-radius:10px;
                    padding:36px;box-shadow:0 2px 8px rgba(0,0,0,0.07);">
          <h2 style="color:#1a3c6e;margin:0 0 4px;">ADX Bank</h2>
          <p style="color:#555;margin-top:0;">Password Reset Request</p>
          <hr style="border:none;border-top:1px solid #eee;margin:16px 0;">
          <p style="color:#333;">
            We received a request to reset your password. Click the button below to proceed.
            This link expires in <strong>15 minutes</strong>.
          </p>
          <div style="text-align:center;margin:28px 0;">
            <a href="{reset_url}"
               style="background:#1a3c6e;color:#fff;text-decoration:none;padding:14px 32px;
                      border-radius:6px;font-weight:bold;font-size:15px;display:inline-block;">
              Reset Password
            </a>
          </div>
          <p style="color:#666;font-size:12px;line-height:1.6;">
            If the button doesn't work, copy and paste this link into your browser:<br>
            <a href="{reset_url}" style="color:#1a3c6e;word-break:break-all;">{reset_url}</a>
          </p>
          <hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
          <p style="color:#aaa;font-size:11px;text-align:center;">
            If you did not request a password reset, please ignore this email.
            &copy; ADX Bank
          </p>
        </div>
      </body>
    </html>
    """

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    await aiosmtplib.send(
        msg,
        hostname=SMTP_HOST,
        port=SMTP_PORT,
        username=SMTP_USER or None,
        password=SMTP_PASSWORD or None,
        start_tls=True,
    )
    logger.info("Reset password email sent", extra={"to": to_email})


async def send_otp_email(
    to_email: str,
    otp: str,
    otp_type: str = "EMAIL_VERIFY",
) -> None:
    """
    Send an OTP to the given email address via SMTP (STARTTLS).

    Raises:
        aiosmtplib.SMTPException: on delivery failure (caller decides how to handle).
    """
    msg = _build_otp_email(to_email, otp, otp_type)
    await aiosmtplib.send(
        msg,
        hostname=SMTP_HOST,
        port=SMTP_PORT,
        username=SMTP_USER or None,
        password=SMTP_PASSWORD or None,
        start_tls=True,
    )
    logger.info("OTP email sent", extra={"to": to_email, "otp_type": otp_type})
