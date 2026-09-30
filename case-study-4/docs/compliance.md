# Compliance Mapping

Applicable obligation → how it is addressed → evidence artifact.

## EU AI Act (limited-risk / transparency obligations for this use case)

| Obligation | How addressed | Evidence |
|---|---|---|
| Human oversight for consequential decisions (Art. 14) | High-value and high-fraud-score cases are always escalated to a human, independent of model confidence; every decision states it is reference-only | `src/nodes.py::decision` (escalation logic); `src/schemas.py::ActionDecision.disclaimer`; `traces/run_transcript_DSP-3001.json` |
| Transparency — users/operators must know they're interacting with an AI system whose output is not final | Every `ActionDecision` carries a fixed disclaimer stating it is an automated recommendation, not a final decision | `src/schemas.py::ActionDecision` |
| Record-keeping / logging (Art. 12) | Machine-generated audit trail of every consequential action, and a tool-invocation log | `logs/agent_actions.jsonl`, `logs/tool_calls.jsonl` |
| Risk management system | Documented risk register with mitigations tied to committed controls | `docs/risk-register.md` |

## NIST AI RMF

| Function | How addressed | Evidence |
|---|---|---|
| **Govern** — policies for data handling and secrets | Synthetic-only data; `.env.example` + `.gitignore` for secrets hygiene | `docs/model-card.md` § Data; `.env.example`, `.gitignore` |
| **Map** — context and intended use documented | Model/system card documents intended use, limitations, out-of-scope | `docs/model-card.md` |
| **Measure** — the system's behavior is evaluated, not assumed | Agent evaluation (hallucination/faithfulness/relevancy) plus routing, loop-guard, and tool-contract tests | `reports/eval_report.json`; `tests/test_routing.py`, `tests/test_loops.py`, `tests/test_tool_contracts.py` |
| **Manage** — failures are found, tracked, and fixed | 3 documented real failures with root cause, fix, and regression tests | `docs/failure-analysis.md`; `tests/test_guardrails.py` |

## DPDP (Digital Personal Data Protection) — synthetic-data posture

Since all data in this exercise is synthetic (Synthetic-Data Rule), DPDP
obligations around real personal data (consent, purpose limitation,
breach notification) do not attach to this repository's data. The
controls that *would* be load-bearing in a real deployment are built
and demonstrated regardless, so the same posture carries over directly:

| Principle | How it would carry over to real data | Evidence (demonstrated on synthetic data now) |
|---|---|---|
| Data minimization | Only the fields needed for triage are returned by any tool (no full PAN, no unrelated customer fields) | `mcp_server/server.py` (masked responses) |
| Purpose limitation / access control | The input guardrail refuses any request that reaches beyond the authenticated customer's own account | `src/guardrails/input_guardrail.py`; `tests/test_guardrails.py` |
| No plaintext sensitive data in logs | Every log write path masks PAN/account patterns before persisting | `src/guardrails/masking.py`; applied in `src/observability/tool_logging.py` and `src/guardrails/audit.py` |
