"""Loads config/config.yaml plus environment overrides (NFR-01)."""

from __future__ import annotations

import os
import pathlib
from functools import lru_cache
from typing import Any

import yaml
from dotenv import load_dotenv

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "config.yaml"

load_dotenv(REPO_ROOT / ".env")


@lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["generation"]["model"] = os.environ.get("GEMINI_MODEL", cfg["generation"]["model"])
    return cfg


def resolve_path(relative: str) -> pathlib.Path:
    return REPO_ROOT / relative


def has_gemini_key() -> bool:
    if os.environ.get("FORCE_OFFLINE") in ("1", "true", "True"):
        return False
    return bool(os.environ.get("GOOGLE_API_KEY"))
