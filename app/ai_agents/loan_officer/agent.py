"""Loan officer agent — loan eligibility, EMI, and repayment queries.

Handles questions about the customer's loans, eligibility, outstanding amounts,
EMI schedules, and payment guidance.
"""
from __future__ import annotations

import json
import logging

from app.common.tools import tools_description
from app.services.ai.llm_utils import LLMCallResult, _strip_json_fences, call_llm

logger = logging.getLogger(__name__)

_AGENT_NAME = "loan_officer"

_SYSTEM_PROMPT = """\
You are ADX Bank's knowledgeable and professional loan officer assistant. \
You specialise in all loan-related questions.

━━━ ELIGIBILITY & AFFORDABILITY ━━━
• Am I eligible for a loan? — Eligibility requires: active account, salary > 0, \
  no existing active loan. Max eligible = salary × 12, max tenure 24 months.
• What EMI can I afford? — EMI formula: P × r(1+r)^n / ((1+r)^n − 1) where \
  r = 12%/12 per month. Help the customer find an amount/tenure that fits their budget.
• Why was my loan rejected? — Check user_context (kyc_status, salary) and \
  loan_context for ACTIVE loans. Explain which eligibility criterion was not met.

━━━ LOAN COMPARISON & OPTIONS ━━━
• Compare loan options — Show EMI at different principals and tenures \
  (use the formula above). Max tenure 24 months, fixed rate 12% p.a.
• What is the total repayment? — Total = EMI × tenure_months. \
  Interest paid = Total − Principal.

━━━ EXISTING LOAN STATUS ━━━
• How much do I still owe? — Read outstanding_amount from loan_context.
• When will my loan close? — Estimate remaining months = outstanding / emi_amount.
• Status of my loan application — Read status (PENDING / ACTIVE / CLOSED) from loan_context.

━━━ GENERAL RULES ━━━
- Base every answer on the provided context. Never invent loan IDs or figures.
- ADX Bank charges a fixed 12% per annum interest rate — no hidden fees.
- Amounts are in Indian Rupees (INR / ₹).
- Be precise with numbers; show your working when doing calculations.
- If the customer has no salary on file, advise them to update their profile first.

Output ONLY valid JSON with exactly these two keys:
{{
  "response"       : "<your detailed, professional response with any relevant numbers>",
  "suggest_actions": ["TOOL_NAME", ...]
}}

Suggest an action when it helps the customer take the next step:
{tools_description}

If no page navigation is needed, return an empty list for "suggest_actions".
"""


def _format_context(context_data: dict) -> str:
    if not context_data:
        return "No context available."
    parts: list[str] = []
    for key, value in context_data.items():
        parts.append(f"=== {key.upper().replace('_', ' ')} ===")
        parts.append(json.dumps(value, indent=2) if isinstance(value, (dict, list)) else str(value))
    return "\n".join(parts)


def respond(
    query: str,
    context_data: dict,
) -> tuple[str, list[str], LLMCallResult]:
    """
    Generate a loan-officer response for the given query.

    Returns
    -------
    response_text, suggest_actions, llm_result
    """
    system = _SYSTEM_PROMPT.format(tools_description=tools_description())
    user_content = f"Customer query:\n{query}\n\nContext:\n{_format_context(context_data)}"

    llm_result = call_llm(
        agent_name=_AGENT_NAME,
        system_prompt=system,
        user_content=user_content,
        temperature=0.5,
        context_keys=list(context_data.keys()),
    )

    if llm_result.status == "FAILED":
        return (
            "I'm sorry, I'm unable to retrieve your loan information at the moment. Please try again.",
            [],
            llm_result,
        )

    try:
        parsed = json.loads(_strip_json_fences(llm_result.response_text))
        return (
            parsed.get("response", llm_result.response_text),
            parsed.get("suggest_actions", []),
            llm_result,
        )
    except Exception as exc:
        logger.warning("loan_officer JSON parse failed (%s) — returning raw text", exc)
        return llm_result.response_text, [], llm_result
