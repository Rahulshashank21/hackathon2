"""
Exports the Phoenix spans captured during a run to a committed trace
file (traces/phoenix_spans.parquet — falls back to .jsonl if pyarrow is
unavailable). Must be run from the SEPARATE .venv-phoenix environment
(see README "Why two virtual environments") since it needs the full
`arize-phoenix` package to query the server:

    ./.venv-phoenix/bin/python scripts/export_phoenix_traces.py

Assumes a Phoenix server is already running locally (launched via
scripts/start_phoenix_server.py or `python -m phoenix.server.main serve`)
and that the app has already been run at least once with
GOOGLE_API_KEY unset or set (either way spans are emitted — see
src/observability/tracing.py).
"""

from __future__ import annotations

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

PROJECT_NAME = "dispute-fraud-triage-copilot"
BASE_URL = "http://localhost:6006"


def main() -> None:
    from phoenix.client import Client

    client = Client(base_url=BASE_URL)
    df = client.spans.get_spans_dataframe(project_name=PROJECT_NAME, limit=5000)

    if df is None or len(df) == 0:
        print(
            "No spans found for project "
            f"{PROJECT_NAME!r} at {BASE_URL}. Make sure the Phoenix server is "
            "running and you have run at least one dispute through the main "
            "app venv first (`./.venv/bin/python cli.py run DSP-3001`)."
        )
        sys.exit(1)

    out_dir = REPO_ROOT / "traces"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        out_path = out_dir / "phoenix_spans.parquet"
        df.to_parquet(out_path)
    except ImportError:
        out_path = out_dir / "phoenix_spans.jsonl"
        df.to_json(out_path, orient="records", lines=True)

    print(f"Exported {len(df)} spans to {out_path}")

    # Also drop a lightweight CSV alongside for anything that wants a
    # quick look without a parquet/pyarrow dependency.
    csv_path = out_dir / "phoenix_spans_preview.csv"
    preview_cols = [
        c for c in ["name", "span_kind", "start_time", "end_time", "status_code", "attributes.tool.name"]
        if c in df.columns
    ]
    df[preview_cols].to_csv(csv_path, index=False)
    print(f"Wrote a preview CSV to {csv_path}")


if __name__ == "__main__":
    main()
