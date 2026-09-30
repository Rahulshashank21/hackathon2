"""Summarization/compression middleware for long threads (context-window
management). Deterministic and dependency-free so behavior is identical
with or without a Gemini key."""

from __future__ import annotations


def compress_if_long(text: str, max_chars: int = 800) -> str:
    """Keeps the first and last portions of long text (dispute narratives
    tend to front-load the incident and back-load contact/closing
    remarks) with an explicit marker showing where content was cut, so
    downstream nodes never silently receive truncated-but-unmarked text."""
    if len(text) <= max_chars:
        return text
    head = text[: max_chars // 2]
    tail = text[-max_chars // 2 :]
    return f"{head}\n[...compressed {len(text) - max_chars} characters...]\n{tail}"
