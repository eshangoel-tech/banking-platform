"""
Razorpay SDK wrapper — thin async-friendly layer over the synchronous SDK.

The official razorpay-python SDK is synchronous.  All network calls are
dispatched via asyncio.to_thread() so they don't block the FastAPI event loop.

Usage (test mode)
-----------------
1.  Install:  pip install razorpay
2.  Set env vars:
        RAZORPAY_KEY_ID      = rzp_test_XXXXXXXXXXXXXXXX
        RAZORPAY_KEY_SECRET  = <secret from dashboard>
        RAZORPAY_WEBHOOK_SECRET = <webhook secret you set in dashboard>

Test card for Razorpay checkout:
    Number  : 4111 1111 1111 1111
    Expiry  : any future MM/YY
    CVV     : any 3 digits
    OTP     : 1234

To simulate a captured payment via cURL:
    curl -u rzp_test_KEY:SECRET \\
         -X POST https://api.razorpay.com/v1/payments/<pay_id>/capture \\
         -d amount=<paise> -d currency=INR
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
from typing import Any, Dict

import razorpay

from app.core.config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, RAZORPAY_WEBHOOK_SECRET

logger = logging.getLogger(__name__)


class RazorpayClient:
    """Thin async wrapper around the Razorpay Python SDK."""

    def __init__(self) -> None:
        self._client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    async def create_order(
        self,
        *,
        amount_paise: int,
        currency: str = "INR",
        receipt: str,
    ) -> Dict[str, Any]:
        """
        Create a Razorpay order.

        Args:
            amount_paise: Amount in paise (1 INR = 100 paise).
            currency:     ISO 4217 currency code (default INR).
            receipt:      Internal reference string (e.g. payment_order UUID).

        Returns:
            Razorpay order dict containing at minimum:
              - id         (razorpay_order_id)
              - amount     (paise)
              - currency
              - receipt
              - status     ("created")
        """
        payload = {
            "amount": amount_paise,
            "currency": currency,
            "receipt": receipt,
            "payment_capture": 1,  # auto-capture on payment success
        }

        def _create() -> Dict[str, Any]:
            return self._client.order.create(payload)

        return await asyncio.to_thread(_create)

    # ------------------------------------------------------------------
    # Webhook verification
    # ------------------------------------------------------------------

    def verify_webhook_signature(self, body: bytes, signature: str) -> bool:
        """
        Verify an incoming Razorpay webhook via HMAC-SHA256.

        Razorpay signs the raw request body with RAZORPAY_WEBHOOK_SECRET.
        The resulting hex digest is sent in the `x-razorpay-signature` header.

        Returns True if valid, False otherwise.
        Never raises — invalid signatures always return False.
        """
        if not RAZORPAY_WEBHOOK_SECRET:
            logger.error("RAZORPAY_WEBHOOK_SECRET is not configured")
            return False

        try:
            expected = hmac.new(
                RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
                body,
                digestmod=hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(expected, signature)
        except Exception:
            logger.exception("Webhook signature verification error")
            return False


# Module-level singleton — one client for the process lifetime
razorpay_client = RazorpayClient()
