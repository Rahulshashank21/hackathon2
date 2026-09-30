"""
Tiered-memory cross-session persistence test (artifact:
tests/test_memory_persistence.py + logs/memory_test.log).

Proves persistence genuinely crosses *sessions* — not just object
instances in one Python process — by running two separate subprocesses
against the same on-disk store: session 1 writes a fact and exits;
session 2 is a brand-new process that opens the same store fresh and
recalls it purely from disk. Output is written to logs/memory_test.log
(the required "output log") in addition to normal pytest output.
"""

from __future__ import annotations

import asyncio
import json
import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

CUSTOMER_ID = "ACC-TEST-MEMORY"
TEST_FACT = "Cross-session verification fact: account ACC-70001 had an unauthorized-transaction dispute escalated to investigate."
RECALL_QUERY = "was there an escalated unauthorized transaction dispute on this account?"


async def _write_session() -> None:
    from src.memory import open_memory_store, remember

    async with open_memory_store() as store:
        key = await remember(store, CUSTOMER_ID, TEST_FACT, importance=0.9, dispute_id="DSP-3001")
    print(f"[session 1 / write] wrote fact key={key}")


async def _recall_session() -> dict:
    from src.memory import open_memory_store, recall

    async with open_memory_store() as store:
        results = await recall(store, CUSTOMER_ID, RECALL_QUERY, limit=3)
    return results


def test_memory_persists_across_separate_sessions():
    log_lines = ["=== Tiered memory cross-session persistence test ===", f"Customer: {CUSTOMER_ID}", ""]

    proc1 = subprocess.run(
        [sys.executable, "-c", f"import asyncio,sys; sys.path.insert(0,{str(REPO_ROOT)!r}); from tests.test_memory_persistence import _write_session; asyncio.run(_write_session())"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    log_lines.append(proc1.stdout.strip())
    assert proc1.returncode == 0, proc1.stderr

    proc2 = subprocess.run(
        [sys.executable, "-c", f"import asyncio,sys,json; sys.path.insert(0,{str(REPO_ROOT)!r}); from tests.test_memory_persistence import _recall_session; print(json.dumps(asyncio.run(_recall_session())))"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert proc2.returncode == 0, proc2.stderr
    results = json.loads(proc2.stdout.strip().splitlines()[-1])

    log_lines.append(f"[session 2 / recall] query={RECALL_QUERY!r}")
    log_lines.append(f"[session 2 / recall] {len(results)} result(s)")

    log_path = REPO_ROOT / "logs" / "memory_test.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    assert len(results) > 0, "\n".join(log_lines + ["RESULT: FAILED (no facts recalled)"])
    top = results[0]
    log_lines.append(f"[session 2 / recall] top result: {top['fact']!r} (score={top['score']:.4f})")

    passed = TEST_FACT in top["fact"]
    log_lines.append("RESULT: PASSED" if passed else "RESULT: FAILED (fact mismatch)")
    log_path.write_text("\n".join(log_lines))

    assert passed, "\n".join(log_lines)


if __name__ == "__main__":
    if "--write" in sys.argv:
        asyncio.run(_write_session())
    elif "--recall" in sys.argv:
        print(json.dumps(asyncio.run(_recall_session())))
