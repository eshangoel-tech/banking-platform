"""Load ADX Bank business rules from bank_rules.json and expose flat constants."""
from __future__ import annotations

import json
from pathlib import Path

_CONFIG_DIR = Path(__file__).parent
_rules: dict = json.loads((_CONFIG_DIR / "bank_rules.json").read_text())

# ---------------------------------------------------------------------------
# OTP
# ---------------------------------------------------------------------------
OTP_MAX_ATTEMPTS: int = _rules["otp"]["max_attempts"]
OTP_EXPIRY_MINUTES: int = _rules["otp"]["expiry_minutes"]

# ---------------------------------------------------------------------------
# Auth / Session
# ---------------------------------------------------------------------------
MAX_LOGIN_ATTEMPTS: int = _rules["auth"]["max_login_attempts"]
ACCOUNT_BLOCK_DURATION_SECONDS: int = _rules["auth"]["account_block_duration_seconds"]
JWT_EXPIRY_MINUTES: int = _rules["auth"]["jwt_expiry_minutes"]
PASSWORD_RESET_TOKEN_EXPIRY_MINUTES: int = _rules["auth"]["password_reset_token_expiry_minutes"]

# ---------------------------------------------------------------------------
# Wallet / Add-money
# ---------------------------------------------------------------------------
ADD_MONEY_MAX_AMOUNT: int = _rules["wallet"]["add_money_max_amount_per_transaction_inr"]
ADD_MONEY_OTP_TTL_SECONDS: int = _rules["wallet"]["add_money_otp_ttl_seconds"]
ADD_MONEY_REDIS_TTL_SECONDS: int = _rules["wallet"]["add_money_redis_ttl_seconds"]

# ---------------------------------------------------------------------------
# Transfer
# ---------------------------------------------------------------------------
TRANSFER_OTP_TTL_SECONDS: int = _rules["transfer"]["otp_ttl_seconds"]
TRANSFER_MIN_AMOUNT: int = _rules["transfer"]["min_amount_inr"]

# ---------------------------------------------------------------------------
# Loans
# ---------------------------------------------------------------------------
LOAN_INTEREST_RATE_PA: float = _rules["loan"]["interest_rate_pa_decimal"]
LOAN_MIN_AMOUNT: int = _rules["loan"]["min_loan_amount_inr"]
LOAN_ALLOWED_TENURES: list[int] = _rules["loan"]["allowed_tenures_months"]
LOAN_MAX_TENURE_MONTHS: int = _rules["loan"]["max_tenure_months"]
LOAN_MIN_SALARY: int = _rules["loan"]["min_monthly_salary_for_eligibility_inr"]
LOAN_PROCESSING_FEE_PERCENT: int = _rules["loan"]["loan_processing_fee_percent"]
LOAN_BOOKING_REDIS_TTL_SECONDS: int = _rules["loan"]["booking_redis_ttl_seconds"]
LOAN_OTP_TTL_SECONDS: int = _rules["loan"]["otp_ttl_seconds"]

# ---------------------------------------------------------------------------
# Account on-boarding
# ---------------------------------------------------------------------------
JOINING_BONUS_AMOUNT: int = _rules["account"]["joining_bonus_amount_inr"]
SALARY_CREDIT_DELAY_SECONDS: int = _rules["account"]["salary_credit_delay_seconds"]
DEFAULT_ACCOUNT_TYPE: str = _rules["account"]["default_account_type"]
DEFAULT_ACCOUNT_CURRENCY: str = _rules["account"]["default_currency"]

# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------
MAX_PAGE_SIZE: int = _rules["pagination"]["max_page_size"]
DEFAULT_PAGE_SIZE: int = _rules["pagination"]["default_page_size"]
