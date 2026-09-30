# Model / System Card — Transaction Dispute & Fraud-Triage Copilot

## Model

**Provider:** Google Gemini (API), the only approved model provider
(Open-Source & Gemini-Only Rule). **Model:** `gemini-flash-latest` —
Google's auto-updating alias rather than a dated model name, configured
in `config/config.yaml: generation.model` and overridable via the
`GEMINI_MODEL` environment variable. Used for: dispute classification,
structured decision synthesis, and bounded ReAct tool-calling in the
`chargeback_rules_retrieval` and `fraud_scoring` workers
(`src/llm.py`).

**Offline fallback:** When `GOOGLE_API_KEY` is unset (or a Gemini call
fails after retries), every worker falls back to a deterministic
heuristic that still calls the same real MCP/RAG tools directly (see
`src/nodes.py`). Every `ActionDecision.generation_mode` field records
which path actually produced it (`"gemini"` or `"offline_stub"`) —
never silently conflated.

**Embeddings:** Local `sentence-transformers` (`BAAI/bge-small-en-v1.5`,
falling back to `all-MiniLM-L6-v2`), used for the agentic-RAG tool and
long-term semantic memory. No API key or network dependency for this
layer (`src/embeddings.py`).

## Data

All data is synthetic (Synthetic-Data Rule): 5 synthetic disputes
(`data/sample_disputes/`), a synthetic transaction/account/prior-dispute
dataset (`mcp_server/dispute_data.py`), and a 10-document synthetic
chargeback-rules/policy corpus (`data/policy_corpus/`). Card numbers
(PANs) and account numbers are fabricated and are always masked before
being returned by any tool, logged, or shown in an answer
(`src/guardrails/masking.py`; see `docs/output-risk.md`).

## Intended Use

Triage assistance for a bank's dispute/fraud-operations team: classify
a flagged dispute, retrieve the applicable network chargeback rule,
score fraud likelihood, and draft a recommended next action with a
rationale and citations — for a human analyst to review and approve.
**Not** intended to autonomously approve, deny, or execute any credit,
chargeback, or account action; every `ActionDecision` carries a fixed
disclaimer to this effect (`src/schemas.py::ActionDecision.disclaimer`).

## Limitations & Known Failure Modes

See `docs/failure-analysis.md` for 3 documented, evidence-cited
failures and their fixes:
1. A reflection-loop confidence tuning issue that let the forced-
   escalation exit path go unexercised (now fixed and regression-tested).
2. MCP tool result shape variability across `langchain-mcp-adapters`
   versions (now normalized defensively).
3. A gap in the input guardrail's account-reference pattern that missed
   a non-dash phrasing (now fixed and regression-tested).

Additional known limitations:
- The offline heuristic classifier is keyword-based and will
  under-perform Gemini's judgment on narratives that don't use the
  expected phrasing — this is a known, documented trade-off for
  reproducibility without an API key, not a claim of offline parity.
- Fraud scoring uses a small, hand-authored synthetic factor model
  (channel, prior disputes, account age, transaction value) — it is a
  triage heuristic, not a production fraud model, and is explicitly
  out of scope for production accuracy claims.
- The Phoenix-derived golden-signals report's token/cost figures are
  0 in offline-stub mode (no LLM spans are emitted without a Gemini
  key) — see `reports/golden_signals.json`'s `note` field.

## Out of Scope

Real card-network or fraud-engine integrations, real customer or
confidential data, production deployment (auth, multi-region,
containerization), and any autonomous execution of a credit, chargeback,
or account action — see the business case's Functional Scope.
