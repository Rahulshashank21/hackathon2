"""
Loop / cascade guard tests: asserts the reflection loop cannot run
forever — a max-retries limit forces an exit (force_escalate) rather
than looping indefinitely, and the compiled graph itself carries a
LangGraph recursion_limit safety net as a second, independent bound.
"""

from __future__ import annotations

from typing import TypedDict

import pytest
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph

from src.config import load_config
from src.nodes import route_after_decision
from src.schemas import ActionDecision


def test_reflection_retry_count_never_exceeds_configured_max():
    """Simulates the loop by repeatedly asking route_after_decision what
    to do next for a permanently-low-confidence decision, and asserts it
    terminates (reaches force_escalate) within max_retries + 1 checks —
    it must never keep returning 'reflect' forever."""
    max_retries = load_config()["reflection"]["max_retries"]
    low_confidence_decision = ActionDecision(
        dispute_id="DSP-LOOP-TEST", action="investigate", rationale="always ambiguous", confidence=0.0
    )

    retry_count = 0
    for _ in range(max_retries + 5):  # loop far past the bound to prove it stops
        route = route_after_decision({"decision": low_confidence_decision, "retry_count": retry_count})
        if route == "force_escalate":
            break
        assert route == "reflect", f"unexpected route {route!r} at retry_count={retry_count}"
        retry_count += 1
    else:
        pytest.fail(f"route_after_decision never reached force_escalate within {max_retries + 5} iterations")

    assert retry_count <= max_retries


# --- module-level fixtures for the recursion-limit test below --------------
# (must be module-level, not nested in the test function, so LangGraph's
# get_type_hints() can resolve the TypedDict/annotation names)

class _LoopState(TypedDict):
    count: int


def _bump(state: _LoopState) -> dict:
    return {"count": state.get("count", 0) + 1}


def _always_loop(state: _LoopState) -> str:
    return "loop"  # never returns "end" — simulates a routing bug


def test_langgraph_recursion_limit_stops_a_genuinely_unbounded_loop():
    """Independent second safety net: even if a routing function had a
    bug and looped forever (unlike our real, bounded route_after_decision
    tested above), LangGraph's own recursion_limit must still stop it
    rather than hanging. Builds a tiny two-node graph with a deliberately
    infinite conditional edge and asserts it raises GraphRecursionError
    within a small configured limit."""
    tiny_graph = StateGraph(_LoopState)
    tiny_graph.add_node("bump", _bump)
    tiny_graph.add_edge(START, "bump")
    tiny_graph.add_conditional_edges("bump", _always_loop, {"loop": "bump", "end": END})
    compiled = tiny_graph.compile()

    with pytest.raises(GraphRecursionError):
        compiled.invoke({"count": 0}, config={"recursion_limit": 5})
