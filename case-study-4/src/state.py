"""The typed state object shared across every node in the graph."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from src.schemas import ActionDecision, ChargebackRuleMatch, DisputeClassification, FraudScore


class TraceEvent(TypedDict):
    node: str
    event: str
    detail: str


class DisputeInvestigationState(TypedDict, total=False):
    # --- Input (write-once) ---
    dispute_id: str
    raw_dispute: dict[str, Any]
    quarantined_narrative: str  # sanitized, clearly-delimited version of raw_dispute["narrative"]
    narrative_flags: list[str]  # injection/PAN-exposure patterns detected during quarantine

    # --- Validated structured hand-offs ---
    classification: DisputeClassification | None
    rule_match: ChargebackRuleMatch | None
    fraud_score: FraudScore | None
    decision: ActionDecision | None

    # --- Control flow ---
    route: str
    retry_count: int
    max_retries_reached: bool
    errors: list[str]

    # --- Evidence / observability ---
    trace: Annotated[list[TraceEvent], lambda a, b: (a or []) + (b or [])]
