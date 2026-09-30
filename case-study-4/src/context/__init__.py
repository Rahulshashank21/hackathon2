"""
Context engineering: write / select / compress / isolate. See
docs/context-engineering.md for the full mapping.

- write:    workers write distilled Pydantic facts into graph state
            (src/schemas.py) instead of leaving raw tool output lying
            around in the prompt for later steps to re-read.
- select:   select.py hand-picks only the fields a given node needs.
- compress: compress.py is the summarization/compression middleware
            for long threads (NFR: context-window management).
- isolate:  isolate.py quarantines untrusted customer-supplied text and
            screens it for injection-style patterns (NFR-03).
"""

from src.context.compress import compress_if_long
from src.context.isolate import quarantine_narrative
from src.context.select import select_context_for

__all__ = ["compress_if_long", "quarantine_narrative", "select_context_for"]
