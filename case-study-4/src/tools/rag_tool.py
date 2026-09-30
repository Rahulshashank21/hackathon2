"""
Agentic-RAG tool: semantic search over the synthetic chargeback-rules
and dispute-policy corpus (data/policy_corpus/).

Exposed as a plain LangChain @tool bound to the chargeback-rules-
retrieval worker's tool-calling LLM, rather than a fixed pipeline step
— the model decides, per dispute, which policy clause to retrieve
(retrieval inside the loop).
"""

from __future__ import annotations

import logging
import re

from langchain_core.tools import tool

from src.config import load_config, resolve_path
from src.embeddings import get_embeddings

logger = logging.getLogger("copilot.rag_tool")

FRONTMATTER_RE = re.compile(r"^---\n(?P<meta>.*?)\n---\n", re.DOTALL)

_vector_store_cache = None


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    meta = {}
    for line in match.group("meta").splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta, text[match.end():].strip()


def build_or_load_index(force: bool = False):
    """Idempotent: rebuilds only if the persisted Chroma dir is missing
    or force=True."""
    from langchain_chroma import Chroma
    from langchain_core.documents import Document

    cfg = load_config()
    index_dir = resolve_path(cfg["paths"]["rag_index_dir"])
    embeddings = get_embeddings()

    if index_dir.exists() and not force:
        return Chroma(
            collection_name="dispute_policy",
            embedding_function=embeddings,
            persist_directory=str(index_dir),
        )

    corpus_dir = resolve_path(cfg["paths"]["policy_corpus_dir"])
    documents = []
    for path in sorted(corpus_dir.glob("*.md")):
        meta, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
        documents.append(
            Document(
                page_content=body,
                metadata={
                    "doc_id": meta.get("doc_id", path.stem),
                    "title": meta.get("title", path.stem),
                    "dispute_type": meta.get("dispute_type", ""),
                },
            )
        )

    store = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        collection_name="dispute_policy",
        persist_directory=str(index_dir),
    )
    logger.info("Built dispute-policy RAG index: %d documents.", len(documents))
    return store


def _get_vector_store():
    global _vector_store_cache
    if _vector_store_cache is None:
        _vector_store_cache = build_or_load_index()
    return _vector_store_cache


@tool
def chargeback_policy_lookup(query: str) -> str:
    """Semantically search the chargeback-rules and dispute-policy
    knowledge base for the network rule or policy clause that best
    matches a dispute description (e.g. unauthorized transaction,
    duplicate charge, goods not received). Call this to find the exact
    rule to cite in your classification. Returns the top matches with a
    relevance distance (lower = closer match)."""
    cfg = load_config()["retrieval"]
    store = _get_vector_store()
    results = store.similarity_search_with_score(query, k=cfg["top_k"])

    if not results:
        return "No matching chargeback rule or policy clause found."

    lines = []
    for doc, score in results:
        lines.append(
            f"- {doc.metadata['title']} (doc_id={doc.metadata['doc_id']}, "
            f"distance={score:.3f}): {doc.page_content}"
        )
    return "\n".join(lines)
