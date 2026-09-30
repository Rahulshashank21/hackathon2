"""Local embedding-model loader shared by the RAG tool and semantic memory."""

from __future__ import annotations

import logging

from src.config import load_config

logger = logging.getLogger("copilot.embeddings")

_cached_embeddings = None


def get_embeddings():
    global _cached_embeddings
    if _cached_embeddings is not None:
        return _cached_embeddings

    import os
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    from langchain_huggingface import HuggingFaceEmbeddings

    cfg = load_config()["embedding"]
    try:
        _cached_embeddings = HuggingFaceEmbeddings(model_name=cfg["model_name"])
    except Exception as exc:  # noqa: BLE001 - deliberate graceful fallback
        logger.warning(
            "Primary embedding model %s unavailable (%s); falling back to %s.",
            cfg["model_name"], exc, cfg["fallback_model_name"],
        )
        _cached_embeddings = HuggingFaceEmbeddings(model_name=cfg["fallback_model_name"])
    return _cached_embeddings
