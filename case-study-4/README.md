# Transaction Dispute & Fraud-Triage Copilot

**Business Case:** BC-AAIE-HACK-03 · Banking & Finance · Agentic Core +
Context Engineering + MCP + Observability + Cost Governance + Security
& Governance + Agent Evaluation

A LangGraph multi-agent copilot that triages a flagged transaction
dispute end-to-end: classifies the dispute type and cites the matching
network chargeback rule (agentic-RAG), scores fraud likelihood via a
custom MCP tool server, and drafts a recommended next action with an
audit trail — instrumented with Arize Phoenix, governed for cost/
latency, hardened with guardrails, documented for compliance, and
evaluated with DeepEval + pytest agent tests.

## Quick Start

```bash
# 1. Main application environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # optional: add GOOGLE_API_KEY for real Gemini reasoning

python cli.py build-rag-index                        # one-time: embed the chargeback-policy corpus
python cli.py run DSP-3001                           # strong fraud signal + adversarial narrative -> investigate + escalate
python cli.py run DSP-3002                           # clean duplicate charge -> provisional_credit, no escalation
python cli.py run DSP-3003                           # ambiguous/out-of-scope -> escalate for clarification
python cli.py run DSP-3004                           # borderline fraud score -> reflection retry -> forced escalate
python cli.py run DSP-3005                           # cross-account request -> refused by the input guardrail
python cli.py recall "prior dispute history" --account ACC-70001

pytest tests/ -v                                     # routing, loop-guard, tool-contract, memory-persistence tests
python cli.py regenerate-evidence                    # SECOND command: reruns everything + the eval harness
```

To regenerate the **Phoenix-derived** evidence (traces, golden-signals
report, cost/latency dashboard) you need the separate observability
environment — see "Why two virtual environments" below:

```bash
# 2. Observability environment (separate terminal)
python -m venv .venv-phoenix
source .venv-phoenix/bin/activate
pip install -r requirements-phoenix.txt

python scripts/start_phoenix_server.py          # leave running; UI at http://localhost:6006
# (in the main-venv terminal) re-run the disputes above so they get traced
python scripts/export_phoenix_traces.py         # -> traces/phoenix_spans.parquet
python scripts/build_golden_signals.py          # -> reports/golden_signals.json
python scripts/build_dashboard.py               # -> reports/dashboard.png + dashboard_data.csv
```

No Docker, no external database service — everything (checkpointer,
long-term memory, RAG index, MCP server, Phoenix) is a local SQLite
file, in-process Chroma directory, or a locally-run server process.

## Why Two Virtual Environments

`arize-phoenix`'s full package transitively requires `mcp>=2.0` (via
`pydantic-ai` → `fastmcp`), while this project's own MCP server/client
stack needs `mcp<2` (the stable `FastMCP` v1 API paired with a
compatible `langchain-mcp-adapters` release — `mcp>=2` renamed
`FastMCP` to `MCPServer` and no adapters release we tested was
mutually compatible with both `mcp>=2` and our other pins). These
cannot coexist in one Python environment. The fix: the main app venv
(`.venv`, `requirements.txt`) sends real OpenTelemetry/OpenInference
spans over plain OTLP/HTTP — no `phoenix` package import needed for
that (`src/observability/tracing.py`) — to a Phoenix collector run from
a second, isolated venv (`.venv-phoenix`, `requirements-phoenix.txt`)
that owns the full `arize-phoenix` package for launching the server and
querying spans back out. If no Phoenix server is listening, span export
fails silently in the background rather than crashing the agent — the
copilot runs identically with or without Phoenix up.

## Architecture

```
START -> supervisor (input guardrail + narrative quarantine)
              |
   (route_after_supervisor: AC-06 guardrail)
      /                          \
 blocked_end (END)         dispute_classification
                                  |
                (route_after_classification: AC-04 ambiguity guard)
                  /                              \
       escalate_ambiguous (END)         chargeback_rules_retrieval  (agentic-RAG + MCP rule engine)
                                                   |
                                             fraud_scoring  <-+       (MCP: transaction_lookup, prior_disputes_lookup)
                                                   |          |
                                               decision       |       (output guardrail + audit log)
                                         (route_after_decision)
                                  /              |             \
                               END       force_escalate (END)  reflect
```

- **dispute_classification** — classifies into one of 5 dispute types
  or `ambiguous_or_out_of_scope`.
- **chargeback_rules_retrieval** — MCP tool `network_rule_check`
  (deterministic rule engine) + agentic-RAG tool `chargeback_policy_lookup`
  (semantic search over `data/policy_corpus/`), called only when
  warranted, not as a fixed step.
