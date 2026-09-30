"""Structured trace/event logging. Every node appends TraceEvent entries
to state["trace"]; this module also mirrors them to the standard
logging module with PII masking, and dumps a claim's full trace to a
committed JSON transcript."""

from __future__ import annotations

import json
import logging

from src.config import load_config, resolve_path
from src.guardrails.masking import mask_sensitive_text

_configured = False


def _ensure_configured() -> None:
    global _configured
    if _configured:
        return
    cfg = load_config()
    log_path = resolve_path(cfg["paths"]["logs_dir"]) / "run.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_path), logging.StreamHandler()],
    )
    _configured = True


def make_event(node: str, event: str, detail: str) -> dict:
    _ensure_configured()
    logging.getLogger(f"copilot.{node}").info("%s: %s", event, mask_sensitive_text(detail)[:500])
    return {"node": node, "event": event, "detail": detail}


def dump_transcript(dispute_id: str, trace: list[dict], out_path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"dispute_id": dispute_id, "trace": trace}, indent=2, default=str))
