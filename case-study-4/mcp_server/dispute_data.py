"""
Synthetic "core banking / card-network" data the MCP server's tools
query: transactions, prior disputes, and a deterministic chargeback
rule engine. All data here is authored for this exercise — no real
account, card, or PII data (Synthetic-Data Rule). Card numbers (PANs)
and account numbers are synthetic and always shown masked.
"""

from __future__ import annotations

import json
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SAMPLE_DISPUTES_DIR = REPO_ROOT / "data" / "sample_disputes"


def mask_pan(pan: str) -> str:
    digits = pan.replace(" ", "").replace("-", "")
    return f"**** **** **** {digits[-4:]}" if len(digits) >= 4 else "****"


def mask_account(account_id: str) -> str:
    return f"ACCT-***{account_id[-3:]}" if len(account_id) >= 3 else "ACCT-***"


# --- Accounts (synthetic) ----------------------------------------------------
ACCOUNTS: dict[str, dict] = {
    "ACC-70001": {
        "account_id": "ACC-70001",
        "holder_name": "Jordan Blake",
        "card_pan": "4111111111111234",
        "opened_date": "2023-02-10",
    },
    "ACC-70002": {
        "account_id": "ACC-70002",
        "holder_name": "Morgan Ellis",
        "card_pan": "4111111111115678",
        "opened_date": "2021-06-01",
    },
    "ACC-70003": {
        "account_id": "ACC-70003",
        "holder_name": "Sam Okafor",
        "card_pan": "4111111111119012",
        "opened_date": "2025-12-01",
    },
    "ACC-70004": {
        "account_id": "ACC-70004",
        "holder_name": "Alex Kim",
        "card_pan": "4111111111113456",
        "opened_date": "2020-01-15",
    },
}

# --- Transactions (synthetic), keyed by transaction_id -----------------------
TRANSACTIONS: dict[str, dict] = {
    "TXN-90001": {
        "transaction_id": "TXN-90001",
        "account_id": "ACC-70001",
        "merchant": "GlobalTech Electronics",
        "amount": 2450.00,
        "currency": "USD",
        "date": "2026-09-14",
        "channel": "card_not_present",
    },
    "TXN-90002": {
        "transaction_id": "TXN-90002",
        "account_id": "ACC-70002",
        "merchant": "CityCafe #482",
        "amount": 42.50,
        "currency": "USD",
        "date": "2026-09-18",
        "channel": "card_present",
    },
    "TXN-90003": {
        "transaction_id": "TXN-90003",
        "account_id": "ACC-70002",
        "merchant": "CityCafe #482",
        "amount": 42.50,
        "currency": "USD",
        "date": "2026-09-18",
        "channel": "card_present",
    },
    "TXN-90004": {
        "transaction_id": "TXN-90004",
        "account_id": "ACC-70003",
        "merchant": "StreamPlus Subscriptions",
        "amount": 14.99,
        "currency": "USD",
        "date": "2026-09-20",
        "channel": "recurring",
    },
    "TXN-90005": {
        "transaction_id": "TXN-90005",
        "account_id": "ACC-70004",
        "merchant": "QuickMart Online",
        "amount": 180.00,
        "currency": "USD",
        "date": "2026-09-21",
        "channel": "card_not_present",
    },
}

# --- Prior (closed) disputes, keyed by account_id -----------------------------
PRIOR_DISPUTES: dict[str, list[dict]] = {
    "ACC-70001": [
        {"dispute_id": "DSP-1001", "date": "2026-05-02", "type": "unauthorized_transaction", "outcome": "chargeback_approved"},
        {"dispute_id": "DSP-1002", "date": "2026-07-19", "type": "unauthorized_transaction", "outcome": "chargeback_approved"},
    ],
    "ACC-70002": [],
    "ACC-70003": [],
    "ACC-70004": [
        {"dispute_id": "DSP-1010", "date": "2025-11-11", "type": "unauthorized_transaction", "outcome": "provisional_credit_finalized"},
    ],
}

# Chargeback reason-code rule engine (deterministic, synthetic).
NETWORK_RULES: dict[str, dict] = {
    "unauthorized_transaction": {
        "rule_code": "VISA-10.4",
        "rule_name": "Other Fraud - Card-Absent Environment",
        "filing_deadline_days": 120,
        "documentation_required": ["cardholder fraud affidavit", "transaction detail"],
    },
    "duplicate_charge": {
        "rule_code": "VISA-12.6.1",
        "rule_name": "Duplicate Processing",
        "filing_deadline_days": 120,
        "documentation_required": ["both transaction records", "cardholder statement"],
    },
    "goods_not_received": {
        "rule_code": "MC-4855",
        "rule_name": "Goods or Services Not Provided",
        "filing_deadline_days": 120,
        "documentation_required": ["proof of non-delivery", "merchant contact attempt"],
    },
    "billing_error": {
        "rule_code": "VISA-12.5",
        "rule_name": "Incorrect Transaction Amount",
        "filing_deadline_days": 120,
        "documentation_required": ["receipt showing correct amount"],
    },
    "subscription_cancelled": {
        "rule_code": "MC-4841",
        "rule_name": "Cancelled Recurring Transaction",
        "filing_deadline_days": 90,
        "documentation_required": ["cancellation confirmation"],
    },
}


def _load_sample_disputes() -> dict[str, dict]:
    disputes = {}
    if not SAMPLE_DISPUTES_DIR.exists():
        return disputes
    for path in sorted(SAMPLE_DISPUTES_DIR.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        disputes[record["dispute_id"]] = record
    return disputes


def get_sample_dispute(dispute_id: str) -> dict | None:
    return _load_sample_disputes().get(dispute_id)
