# Failure-Mode Analysis

Three real failures found during this project's own development and
testing runs, each with a citation that resolves to a committed
artifact, root cause, and fix.

---

## Failure 1 — Reflection loop naturally resolved instead of exercising the forced-escalation exit path

**Citation:** Phoenix `trace_id=fa5c2189c0d55d2fed2772fd176cdf93`,
`span_id=e729a2dd3f8d158d` (first `decision` pass, confidence 0.47) and
`span_id=9d773c3fd71d2577` (the `reflect` node in the same trace), both
in `traces/phoenix_spans.parquet` — this trace is dispute **DSP-3004**.
Also visible in `traces/run_transcript_DSP-3004.json` and the matching
`logs/agent_actions.jsonl` records for that dispute.

**Symptom:** With the reflection confidence bump originally set to
`+0.15` per retry, DSP-3004's first-pass confidence (0.47) crossed the
0.6 threshold after exactly one reflection retry (0.47 + 0.15 = 0.62),
so the loop always resolved "successfully" and `force_escalate` (the
loop/cascade guard's exhaustion path) never actually fired for any
committed sample dispute — leaving that code path untested by real
evidence, only by unit tests.

**Root cause:** The bump constant was too large relative to
`reflection.max_retries: 1` in `config/config.yaml`, given DSP-3004's
base confidence band position.

**Fix:** Reduced the bump to `+0.08` per retry in
`src/nodes.py::decision` (offline path). Re-running DSP-3004 now
produces confidence 0.47 → 0.55, correctly falling through to
`force_escalate` (see the current `traces/run_transcript_DSP-3004.json`
and `tests/test_loops.py::test_reflection_retry_count_never_exceeds_configured_max`,
which pins the bounded-retry behavior against regression).

---

## Failure 2 — MCP tool result shape varies by installed adapter version

**Citation:** `logs/tool_calls.jsonl`, the `network_rule_check` records
for dispute DSP-3001 (e.g. `trace_id=b9e36f8a99ddf152624441ea34047f02`,
`span_id=7da1ee606f252092` in `traces/phoenix_spans.parquet` for the
corresponding tool span).

**Symptom:** Calling an MCP tool via `langchain-mcp-adapters` returns
its JSON payload as a plain string on some installed versions, but as a
list of MCP content blocks (`[{"type": "text", "text": "...", "id": ...}]`)
or a `(content, artifact)` tuple on others — `_call_json_tool` in
`src/nodes.py`, written against only the string shape, raised
`TypeError`/`json.JSONDecodeError` the first time this project's pinned
`langchain-mcp-adapters==0.3.2` was exercised end-to-end.

**Root cause:** The adapter library's return shape for
`BaseTool.ainvoke()` is not stable across its own release history (the
project also uses a two-step pin-then-upgrade install sequence — see
README "Why two virtual environments" — that changes exactly which
adapter/langchain-core patch versions land).

**Fix:** `src/nodes.py::_coerce_tool_result_to_dict` normalizes dict,
string, and list-of-content-block shapes into a plain dict before use;
`src/observability/tool_logging.py`'s wrapper additionally unwraps a
`(content, artifact)` tuple before logging so `logs/tool_calls.jsonl`
records the actual tool output, not a raw tuple repr.

---

## Failure 3 — Input guardrail missed a non-dash account-reference phrasing

**Citation:** `tests/test_guardrails.py` (all four cases, including the
regression case that reproduces this exact failure) — a permanent,
re-runnable citation per the Citation-Resolves Rule, since the original
failing input was found via ad-hoc red-teaming rather than a committed
sample dispute's narrative.

**Symptom:** `check_input()`'s original account-reference pattern was
`r"\bACC-\d{4,}\b"` (dash form only). The phrasing *"please check my
friend account_70009 too"* was not flagged or blocked, even though it
clearly references a different account than the authenticated one —
demonstrated live during red-teaming for this analysis:
`check_input("...account_70009...", "ACC-70002")` returned
`{"blocked": False, "flags": []}` before the fix.

**Root cause:** The regex only anticipated the `ACC-NNNNN` format used
internally by `mcp_server/dispute_data.py`, not the underscore/space/
word-form variants a real customer might type.

**Fix:** Broadened the pattern to
`r"\b(?:ACC|ACCOUNT)[ _-]?(\d{4,})\b"` and switched the "same account?"
comparison to digit-only equality (`src/guardrails/input_guardrail.py`)
so dash, underscore, and spaced forms are all recognized consistently,
while the customer's own account (in any of those forms) is still
correctly allowed through. `tests/test_guardrails.py` pins all four
cases (dash/underscore/spaced-other-account blocked; own-account in any
form allowed) against regression.