- **fraud_scoring** — MCP tools `transaction_lookup` + `prior_disputes_lookup`.
- **decision** — final structured recommendation; forces escalation on
  high value/high fraud score regardless of confidence; a low-confidence
  decision triggers one bounded reflection retry, then a forced,
  safe exit (`investigate` + escalate) rather than looping.

## Repository Layout

```
cli.py                             single entry point (run / resume / state / build-rag-index / recall / regenerate-evidence)
config/config.yaml                 every tunable graph/memory/reflection/guardrail parameter
data/sample_disputes/              5 synthetic flagged disputes (AC-01 input)
data/policy_corpus/                10 synthetic chargeback-rules/policy documents (agentic-RAG)
mcp_server/                        custom MCP server: 3 tools + 1 resource
src/state.py, schemas.py           typed state + validated structured handoffs
src/graph.py, nodes.py             supervisor + 3 named workers + decision + conditional routing
src/context/                       write / select / compress / isolate
src/memory/                        tiered memory: checkpointer (short-term) + AsyncSqliteStore (long-term)
src/guardrails/                    input/output guardrails, PAN/account masking, audit trail
src/observability/                 OpenInference/OTel tracing + tool-invocation logging middleware
src/tools/rag_tool.py              agentic-RAG chargeback-policy lookup tool
scripts/export_phoenix_traces.py   -> traces/phoenix_spans.parquet (run from .venv-phoenix)
scripts/build_golden_signals.py    -> reports/golden_signals.json (run from .venv-phoenix)
scripts/build_dashboard.py         -> reports/dashboard.png + dashboard_data.csv (run from .venv-phoenix)
scripts/run_eval.py                -> reports/eval_report.json (DeepEval, run from main .venv)
scripts/generate_evidence.py       regenerates every main-venv evidence artifact from a clean state
tests/                             routing, loop-guard, tool-contract, memory-persistence, guardrail-regression tests
logs/                              tool_calls.jsonl, agent_actions.jsonl, run.log, memory_test.log
traces/                            run_transcript_*.json, phoenix_spans.parquet, phoenix_spans_preview.csv
reports/                           eval_report.json, golden_signals.json, dashboard.png, dashboard_data.csv
docs/                              failure-analysis, risk-register, model-card, compliance, output-risk, context-engineering
specs/acceptance-criteria.md       every AC mapped to committed evidence
```

## Evidence Committed in This Repo

| Artifact | What it shows |
|---|---|
| [traces/run_transcript_DSP-3001.json](traces/run_transcript_DSP-3001.json) | Full pipeline run: strong fraud signals, quarantined injection attempt, `investigate` + escalate. |
| [traces/run_transcript_DSP-3002.json](traces/run_transcript_DSP-3002.json) | Clean duplicate-charge case: `provisional_credit`, no escalation. |
| [traces/run_transcript_DSP-3003.json](traces/run_transcript_DSP-3003.json) | Ambiguous/out-of-scope request escalated for clarification (AC-04). |
| [traces/run_transcript_DSP-3004.json](traces/run_transcript_DSP-3004.json) | Reflection retry, then forced escalation once exhausted (loop/cascade guard). |
| [traces/run_transcript_DSP-3005.json](traces/run_transcript_DSP-3005.json) | Cross-account request refused outright by the input guardrail. |
| [traces/phoenix_spans.parquet](traces/phoenix_spans.parquet) | Real OTel/OpenInference spans across every agent and tool call. |
| [logs/tool_calls.jsonl](logs/tool_calls.jsonl) | Machine-generated tool-invocation log (AC-07). |
| [logs/agent_actions.jsonl](logs/agent_actions.jsonl) | Machine-generated audit trail (AC-10). |
| [logs/memory_test.log](logs/memory_test.log) | Cross-session memory persistence proof (two separate subprocesses). |
| [reports/eval_report.json](reports/eval_report.json) | Hallucination/faithfulness/relevancy over the golden set. |
| [reports/golden_signals.json](reports/golden_signals.json) | Phoenix-derived latency/tokens/cost + eval accuracy/hallucination. |
| [reports/dashboard.png](reports/dashboard.png) / [dashboard_data.csv](reports/dashboard_data.csv) | Cost/latency dashboard + underlying data. |
| [docs/failure-analysis.md](docs/failure-analysis.md) | 3 real failures, each citing a Phoenix span or committed test. |

Regenerate the main-venv evidence at any time with
`python cli.py regenerate-evidence`; regenerate the Phoenix-derived
evidence with the 3 `.venv-phoenix` scripts above (NFR-02).

## Scope Notes

Out of scope, per the business case: containerized/cloud deployment,
real card-network/fraud-engine integrations, front-end polish, and
generic unit-test volume for its own sake.
