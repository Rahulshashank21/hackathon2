"""
Validated structured objects exchanged at every node handoff boundary
(structured output at node boundaries — LangGraph graph artifact
requirement). Each worker agent's raw output is parsed into one of
these before being merged into the shared graph state.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DisputeType = Literal[
    "unauthorized_transaction",
    "duplicate_charge",
    "goods_not_received",
    "billing_error",
    "subscription_cancelled",
    "ambiguous_or_out_of_scope",
]


class DisputeClassification(BaseModel):
    """Output of the dispute-classification worker."""

    dispute_id: str
    dispute_type: DisputeType
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str = ""


class ChargebackRuleMatch(BaseModel):
    """Output of the chargeback-rules-retrieval worker (agentic-RAG in the loop)."""

    dispute_id: str
    rule_code: str | None = None
    rule_name: str | None = None
    citation_snippet: str = ""
    filing_deadline_days: int | None = None
    documentation_required: list[str] = Field(default_factory=list)
    rag_tool_called: bool = False


class FraudScore(BaseModel):
    """Output of the fraud-scoring worker."""

    dispute_id: str
    fraud_score: float = Field(ge=0.0, le=1.0)
    top_factors: list[str] = Field(default_factory=list)
    tools_called: list[str] = Field(default_factory=list)


class ActionDecision(BaseModel):
    """Final structured recommendation."""

    dispute_id: str
    action: Literal["provisional_credit", "chargeback", "investigate", "deny", "clarify_with_customer"]
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)
    escalate_to_human: bool = False
    citations: list[str] = Field(default_factory=list)
    disclaimer: str = Field(
        default=(
            "This is an automated triage recommendation, not a final "
            "decision. A human analyst must review and approve any "
            "credit, chargeback, or denial."
        )
    )
    generation_mode: Literal["gemini", "offline_stub"] = "offline_stub"
