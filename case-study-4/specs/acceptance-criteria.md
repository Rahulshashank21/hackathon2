# Acceptance Criteria — Evidence Mapping

Each AC is mapped to a committed evidence artifact or code location a
reviewer can inspect directly (Evidence-in-Repo Rule, Citation-Resolves
Rule).

### AC-01 — Classify dispute type + retrieve matching rule, citing it
`src/nodes.py::dispute_classification` + `chargeback_rules_retrieval`;
`src/tools/rag_tool.py`; `data/policy_corpus/`. Evidence:
`traces/run_transcript_DSP-3001.json` (`rule_match.rule_code="VISA-10.4"`,
citation snippet present).

### AC-02 — Score fraud likelihood, explain top factors
`src/nodes.py::fraud_scoring`. Evidence: `FraudScore.top_factors` in
every `traces/run_transcript_*.json` (e.g. DSP-3001: "card-not-present
channel, high-value transaction, 2 prior unauthorized-transaction
disputes").

### AC-03 — Recommend next action with rationale; escalate high-value/high-fraud
`src/nodes.py::decision`. Evidence: `traces/run_transcript_DSP-3001.json`
(`action="investigate"`, `escalate_to_human=true` on a $2,450
transaction with fraud_score 0.8).

### AC-04 — Identify intent, handle with right capability; escalate ambiguous/out-of-scope
`src/nodes.py::route_after_classification` + `escalate_ambiguous`,
tested in `tests/test_routing.py`. Evidence:
`traces/run_transcript_DSP-3003.json` (a rewards-points question routed
to `clarify_with_customer`, never guessed at as a dispute type).

### AC-05 — Maintains context; recalls prior-session context
Short-term: LangGraph checkpointer (`src/pipeline.py`), demonstrated by
pause/resume (`python cli.py run DSP-3001 --pause-before fraud_scoring`
then `resume`). Long-term/cross-session:
`tests/test_memory_persistence.py` + `logs/memory_test.log` (two
separate subprocesses, not two objects in one process).

### AC-06 — Handle untrusted input safely; refuse cross-account access; never expose PAN/account
`src/context/isolate.py` (quarantine), `src/guardrails/input_guardrail.py`
(refusal), `src/guardrails/masking.py` (PAN/account masking everywhere
data is logged or returned). Evidence: `traces/run_transcript_DSP-3005.json`
(cross-account attempt refused); `traces/run_transcript_DSP-3001.json`
(injection attempt neutralized, decision driven by real signals);
`logs/tool_calls.jsonl` and `logs/agent_actions.jsonl` (every PAN/account
shown is pre-masked).

### AC-07 — Machine-generated tool-invocation log; names reconcile with code
`src/observability/tool_logging.py` → `logs/tool_calls.jsonl`. Tool
names (`transaction_lookup`, `prior_disputes_lookup`, `network_rule_check`,
`chargeback_policy_lookup`) match exactly the `@mcp.tool()` function
names in `mcp_server/server.py` and the `@tool` in `src/tools/rag_tool.py`.

### AC-08 — Failure analysis, ≥3 real failures citing Phoenix run_id+span_id or tool log
`docs/failure-analysis.md` — 3 failures, each citing a real
`trace_id`/`span_id` from `traces/phoenix_spans.parquet` or a
`logs/tool_calls.jsonl` record, with root cause, fix, and (for Failure
1 and 3) a regression test.

### AC-09 — Phoenix-derived golden-signals report + cost/latency dashboard
`scripts/build_golden_signals.py` → `reports/golden_signals.json`
(latency by span kind, tokens, cost estimate, eval accuracy/hallucination
merged in). `scripts/build_dashboard.py` → `reports/dashboard.png` +
`reports/dashboard_data.csv`. Both are derived from the real
`traces/phoenix_spans.parquet` export — see README "Why two virtual
environments" for why these run from `.venv-phoenix`.

### AC-10 — Input/output guardrails wired in; audit trail
`src/guardrails/input_guardrail.py` (wired at `supervisor`),
`src/guardrails/output_guardrail.py` (wired at `decision`),
`src/guardrails/audit.py` → `logs/agent_actions.jsonl` (every
classification, score, escalation, and decision logged with
actor/action/tool/decision/timestamp).

### AC-11 — Governance pack: risk register, model card, compliance mapping, output-risk
`docs/risk-register.md`, `docs/model-card.md`, `docs/compliance.md`,
`docs/output-risk.md` — every entry cites a committed control or
artifact.

### AC-12 — Agent evaluation (LLM-as-judge + hallucination) + agent tests
`scripts/run_eval.py` → `reports/eval_report.json` (DeepEval with
Gemini judge when `GOOGLE_API_KEY` is set; a labeled deterministic
proxy otherwise). `tests/test_routing.py` (routing-logic),
`tests/test_loops.py` (loop/cascade guard), `tests/test_tool_contracts.py`
(tool I/O schema + error path) — all pass (`pytest tests/ -v`).

---

## Non-Functional Requirements

| ID | Evidenced by |
|---|---|
| NFR-01 | `.env.example`; `.gitignore` excludes `.env` and the sqlite stores |
| NFR-02 | `README.md` quick-start; `python cli.py run <id>` (single command); `python cli.py regenerate-evidence` (second command, plus the Phoenix-venv export steps) |
| NFR-03 | `src/context/isolate.py::quarantine_narrative` |
| NFR-04 | `src/llm.py` (tenacity retries); every worker in `src/nodes.py` catches Gemini failures and falls back; `src/pipeline.py` is fully async |
| NFR-05 | All sample data synthetic; `src/guardrails/masking.py` applied before every log write |
| NFR-06 | Every evidence artifact under `traces/`, `logs/`, `reports/` is produced by a committed script/module referenced above, not hand-written |
