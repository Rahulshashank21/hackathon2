"""
Golden-signals report (run from .venv-phoenix, since it needs pandas to
read the exported spans): reads traces/phoenix_spans.parquet, computes
p50/p95 latency by span kind (thinking = LLM spans if any Gemini calls
were made, acting = graph-node CHAIN spans, tool = TOOL spans), pulls
token totals from any LLM spans present, estimates cost, and merges in
accuracy + hallucination rate from reports/eval_report.json.

    ./.venv-phoenix/bin/python scripts/build_golden_signals.py
"""

from __future__ import annotations

import json
import pathlib

import pandas as pd

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SPANS_PATH = REPO_ROOT / "traces" / "phoenix_spans.parquet"
EVAL_REPORT_PATH = REPO_ROOT / "reports" / "eval_report.json"
OUT_PATH = REPO_ROOT / "reports" / "golden_signals.json"

# Gemini Flash list pricing used only as an illustrative cost estimate
# (USD per 1K tokens) — see docs/model-card.md for the caveat that this
# is a concept-level estimate, not a billed invoice.
PRICE_PER_1K_INPUT_TOKENS = 0.000075
PRICE_PER_1K_OUTPUT_TOKENS = 0.0003


def _latency_ms(df: pd.DataFrame) -> pd.Series:
    return (df["end_time"] - df["start_time"]).dt.total_seconds() * 1000


def _percentile_by_group(df: pd.DataFrame, group_col: str, value_col: str) -> dict:
    out = {}
    for group, sub in df.groupby(group_col):
        out[str(group)] = {
            "count": int(len(sub)),
            "p50_ms": round(float(sub[value_col].quantile(0.5)), 2),
            "p95_ms": round(float(sub[value_col].quantile(0.95)), 2),
        }
    return out


def main() -> None:
    if not SPANS_PATH.exists():
        raise SystemExit(f"{SPANS_PATH} not found — run scripts/export_phoenix_traces.py first.")

    df = pd.read_parquet(SPANS_PATH)
    df["latency_ms"] = _latency_ms(df)

    kind_col = "attributes.openinference.span.kind"
    llm_spans = df[df[kind_col] == "LLM"] if kind_col in df.columns else df.iloc[0:0]
    tool_spans = df[df[kind_col] == "TOOL"] if kind_col in df.columns else df.iloc[0:0]
    chain_spans = df[df[kind_col] == "CHAIN"] if kind_col in df.columns else df.iloc[0:0]

    latency_by_type = {
        "thinking_llm": _percentile_by_group(llm_spans.assign(_g="llm"), "_g", "latency_ms") if len(llm_spans) else {
            "llm": {"count": 0, "note": "No LLM spans captured — GOOGLE_API_KEY was unset for this run, so all reasoning used the offline heuristic path (see src/nodes.py generation_mode='offline_stub'). Re-run with a key to populate this section."}
        },
        "acting_graph_nodes": _percentile_by_group(chain_spans, "name", "latency_ms"),
        "tool_calls": _percentile_by_group(tool_spans, "name", "latency_ms"),
    }

    token_cols = [c for c in df.columns if "token_count" in c.lower()]
    total_input_tokens = int(df.get("attributes.llm.token_count.prompt", pd.Series(dtype=float)).fillna(0).sum())
    total_output_tokens = int(df.get("attributes.llm.token_count.completion", pd.Series(dtype=float)).fillna(0).sum())
    estimated_cost_usd = round(
        (total_input_tokens / 1000) * PRICE_PER_1K_INPUT_TOKENS
        + (total_output_tokens / 1000) * PRICE_PER_1K_OUTPUT_TOKENS,
        6,
    )

    eval_summary = {}
    if EVAL_REPORT_PATH.exists():
        eval_report = json.loads(EVAL_REPORT_PATH.read_text())
        eval_summary = {
            "mode": eval_report.get("mode"),
            "accuracy": eval_report.get("aggregate", {}).get("answer_relevancy_mean"),
            "hallucination_rate": eval_report.get("aggregate", {}).get("hallucination_rate"),
            "faithfulness": eval_report.get("aggregate", {}).get("faithfulness_mean"),
        }
    else:
        eval_summary = {"note": "reports/eval_report.json not found — run scripts/run_eval.py first."}

    report = {
        "source": "Phoenix spans exported to traces/phoenix_spans.parquet",
        "total_spans": int(len(df)),
        "token_columns_present": token_cols,
        "latency_by_type": latency_by_type,
        "tokens": {"total_input_tokens": total_input_tokens, "total_output_tokens": total_output_tokens},
        "estimated_cost_usd": estimated_cost_usd,
        "eval": eval_summary,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, indent=2, default=str))
    print(f"Wrote {OUT_PATH}")
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
