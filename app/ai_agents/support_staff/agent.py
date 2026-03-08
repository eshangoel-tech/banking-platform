"""Support staff agent — general banking questions answered via RAG context.

Handles policy questions, fee inquiries, process explanations, and anything
that requires looking up the bank's policies or rules documents.
"""
from __future__ import annotations

import json
import logging

from app.common.tools import tools_description
from app.services.ai.llm_utils import LLMCallResult, _strip_json_fences, call_llm

logger = logging.getLogger(__name__)

_AGENT_NAME = "support"

_SYSTEM_PROMPT = """\
You are ADX Bank's knowledgeable customer support assistant. \
You answer knowledge questions and help troubleshoot common issues.

━━━ KNOWLEDGE / POLICY QUESTIONS ━━━
• What is the loan interest calculation? — ADX Bank uses a fixed 12% p.a. reducing \
  balance EMI formula: P × r(1+r)^n / ((1+r)^n − 1). Explain it with an example.
• What is foreclosure? — Foreclosure means repaying the entire outstanding loan amount \
  before the tenure ends. Explain the steps at ADX Bank.
• What are the bank charges? — Refer to the bank_policy context. ADX Bank currently \
  charges zero transaction fees. Explain any policy-mentioned charges.
• How does salary credit work? — Salary is credited automatically after account \
  verification. Explain the joining bonus (₹500) and subsequent salary credits.
• How does KYC work? / What documents are needed? — Refer to bank_policy for KYC \
  requirements.
• Any other "how does X work" question — Use the bank_policy and bank_rules context.

━━━ TROUBLESHOOTING ━━━
• Payment stuck / pending — Advise the customer: PENDING transfers auto-resolve within \
  24 hours. If stuck longer, note their reference number and contact support.
• OTP not received — Common causes: incorrect email, spam folder, email server delay. \
  Advise: check spam, wait 2 minutes, then request a new OTP. OTPs expire in 5 minutes.
• Account verification failing — Ensure email OTP is entered correctly and hasn't expired. \
  Max 3 attempts; after that a new OTP must be requested.
• Can't log in — Check if account is blocked (3 failed attempts = 1 hour lockout). \
  Advise to wait or use forgot-password if needed.
• General "I can't do X" — Refer to relevant policy/rules context to explain the process.

━━━ GENERAL RULES ━━━
- Always base answers on the provided bank_policy and bank_rules context.
- Reference the policy explicitly ("According to ADX Bank's loan policy…").
- Do NOT invent policies or charges not mentioned in the context.
- Be empathetic and helpful, especially for troubleshooting queries.
- For issues that cannot be resolved via the assistant, direct the customer to support.

Output ONLY valid JSON with exactly these two keys:
{{
  "response"       : "<your helpful, policy-grounded response>",
  "suggest_actions": ["TOOL_NAME", ...]
}}

Suggest an action when it helps the customer resolve their issue:
{tools_description}

If no page navigation is needed, return an empty list for "suggest_actions".
"""


def _format_context(context_data: dict) -> str:
    if not context_data:
        return "No context available."
    parts: list[str] = []
    for key, value in context_data.items():
        parts.append(f"=== {key.upper().replace('_', ' ')} ===")
        if isinstance(value, list):
            # RAG chunks are a list of annotated strings
            parts.append("\n---\n".join(str(v) for v in value))
        elif isinstance(value, dict):
            parts.append(json.dumps(value, indent=2))
        else:
            parts.append(str(value))
    return "\n".join(parts)


def respond(
    query: str,
    context_data: dict,
) -> tuple[str, list[str], LLMCallResult]:
    """
    Generate a support response for the given query.

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
        temperature=0.6,
        context_keys=list(context_data.keys()),
    )

    if llm_result.status == "FAILED":
        return (
            "I'm sorry, I'm unable to answer your question right now. Please try again or contact support.",
            ["CONTACT_SUPPORT"],
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
        logger.warning("support JSON parse failed (%s) — returning raw text", exc)
        return llm_result.response_text, [], llm_result
