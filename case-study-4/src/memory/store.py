"""
Long-term / semantic memory: `langgraph.store.sqlite.aio.AsyncSqliteStore`
— LangGraph's own persisted, semantically-indexed cross-thread store,
indexed with the same local embedding model used elsewhere. Facts are
namespaced per customer: `(customer_id, "facts")`.

Short-term / working memory is the LangGraph checkpointer (per-thread
graph state — see src/pipeline.py) and is not duplicated here.

Eviction / importance policy: every fact is written with a TTL derived
from its importance score (docs/memory-policy.md). LangGraph's store
handles TTL expiry natively; `evict_lru_if_over_capacity()` additionally
enforces a hard per-customer cap by dropping the lowest-importance,
least-recently-written facts first — a combined TTL + importance-
weighted-LRU policy.
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

from langgraph.store.base import BaseStore
from langgraph.store.sqlite.aio import AsyncSqliteStore

from src.config import load_config, resolve_path
from src.embeddings import get_embeddings


def _patch_sqlite_for_extension_loading():
    """On macOS where Python standard library sqlite3 lacks enable_load_extension,
    patch aiosqlite.Connection using ctypes to call the underlying C functions."""
    import sqlite3

    if hasattr(sqlite3.Connection, "enable_load_extension"):
        return

    import ctypes
    import _sqlite3
    import aiosqlite

    class PyConnection(ctypes.Structure):
        _fields_ = [
            ("ob_refcnt", ctypes.c_ssize_t),
            ("ob_type", ctypes.c_void_p),
            ("db", ctypes.c_void_p),
        ]

    _lib = ctypes.CDLL(_sqlite3.__file__)
    if not hasattr(_lib, "sqlite3_enable_load_extension") or not hasattr(_lib, "sqlite3_load_extension"):
        return

    _lib.sqlite3_enable_load_extension.argtypes = [ctypes.c_void_p, ctypes.c_int]
    _lib.sqlite3_enable_load_extension.restype = ctypes.c_int
    _lib.sqlite3_load_extension.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_char_p),
    ]
    _lib.sqlite3_load_extension.restype = ctypes.c_int

    def _enable_load_extension(raw_conn, enable=True):
        py_conn = PyConnection.from_address(id(raw_conn))
        rc = _lib.sqlite3_enable_load_extension(py_conn.db, 1 if enable else 0)
        if rc != 0:
            raise sqlite3.OperationalError(f"enable_load_extension failed with code {rc}")

    def _load_extension(raw_conn, path, entry_point=None):
        py_conn = PyConnection.from_address(id(raw_conn))
        errmsg = ctypes.c_char_p()
        ep = entry_point.encode("utf-8") if entry_point else None
        rc = _lib.sqlite3_load_extension(py_conn.db, path.encode("utf-8"), ep, ctypes.byref(errmsg))
        if rc != 0:
            err = errmsg.value.decode("utf-8") if errmsg.value else f"code {rc}"
            raise sqlite3.OperationalError(f"load_extension failed: {err}")

    async def _patch_enable_load_extension(self, value: bool) -> None:
        if hasattr(self._conn, "enable_load_extension"):
            await self._execute(self._conn.enable_load_extension, value)
        else:
            await self._execute(_enable_load_extension, self._conn, value)

    async def _patch_load_extension(self, path: str, entrypoint: str | None = None):
        if hasattr(self._conn, "load_extension"):
            await self._execute(self._conn.load_extension, path)
        else:
            await self._execute(_load_extension, self._conn, path, entrypoint)

    aiosqlite.Connection.enable_load_extension = _patch_enable_load_extension
    aiosqlite.Connection.load_extension = _patch_load_extension


_patch_sqlite_for_extension_loading()


NAMESPACE_SUFFIX = "facts"


def _importance_to_ttl_minutes(importance: float) -> float:
    cfg = load_config()["memory"]
    if importance >= cfg["high_importance_threshold"]:
        days = cfg["ttl_high_importance_days"]
    elif importance >= cfg["medium_importance_threshold"]:
        days = cfg["ttl_medium_importance_days"]
    else:
        days = cfg["ttl_low_importance_days"]
    return days * 24 * 60


@asynccontextmanager
async def open_memory_store():
    """Opens a fresh, persisted long-term memory store. A new sqlite
    connection each time is what makes cross-session persistence
    meaningful — nothing is kept alive in Python process memory between
    sessions."""
    cfg = load_config()
    db_path = resolve_path(cfg["paths"]["long_term_store_db"])
    db_path.parent.mkdir(parents=True, exist_ok=True)

    from langgraph.store.base import TTLConfig
    from langgraph.store.sqlite.base import SqliteIndexConfig

    index_config = SqliteIndexConfig(
        dims=cfg["embedding"]["dims"],
        embed=get_embeddings(),
        fields=["fact"],
    )
    ttl_config = TTLConfig(
        refresh_on_read=True,
        sweep_interval_minutes=cfg["memory"]["sweep_interval_minutes"],
    )
    async with AsyncSqliteStore.from_conn_string(
        str(db_path), index=index_config, ttl=ttl_config
    ) as store:
        await store.setup()
        yield store


async def remember(
    store: BaseStore,
    customer_id: str,
    fact: str,
    importance: float,
    dispute_id: str | None = None,
    tags: list[str] | None = None,
) -> str:
    """Writes a long-term fact with an importance-derived TTL."""
    namespace = (customer_id, NAMESPACE_SUFFIX)
    key = str(uuid.uuid4())
    await store.aput(
        namespace,
        key,
        {
            "fact": fact,
            "importance": importance,
            "dispute_id": dispute_id,
            "tags": tags or [],
            "written_at": time.time(),
        },
        ttl=_importance_to_ttl_minutes(importance),
    )
    return key


async def recall(store: BaseStore, customer_id: str, query: str, limit: int = 5) -> list[dict]:
    """Semantic recall of prior facts for this customer."""
    namespace = (customer_id, NAMESPACE_SUFFIX)
    items = await store.asearch(namespace, query=query, limit=limit)
    return [
        {
            "key": item.key,
            "fact": item.value["fact"],
            "importance": item.value["importance"],
            "dispute_id": item.value.get("dispute_id"),
            "score": item.score,
        }
        for item in items
    ]


async def evict_lru_if_over_capacity(store: BaseStore, customer_id: str) -> int:
    """Hard cap on facts per customer: once exceeded, drop the
    lowest-importance / oldest-written facts first. Returns the number
    of facts evicted."""
    cfg = load_config()["memory"]
    namespace = (customer_id, NAMESPACE_SUFFIX)
    all_items = await store.asearch(namespace, limit=1000)

    max_facts = cfg["max_facts_per_investigator"]
    if len(all_items) <= max_facts:
        return 0

    ranked = sorted(
        all_items,
        key=lambda item: (item.value.get("importance", 0.0), item.value.get("written_at", 0.0)),
    )
    to_evict = ranked[: len(all_items) - max_facts]
    for item in to_evict:
        await store.adelete(namespace, item.key)
    return len(to_evict)
