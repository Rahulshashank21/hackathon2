"""
Routing-logic tests: asserts the conditional edge functions in
src/nodes.py route to the right worker for given states, without
needing a live LLM call or MCP subprocess (these functions are pure
functions of state).
"""

from __future__ import annotations

from src.nodes import route_after_classification, route_after_decision, route_after_supervisor
from src.schemas import ActionDecision, DisputeClassification


def test_route_after_supervisor_continues_when_not_blocked():
    assert route_after_supervisor({"route": "continue"}) == "dispute_classification"


def test_route_after_supervisor_blocks_on_guardrail():
    assert route_after_supervisor({"route": "blocked"}) == "blocked_end"


def test_route_after_classification_escalates_ambiguous_type():
    classification = DisputeClassification(
        dispute_id="DSP-TEST", dispute_type="ambiguous_or_out_of_scope", confidence=0.9
    )
    assert route_after_classification({"classification": classification}) == "escalate_ambiguous"


def test_route_after_classification_escalates_low_confidence_even_if_typed():
    # A confidently-typed-looking classification but with low confidence
    # should still be escalated (AC-04: don't mishandle ambiguous cases).
    classification = DisputeClassification(
        dispute_id="DSP-TEST", dispute_type="unauthorized_transaction", confidence=0.1
    )
    assert route_after_classification({"classification": classification}) == "escalate_ambiguous"


def test_route_after_classification_continues_for_confident_specific_type():
    classification = DisputeClassification(
        dispute_id="DSP-TEST", dispute_type="duplicate_charge", confidence=0.9
    )
    assert route_after_classification({"classification": classification}) == "chargeback_rules_retrieval"


def test_route_after_decision_ends_on_high_confidence():
    decision = ActionDecision(
        dispute_id="DSP-TEST", action="chargeback", rationale="r", confidence=0.9
    )
    assert route_after_decision({"decision": decision, "retry_count": 0}) == "END"


def test_route_after_decision_reflects_on_low_confidence_with_retries_left():
    decision = ActionDecision(
        dispute_id="DSP-TEST", action="chargeback", rationale="r", confidence=0.3
    )
    assert route_after_decision({"decision": decision, "retry_count": 0}) == "reflect"


def test_route_after_decision_force_escalates_once_retries_exhausted():
    decision = ActionDecision(
        dispute_id="DSP-TEST", action="chargeback", rationale="r", confidence=0.3
    )
    # config/config.yaml reflection.max_retries is 1
    assert route_after_decision({"decision": decision, "retry_count": 1}) == "force_escalate"
