#!/usr/bin/env python3
"""
Single-command CLI for the Transaction Dispute & Fraud-Triage Copilot
(NFR-02).

Usage:
    python cli.py run DSP-3001
    python cli.py run DSP-3001 --pause-before fraud_scoring
    python cli.py resume DSP-3001
    python cli.py state DSP-3001
    python cli.py build-rag-index
    python cli.py recall "prior dispute history" --account ACC-70001
    python cli.py regenerate-evidence   # runs all sample disputes + rebuilds traces/reports/eval
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from src.config import resolve_path  # noqa: E402
from src.pipeline import get_checkpoint_state, resume_dispute, run_dispute  # noqa: E402
from src.tools.rag_tool import build_or_load_index  # noqa: E402
from src.rich_ui import print_rich_dispute_result  # noqa: E402
from src.trace import dump_transcript  # noqa: E402


def _print_result(dispute_id: str, result: dict) -> None:
    trace = result.get("trace", [])
    out_path = resolve_path("traces") / f"run_transcript_{dispute_id}.json"
    dump_transcript(dispute_id, trace, out_path)

    try:
        print_rich_dispute_result(dispute_id, result)
    except Exception:
        result_decision = result.get("decision")
        if result_decision is None:
            print(f"Dispute {dispute_id}: paused (no decision yet). Run `python cli.py resume {dispute_id}`.")
        else:
            print(f"Dispute {dispute_id}: action={result_decision.action} confidence={result_decision.confidence} escalate={result_decision.escalate_to_human}")
            print(f"  rationale: {result_decision.rationale}")
            print(f"  citations: {result_decision.citations}")
            print(f"  disclaimer: {result_decision.disclaimer}")
        print(f"  Transcript written to {out_path}")


async def _run(args: argparse.Namespace) -> None:
    interrupt_before = [args.pause_before] if args.pause_before else None
    result = await run_dispute(args.dispute_id, interrupt_before=interrupt_before)
    _print_result(args.dispute_id, result)


async def _resume(args: argparse.Namespace) -> None:
    result = await resume_dispute(args.dispute_id)
    _print_result(args.dispute_id, result)


async def _state(args: argparse.Namespace) -> None:
    state = await get_checkpoint_state(args.dispute_id)
    if state is None:
        print(f"No checkpoint found for dispute {args.dispute_id}.")
        return
    printable = {k: (v.model_dump() if hasattr(v, "model_dump") else v) for k, v in state.items()}
    print(json.dumps(printable, indent=2, default=str))


async def _recall(args: argparse.Namespace) -> None:
    from src.memory import open_memory_store, recall

    async with open_memory_store() as store:
        results = await recall(store, args.account, args.query)
    print(json.dumps(results, indent=2, default=str))


async def _interactive() -> None:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt

    console = Console()
    cases = [
        ("DSP-3001", "Unauthorized $2,450 purchase at GlobalTech Electronics (with prompt injection)"),
        ("DSP-3002", "Duplicate coffee charge $42.50 at CityCafe"),
        ("DSP-3003", "Rewards points balance inquiry (out-of-scope / ambiguous)"),
        ("DSP-3004", "Borderline fraud $180 charge at QuickMart (triggers reflection retry)"),
        ("DSP-3005", "Customer requesting information about another account (cross-account attack)"),
    ]

    while True:
        menu_lines = [
            f"[bold cyan][{i}][/bold cyan] [bold]{cid}[/bold]: {desc}"
            for i, (cid, desc) in enumerate(cases, 1)
        ]
        menu_lines.append("[bold cyan][6][/bold cyan] Semantic Memory Recall")
        menu_lines.append("[bold cyan][7][/bold cyan] Rebuild RAG Vector Index")
        menu_lines.append("[bold cyan][q][/bold cyan] Exit")

        console.print(
            Panel(
                "[bold white]Select a dispute to triage with the Multi-Agent Copilot:[/bold white]\n\n"
                + "\n".join(menu_lines),
                title="[bold blue]💳 Dispute Triage Copilot — Interactive CLI[/bold blue]",
                border_style="blue",
            )
        )
        choice = Prompt.ask("Enter option", default="1")
        if choice.lower() in ("q", "quit", "exit"):
            break
        if choice in ("1", "2", "3", "4", "5"):
            dispute_id = cases[int(choice) - 1][0]
            console.print(f"\n[bold green]Running {dispute_id} through LangGraph multi-agent pipeline...[/bold green]\n")
            result = await run_dispute(dispute_id)
            _print_result(dispute_id, result)
        elif choice == "6":
            acc = Prompt.ask("Account ID", default="ACC-70001")
            q = Prompt.ask("Query", default="prior dispute history")
            from src.memory import open_memory_store, recall

            async with open_memory_store() as store:
                results = await recall(store, acc, q)
            console.print_json(json.dumps(results, indent=2, default=str))
        elif choice == "7":
            build_or_load_index(force=True)
            console.print("[green]RAG index rebuilt successfully.[/green]")


def _web(args: argparse.Namespace) -> None:
    import http.server
    import socketserver
    import webbrowser

    port = args.port
    dashboard_file = resolve_path("reports/dashboard.html")
    if not dashboard_file.exists():
        print(f"Dashboard file not found at {dashboard_file}")
        return

    class Handler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/", "/index.html", "/dashboard"):
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(dashboard_file.read_bytes())
            elif self.path == "/api/cases":
                cases = {}
                sample_dir = resolve_path("data/sample_disputes")
                for f in sorted(sample_dir.glob("DSP-*.json")):
                    cases[f.stem] = json.loads(f.read_text(encoding="utf-8"))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(cases).encode("utf-8"))
            else:
                super().do_GET()

        def do_POST(self):
            if self.path == "/api/triage":
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                try:
                    payload = json.loads(body.decode("utf-8"))
                    dispute_id = payload.get("dispute_id")
                    from src.pipeline import run_custom_dispute, run_dispute

                    if dispute_id and not payload.get("is_custom"):
                        result = asyncio.run(run_dispute(dispute_id))
                    else:
                        raw = payload.get("raw_dispute") or {
                            "dispute_id": dispute_id or "DSP-CUSTOM",
                            "account_id": payload.get("account_id", "ACC-70001"),
                            "transaction_id": payload.get("transaction_id", "TXN-CUSTOM"),
                            "amount": float(payload.get("amount", 100.0)),
                            "filed_date": "2026-09-29",
                            "narrative": payload.get("narrative", ""),
                        }
                        result = asyncio.run(run_custom_dispute(raw))

                    resp_data = {
                        "dispute_id": result.get("raw_dispute", {}).get("dispute_id", dispute_id),
                        "decision": result.get("decision").model_dump() if hasattr(result.get("decision"), "model_dump") else result.get("decision"),
                        "trace": result.get("trace", []),
                        "raw_dispute": result.get("raw_dispute"),
                    }
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(resp_data, default=str).encode("utf-8"))
                except Exception as exc:
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))
            else:
                self.send_error(404)

    print(f"\n🚀 Dispute & Fraud-Triage Copilot Web UI running at http://localhost:{port}")
    print("Press Ctrl+C to stop.\n")
    try:
        webbrowser.open(f"http://localhost:{port}")
    except Exception:
        pass
    try:
        with socketserver.TCPServer(("", port), Handler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping web server.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Transaction Dispute & Fraud-Triage Copilot")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("interactive", help="Launch interactive Rich terminal copilot.")

    web_parser = subparsers.add_parser("web", help="Launch local interactive Web UI dashboard.")
    web_parser.add_argument("--port", type=int, default=8080)

    run_parser = subparsers.add_parser("run", help="Run a dispute through the graph.")
    run_parser.add_argument("dispute_id")
    run_parser.add_argument("--pause-before", type=str, default=None)

    resume_parser = subparsers.add_parser("resume", help="Resume a paused dispute investigation.")
    resume_parser.add_argument("dispute_id")

    state_parser = subparsers.add_parser("state", help="Print the current checkpointed state for a dispute.")
    state_parser.add_argument("dispute_id")

    subparsers.add_parser("build-rag-index", help="(Re)build the chargeback-policy RAG index.")

    recall_parser = subparsers.add_parser("recall", help="Semantically recall a long-term memory fact.")
    recall_parser.add_argument("query")
    recall_parser.add_argument("--account", default="ACC-70001")

    subparsers.add_parser(
        "regenerate-evidence",
        help="Run every sample dispute and regenerate all committed evidence artifacts.",
    )

    args = parser.parse_args()

    if args.command == "interactive":
        asyncio.run(_interactive())
    elif args.command == "web":
        _web(args)
    elif args.command == "run":
        asyncio.run(_run(args))
    elif args.command == "resume":
        asyncio.run(_resume(args))
    elif args.command == "state":
        asyncio.run(_state(args))
    elif args.command == "build-rag-index":
        build_or_load_index(force=True)
        print("RAG index rebuilt.")
    elif args.command == "recall":
        asyncio.run(_recall(args))
    elif args.command == "regenerate-evidence":
        from scripts.generate_evidence import main as generate_evidence_main

        generate_evidence_main()


if __name__ == "__main__":
    main()
