"""
Output guardrail (AC-06, AC-10): wired into the agent's I/O path at the
decision node, before the final ActionDecision is returned. Ensures no
card/account number ever leaks into a customer-facing rationale, and
that every decision carries the reference-only disclaimer.
"""

from __future__ import annotations

from src.guardrails.masking import mask_sensitive_text
from src.schemas import ActionDecision


def check_output(decision: ActionDecision) -> tuple[ActionDecision, list[str]]:
    """Returns (possibly-sanitized decision, flags raised)."""
    flags: list[str] = []

    masked_rationale = mask_sensitive_text(decision.rationale)
    if masked_rationale != decision.rationale:
        flags.append("masked_sensitive_data_in_rationale")
        decision = decision.model_copy(update={"rationale": masked_rationale})

    if "reference only" not in decision.disclaimer.lower() and "not a final" not in decision.disclaimer.lower():
        flags.append("missing_disclaimer_restored")
        decision = decision.model_copy(
            update={
                "disclaimer": (
                    "This is an automated triage recommendation, not a final "
                    "decision. A human analyst must review and approve any "
                    "credit, chargeback, or denial."
                )
            }
        )

    return decision, flags
