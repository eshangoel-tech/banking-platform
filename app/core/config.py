"""Application configuration — Razorpay and other third-party settings."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Razorpay (test-mode)
#
# How to obtain test keys:
#   1. Sign up at https://dashboard.razorpay.com
#   2. Switch to "Test Mode" (toggle in the top-left corner)
#   3. Go to Settings → API Keys → Generate Key
#   4. Copy Key ID  (rzp_test_XXXXXXXXXXXXXXXX) → RAZORPAY_KEY_ID
#      Copy Key Secret                           → RAZORPAY_KEY_SECRET
#
# How to configure the webhook:
#   1. In Razorpay Dashboard → Settings → Webhooks → Add new webhook
#   2. URL: https://<your-server>/api/v1/wallet/add-money/webhook
#      (Use ngrok for local dev: ngrok http 8000)
#   3. Tick the events: payment.captured, payment.failed
#   4. Set a webhook secret (any random string) → RAZORPAY_WEBHOOK_SECRET
#
# Test card for checkout:
#   Card number : 4111 1111 1111 1111
#   Expiry      : any future date
#   CVV         : any 3 digits
#   OTP         : 1234 (Razorpay test OTP)
#
# To simulate a payment programmatically (using test API):
#   POST https://api.razorpay.com/v1/payments/<payment_id>/capture
#   (Basic auth: KEY_ID:KEY_SECRET)
#   body: { "amount": <amount_in_paise>, "currency": "INR" }
# ---------------------------------------------------------------------------

RAZORPAY_KEY_ID: str = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET: str = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET: str = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

# Business rule: maximum single add-money transaction (INR)
ADD_MONEY_MAX_AMOUNT: int = 20_000
