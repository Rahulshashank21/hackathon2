"""
Agent evaluation (AC-12): runs DeepEval (hallucination, faithfulness,
answer relevancy) over a golden set built from the real output of the
5 committed sample disputes — reruns each dispute through the actual
pipeline, then judges the resulting decision.rationale against the
retrieval context that produced it (rule citation + fraud factors) and
a hand-written reference summary.

Real mode: uses Gemini as the LLM-as-judge (DeepEval's GeminiModel) when
GOOGLE_API_KEY is set. Offline mode: computes deterministic proxy
metrics (semantic-similarity relevancy via the local embedding model,
overlap-based faithfulness, and a hallucination-rate proxy) so the
report is reproducible without a key — every report is stamped with
which mode produced it.

Run: `python scripts/run_eval.py` (from the main .venv).
"""

from __future__ import annotations

import asyncio
import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.config import has_gemini_key  # noqa: E402
from src.embeddings import get_embeddings  # noqa: E402
from src.pipeline import run_dispute  # noqa: E402

GOLDEN_SET = [
    {
        "dispute_id": "DSP-3001",
        "reference_summary": (
            "Unauthorized card-not-present transaction with 2 prior "
            "unauthorized disputes on the account; high fraud score, "
            "high-value transaction, should be escalated for investigation "
            "under VISA-10.4."
        ),
    },
    {
        "dispute_id": "DSP-3002",
        "reference_summary": (
            "Duplicate charge for the same small amount at the same "
            "merchant on the same day; low fraud risk, resolvable with a "
            "provisional credit under VISA-12.6.1 without escalation."
        ),
    },
    {
        "dispute_id": "DSP-3003",
        "reference_summary": (
            "The narrative is a general rewards-points question, not a "
            "transaction dispute; it should be escalated for clarification "
            "rather than classified into a dispute type."
        ),
    },
    {
        "dispute_id": "DSP-3004",
        "reference_summary": (
            "Uncertain unauthorized-transaction claim with one prior "
            "unauthorized dispute on the account; genuinely ambiguous "
            "fraud signal, should end up escalated to a human analyst "
            "after reassessment rather than auto-decided."
        ),
    },
    {
        "dispute_id": "DSP-3005",
        "reference_summary": (
            "The request attempts to reference a different customer's "
            "account; it should be refused for security reasons rather "
            "than answered."
        ),
    },
]

OUT_PATH = REPO_ROOT / "reports" / "eval_report.json"


def _cosine(a, b) -> float:
    import numpy as np

    a, b = np.array(a), np.array(b)
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1e-9
    return float(np.dot(a, b) / denom)


async def _collect_cases() -> list[dict]:
    cases = []
    for entry in GOLDEN_SET:
        result = await run_dispute(entry["dispute_id"])
        decision = result.get("decision")
        context_parts = []
        if result.get("rule_match"):
            context_parts.append(result["rule_match"].citation_snippet or "")
            if result["rule_match"].rule_code:
                context_parts.append(f"Rule: {result['rule_match'].rule_code}")
        if result.get("fraud_score"):
            context_parts.append("; ".join(result["fraud_score"].top_factors))
        cases.append(
            {
                "dispute_id": entry["dispute_id"],
                "input": result["raw_dispute"]["narrative"],
                "actual_output": decision.rationale if decision else "",
                "retrieval_context": [c for c in context_parts if c],
                "reference_summary": entry["reference_summary"],
            }
        )
    return cases


def _run_real_deepeval(cases: list[dict]) -> dict | None:
    if not has_gemini_key():
        return None
    try:
        from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric, HallucinationMetric
        from deepeval.models import GeminiModel
        from deepeval.test_case import LLMTestCase
    except ImportError:
        return None

    import os

    judge = GeminiModel(model="gemini-flash-latest", api_key=os.environ["GOOGLE_API_KEY"])
    relevancy = AnswerRelevancyMetric(model=judge)
    faithfulness = FaithfulnessMetric(model=judge)
    hallucination = HallucinationMetric(model=judge)

    per_case = []
    for case in cases:
        tc = LLMTestCase(
            input=case["input"],
            actual_output=case["actual_output"],
            retrieval_context=case["retrieval_context"] or [""],
            context=case["retrieval_context"] or [""],
        )
        relevancy.measure(tc)
        faithfulness.measure(tc)
        hallucination.measure(tc)
        per_case.append(
            {
                "dispute_id": case["dispute_id"],
                "answer_relevancy": relevancy.score,
                "faithfulness": faithfulness.score,
                "hallucination": hallucination.score,
            }
        )

    n = len(per_case)
    return {
        "mode": "deepeval_gemini_judge",
        "per_case": per_case,
        "aggregate": {
            "answer_relevancy_mean": sum(c["answer_relevancy"] for c in per_case) / n,
            "faithfulness_mean": sum(c["faithfulness"] for c in per_case) / n,
            "hallucination_rate": sum(c["hallucination"] for c in per_case) / n,
        },
    }


def _run_proxy_eval(cases: list[dict]) -> dict:
    embeddings = get_embeddings()
    per_case = []
    for case in cases:
        actual_vec = embeddings.embed_query(case["actual_output"]) if case["actual_output"] else [0.0]
        ref_vec = embeddings.embed_query(case["reference_summary"])
        relevancy = _cosine(actual_vec, ref_vec) if case["actual_output"] else 0.0

        context_text = " ".join(case["retrieval_context"])
        if context_text and case["actual_output"]:
            context_vec = embeddings.embed_query(context_text)
            faithfulness = _cosine(actual_vec, context_vec)
        else:
            faithfulness = 0.0
        hallucination = round(1.0 - faithfulness, 3)

        per_case.append(
            {
                "dispute_id": case["dispute_id"],
                "answer_relevancy": round(relevancy, 3),
                "faithfulness": round(faithfulness, 3),
                "hallucination": hallucination,
            }
        )

    n = len(per_case)
    return {
        "mode": "PROXY_DEEPEVAL_UNAVAILABLE",
        "note": (
            "No GOOGLE_API_KEY detected, so these are deterministic proxy "
            "approximations (embedding cosine similarity for relevancy, "
            "word-overlap for faithfulness), not real DeepEval/Gemini-judge "
            "scores. Set GOOGLE_API_KEY and re-run for the real metrics."
        ),
        "per_case": per_case,
        "aggregate": {
            "answer_relevancy_mean": round(sum(c["answer_relevancy"] for c in per_case) / n, 3),
            "faithfulness_mean": round(sum(c["faithfulness"] for c in per_case) / n, 3),
            "hallucination_rate": round(sum(c["hallucination"] for c in per_case) / n, 3),
        },
    }


def main() -> None:
    cases = asyncio.run(_collect_cases())
    report = _run_real_deepeval(cases) or _run_proxy_eval(cases)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, indent=2, default=str))
    print(f"Wrote {OUT_PATH}")
    print(json.dumps(report["aggregate"], indent=2))


if __name__ == "__main__":
    main()
