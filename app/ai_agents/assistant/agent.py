"""Router / dispatcher agent — Layer 1 of the ADX Bank AI pipeline.

Analyses the user's message, breaks it into sub-queries, and assigns each
sub-query to the most appropriate specialist agent together with the context
types it will need.

Returns a list of ``RouterDecision`` objects plus the ``LLMCallResult`` so the
caller can persist the interaction to the database.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from app.common.tools import tools_description
from app.services.ai.llm_utils import LLMCallResult, _strip_json_fences, call_llm

logger = logging.getLogger(__name__)

_AGENT_NAME = "assistant"

_SYSTEM_PROMPT = """\
You are the ADX Bank AI assistant router. Analyse the user's message, break it \
into sub-queries when needed, and assign each to the correct specialist agent with \
the minimum context required to answer it.

━━━ AVAILABLE AGENTS & THEIR SCOPE ━━━

bank_manager — Account & financial advice questions:
  • Account: "How do I open an account?", "Why was my account blocked?",
    "Show my account summary", "Explain charges on my account"
  • Financial advice: "Can I increase my loan eligibility?",
    "Should I prepay my loan?", "How do I reduce my EMI burden?"
  → Typical context: account_context, user_context, transaction_context (for summaries/charges),
    loan_context + bank_rules (for financial advice queries)

loan_officer — Loan-specific questions:
  • "Am I eligible for a loan?", "What EMI can I afford?",
    "Why was my loan rejected?", "Compare loan options",
    "How much will I repay in total?"
  → Typical context: user_context + bank_rules (eligibility/affordability),
    loan_context + bank_rules (rejection/comparison)

accountant — Payment tracking & transaction analysis:
  • "Why did my payment fail?", "Where did my payment go?",
    "Explain my transaction history", "Show me my spending summary"
  → Typical context: transaction_context, account_context

support — Knowledge base & troubleshooting (uses RAG):
  • Knowledge: "What is loan interest calculation?", "What is foreclosure?",
    "What are bank charges?", "How does salary credit work?"
  • Troubleshooting: "My payment is stuck", "I didn't receive my OTP",
    "Account verification is failing", "How do I reset my password?"
  → Typical context: bank_rules and/or bank_policy (always via RAG)

receptionist — Greetings, navigation, unclear queries, redirect confirmations:
  • Greetings ("Hi", "Hello", "Good morning")
  • User says "yes" / "okay" / "sure" confirming a redirect from previous turn
  • Unclear or completely off-topic messages
  • User explicitly asks to go somewhere ("take me to loans", "open transfer page")
  → Typical context: [] (empty) — optionally chat_history for redirect confirmation

━━━ AVAILABLE CONTEXT TYPES ━━━
Only include what is strictly needed for that sub-query:
- user_context       : User profile (full name, email, salary, KYC status, account status)
- chat_history       : Last few conversation turns (needed for redirect confirmation)
- account_context    : Account number, balance, type, currency, status
- transaction_context: Recent ledger entries (type, amount, description, date)
- loan_context       : Active / closed loans with amounts, EMI, outstanding balance
- bank_policy        : Bank policy documents via semantic search (RAG)
- bank_rules         : Bank business rules via semantic search (RAG)

━━━ AVAILABLE REDIRECT ACTIONS ━━━
Include in "action" when the user wants to navigate or when navigation is the right next step:
{tools_description}

━━━ OUTPUT FORMAT ━━━
Output ONLY a valid JSON array — no other text before or after.
Each element must have exactly these four keys:
{{
  "text"   : "<sub-query or relevant portion of the user message>",
  "agent"  : "<agent_name>",
  "context": ["<context_type>", ...],
  "action" : ["<TOOL_NAME>", ...]
}}

━━━ ROUTING RULES ━━━
1. Navigation requests → assign to "receptionist", add tool name in "action".
2. Redirect confirmation ("yes", "sure", "okay") → check chat_history for what was suggested,
   assign to "receptionist" with that tool in "action" and ["chat_history"] in context.
3. Greetings / off-topic / unclear → "receptionist", empty context, empty action.
4. Do NOT request context types not needed for that sub-query.
5. Split only when the message genuinely requires different specialist agents.
6. When in doubt between bank_manager and loan_officer, prefer loan_officer for pure loan \
   mechanics and bank_manager for account-level or advisory questions.
"""


@dataclass
class RouterDecision:
    text: str
    agent: str
    context: list[str] = field(default_factory=list)
    action: list[str] = field(default_factory=list)


def route_message(
    user_message: str,
    chat_history: list[dict],
) -> tuple[list[RouterDecision], LLMCallResult]:
    """
    Analyse the user message and return routing decisions.

    This function is **synchronous** — wrap with ``asyncio.to_thread()`` when
    calling from an async context.

    Returns
    -------
    decisions : list[RouterDecision]
        One entry per sub-query; falls back to a single receptionist decision on error.
    llm_result : LLMCallResult
        Full interaction metadata for DB persistence.
    """
    # Format the last 6 turns — enough context for routing without token bloat
    history_lines: list[str] = []
    for turn in chat_history[-6:]:
        history_lines.append(f"User: {turn.get('user_message', '')}")
        history_lines.append(f"Assistant: {turn.get('assistant_response', '')}")
    history_text = "\n".join(history_lines) or "No previous conversation."

    system = _SYSTEM_PROMPT.format(tools_description=tools_description())
    user_content = (
        f"Chat history:\n{history_text}\n\nCurrent user message:\n{user_message}"
    )

    llm_result = call_llm(
        agent_name=_AGENT_NAME,
        system_prompt=system,
        user_content=user_content,
        temperature=0.1,
        context_keys=["chat_history"],
    )

    decisions: list[RouterDecision] = []

    if llm_result.status == "FAILED":
        decisions.append(RouterDecision(text=user_message, agent="receptionist"))
        return decisions, llm_result

    try:
        raw = _strip_json_fences(llm_result.response_text)
        parsed = json.loads(raw)
        for item in parsed:
            decisions.append(
                RouterDecision(
                    text=item.get("text", user_message),
                    agent=item.get("agent", "receptionist"),
                    context=item.get("context", []),
                    action=item.get("action", []),
                )
            )
    except Exception as exc:
        logger.warning("Router JSON parse failed (%s) — fallback to receptionist", exc)
        decisions.append(RouterDecision(text=user_message, agent="receptionist"))

    if not decisions:
        decisions.append(RouterDecision(text=user_message, agent="receptionist"))

    return decisions, llm_result
