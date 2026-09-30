# Context Engineering — Write / Select / Compress / Isolate

Implementation: `src/context/` (a package: `isolate.py`, `select.py`,
`compress.py`).

## Write

Every worker writes a **validated, distilled** Pydantic object into
state (`src/schemas.py`: `DisputeClassification`, `ChargebackRuleMatch`,
`FraudScore`, `ActionDecision`) instead of leaving raw tool output or
LLM scratchpad text around for later nodes to re-parse. Downstream
nodes read `state["fraud_score"].top_factors`, not a wall of raw JSON.

## Select

`src/context/select.py::select_context_for(node_name, state)`
hand-picks the subset of state each node actually needs before it's
included in a prompt — e.g. the `decision` node gets `classification` +
`rule_match` + `fraud_score` + `retry_count`, not the raw narrative it
doesn't need to re-decide from.

## Compress

`src/context/compress.py::compress_if_long(text, max_chars=800)` is the
summarization/compression middleware: any narrative text over the
character budget is compressed (head + tail retained, with an explicit
`[...compressed N characters...]` marker) before being included in a
worker's prompt — used in `dispute_classification` and `fraud_scoring`,
the two nodes that include the narrative directly.

## Isolate

`src/context/isolate.py::quarantine_narrative(raw_narrative)` is the
Context-Isolation Rule (NFR-03) mechanism: every customer-submitted
narrative is wrapped in an explicit
`<untrusted_customer_narrative>...</untrusted_customer_narrative>` block
with an instruction that it is data, not a directive, and screened
against a configurable set of injection-style regex patterns
(`config/config.yaml: guardrails.injection_patterns`) — every detection
is recorded as a trace event, never a silent no-op. Only the
`supervisor` node ever touches the raw narrative; every other node only
ever sees `state["quarantined_narrative"]`.

This is distinct from (but complementary to) the **input guardrail**
(`src/guardrails/input_guardrail.py`), which additionally decides
whether a request should be blocked outright (e.g. an attempt to
reference another customer's account) — quarantine neutralizes an
injection attempt's *effect*; the guardrail refuses the *request*.

See `evidence` in `traces/run_transcript_DSP-3001.json` (quarantine
flags an injection attempt but the pipeline still classifies and scores
correctly) and `traces/run_transcript_DSP-3005.json` (the guardrail
blocks a cross-account request outright).
