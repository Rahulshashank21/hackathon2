"""
Input guardrail (AC-06): wired into the agent's I/O path at the
supervisor node, before any customer-supplied narrative reaches an LLM
or tool. Refuses attempts to reach another customer's data or to
smuggle a raw card number into the narrative (which should never be
necessary — the copilot looks up transaction/account data by ID via
the MCP tools, not from customer-typed digits).

This is distinct from (and runs alongside) context quarantine
(src/context/isolate.py): quarantine neutralizes injection attempts by
wrapping the text as inert data; this guardrail additionally decides
whether the request should be BLOCKED outright.
"""

from __future__ import annotations

import re

# Matches "ACC-70009", "acc 70009", "account_70009", "account 70009",
# etc. — see docs/failure-analysis.md Failure #3: the original
# dash-only pattern missed underscore/space/word-form variants.
_OTHER_ACCOUNT_RE = re.compile(r"\b(?:ACC|ACCOUNT)[ _-]?(\d{4,})\b", re.IGNORECASE)
_RAW_PAN_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_CROSS_ACCOUNT_PHRASES = [
    r"show me (another|a different) (customer|account)",
    r"look ?up (someone|another person|a different customer)",
]


def check_input(narrative: str, own_account_id: str) -> dict:
    """Returns {"blocked": bool, "reason": str | None, "flags": [str]}."""
    flags: list[str] = []
    lowered = narrative.lower()

    own_digits = re.sub(r"\D", "", own_account_id)
    for match in _OTHER_ACCOUNT_RE.finditer(narrative):
        mentioned_digits = match.group(1)
        if mentioned_digits != own_digits:
            flags.append(f"referenced_other_account:{match.group(0)}")

    if _RAW_PAN_RE.search(narrative):
        flags.append("raw_card_number_in_narrative")

    for pattern in _CROSS_ACCOUNT_PHRASES:
        if re.search(pattern, lowered):
            flags.append(f"cross_account_phrase:{pattern}")

    blocked = any(
        f.startswith("referenced_other_account") or f.startswith("cross_account_phrase")
        for f in flags
    )
    reason = (
        "This request appears to reference another customer's account. "
        "For your security, I can only discuss the account and dispute "
        "you are authenticated as. Please contact support directly if "
        "you believe there is an issue with a different account."
        if blocked
        else None
    )
    return {"blocked": blocked, "reason": reason, "flags": flags}
