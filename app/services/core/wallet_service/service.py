"""Wallet service: add-money initiation and Razorpay webhook processing."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.utils.exceptions import (
    account_not_active,
    invalid_webhook_signature,
    not_found,
    razorpay_order_failed,
)
from app.core.config import RAZORPAY_KEY_ID
from app.repository.core.wallet_repository.repository import WalletRepository
from app.repository.models.audit_log import AuditLog
from app.repository.models.user import User
from app.services.external.razorpay_client import razorpay_client

logger = logging.getLogger(__name__)

# Razorpay events we act on
_EVENT_CAPTURED = "payment.captured"
_EVENT_FAILED = "payment.failed"


class WalletService:
    def __init__(self, repo: WalletRepository | None = None) -> None:
        self.repo = repo or WalletRepository()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _audit(
        self,
        *,
        user_id: Optional[UUID],
        session_id: Optional[UUID],
        event_type: str,
        metadata: dict,
    ) -> AuditLog:
        return AuditLog(
            user_id=user_id,
            session_id=session_id,
            event_type=event_type,
            event_metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Step 1: initiate add-money
    # ------------------------------------------------------------------

    async def initiate_add_money(
        self,
        db: AsyncSession,
        *,
        user: User,
        session_id: UUID,
        amount: Decimal,
    ) -> dict:
        """
        Create a Razorpay order and persist a PaymentOrder record.

        Returns the data the frontend needs to open Razorpay Checkout:
          order_id, razorpay_key_id, amount, currency.
        """
        # -- Fetch account
        account = await self.repo.get_account_by_user_id(db, user.id)
        if not account:
            raise not_found("Account")
        if account.status != "ACTIVE":
            raise account_not_active()

        # -- Create Razorpay order (amount in paise, 1 INR = 100 paise)
        receipt = str(uuid.uuid4())
        amount_paise = int(amount * 100)

        try:
            rz_order = await razorpay_client.create_order(
                amount_paise=amount_paise,
                currency="INR",
                receipt=receipt,
            )
        except Exception:
            logger.exception(
                "Razorpay order creation failed",
                extra={"user_id": str(user.id), "amount": str(amount)},
            )
            raise razorpay_order_failed()

        razorpay_order_id: str = rz_order["id"]

        # -- Persist payment order + audit event in one transaction
        async with db.begin():
            payment_order = await self.repo.create_payment_order(
                db,
                user_id=user.id,
                account_id=account.id,
                razorpay_order_id=razorpay_order_id,
                amount_requested=amount,
                currency="INR",
            )
            db.add(
                self._audit(
                    user_id=user.id,
                    session_id=session_id,
                    event_type="ADD_MONEY_INITIATED",
                    metadata={
                        "payment_order_id": str(payment_order.id),
                        "razorpay_order_id": razorpay_order_id,
                        "amount": str(amount),
                    },
                )
            )

        return {
            "order_id": razorpay_order_id,
            "razorpay_key_id": RAZORPAY_KEY_ID,
            "amount": str(amount),
            "currency": "INR",
        }

    # ------------------------------------------------------------------
    # Step 2: webhook handler
    # ------------------------------------------------------------------

    async def process_webhook(
        self,
        db: AsyncSession,
        *,
        body: bytes,
        signature: str,
    ) -> None:
        """
        Verify and process an incoming Razorpay webhook.

        Security:
        - Signature is verified before any DB access.
        - Idempotency: already-SUCCESS orders are silently ignored.
        - Amount is taken from the signed webhook payload (never from caller).
        - SELECT FOR UPDATE prevents duplicate credits under concurrent delivery.

        Raises AppException(400) on invalid signature.
        All other errors are logged but do not raise (webhook must ack quickly).
        """
        # -- 1. Signature verification (gate everything behind this)
        if not razorpay_client.verify_webhook_signature(body, signature):
            raise invalid_webhook_signature()

        # -- 2. Parse payload
        try:
            event = json.loads(body)
        except json.JSONDecodeError:
            logger.error("Webhook body is not valid JSON")
            return

        event_type: str = event.get("event", "")
        logger.info("Razorpay webhook received", extra={"event": event_type})

        # -- 3. Only handle capture and failure events
        if event_type not in (_EVENT_CAPTURED, _EVENT_FAILED):
            return  # other events (e.g. order.paid, refund.*) — silently ack

        try:
            payment_entity: dict = event["payload"]["payment"]["entity"]
            razorpay_order_id: str = payment_entity["order_id"]
            amount_paise: int = int(payment_entity.get("amount", 0))
        except (KeyError, TypeError, ValueError):
            logger.exception("Malformed webhook payload", extra={"event": event_type})
            return

        amount_inr = Decimal(amount_paise) / Decimal(100)

        # -- 4. Load payment order
        payment_order = await self.repo.get_payment_order_by_razorpay_id(
            db, razorpay_order_id
        )
        if payment_order is None:
            # Unknown order — not created by us; silently ack
            logger.warning(
                "Webhook for unknown razorpay_order_id",
                extra={"razorpay_order_id": razorpay_order_id},
            )
            return

        # -- 5. Idempotency guard
        if payment_order.status == "SUCCESS":
            logger.info(
                "Duplicate webhook ignored (already SUCCESS)",
                extra={"razorpay_order_id": razorpay_order_id},
            )
            return

        user_id: Optional[UUID] = payment_order.user_id
        account_id: Optional[UUID] = payment_order.account_id

        # -- 6a. Payment FAILED
        if event_type == _EVENT_FAILED:
            async with db.begin():
                await self.repo.update_payment_status(
                    db, payment_order.id, "FAILED"
                )
                db.add(
                    self._audit(
                        user_id=user_id,
                        session_id=None,
                        event_type="ADD_MONEY_FAILED",
                        metadata={
                            "razorpay_order_id": razorpay_order_id,
                            "amount": str(amount_inr),
                        },
                    )
                )
            return

        # -- 6b. Payment CAPTURED — atomic credit
        if account_id is None:
            logger.error(
                "PaymentOrder has no account_id — cannot credit",
                extra={"razorpay_order_id": razorpay_order_id},
            )
            return

        try:
            async with db.begin():
                # Lock account row for the duration of this transaction
                account = await self.repo.get_account_for_update(db, account_id)
                if account is None:
                    logger.error(
                        "Account not found for credit",
                        extra={"account_id": str(account_id)},
                    )
                    return

                # Atomic credit with RETURNING to get exact new balance
                new_balance = await self.repo.credit_account_balance(
                    db, account_id, amount_inr
                )

                # Ledger entry
                await self.repo.create_ledger_entry(
                    db,
                    account_id=account_id,
                    entry_type="CREDIT",
                    amount=amount_inr,
                    balance_after=new_balance,
                    reference_type="ADD_MONEY",
                    reference_id=payment_order.id,
                    description=f"Add money via Razorpay order {razorpay_order_id}",
                )

                # Finalise payment order
                await self.repo.update_payment_status(
                    db,
                    payment_order.id,
                    "SUCCESS",
                    amount_paid=amount_inr,
                    completed_at=datetime.utcnow(),
                )

                db.add(
                    self._audit(
                        user_id=user_id,
                        session_id=None,
                        event_type="ADD_MONEY_SUCCESS",
                        metadata={
                            "razorpay_order_id": razorpay_order_id,
                            "amount_credited": str(amount_inr),
                            "balance_after": str(new_balance),
                        },
                    )
                )

        except Exception:
            logger.exception(
                "Error processing payment.captured webhook",
                extra={"razorpay_order_id": razorpay_order_id},
            )
            # Do not re-raise — webhook must always return 200 after signature
            # verification to prevent Razorpay retry storms.
            # The failure is fully logged; ops can replay via Razorpay dashboard.
