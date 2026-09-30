"""
Graph assembly: a typed-state StateGraph with a supervisor, three
named worker agents (dispute_classification, chargeback_rules_retrieval,
fraud_scoring) plus a decision synthesis node, two escalation/guard
nodes, and conditional edges driven entirely by state.

    START -> supervisor
                |
      (route_after_supervisor: input guardrail)
         /                          \\
   blocked_end (END)         dispute_classification
                                     |
                     (route_after_classification: AC-04 ambiguity guard)
                       /                              \\
            escalate_ambiguous (END)         chargeback_rules_retrieval
                                                        |
                                                  fraud_scoring  <-+
                                                        |          |
                                                    decision       |
                                              (route_after_decision)
                                       /              |             \\
                                    END       force_escalate (END)  reflect
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from src.nodes import (
    blocked_end,
    chargeback_rules_retrieval,
    decision,
    dispute_classification,
    escalate_ambiguous,
    force_escalate,
    fraud_scoring,
    reflect,
    route_after_classification,
    route_after_decision,
    route_after_supervisor,
    supervisor,
)
from src.state import DisputeInvestigationState


def build_graph() -> StateGraph:
    graph = StateGraph(DisputeInvestigationState)

    graph.add_node("supervisor", supervisor)
    graph.add_node("blocked_end", blocked_end)
    graph.add_node("dispute_classification", dispute_classification)
    graph.add_node("escalate_ambiguous", escalate_ambiguous)
    graph.add_node("chargeback_rules_retrieval", chargeback_rules_retrieval)
    graph.add_node("fraud_scoring", fraud_scoring)
    graph.add_node("decision", decision)
    graph.add_node("reflect", reflect)
    graph.add_node("force_escalate", force_escalate)

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {"blocked_end": "blocked_end", "dispute_classification": "dispute_classification"},
    )
    graph.add_edge("blocked_end", END)

    graph.add_conditional_edges(
        "dispute_classification",
        route_after_classification,
        {"escalate_ambiguous": "escalate_ambiguous", "chargeback_rules_retrieval": "chargeback_rules_retrieval"},
    )
    graph.add_edge("escalate_ambiguous", END)
    graph.add_edge("chargeback_rules_retrieval", "fraud_scoring")
    graph.add_edge("fraud_scoring", "decision")

    graph.add_conditional_edges(
        "decision",
        route_after_decision,
        {"END": END, "reflect": "reflect", "force_escalate": "force_escalate"},
    )
    graph.add_edge("reflect", "fraud_scoring")
    graph.add_edge("force_escalate", END)

    return graph
