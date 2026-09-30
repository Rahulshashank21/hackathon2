"""
Custom MCP server for the Transaction Dispute & Fraud-Triage Copilot
(artifact: mcp_server/ + logs/mcp_transcript.jsonl).

Exposes 3 tools and 1 resource over stdio via the official MCP Python
SDK's FastMCP helper:

  Tools:
    - transaction_lookup(transaction_id)   — transaction + masked account/card
    - prior_disputes_lookup(account_id)    — prior dispute history for the account
    - network_rule_check(dispute_type, transaction_id) — deterministic
      chargeback-rule engine (filing deadline, required docs, a
      high-value flag) — distinct from the agentic-RAG tool, which does
      semantic search over the richer policy corpus for citable prose.

  Resource:
    - dispute://reason-code-catalog — a static reference table of
      dispute-type -> network reason code, for quick lookup without a
      full RAG query.

NFR-05 / Synthetic-Data Rule: card PANs and account numbers are never
returned in full — every response is pre-masked before leaving this
process.

Run standalone for a manual smoke test: `python mcp_server/server.py`
(waits on stdio; Ctrl+C to exit). Normally launched as a subprocess by
src/mcp_client.py via langchain-mcp-adapters.
"""

from __future__ import annotations

import json
import pathlib
import sys

from mcp.server.fastmcp import FastMCP

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from mcp_server.dispute_data import (  # noqa: E402
    ACCOUNTS,
    NETWORK_RULES,
    PRIOR_DISPUTES,
    TRANSACTIONS,
    get_sample_dispute,
    mask_account,
    mask_pan,
)

HIGH_VALUE_THRESHOLD = 1000.00

mcp = FastMCP(
    name="dispute-fraud-triage-tools",
    instructions=(
        "Synthetic banking dispute/fraud back-office tools: transaction "
        "lookup, prior dispute history, and chargeback rule checks. All "
        "data is synthetic and for a training exercise only. Card/account "
        "numbers are always returned masked."
    ),
)


@mcp.tool()
def transaction_lookup(transaction_id: str) -> dict:
    """Return a transaction's details plus the masked account/card it
    belongs to."""
    txn = TRANSACTIONS.get(transaction_id)
    if txn is None:
        return {"error": f"Unknown transaction_id: {transaction_id}"}

    account = ACCOUNTS.get(txn["account_id"], {})
    return {
        "transaction_id": transaction_id,
        "merchant": txn["merchant"],
        "amount": txn["amount"],
        "currency": txn["currency"],
        "date": txn["date"],
        "channel": txn["channel"],
        "account_id": mask_account(txn["account_id"]),
        "card_pan_masked": mask_pan(account.get("card_pan", "")),
        "account_opened_date": account.get("opened_date"),
        "high_value": txn["amount"] >= HIGH_VALUE_THRESHOLD,
    }


@mcp.tool()
def prior_disputes_lookup(account_id: str) -> dict:
    """Return an account's prior (closed) dispute history."""
    if account_id not in ACCOUNTS:
        return {"error": f"Unknown account_id: {account_id}"}

    prior = PRIOR_DISPUTES.get(account_id, [])
    return {
        "account_id": mask_account(account_id),
        "prior_dispute_count": len(prior),
        "prior_disputes": prior,
    }


@mcp.tool()
def network_rule_check(dispute_type: str, transaction_id: str) -> dict:
    """Deterministic chargeback-rule engine: given a dispute type and the
    disputed transaction, return the applicable network rule code, the
    filing deadline, required documentation, and a high-value flag."""
    rule = NETWORK_RULES.get(dispute_type)
    if rule is None:
        return {"error": f"Unknown dispute_type: {dispute_type}"}

    txn = TRANSACTIONS.get(transaction_id)
    high_value = bool(txn and txn["amount"] >= HIGH_VALUE_THRESHOLD)

    return {
        "dispute_type": dispute_type,
        "rule_code": rule["rule_code"],
        "rule_name": rule["rule_name"],
        "filing_deadline_days": rule["filing_deadline_days"],
        "documentation_required": rule["documentation_required"],
        "high_value": high_value,
    }


REASON_CODE_CATALOG = {
    dispute_type: {"rule_code": r["rule_code"], "rule_name": r["rule_name"]}
    for dispute_type, r in NETWORK_RULES.items()
}


@mcp.resource("dispute://reason-code-catalog")
def reason_code_catalog() -> str:
    """A static reference table mapping dispute types to their network
    reason code and name, for quick lookup alongside a full RAG citation."""
    return json.dumps(REASON_CODE_CATALOG, indent=2)


if __name__ == "__main__":
    mcp.run()
