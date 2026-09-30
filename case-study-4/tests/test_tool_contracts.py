"""
Tool-contract tests: asserts each MCP tool's input/output schema and one
error path, calling the plain Python functions directly (no subprocess
needed — mcp_server/server.py's @mcp.tool()-decorated functions remain
directly callable).
"""

from __future__ import annotations

from mcp_server.server import network_rule_check, prior_disputes_lookup, transaction_lookup
from src.tools.rag_tool import chargeback_policy_lookup


def test_transaction_lookup_contract_success():
    result = transaction_lookup("TXN-90001")
    assert set(result.keys()) >= {
        "transaction_id", "merchant", "amount", "currency", "date", "channel",
        "account_id", "card_pan_masked", "high_value",
    }
    assert result["account_id"].startswith("ACCT-***")
    assert result["card_pan_masked"].startswith("**** **** ****")
    assert isinstance(result["amount"], float)
    assert isinstance(result["high_value"], bool)


def test_transaction_lookup_error_path():
    result = transaction_lookup("TXN-DOES-NOT-EXIST")
    assert "error" in result


def test_prior_disputes_lookup_contract_success():
    result = prior_disputes_lookup("ACC-70001")
    assert set(result.keys()) == {"account_id", "prior_dispute_count", "prior_disputes"}
    assert isinstance(result["prior_disputes"], list)
    assert result["prior_dispute_count"] == len(result["prior_disputes"])
    assert result["account_id"].startswith("ACCT-***")


def test_prior_disputes_lookup_error_path():
    result = prior_disputes_lookup("ACC-DOES-NOT-EXIST")
    assert "error" in result


def test_network_rule_check_contract_success():
    result = network_rule_check("unauthorized_transaction", "TXN-90001")
    assert set(result.keys()) == {
        "dispute_type", "rule_code", "rule_name", "filing_deadline_days",
        "documentation_required", "high_value",
    }
    assert isinstance(result["documentation_required"], list)
    assert isinstance(result["filing_deadline_days"], int)


def test_network_rule_check_error_path():
    result = network_rule_check("not_a_real_dispute_type", "TXN-90001")
    assert "error" in result


def test_chargeback_policy_lookup_rag_tool_contract():
    result = chargeback_policy_lookup.invoke({"query": "duplicate charge"})
    assert isinstance(result, str)
    assert len(result) > 0
