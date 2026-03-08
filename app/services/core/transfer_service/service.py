"""Transfer service: initiate and confirm internal money transfers."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.utils.exceptions import (
    account_not_active,
    insufficient_balance,
    invalid_otp,
    max_otp_attempts,
    not_found,
    otp_expired,
    self_transfer_not_allowed,
    transfer_already_completed,
    transfer_not_found,
)
from app.common.utils.otp import generate_otp, hash_otp, send_otp_email, verify_otp_hash
from app.repository.core.transfer_repository.repository import TransferRepository
from app.repository.models.audit_log import AuditLog
from app.repository.models.user import User

logger = logging.getLogger(__name__)

_OTP_TTL_MINUTES = 5


class TransferService:
    def __init__(self, repo: TransferRepository | None = None) -> None:
        self.repo = repo or TransferRepository()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _audit(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
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
    # Step 1: initiate
    # ------------------------------------------------------------------

    async def initiate_transfer(
        self,
        db: AsyncSession,
        *,
        user: User,
        session_id: UUID,
        receiver_account_number: str,
        amount: Decimal,
    ) -> dict:
        """
        Validate accounts, create a PENDING transfer, issue a TRANSFER OTP.

        Returns {'transfer_id': str}
        """
        # -- Fetch sender account
        sender_account = await self.repo.get_account_by_user_id(db, user.id)
        if not sender_account:
            raise not_found("Sender account")

        if sender_account.status != "ACTIVE":
            raise account_not_active("Your account is not active")

        # -- Fetch receiver account
        receiver_account = await self.repo.get_account_by_number(
            db, receiver_account_number
        )
        if not receiver_account:
            raise not_found("Receiver account")

        if receiver_account.status != "ACTIVE":
            raise account_not_active("Receiver account is not active")

        # -- Self-transfer guard
        if sender_account.id == receiver_account.id:
            raise self_transfer_not_allowed()

        # -- Balance check (soft — hard recheck happens inside the confirm transaction)
        if sender_account.balance < amount:
            raise insufficient_balance()

        # -- Create transfer + OTP atomically
        otp_plaintext = generate_otp()
        otp_hash_value = hash_otp(otp_plaintext)
        expires_at = datetime.utcnow() + timedelta(minutes=_OTP_TTL_MINUTES)

        transfer = await self.repo.create_transfer(
            db,
            sender_account_id=sender_account.id,
            receiver_account_id=receiver_account.id,
            amount=amount,
        )
        await self.repo.create_transfer_otp(
            db,
            user_id=user.id,
            otp_hash=otp_hash_value,
            expires_at=expires_at,
            transfer_id=transfer.id,
        )
        db.add(
            self._audit(
                user_id=user.id,
                session_id=session_id,
                event_type="TRANSFER_INITIATED",
                metadata={
                    "transfer_id": str(transfer.id),
                    "amount": str(amount),
                    "receiver_account_id": str(receiver_account.id),
                },
            )
        )
        await db.commit()

        # -- Send OTP email (best-effort)
        try:
            await send_otp_email(user.email, otp_plaintext, otp_type="TRANSFER")
        except Exception:
            logger.exception(
                "Failed to send transfer OTP",
                extra={"user_id": str(user.id), "transfer_id": str(transfer.id)},
            )

        return {"transfer_id": str(transfer.id)}

    # ------------------------------------------------------------------
    # Step 2: confirm
    # ------------------------------------------------------------------

    async def confirm_transfer(
        self,
        db: AsyncSession,
        *,
        user: User,
        session_id: UUID,
        transfer_id: UUID,
        otp: str,
    ) -> None:
        """
        Verify OTP, execute the atomic debit/credit, and mark transfer COMPLETED.
        Raises on any validation or balance failure (transaction is rolled back).
        """
        # -- Load transfer
        transfer = await self.repo.get_transfer_by_id(db, transfer_id)
        if transfer is None:
            raise transfer_not_found()

        # -- Ownership: sender account must belong to the authenticated user
        sender_account_check = await self.repo.get_account_by_user_id(db, user.id)
        if (
            sender_account_check is None
            or sender_account_check.id != transfer.sender_account_id
        ):
            raise transfer_not_found()  # don't reveal existence to wrong user

        # -- Status guard
        if transfer.status != "PENDING":
            raise transfer_already_completed()

        # -- Validate OTP
        now = datetime.utcnow()
        otp_row = await self.repo.get_valid_transfer_otp(
            db, user_id=user.id, transfer_id=transfer_id, now=now
        )
        if otp_row is None:
            raise otp_expired()

        if otp_row.attempts is not None and otp_row.attempts >= otp_row.max_attempts:
            raise max_otp_attempts()

        if not verify_otp_hash(otp, otp_row.otp_hash):
            otp_row = await self.repo.increment_otp_attempts(db, otp_row)
            if otp_row.attempts >= (otp_row.max_attempts or 3):
                # Also mark transfer FAILED when max OTP attempts exceeded
                await self.repo.update_transfer_status(
                    db, transfer_id, "FAILED"
                )
                db.add(
                    self._audit(
                        user_id=user.id,
                        session_id=session_id,
                        event_type="TRANSFER_FAILED",
                        metadata={
                            "transfer_id": str(transfer_id),
                            "reason": "max_otp_attempts",
                        },
                    )
                )
                await db.commit()
                raise max_otp_attempts()
            await db.commit()
            raise invalid_otp()

        # -- Atomic execution block (implicit transaction already open from reads above)
        # Lock sender row; recheck balance inside the transaction
        sender = await self.repo.get_account_for_update(
            db, transfer.sender_account_id
        )
        if sender is None:
            raise not_found("Sender account")

        if sender.balance < transfer.amount:
            await self.repo.update_transfer_status(db, transfer_id, "FAILED")
            db.add(
                self._audit(
                    user_id=user.id,
                    session_id=session_id,
                    event_type="TRANSFER_FAILED",
                    metadata={
                        "transfer_id": str(transfer_id),
                        "reason": "insufficient_balance",
                    },
                )
            )
            await db.commit()
            raise insufficient_balance()

        # Deduct from sender
        new_sender_balance = sender.balance - transfer.amount
        await self.repo.set_account_balance(
            db, transfer.sender_account_id, new_sender_balance
        )

        # Credit receiver (atomic UPDATE … RETURNING)
        new_receiver_balance = await self.repo.credit_account_balance(
            db, transfer.receiver_account_id, transfer.amount
        )

        # Ledger: DEBIT entry for sender
        await self.repo.create_ledger_entry(
            db,
            account_id=transfer.sender_account_id,
            entry_type="DEBIT",
            amount=transfer.amount,
            balance_after=new_sender_balance,
            reference_type="TRANSFER",
            reference_id=transfer.id,
            description=f"Transfer to account {transfer.receiver_account_id}",
        )

        # Ledger: CREDIT entry for receiver
        await self.repo.create_ledger_entry(
            db,
            account_id=transfer.receiver_account_id,
            entry_type="CREDIT",
            amount=transfer.amount,
            balance_after=new_receiver_balance,
            reference_type="TRANSFER",
            reference_id=transfer.id,
            description=f"Transfer from account {transfer.sender_account_id}",
        )

        # Finalise transfer and OTP
        await self.repo.update_transfer_status(
            db, transfer_id, "COMPLETED", completed_at=datetime.utcnow()
        )
        await self.repo.mark_otp_verified(db, otp_row.id)

        db.add(
            self._audit(
                user_id=user.id,
                session_id=session_id,
                event_type="TRANSFER_COMPLETED",
                metadata={
                    "transfer_id": str(transfer_id),
                    "amount": str(transfer.amount),
                    "sender_account_id": str(transfer.sender_account_id),
                    "receiver_account_id": str(transfer.receiver_account_id),
                },
            )
        )
        await db.commit()
