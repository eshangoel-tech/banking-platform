"""OTP generation, hashing, and SMTP email delivery."""
from __future__ import annotations

import hashlib
import logging
import os
import secrets
from decimal import Decimal
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib
from dotenv import load_dotenv

load_dotenv()

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
# Shared disclaimer — appended to every email
# ---------------------------------------------------------------------------
_DEMO_DISCLAIMER_HTML = """
  <hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
  <div style="background:#fff8e1;border-left:4px solid #f59e0b;padding:10px 14px;
              border-radius:4px;margin-bottom:12px;">
    <p style="margin:0;color:#92400e;font-size:12px;font-weight:600;">
      &#x26A0;&#xFE0F; This is a student / demo project
    </p>
    <p style="margin:4px 0 0;color:#92400e;font-size:11px;line-height:1.5;">
      ADX Bank is <strong>not a real bank</strong>. All accounts, balances, and
      transactions are entirely simulated for educational purposes.
      No real money is involved.
    </p>
  </div>
  <p style="color:#aaa;font-size:11px;text-align:center;">
    &copy; ADX Bank Demo Project. Built with FastAPI &amp; PostgreSQL.
  </p>
"""

_DEMO_DISCLAIMER_PLAIN = (
    "\n\n---\n"
    "NOTE: ADX Bank is a demo/student project and NOT a real bank.\n"
    "All accounts and transactions are simulated. No real money is involved.\n"
)


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
# SMTP helpers
# ---------------------------------------------------------------------------

async def _send(msg: MIMEMultipart) -> None:
    """Send a pre-built MIME message via SMTP STARTTLS."""
    await aiosmtplib.send(
        msg,
        hostname=SMTP_HOST,
        port=SMTP_PORT,
        username=SMTP_USER or None,
        password=SMTP_PASSWORD or None,
        start_tls=True,
    )


# ---------------------------------------------------------------------------
# OTP emails
# ---------------------------------------------------------------------------

_OTP_SUBJECTS: dict[str, str] = {
    "EMAIL_VERIFY": "ADX Bank — Verify your email",
    "PASSWORD_RESET": "ADX Bank — Password reset OTP",
    "LOGIN": "ADX Bank — Login OTP",
    "TRANSFER": "ADX Bank — Transfer OTP",
    "ADD_MONEY": "ADX Bank — Add Money OTP",
    "LOAN_BOOK": "ADX Bank — Loan confirmation OTP",
    "LOAN_PAY": "ADX Bank — EMI payment OTP",
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
        + _DEMO_DISCLAIMER_PLAIN
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
          {_DEMO_DISCLAIMER_HTML}
        </div>
      </body>
    </html>
    """

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))
    return msg


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
    await _send(msg)
    logger.info("OTP email sent", extra={"to": to_email, "otp_type": otp_type})


async def send_reset_password_email(to_email: str, reset_token: str) -> None:
    """
    Send a password-reset link to the given email address.

    The raw token is embedded in the link — never log it.
    Raises:
        aiosmtplib.SMTPException: on delivery failure (caller decides how to handle).
    """
    reset_url = f"{FRONTEND_URL}/reset-password?token={reset_token}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "ADX Bank — Reset your password"
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
    msg["To"] = to_email

    plain = (
        f"You requested a password reset for your ADX Bank account.\n\n"
        f"Click the link below to set a new password (expires in 15 minutes):\n"
        f"{reset_url}\n\n"
        "If you did not request this, please ignore this email."
        + _DEMO_DISCLAIMER_PLAIN
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
            If the button doesn't work, copy and paste this link:<br>
            <a href="{reset_url}" style="color:#1a3c6e;word-break:break-all;">{reset_url}</a>
          </p>
          {_DEMO_DISCLAIMER_HTML}
        </div>
      </body>
    </html>
    """

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))
    await _send(msg)
    logger.info("Reset password email sent", extra={"to": to_email})


# ---------------------------------------------------------------------------
# Welcome email — sent after email verification + joining bonus
# ---------------------------------------------------------------------------

