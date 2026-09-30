"""
Audit trail middleware (AC-10): machine-generated log of every
consequential agent action — a classification, a fraud score, an
escalation, or a final decision — to logs/agent_actions.jsonl.
{actor, action, tool, decision, timestamp} per the spec's format.
"""

from __future__ import annotations

import json
import time

from src.config import load_config, resolve_path
from src.guardrails.masking import mask_sensitive_text


def log_agent_action(actor: str, action: str, decision: str, tool: str | None = None) -> None:
    cfg = load_config()
    log_path = resolve_path(cfg["paths"]["logs_dir"]) / "agent_actions.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "timestamp": time.time(),
        "actor": actor,
        "action": action,
        "tool": tool,
        "decision": mask_sensitive_text(decision),
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
