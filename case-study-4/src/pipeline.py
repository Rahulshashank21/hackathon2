"""
Runs a dispute through the compiled graph, owning the checkpointer's
connection lifetime and writing a long-term-memory fact after each
completed investigation. Also where tracing gets initialized — called
from here (the run path), not just imported (mandated Phoenix wiring).
"""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from src.config import load_config, resolve_path
from src.graph import build_graph
from src.memory import evict_lru_if_over_capacity, open_memory_store, remember
from src.observability.tracing import init_tracing
from src.state import DisputeInvestigationState

_IMPORTANCE_BY_ACTION = {
    "chargeback": 0.8,
    "investigate": 0.9,
    "provisional_credit": 0.5,
    "deny": 0.5,
    "clarify_with_customer": 0.4,
}


def load_dispute(dispute_id: str) -> dict:
    cfg = load_config()
    path = resolve_path(cfg["paths"]["sample_disputes_dir"]) / f"{dispute_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


@asynccontextmanager
async def _checkpointer():
    cfg = load_config()
    db_path = resolve_path(cfg["paths"]["checkpoint_db"])
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with AsyncSqliteSaver.from_conn_string(str(db_path)) as saver:
        yield saver


async def _write_memory_fact(dispute_id: str, final_state: dict) -> None:
    result = final_state.get("decision")
    if result is None:
        return
    fact = (
        f"Dispute {dispute_id} (account {final_state['raw_dispute']['account_id']}): "
        f"action={result.action}, confidence={result.confidence}, escalated={result.escalate_to_human}, "
        f"rationale={result.rationale}"
    )
    importance = _IMPORTANCE_BY_ACTION.get(result.action, 0.5)
    async with open_memory_store() as store:
        await remember(store, final_state["raw_dispute"]["account_id"], fact, importance=importance, dispute_id=dispute_id)
        await evict_lru_if_over_capacity(store, final_state["raw_dispute"]["account_id"])


async def run_dispute(dispute_id: str, interrupt_before: list[str] | None = None) -> dict:
    init_tracing()
    raw_dispute = load_dispute(dispute_id)
    initial_state: DisputeInvestigationState = {"raw_dispute": raw_dispute}

    async with _checkpointer() as checkpointer:
        graph = build_graph().compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": dispute_id}}
        result = await graph.ainvoke(initial_state, config=config, interrupt_before=interrupt_before)

    if result.get("decision") is not None:
        await _write_memory_fact(dispute_id, result)
    return result


async def run_custom_dispute(raw_dispute: dict, interrupt_before: list[str] | None = None) -> dict:
    """Run a custom dispute dict submitted from the Web UI through the compiled graph."""
    init_tracing()
    dispute_id = raw_dispute.get("dispute_id") or f"DSP-USER-{uuid.uuid4().hex[:6].upper()}"
    raw_dispute["dispute_id"] = dispute_id
    initial_state: DisputeInvestigationState = {"raw_dispute": raw_dispute}

    async with _checkpointer() as checkpointer:
        graph = build_graph().compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": dispute_id}}
        result = await graph.ainvoke(initial_state, config=config, interrupt_before=interrupt_before)

    if result.get("decision") is not None:
        await _write_memory_fact(dispute_id, result)
    return result


async def resume_dispute(dispute_id: str) -> dict:
    init_tracing()
    async with _checkpointer() as checkpointer:
        graph = build_graph().compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": dispute_id}}
        result = await graph.ainvoke(None, config=config)

    if result.get("decision") is not None:
        await _write_memory_fact(dispute_id, result)
    return result


async def get_checkpoint_state(dispute_id: str) -> dict | None:
    async with _checkpointer() as checkpointer:
        graph = build_graph().compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": dispute_id}}
        snapshot = await graph.aget_state(config)
        return snapshot.values if snapshot else None
