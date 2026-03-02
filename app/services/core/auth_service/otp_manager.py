"""Re-export from canonical location. Import from app.common.utils.otp instead."""
from app.common.utils.otp import (  # noqa: F401
    generate_otp,
    hash_otp,
    send_otp_email,
    verify_otp_hash,
)
