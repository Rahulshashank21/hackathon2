"""
PAN / account-number masking (NFR-05, Synthetic-Data Rule): defense in
depth so that even if a tool or model output ever included a raw card
or account number, it is masked before being logged or shown — never
written to logs or answers in plaintext.
"""

from __future__ import annotations

import re

# 13-19 digit runs (with optional spaces/dashes every 4) look like a PAN.
_PAN_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_ACCOUNT_RE = re.compile(r"\bACC-\d{4,}\b", re.IGNORECASE)


def mask_sensitive_text(text: str) -> str:
    if not text:
        return text
    masked = _PAN_RE.sub(lambda m: _mask_digit_run(m.group(0)), text)
    masked = _ACCOUNT_RE.sub(lambda m: f"ACC-***{m.group(0)[-3:]}", masked)
    return masked


def _mask_digit_run(run: str) -> str:
    digits = re.sub(r"[ -]", "", run)
    if len(digits) < 13:
        return run
    return f"**** **** **** {digits[-4:]}"
