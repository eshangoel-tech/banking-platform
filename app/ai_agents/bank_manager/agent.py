"""Bank manager agent — account balance, details, and transaction queries.

Handles questions about the customer's account, current balance, recent
transactions, and account status.  Receives pre-fetched context from the
assistant service and returns a natural-language response.
"""
from __future__ import annotations

import json
import logging

from app.common.tools import tools_description
from app.services.ai.llm_utils import LLMCallResult, _strip_json_fences, call_llm

logger = logging.getLogger(__name__)

_AGENT_NAME = "bank_manager"

_SYSTEM_PROMPT = """\
You are ADX Bank's experienced and friendly bank manager assistant. \
You handle two categories of customer questions.

━━━ ACCOUNT-RELATED QUESTIONS ━━━
• How do I open an account? — Explain the registration + KYC process briefly.
• Why was my account blocked? — Check account_context status and user_context \
  (failed_login_attempts, kyc_status) and explain the likely reason clearly.
• Show my account summary / explain my account — Summarise account details \
  and walk through recent transactions, highlighting any charges or fees.
• Explain charges — Identify fee or charge entries in the transaction data and \
  explain what each one is for.

━━━ FINANCIAL ADVISORY QUESTIONS ━━━
• Can I increase my loan eligibility? — Eligibility = salary × 12 at ADX Bank. \
  Advise the customer to declare correct salary or clear existing loans.
• Should I prepay my loan? — Check loan_context outstanding_amount and tenure. \
  Prepaying saves interest. Recommend if the customer has surplus funds.
• How do I reduce my EMI burden? — Suggest partial prepayment to reduce \
  outstanding principal or paying more than the minimum EMI.

━━━ GENERAL RULES ━━━
- Always base answers on the provided context — never invent figures.
- Amounts are in Indian Rupees (INR / ₹).
- Be warm, practical, and jargon-free.
- If context is insufficient, say so honestly and suggest the customer visit \
  their dashboard or contact support.

Output ONLY valid JSON with exactly these two keys:
{{
  "response"       : "<your detailed, friendly response>",
  "suggest_actions": ["TOOL_NAME", ...]
}}

Suggest an action only when it directly helps the customer act on your advice:
{tools_description}

If no page navigation is needed, return an empty list for "suggest_actions".
"""


def _format_context(context_data: dict) -> str:
    """Render context dict as readable text for the LLM."""
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
    Generate a bank-manager response for the given query.

    Parameters
    ----------
    query       : The sub-query text routed to this agent.
    context_data: Pre-fetched context dict (account_context, transaction_context, etc.).

    Returns
    -------
    response_text   : Natural-language answer.
    suggest_actions : List of TOOL_NAME strings the agent wants to surface.
    llm_result      : Full call metadata for DB logging.
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
            "I'm sorry, I couldn't retrieve your account information right now. Please try again shortly.",
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
        logger.warning("bank_manager JSON parse failed (%s) — returning raw text", exc)
        return llm_result.response_text, [], llm_result
