"""Re-export from canonical location. Import from app.common.utils.exceptions instead."""
from app.common.utils.exceptions import (  # noqa: F401
    AppException,
    account_locked,
    forbidden,
    invalid_credentials,
    invalid_otp,
    max_otp_attempts,
    not_found,
    otp_expired,
    token_expired,
    token_invalid,
    user_already_exists,
    user_not_found,
)
