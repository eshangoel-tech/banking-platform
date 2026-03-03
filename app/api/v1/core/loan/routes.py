"""Loan API v1 routes."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.core.auth.dependencies import AuthContext, get_current_user
from app.repository.session import get_db
from app.schemas.loan import LoanBookRequest, LoanConfirmRequest, LoanSimulateRequest
from app.services.core.loan_service.service import LoanService

router = APIRouter()


def _request_id(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    return str(rid) if rid else ""


def _ok(request: Request, message: str, data: dict | None = None) -> dict:
    return {
        "success": True,
        "message": message,
        "data": data,
        "request_id": _request_id(request),
    }


# ---------------------------------------------------------------------------
# GET /loan/eligibility
# ---------------------------------------------------------------------------

@router.get("/eligibility")
async def get_loan_eligibility(
    request: Request,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return the user's loan eligibility based on their declared salary.

    max_eligible_amount = salary × 12  (up to 24 months at 12% p.a.)
    """
    service = LoanService()
    data = await service.get_eligibility(db, user=auth.user, session_id=auth.session_id)
    return _ok(request, "Loan eligibility fetched.", data=data)


# ---------------------------------------------------------------------------
# POST /loan/simulate
# ---------------------------------------------------------------------------

@router.post("/simulate")
async def simulate_loan(
    request: Request,
    payload: LoanSimulateRequest,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Simulate EMI for a given principal + tenure.

    Saves a LoanSimulation record for analytics and returns:
      amount, tenure_months, interest_rate, emi_amount, total_payable.
    """
    service = LoanService()
    data = await service.simulate(
        db,
        user=auth.user,
        session_id=auth.session_id,
        amount=payload.amount,
        tenure_months=payload.tenure_months,
    )
    return _ok(request, "Loan simulation completed.", data=data)


# ---------------------------------------------------------------------------
# POST /loan/book
# ---------------------------------------------------------------------------

@router.post("/book")
async def book_loan(
    request: Request,
    payload: LoanBookRequest,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Step 1 of loan booking: validate eligibility, store booking in Redis (5 min TTL),
    and send a 6-digit OTP to the user's email.

    Returns booking_id — pass it along with the OTP to /loan/confirm.
    """
    service = LoanService()
    data = await service.book_loan(
        db,
        user=auth.user,
        session_id=auth.session_id,
        amount=payload.amount,
        tenure_months=payload.tenure_months,
    )
    return _ok(request, data["message"], data={"booking_id": data["booking_id"]})


# ---------------------------------------------------------------------------
# POST /loan/confirm
# ---------------------------------------------------------------------------

@router.post("/confirm")
async def confirm_loan(
    request: Request,
    payload: LoanConfirmRequest,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Step 2 of loan booking: verify OTP, create Loan record (PENDING), and
    dispatch background Celery task to approve it (→ ACTIVE).

    On success returns loan_id, emi_amount, and current status.
    """
    service = LoanService()
    data = await service.confirm_loan(
        db,
        user=auth.user,
        session_id=auth.session_id,
        booking_id=payload.booking_id,
        otp=payload.otp,
    )
    return _ok(request, data.pop("message"), data=data)


# ---------------------------------------------------------------------------
# GET /loan/list
# ---------------------------------------------------------------------------

@router.get("/list")
async def list_loans(
    request: Request,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all loans belonging to the authenticated user, newest first."""
    service = LoanService()
    data = await service.get_loans(db, user_id=auth.user.id)
    return _ok(request, "Loans fetched.", data=data)


# ---------------------------------------------------------------------------
# POST /loan/{loan_id}/pay
# ---------------------------------------------------------------------------

@router.post("/{loan_id}/pay")
async def pay_loan(
    request: Request,
    loan_id: UUID,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Pay one EMI instalment for an active loan.

    Deducts min(emi_amount, outstanding_amount) from the wallet balance,
    creates a DEBIT ledger entry, and closes the loan when outstanding
    reaches zero.
    """
    service = LoanService()
    data = await service.pay_loan(
        db,
        user=auth.user,
        session_id=auth.session_id,
        loan_id=loan_id,
    )
    return _ok(request, "Loan payment successful.", data=data)
