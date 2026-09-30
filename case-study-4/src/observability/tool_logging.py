"""
Tool-invocation logging middleware (AC-07): every MCP/RAG tool call made
by any worker is appended to logs/tool_calls.jsonl as
{timestamp, agent, tool_name, args, result, latency_ms, status} — tool
names here are the exact names registered in mcp_server/server.py and
src/tools/rag_tool.py, so they reconcile directly with the code.
"""

from __future__ import annotations

import json
import time

from src.config import load_config, resolve_path
from src.guardrails.masking import mask_sensitive_text


def log_tool_call(agent: str, tool_name: str, args: dict, result, latency_ms: float, status: str) -> None:
    cfg = load_config()
    log_path = resolve_path(cfg["paths"]["logs_dir"]) / "tool_calls.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "timestamp": time.time(),
        "agent": agent,
        "tool_name": tool_name,
        "args": args,
        "result": mask_sensitive_text(str(result))[:2000],
        "latency_ms": round(latency_ms, 2),
        "status": status,
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def wrap_tools_with_logging(tools: list, agent: str) -> list:
    """Returns the same tool objects with their coroutine replaced by a
    logging wrapper — used for both the Gemini tool-calling path and the
    offline heuristic path, so the tool-call log is real either way."""
    for t in tools:
        original_coroutine = t.coroutine

        def make_wrapper(tool_name: str, original):
            async def wrapper(*args, **kwargs):
                start = time.monotonic()
                status = "success"
                try:
                    result = await original(*args, **kwargs)
                    return result
                except Exception as exc:  # noqa: BLE001 - log then re-raise; caller handles fallback
                    status = "error"
                    result = str(exc)
                    raise
                finally:
                    latency_ms = (time.monotonic() - start) * 1000
                    # `result` may be a (content, artifact) tuple depending on
                    # the installed adapters version — log just the content
                    # half so the evidence log reads as the actual tool output.
                    logged_result = result[0] if isinstance(result, tuple) else result
                    log_tool_call(agent, tool_name, kwargs or {}, logged_result, latency_ms, status)

            return wrapper

        t.coroutine = make_wrapper(t.name, original_coroutine)
    return tools
