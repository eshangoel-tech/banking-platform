"""AI assistant redirect tools.

Maps action names to frontend page routes.  Agents include tool names in their
output when the user should be navigated to a specific page.  The receptionist
resolves names to full ``RedirectTool`` objects, and the API response sends them
to the frontend which handles the actual navigation.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RedirectTool:
    name: str
    label: str
    url: str
    description: str


_TOOLS: dict[str, RedirectTool] = {
    "PAY_EMI": RedirectTool(
        name="PAY_EMI",
        label="Pay EMI",
        url="/loans",
        description="Navigate to the loans page to pay an EMI instalment",
    ),
    "GET_LOAN": RedirectTool(
        name="GET_LOAN",
        label="Apply for Loan",
        url="/loans",
        description="Navigate to the loan application page",
    ),
    "ADD_MONEY": RedirectTool(
        name="ADD_MONEY",
        label="Add Money",
        url="/wallet",
        description="Navigate to the wallet page to top up balance",
    ),
    "TRANSFER_MONEY": RedirectTool(
        name="TRANSFER_MONEY",
        label="Transfer Money",
        url="/transfer",
        description="Navigate to the money transfer page",
    ),
    "EDIT_PROFILE": RedirectTool(
        name="EDIT_PROFILE",
        label="Edit Profile",
        url="/profile",
        description="Navigate to the profile edit page",
    ),
    "VIEW_TRANSACTIONS": RedirectTool(
        name="VIEW_TRANSACTIONS",
        label="View Transactions",
        url="/transactions",
        description="Navigate to the transaction history page",
    ),
    "VIEW_LOANS": RedirectTool(
        name="VIEW_LOANS",
        label="View Loans",
        url="/loans",
        description="Navigate to the loan details page",
    ),
    "VIEW_ACCOUNT": RedirectTool(
        name="VIEW_ACCOUNT",
        label="View Account",
        url="/dashboard",
        description="Navigate to the account dashboard",
    ),
    "CONTACT_SUPPORT": RedirectTool(
        name="CONTACT_SUPPORT",
        label="Contact Support",
        url="/support",
        description="Navigate to the customer support page",
    ),
}


def get_tool(name: str) -> RedirectTool | None:
    """Return a RedirectTool by name (case-insensitive). None if not found."""
    return _TOOLS.get(name.upper())


def get_all_tools() -> dict[str, RedirectTool]:
    """Return all available tools."""
    return dict(_TOOLS)


def tools_description() -> str:
    """Return a human-readable list of tools for inclusion in LLM prompts."""
    return "\n".join(
        f"- {key}: {tool.description}" for key, tool in _TOOLS.items()
    )
