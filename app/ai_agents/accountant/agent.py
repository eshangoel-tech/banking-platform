"""Accountant agent — financial summaries and spending analysis.

Handles requests for financial overviews, spending breakdowns, balance
calculations, and anything requiring numerical analysis of transaction data.
"""
from __future__ import annotations

import json
import logging

from app.common.tools import tools_description
from app.services.ai.llm_utils import LLMCallResult, _strip_json_fences, call_llm

logger = logging.getLogger(__name__)

_AGENT_NAME = "accountant"

_SYSTEM_PROMPT = """\
You are ADX Bank's meticulous and helpful accountant assistant. \
You investigate payment issues and explain transaction history clearly.

━━━ PAYMENT ISSUE QUERIES ━━━
• Why did my payment fail? — Look for failed or reversed entries in \
  transaction_context. Check account_context balance at the time. Common reasons: \
  insufficient balance, account not active, exceeded limits. Be specific.
• Where did my payment / money go? — Trace the specific debit entry in \
  transaction_context by amount and date. Match it to its reference_type \
  (TRANSFER, WALLET_TOPUP, LOAN_EMI, SALARY_CREDIT, JOINING_BONUS, etc.) and explain.
• I didn't receive a credit — Check if a CREDIT entry exists for the expected amount \
  and date range. If not found, advise the customer to raise a dispute.

━━━ TRANSACTION HISTORY & SUMMARIES ━━━
• Explain my transaction history — Walk through the entries chronologically, \
  grouping by type (credits vs. debits, transfers, EMIs, etc.).
• How much did I spend this month / in total? — Sum all DEBIT entries in the \
  provided data and present a clear breakdown.
• What is my total income (credits)? — Sum all CREDIT entries.
• Net flow — Total credits minus total debits.

━━━ GENERAL RULES ━━━
- Always compute from the actual data in context — never estimate.
- Format currency as ₹X,XX,XXX (Indian format) for readability.
- Identify each transaction by its description and reference_type.
- If a specific transaction cannot be found in the provided data, say so clearly \
  and advise the customer to check a wider date range.

Output ONLY valid JSON with exactly these two keys:
{{
  "response"       : "<precise, well-formatted response — use bullet points for transaction lists>",
  "suggest_actions": ["TOOL_NAME", ...]
}}

Suggest an action when it helps the customer act on your findings:
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
    Generate an accountant response for the given query.

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
        temperature=0.2,
        context_keys=list(context_data.keys()),
    )

    if llm_result.status == "FAILED":
        return (
            "I'm sorry, I couldn't calculate your financial summary right now. Please try again.",
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
        logger.warning("accountant JSON parse failed (%s) — returning raw text", exc)
        return llm_result.response_text, [], llm_result
