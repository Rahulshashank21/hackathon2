"""
Rich terminal UI for the Transaction Dispute & Fraud-Triage Copilot.
Provides formatted console dashboards, stage-by-stage pipeline visualization,
and an interactive terminal interface.
"""

from __future__ import annotations

import asyncio
import json
import pathlib
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


def _format_confidence_bar(confidence: float) -> str:
    bar_length = 15
    filled = int(confidence * bar_length)
    empty = bar_length - filled
    pct = int(confidence * 100)
    color = "green" if confidence >= 0.75 else "yellow" if confidence >= 0.5 else "red"
    return f"[{color}]{'█' * filled}{'░' * empty}[/{color}] [bold]{pct}%[/bold]"


def print_rich_dispute_result(dispute_id: str, result: dict, raw_dispute: dict | None = None) -> None:
    raw = raw_dispute or result.get("raw_dispute") or {}
    decision = result.get("decision")
    trace = result.get("trace", [])

    # 1. Header: Dispute Overview Panel
    header_table = Table.grid(padding=(0, 2))
    header_table.add_column(style="bold cyan", justify="right")
    header_table.add_column()
    header_table.add_column(style="bold cyan", justify="right")
    header_table.add_column()

    header_table.add_row(
        "Dispute ID:", f"[bold white]{dispute_id}[/bold white]",
        "Account:", f"[yellow]{raw.get('account_id', 'N/A')}[/yellow]",
    )
    amt = raw.get("amount", 0.0)
    header_table.add_row(
        "Transaction ID:", f"{raw.get('transaction_id', 'N/A')}",
        "Amount:", f"[bold green]${amt:,.2f}[/bold green]" if amt else "$0.00",
    )
    header_table.add_row(
        "Filed Date:", f"{raw.get('filed_date', 'N/A')}",
        "Channel:", f"{raw.get('channel', 'N/A')}",
    )

    console.print()
    console.print(Panel(
        header_table,
        title=f"[bold blue]💳 Dispute Triage Copilot — {dispute_id}[/bold blue]",
        border_style="blue",
        box=box.ROUNDED,
    ))

    # 2. Customer Narrative & Guardrail Status
    narrative = raw.get("narrative", "")
    if narrative:
        quarantine_events = [e for e in trace if e.get("node") == "supervisor" and "quarantine" in e.get("event", "")]
        flagged = any("flagged" in e.get("event", "") for e in quarantine_events)
        blocked = any(e.get("node") == "supervisor" and "blocked" in e.get("event", "") for e in trace)

        status_text = Text()
        if blocked:
            status_text.append("🚫 INPUT BLOCKED BY GUARDRAIL (Cross-Account Attempt)\n", style="bold red")
        elif flagged:
            status_text.append("⚠️ PROMPT INJECTION DETECTED & QUARANTINED\n", style="bold yellow")
        else:
            status_text.append("✅ Narrative Verified (No Injection Patterns)\n", style="bold green")

        status_text.append(f'"{narrative}"', style="italic white")
        console.print(Panel(status_text, title="[bold]Customer Narrative & Input Guardrails[/bold]", box=box.ROUNDED, border_style="red" if blocked else "yellow" if flagged else "green"))

    # 3. Multi-Agent Execution Steps (show events from the latest run)
    if trace:
        last_start = 0
        for idx, event in enumerate(trace):
            if event.get("event") == "dispute_received":
                last_start = idx
        current_trace = trace[last_start:]

        trace_table = Table(title="🤖 Multi-Agent Execution Trace", box=box.ROUNDED, show_header=True, header_style="bold magenta")
        trace_table.add_column("Agent / Node", style="cyan", width=25)
        trace_table.add_column("Event", style="yellow", width=26)
        trace_table.add_column("Detail", style="white")

        for event in current_trace:
            node = event.get("node", "")
            evt = event.get("event", "")
            detail = event.get("detail", "")
            node_display = {
                "supervisor": "🛡️ Supervisor",
                "dispute_classification": "🏷️ Classification",
                "chargeback_rules_retrieval": "📜 Rules & Policy RAG",
                "fraud_scoring": "🔍 Fraud Scoring",
                "decision": "⚖️ Decision Engine",
                "reflect": "🔄 Reflection Loop",
                "force_escalate": "🚨 Force Escalate",
                "blocked_end": "🛑 Blocked End",
                "escalate_ambiguous": "❓ Ambiguity Escalate",
            }.get(node, node)
            trace_table.add_row(node_display, evt, str(detail)[:120] + ("..." if len(str(detail)) > 120 else ""))
        console.print(trace_table)

    # 4. Final Triage Recommendation Panel
    if decision is None:
        console.print(Panel(
            f"[bold yellow]Dispute paused (human-in-the-loop breakpoint reached).[/bold yellow]\nRun `python cli.py resume {dispute_id}` to proceed.",
            title="[bold yellow]Paused at Checkpoint[/bold yellow]",
            box=box.ROUNDED,
            border_style="yellow",
        ))
    else:
        action = decision.action.upper()
        action_color = {
            "INVESTIGATE": "bold red",
            "CHARGEBACK": "bold blue",
            "PROVISIONAL_CREDIT": "bold green",
            "CLARIFY_WITH_CUSTOMER": "bold yellow",
            "DENY": "bold red",
        }.get(action, "bold white")

        escalate_badge = "[bold red]⚠️ ESCALATE TO HUMAN ANALYST[/bold red]" if decision.escalate_to_human else "[bold green]✓ AUTOMATED RESOLUTION APPROVED[/bold green]"
        citations = ", ".join(decision.citations) if decision.citations else "None"

        body = (
            f"[bold]Action:[/bold] [{action_color}]{action}[/{action_color}]   "
            f"[bold]Review Status:[/bold] {escalate_badge}\n"
            f"[bold]Confidence:[/bold] {_format_confidence_bar(decision.confidence)}   "
            f"[bold]Network Citations:[/bold] [cyan]{citations}[/cyan]   "
            f"[bold]Engine:[/bold] [dim]{getattr(decision, 'generation_mode', 'standard')}[/dim]\n\n"
            f"[bold]Rationale:[/bold]\n{decision.rationale}\n\n"
            f"[dim]Compliance Disclaimer: {decision.disclaimer}[/dim]"
        )

        border = "red" if decision.escalate_to_human else "green"
        console.print(Panel(
            body,
            title="[bold green]📋 Final Triage Recommendation[/bold green]",
            box=box.DOUBLE,
            border_style=border,
        ))

    console.print(f"[dim]Audit transcript saved to: traces/run_transcript_{dispute_id}.json[/dim]\n")
