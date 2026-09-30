"""Context selection: hand-pick the state fields a given node actually
needs, instead of forwarding the entire accumulated state into every
prompt."""

from __future__ import annotations


def select_context_for(node_name: str, state: dict) -> dict:
    common = {"dispute_id": state.get("dispute_id")}

    if node_name == "dispute_classification":
        return {**common, "quarantined_narrative": state.get("quarantined_narrative")}

    if node_name == "chargeback_rules_retrieval":
        return {**common, "classification": state.get("classification")}

    if node_name == "fraud_scoring":
        return {
            **common,
            "classification": state.get("classification"),
            "quarantined_narrative": state.get("quarantined_narrative"),
        }

    if node_name == "decision":
        return {
            **common,
            "classification": state.get("classification"),
            "rule_match": state.get("rule_match"),
            "fraud_score": state.get("fraud_score"),
            "retry_count": state.get("retry_count", 0),
        }

    return common
