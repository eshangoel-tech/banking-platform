"""Receptionist agent — Layer 3 of the ADX Bank AI pipeline.

Combines all domain-agent responses into a single coherent reply and handles:
  - Direct receptionist tasks (greetings, unclear queries, redirect confirmations)
  - Collecting and deduplicating redirect actions from all agents
  - Presenting a natural, friendly final message to the customer
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from app.common.tools import RedirectTool, get_tool, tools_description
from app.services.ai.llm_utils import LLMCallResult, _strip_json_fences, call_llm

logger = logging.getLogger(__name__)

_AGENT_NAME = "receptionist"

_SYSTEM_PROMPT = """\
You are ADX Bank's warm, professional, and empathetic receptionist. \
You are the voice the customer hears — make every response feel human and helpful.

━━━ YOUR RESPONSIBILITIES ━━━

1. COMBINE specialist-agent responses into ONE coherent, natural reply.
   - Weave the information together smoothly — do not list agent names or show seams.
   - Remove duplication and keep it concise.

2. HANDLE direct tasks (when no specialist agent was called):
   • Greetings ("Hi", "Hello") — Welcome the customer warmly, introduce the assistant, \
     and ask how you can help.
   • Farewell ("Bye", "Thanks") — Acknowledge warmly and close the session.
   • Unclear queries — Politely ask the customer to clarify what they need.
   • Off-topic messages — Gently steer back: "I'm here to help with your ADX Bank \
     account — what can I assist you with today?"

3. NAVIGATION SUGGESTIONS — when a domain agent or the router suggests an action:
   • Phrase it naturally: "Would you like to head over to the Loans page to pay your EMI?"
   • Include the action in the "actions" array of the response.

4. REDIRECT CONFIRMATIONS — when the user says "yes", "sure", "okay", "go ahead":
   • Respond warmly: "Of course! I'll take you there now." or "Sure thing! Heading over."
   • Include the confirmed redirect action in "actions".

5. MULTI-TOPIC responses — combine all agent answers into a single flowing paragraph \
   or use short labelled sections only if the topics are very different.

━━━ TONE GUIDELINES ━━━
- Warm, concise, and professional — like a real bank employee.
- Use the customer's name if available in the context.
- Empathise with problems: "I understand that can be frustrating…"
- Never use raw JSON field names, agent names, or technical jargon in the response.

Output ONLY valid JSON with exactly these two keys:
{{
  "response": "<final natural language reply to the customer>",
  "actions" : [
    {{"name": "<TOOL_NAME>", "label": "<button label>", "url": "<frontend url>"}}
  ]
}}

If no navigation is needed, return an empty list for "actions".

Available redirect tools:
{tools_description}
"""


@dataclass
class AgentResponse:
    """Structured output from a single domain agent call."""
    agent: str
    query: str
    response: str
    suggest_actions: list[str] = field(default_factory=list)


@dataclass
class ReceptionistTask:
    """A sub-query the router assigned directly to the receptionist."""
    text: str
    action: list[str] = field(default_factory=list)


def combine_responses(
    user_message: str,
    agent_responses: list[AgentResponse],
    receptionist_tasks: list[ReceptionistTask],
) -> tuple[str, list[dict], LLMCallResult]:
    """
    Combine domain-agent responses and handle direct receptionist tasks.

    This function is **synchronous** — wrap with ``asyncio.to_thread()`` when
    calling from an async context.

    Returns
    -------
    final_response  : str — the final message to return to the customer.
    redirect_actions: list[dict] — resolved redirect actions ({name, label, url}).
    llm_result      : LLMCallResult — full interaction metadata for DB logging.
    """
    # --- Collect all suggested actions from domain agents and router tasks ---
    all_action_names: list[str] = []
    for ar in agent_responses:
        all_action_names.extend(ar.suggest_actions)
    for rt in receptionist_tasks:
        all_action_names.extend(rt.action)

    # --- Build the input for the receptionist LLM ---
    parts: list[str] = []

    if agent_responses:
        agent_lines = [
            f"[{ar.agent.upper()}] (query: \"{ar.query}\"): {ar.response}"
            for ar in agent_responses
        ]
        parts.append("Specialist agent responses:\n" + "\n\n".join(agent_lines))

    if receptionist_tasks:
        task_lines: list[str] = []
        for rt in receptionist_tasks:
            line = f"- {rt.text}"
            if rt.action:
                line += f"  (suggested actions: {', '.join(rt.action)})"
            task_lines.append(line)
        parts.append("Direct tasks:\n" + "\n".join(task_lines))

    if all_action_names:
        parts.append(f"Collected redirect suggestions: {', '.join(all_action_names)}")

    context_text = "\n\n".join(parts) if parts else "No specialist responses — handle directly."

    system = _SYSTEM_PROMPT.format(tools_description=tools_description())
    user_content = f"User message: {user_message}\n\n{context_text}"

    llm_result = call_llm(
        agent_name=_AGENT_NAME,
        system_prompt=system,
        user_content=user_content,
        temperature=0.7,
    )

    # --- Parse LLM output ---
    if llm_result.status == "FAILED":
        return (
            "I apologise, I'm having trouble processing your request right now. Please try again.",
            [],
            llm_result,
        )

    final_response = ""
    redirect_actions: list[dict] = []

    try:
        parsed = json.loads(_strip_json_fences(llm_result.response_text))
        final_response = parsed.get("response", llm_result.response_text)

        seen: set[str] = set()
        # Actions explicitly chosen by the receptionist LLM
        for action in parsed.get("actions", []):
            if isinstance(action, dict):
                name = action.get("name", "").upper()
            else:
                name = str(action).upper()
            tool = get_tool(name)
            if tool and name not in seen:
                redirect_actions.append({"name": tool.name, "label": tool.label, "url": tool.url})
                seen.add(name)

        # Also include any domain-agent suggestions not already present
        for name in all_action_names:
            tool = get_tool(name)
            if tool and tool.name not in seen:
                redirect_actions.append({"name": tool.name, "label": tool.label, "url": tool.url})
                seen.add(tool.name)

    except Exception as exc:
        logger.warning("receptionist JSON parse failed (%s) — returning raw text", exc)
        final_response = llm_result.response_text

    return final_response, redirect_actions, llm_result
