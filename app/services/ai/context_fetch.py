"""
Context fetchers for the ADX Bank AI assistant.

Each function fetches one type of context and returns a clean,
serialisable Python dict or list ready to be injected into an LLM prompt.

Available fetchers
------------------
1. fetch_user_context              — full user profile
2. fetch_chat_history_context      — last N chat turns for the user
3. fetch_account_context           — account details + current balance
4. fetch_transaction_context       — last N ledger entries (all if limit=None)
5. fetch_loan_details              — active/all loans with filters
6. fetch_bank_policy_context       — RAG over bank_policies collection (top_k=3)
7. fetch_bank_rules_context        — RAG over bank_rules collection (top_k=3)

Tools (richer, targeted fetchers used by the router as named context types)
8. fetch_transactions_tool         — full transaction history + spending summary
9. fetch_bank_policy_document      — deep RAG over bank_policies (top_k=6)
"""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repository.models.account import Account
from app.repository.models.chat_response import ChatResponse
from app.repository.models.chat_session import ChatSession
from app.repository.models.ledger_entry import LedgerEntry
from app.repository.models.loan import Loan
from app.repository.models.user import User
from app.services.ai.rag.retriever import retrieve_bank_policies, retrieve_bank_rules

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. User context
# ---------------------------------------------------------------------------

