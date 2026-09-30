# Output-Risk Classification

Every `ActionDecision` (`src/schemas.py`) is classified into one of
three output-risk tiers, gated as shown.

## Low risk — informational, no account impact

Clarification/escalation outputs where no financial action is
recommended: `action="clarify_with_customer"`. Gating: none beyond the
standard disclaimer — these are inherently the safe path (AC-04's
ambiguity handling and AC-06's guardrail refusals both land here).

**Sample:** `traces/run_transcript_DSP-3003.json` — ambiguous request,
`action="clarify_with_customer"`, `escalate_to_human=true`.

## Medium risk — recommends a financial action, low-to-moderate confidence/value

`action` is `provisional_credit`, `chargeback`, or `deny` on a
transaction below the high-value threshold, with `confidence >= 0.6`
and `escalate_to_human=false`. Gating: the output guardrail
(`src/guardrails/output_guardrail.py`) still runs on every case (PAN/
account masking, disclaimer enforcement); the recommendation is logged
to the audit trail (`logs/agent_actions.jsonl`) for after-the-fact
review, but does not require synchronous human sign-off before the
recommendation is returned to the analyst.

**Sample:** `traces/run_transcript_DSP-3002.json` — duplicate charge,
`action="provisional_credit"`, `confidence=0.99`, `escalate_to_human=false`.

## High risk — high value, high fraud score, or low confidence

Any of: transaction amount ≥ `fraud_scoring.high_value_threshold`,
fraud score ≥ `fraud_scoring.high_fraud_score_threshold`, or decision
confidence that never cleared `reflection.confidence_threshold` even
after the reflection retry. Gating: `escalate_to_human` is forced to
`true` regardless of the model's own output
(`src/nodes.py::decision`), and after retries are exhausted the action
itself is forced to `"investigate"` rather than trusting a
low-confidence `chargeback`/`deny`/`provisional_credit`
(`src/nodes.py::force_escalate`) — human-in-the-loop is mandatory
before any action is taken.

**Sample:** `traces/run_transcript_DSP-3001.json` — high-value
unauthorized-transaction dispute, `action="investigate"`,
`escalate_to_human=true`. **Sample (reflection-exhausted):**
`traces/run_transcript_DSP-3004.json` — `action` forced to
`"investigate"` after the reflection retry did not reach the confidence
threshold (see `docs/failure-analysis.md` Failure #1 for how this exit
path was verified to actually fire).
