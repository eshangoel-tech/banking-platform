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
  • Financial health: "Tell me about my financial health", "Give me a financial overview",
    "How am I doing financially?", "What is my financial status?"
  • Financial advice: "Can I increase my loan eligibility?",
    "Should I prepay my loan?", "How do I reduce my EMI burden?"
  → Typical context for financial health: account_context, user_context, transaction_context, loan_context
  → Typical context for summaries/charges: account_context, transaction_context
  → Typical context for financial advice: user_context, loan_context, bank_rules

loan_officer — Loan-specific questions:
  • "Am I eligible for a loan?", "What EMI can I afford?",
    "How much loan can I afford?", "What is my max loan amount?",
    "Why was my loan rejected?", "Compare loan options",
    "How much will I repay in total?", "Can I foreclose my loan?",
    "What are the foreclosure charges?"
  → Typical context: user_context + bank_rules (eligibility/affordability — salary is in user_context),
    loan_context + bank_rules (rejection/comparison/status)

accountant — Payment tracking & transaction analysis:
  • "Why did my payment fail?", "Where did my payment go?",
    "Explain my transaction history", "Show me my spending summary",
    "How much did I spend this month?", "What were my biggest transactions?"
  → Use transaction_context for recent entries only.
     Use transaction_analysis (tool) for spending breakdowns and full history analysis.

support — Knowledge base & troubleshooting (uses RAG):
  • Knowledge: "What is loan interest calculation?", "What is foreclosure?",
    "What are bank charges?", "How does salary credit work?",
    "What is the transfer limit?", "What happens if I miss an EMI?"
  • Troubleshooting: "My payment is stuck", "I didn't receive my OTP",
    "Account verification is failing", "How do I reset my password?"
  → Use bank_rules for specific limits/constants.
     Use bank_policy for general process/policy questions.
     Use bank_policy_document (tool) when the question needs comprehensive policy
     coverage (fees + limits + process all in one), e.g. "Tell me everything about loans".

receptionist — Greetings, navigation, unclear queries, redirect confirmations:
  • Greetings ("Hi", "Hello", "Good morning")
  • User says "yes" / "okay" / "sure" confirming a redirect from previous turn
  • Unclear or completely off-topic messages
  • User explicitly asks to go somewhere ("take me to loans", "open transfer page")
  → Typical context: [] (empty) — optionally chat_history for redirect confirmation

━━━ AVAILABLE CONTEXT TYPES ━━━
Only include what is strictly needed for that sub-query.

Standard context (always available, cheap):
- user_context          : User profile (full name, email, salary, KYC status, account status)
- chat_history          : Last few conversation turns (for redirect confirmation)
- account_context       : Account number, balance, type, currency, status
- transaction_context   : Last 10 ledger entries (type, amount, description, date)
- loan_context          : Active/closed loans with amounts, EMI, outstanding balance

RAG context (semantic search — use the sub-query text as the search query):
- bank_policy           : Bank policy docs via semantic search, top 3 chunks
                          → for specific process/policy questions
- bank_rules            : Bank business rules via semantic search, top 3 chunks
                          → for specific limits, fees, numeric thresholds

Tool-based context (richer fetch — use when depth matters):
- transaction_analysis  : FULL transaction history + computed spending summary
                          (total credits, total debits, breakdown by category).
                          → use instead of transaction_context when user asks for
                            spending analysis, monthly summary, or full audit.
- bank_policy_document  : Deep policy retrieval, top 6 chunks from policy + FAQ docs.
                          → use instead of bank_policy when the question is broad or
                            needs multiple policy sections (e.g. "explain all loan rules",
                            "what are all the fees?", "tell me about security").

━━━ AVAILABLE REDIRECT ACTIONS ━━━
Include in "action" when the user wants to navigate or when navigation is the right next step:
{tools_description}

━━━ OUTPUT FORMAT ━━━
Output ONLY a valid JSON array — no other text before or after.
Each element must have exactly these four keys:
{{
  "text"   : "<the specific sub-query — this is also used as the RAG search query>",
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
7. The "text" field is used as the RAG search query — make it specific and descriptive \
   so the right policy/rules chunks are retrieved (e.g. "loan interest rate and EMI formula" \
   is better than just "loan").
8. Prefer transaction_analysis over transaction_context when the user asks for summaries, \
   spending breakdowns, or analysis covering more than a few recent entries.
9. Prefer bank_policy_document over bank_policy for broad or multi-faceted policy questions.
10. NEVER route to "receptionist" if a specialist agent can answer using account/user/loan \
    data. Financial health, loan affordability, spending summaries — these go to domain agents.
11. For "financial health / financial overview" → bank_manager with \
    [account_context, user_context, transaction_context, loan_context].
12. For "how much loan can I afford / max loan / loan eligibility" → loan_officer with \
    [user_context, bank_rules] — user_context contains salary so the agent can compute directly.
13. Do NOT split "how much to pay to clear/foreclose my loan + any charges?" into two sub-queries. \
    It is ONE query → loan_officer with [loan_context, bank_rules]. \
    Foreclosure amount = outstanding_amount (not total EMI × remaining months).
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