async def send_welcome_email(
    to_email: str,
    full_name: str,
    account_number: str,
    bonus_amount: Decimal,
) -> None:
    """
    Welcome email confirming account activation and joining bonus.
    Raised by Celery task on_email_verified_task (best-effort).
    """
    masked = f"XXXX XXXX {account_number[-4:]}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "ADX Bank — Welcome! Your ₹500 joining bonus is here"
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
    msg["To"] = to_email

    plain = (
        f"Hi {full_name},\n\n"
        f"Welcome to ADX Bank! Your account is now active.\n\n"
        f"Account number : {masked}\n"
        f"Joining bonus  : ₹{bonus_amount} credited instantly!\n\n"
        "Log in to explore transfers, wallet top-ups, and loan features.\n\n"
        "— ADX Bank Team"
        + _DEMO_DISCLAIMER_PLAIN
    )

    html = f"""
    <html>
      <body style="font-family:Arial,sans-serif;background:#f5f5f5;padding:24px;margin:0;">
        <div style="max-width:520px;margin:auto;background:#fff;border-radius:10px;
                    padding:36px;box-shadow:0 2px 8px rgba(0,0,0,0.07);">
          <h2 style="color:#1a3c6e;margin:0 0 4px;">ADX Bank</h2>
          <p style="color:#555;margin-top:0;">Welcome to the family!</p>
          <hr style="border:none;border-top:1px solid #eee;margin:16px 0;">
          <p style="color:#333;font-size:15px;">Hi <strong>{full_name}</strong>,</p>
          <p style="color:#333;">
            Your ADX Bank account is now <strong>active</strong>.
          </p>
          <table style="width:100%;border-collapse:collapse;margin:16px 0;">
            <tr>
              <td style="padding:8px 12px;background:#f0f4ff;border-radius:6px 0 0 6px;
                          color:#555;font-size:13px;width:45%;">Account Number</td>
              <td style="padding:8px 12px;background:#f0f4ff;border-radius:0 6px 6px 0;
                          color:#1a3c6e;font-weight:700;">{masked}</td>
            </tr>
          </table>
          <div style="background:#ecfdf5;border:2px solid #10b981;border-radius:8px;
                      padding:16px;margin:20px 0;text-align:center;">
            <p style="margin:0;font-size:12px;color:#065f46;">Joining Bonus Credited</p>
            <p style="margin:4px 0 0;font-size:36px;font-weight:800;color:#065f46;">
              &#x20B9;{bonus_amount}
            </p>
          </div>
          <p style="color:#555;font-size:13px;line-height:1.6;">
            Explore transfers, wallet top-ups, and loans — all secured with OTP.
          </p>
          {_DEMO_DISCLAIMER_HTML}
        </div>
      </body>
    </html>
    """

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))
    await _send(msg)
    logger.info("Welcome email sent", extra={"to": to_email})


# ---------------------------------------------------------------------------
# Salary credit email — sent ~2 minutes after verification (Celery task)
# ---------------------------------------------------------------------------

async def send_salary_credit_email(
    to_email: str,
    full_name: str,
    salary_amount: Decimal,
) -> None:
    """
    Congratulations email for the simulated monthly salary credit.
    Raised by Celery task credit_monthly_salary_task (best-effort).
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "ADX Bank — Your monthly salary has been credited!"
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
    msg["To"] = to_email

    plain = (
        f"Hi {full_name},\n\n"
        f"Congratulations! Your simulated monthly salary of ₹{salary_amount} "
        f"has been credited to your ADX Bank account.\n\n"
        "Check your updated balance on the dashboard.\n\n"
        "Happy banking!\n— ADX Bank Team"
        + _DEMO_DISCLAIMER_PLAIN
    )

    html = f"""
    <html>
      <body style="font-family:Arial,sans-serif;background:#f5f5f5;padding:24px;margin:0;">
        <div style="max-width:520px;margin:auto;background:#fff;border-radius:10px;
                    padding:36px;box-shadow:0 2px 8px rgba(0,0,0,0.07);">
          <h2 style="color:#1a3c6e;margin:0 0 4px;">ADX Bank</h2>
          <p style="color:#555;margin-top:0;">Monthly Salary Credit</p>
          <hr style="border:none;border-top:1px solid #eee;margin:16px 0;">
          <p style="color:#333;font-size:15px;">Hi <strong>{full_name}</strong>! &#x1F389;</p>
          <p style="color:#333;">Your simulated monthly salary has arrived.</p>
          <div style="background:#eff6ff;border:2px solid #3b82f6;border-radius:8px;
                      padding:20px;margin:20px 0;text-align:center;">
            <p style="margin:0;font-size:12px;color:#1e40af;">Salary Credited</p>
            <p style="margin:4px 0 0;font-size:36px;font-weight:800;color:#1e40af;">
              &#x20B9;{salary_amount}
            </p>
            <p style="margin:4px 0 0;font-size:11px;color:#1e40af;">
              Simulated credit — ADX Bank demo
            </p>
          </div>
          <p style="color:#555;font-size:13px;line-height:1.6;">
            Your updated balance is visible on the dashboard.
            Try sending money, topping up your wallet, or applying for a loan!
          </p>
          {_DEMO_DISCLAIMER_HTML}
        </div>
      </body>
    </html>
    """

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))
    await _send(msg)
    logger.info("Salary credit email sent", extra={"to": to_email})