async def fetch_user_context(db: AsyncSession, user_id: UUID) -> dict:
    """
    Return full user profile (excludes sensitive fields: password_hash, tokens).
    """
    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalar_one_or_none()
    if user is None:
        return {}

    return {
        "user_id": str(user.id),
        "customer_id": user.customer_id,
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "address": user.address,
        "salary": float(user.salary) if user.salary else None,
        "kyc_status": user.kyc_status,
        "account_status": user.status,
        "failed_login_attempts": user.failed_login_attempts,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


# ---------------------------------------------------------------------------
# 2. Chat history context
# ---------------------------------------------------------------------------

async def fetch_chat_history_context(
    db: AsyncSession,
    customer_id: str,
    limit: int = 10,
) -> list[dict]:
    """
    Return the last `limit` chat turns (user + assistant) for the given customer.

    Joins chat_responses -> chat_sessions on customer_id.
    Returns oldest-first so the LLM sees conversation flow naturally.
    """
    stmt = (
        select(
            ChatResponse.response_id,
            ChatResponse.user_message,
            ChatResponse.assistant_response,
            ChatResponse.created_at,
        )
        .join(ChatSession, ChatResponse.chat_sess_id == ChatSession.chat_sess_id)
        .where(ChatSession.customer_id == customer_id)
        .order_by(desc(ChatResponse.created_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.fetchall()

    # Reverse so oldest first for natural LLM reading order
    history = [
        {
            "response_id": str(row.response_id),
            "user_message": row.user_message,
            "assistant_response": row.assistant_response,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in reversed(rows)
    ]
    return history


# ---------------------------------------------------------------------------
# 3. Account context
# ---------------------------------------------------------------------------

async def fetch_account_context(db: AsyncSession, user_id: UUID) -> dict:
    """Return the user's primary account details including current balance."""
    res = await db.execute(select(Account).where(Account.user_id == user_id))
    account = res.scalar_one_or_none()
    if account is None:
        return {}

    return {
        "account_id": str(account.id),
        "account_number": account.account_number,
        "account_type": account.account_type,
        "balance": float(account.balance),
        "currency": account.currency,
        "status": account.status,
        "created_at": account.created_at.isoformat() if account.created_at else None,
    }


# ---------------------------------------------------------------------------
# 4. Transaction context
# ---------------------------------------------------------------------------

async def fetch_transaction_context(
    db: AsyncSession,
    user_id: UUID,
    limit: Optional[int] = None,
) -> list[dict]:
    """
    Return ledger entries for the user's account.

    Parameters
    ----------
    limit : int | None
        Number of most-recent transactions to return.
        Pass None to return all transactions.
    """
    acc_res = await db.execute(select(Account.id).where(Account.user_id == user_id))
    account_id = acc_res.scalar_one_or_none()
    if account_id is None:
        return []

    stmt = (
        select(LedgerEntry)
        .where(LedgerEntry.account_id == account_id)
        .order_by(desc(LedgerEntry.created_at))
    )
    if limit is not None:
        stmt = stmt.limit(limit)

    result = await db.execute(stmt)
    entries = result.scalars().all()

    return [
        {
            "entry_id": str(e.id),
            "type": e.entry_type,
            "amount": float(e.amount),
            "balance_after": float(e.balance_after),
            "reference_type": e.reference_type,
            "description": e.description,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in entries
    ]


# ---------------------------------------------------------------------------
# 5. Loan details
# ---------------------------------------------------------------------------

async def fetch_loan_details(
    db: AsyncSession,
    user_id: UUID,
    status_filter: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    """
    Return the user's loans.

    Parameters
    ----------
    status_filter : str | None
        Filter by loan status: "ACTIVE", "PENDING", "CLOSED".
        Pass None to return all statuses.
    limit : int
        Maximum number of loans to return (newest first).
    """
    stmt = select(Loan).where(Loan.user_id == user_id)

    if status_filter:
        stmt = stmt.where(Loan.status == status_filter.upper())

    stmt = stmt.order_by(desc(Loan.created_at)).limit(limit)

    result = await db.execute(stmt)
    loans = result.scalars().all()

    return [
        {
            "loan_id": str(loan.id),
            "principal_amount": float(loan.principal_amount),
            "interest_rate": float(loan.interest_rate),
            "tenure_months": loan.tenure_months,
            "emi_amount": float(loan.emi_amount),
            "outstanding_amount": float(loan.outstanding_amount),
            "status": loan.status,
            "approved_at": loan.approved_at.isoformat() if loan.approved_at else None,
            "created_at": loan.created_at.isoformat() if loan.created_at else None,
        }
        for loan in loans
    ]


# ---------------------------------------------------------------------------
# 6. Bank policy context  (RAG — synchronous, no DB)
# ---------------------------------------------------------------------------

def fetch_bank_policy_context(query: str, top_k: int = 3) -> list[str]:  # noqa: E501
    """
    Retrieve the most relevant bank policy chunks for a natural-language query.

    Returns annotated text strings: [source | section | similarity]\\ntext
    """
    chunks = retrieve_bank_policies(query, top_k=top_k)
    logger.debug("Policy context: %d chunks for query: %.60s", len(chunks), query)
    return chunks


# ---------------------------------------------------------------------------
# 7. Bank rules context  (RAG — synchronous, no DB)
# ---------------------------------------------------------------------------

def fetch_bank_rules_context(query: str, top_k: int = 3) -> list[str]:
    """
    Retrieve the most relevant bank rules chunks for a natural-language query.

    Returns annotated text strings: [source | section | similarity]\\ntext
    """
    chunks = retrieve_bank_rules(query, top_k=top_k)
    logger.debug("Rules context: %d chunks for query: %.60s", len(chunks), query)
    return chunks


# ---------------------------------------------------------------------------
# 8. Tool: fetch_transactions_tool  (DB — full history + spending summary)
# ---------------------------------------------------------------------------

async def fetch_transactions_tool(db: AsyncSession, user_id: UUID) -> dict:
    """
    Fetch the full transaction history for a user and compute a spending summary.

    Used by the router as the ``transaction_analysis`` context type when the
    user asks for spending analysis, category breakdowns, or audits that need
    more than the last 10 entries.

    Returns
    -------
    {
        "transactions": [...],        # full ledger entries, newest first
        "summary": {
            "total_credits": float,
            "total_debits": float,
            "net_balance_change": float,
            "transaction_count": int,
            "credit_count": int,
            "debit_count": int,
            "by_reference_type": { "<ref_type>": {"count": int, "total": float} }
        }
    }
    """
    entries = await fetch_transaction_context(db, user_id, limit=None)

    total_credits = 0.0
    total_debits = 0.0
    credit_count = 0
    debit_count = 0
    by_ref: dict[str, dict] = {}

    for e in entries:
        amt = e["amount"]
        ref = e.get("reference_type") or "OTHER"
        if e["type"] == "CREDIT":
            total_credits += amt
            credit_count += 1
        else:
            total_debits += amt
            debit_count += 1

        if ref not in by_ref:
            by_ref[ref] = {"count": 0, "total": 0.0}
        by_ref[ref]["count"] += 1
        by_ref[ref]["total"] = round(by_ref[ref]["total"] + amt, 2)

    summary = {
        "total_credits": round(total_credits, 2),
        "total_debits": round(total_debits, 2),
        "net_balance_change": round(total_credits - total_debits, 2),
        "transaction_count": len(entries),
        "credit_count": credit_count,
        "debit_count": debit_count,
        "by_reference_type": by_ref,
    }

    logger.debug(
        "fetch_transactions_tool: %d entries fetched for user_id=%s", len(entries), user_id
    )
    return {"transactions": entries, "summary": summary}


# ---------------------------------------------------------------------------
# 9. Tool: fetch_bank_policy_document  (RAG — deeper retrieval, top_k=6)
# ---------------------------------------------------------------------------

def fetch_bank_policy_document(query: str) -> list[str]:
    """
    Deep retrieval over the bank_policies collection (top_k=6 chunks).

    Used by the router as the ``bank_policy_document`` context type when the
    user asks detailed policy questions that may need multiple policy sections
    (e.g. fees + limits + process all in one answer).

    Returns annotated text strings: [source | section | similarity]\\ntext
    """
    chunks = retrieve_bank_policies(query, top_k=6)
    logger.debug(
        "fetch_bank_policy_document: %d chunks for query: %.60s", len(chunks), query
    )
    return chunks
