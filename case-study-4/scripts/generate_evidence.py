"""
Regenerates every main-venv evidence artifact from a clean state
(Evidence-in-Repo Rule + Reproducibility Rule): rebuilds the RAG index,
runs all 5 sample disputes fresh, and runs the evaluation harness.

For the Phoenix-derived artifacts (traces/phoenix_spans.parquet,
reports/golden_signals.json, reports/dashboard.png/.csv) start the
Phoenix server first (see scripts/start_phoenix_server.py) — those
three scripts run from the separate .venv-phoenix environment, per
README "Why two virtual environments".

Run: `python cli.py regenerate-evidence` or `python scripts/generate_evidence.py`
(from the main .venv).
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

DISPUTE_IDS = ["DSP-3001", "DSP-3002", "DSP-3003", "DSP-3004", "DSP-3005"]


def _clean_state() -> None:
    for path in [
        REPO_ROOT / "data" / "memory" / "checkpoints.sqlite",
        REPO_ROOT / "data" / "memory" / "checkpoints.sqlite-wal",
        REPO_ROOT / "data" / "memory" / "checkpoints.sqlite-shm",
        REPO_ROOT / "data" / "memory" / "long_term_memory.sqlite",
        REPO_ROOT / "logs" / "tool_calls.jsonl",
        REPO_ROOT / "logs" / "agent_actions.jsonl",
    ]:
        path.unlink(missing_ok=True)
    for f in (REPO_ROOT / "traces").glob("run_transcript_*.json"):
        f.unlink()


def main() -> None:
    _clean_state()

    from src.tools.rag_tool import build_or_load_index

    build_or_load_index(force=False)

    for dispute_id in DISPUTE_IDS:
        print(f"Running {dispute_id} ...")
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "cli.py"), "run", dispute_id],
            cwd=REPO_ROOT,
        )
        if proc.returncode != 0:
            print(f"WARNING: {dispute_id} exited with code {proc.returncode}")

    print("\nRunning evaluation harness ...")
    subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "run_eval.py")], cwd=REPO_ROOT, check=True)

    print(
        "\nMain-venv evidence regenerated: logs/tool_calls.jsonl, "
        "logs/agent_actions.jsonl, traces/run_transcript_*.json, "
        "reports/eval_report.json.\n"
        "Now regenerate the Phoenix-derived artifacts from .venv-phoenix:\n"
        "  1. ./.venv-phoenix/bin/python scripts/start_phoenix_server.py  (separate terminal, leave running)\n"
        "  2. Re-run the disputes above so they get traced to the now-live server\n"
        "  3. ./.venv-phoenix/bin/python scripts/export_phoenix_traces.py\n"
        "  4. ./.venv-phoenix/bin/python scripts/build_golden_signals.py\n"
        "  5. ./.venv-phoenix/bin/python scripts/build_dashboard.py"
    )


if __name__ == "__main__":
    main()
