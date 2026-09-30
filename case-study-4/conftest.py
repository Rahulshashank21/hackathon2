"""Ensures `src`, `mcp_server`, and `scripts` are importable when running
pytest from the repo root."""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
