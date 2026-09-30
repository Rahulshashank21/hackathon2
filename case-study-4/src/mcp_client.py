"""
Wires the custom MCP server (mcp_server/server.py) into the agent via
langchain-mcp-adapters. The server is launched as a stdio subprocess
per client — this module owns spawning, tool discovery, and wrapping
every discovered tool with the invocation-logging middleware.
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager

from langchain_mcp_adapters.client import MultiServerMCPClient

from src.config import load_config, resolve_path
from src.observability.tool_logging import wrap_tools_with_logging


def _build_client() -> MultiServerMCPClient:
    cfg = load_config()["mcp"]
    server_path = resolve_path("mcp_server/server.py")
    return MultiServerMCPClient(
        {
            cfg["server_name"]: {
                "transport": "stdio",
                "command": sys.executable,
                "args": [str(server_path)],
            }
        }
    )


@asynccontextmanager
async def mcp_tools_and_resource(agent: str):
    """Yields (tools, reason_code_catalog_text) for the given calling
    agent/node name — the tools returned are already wrapped with the
    tool-call logging middleware, tagged with `agent`."""
    cfg = load_config()["mcp"]
    client = _build_client()
    tools = await client.get_tools()
    tools = wrap_tools_with_logging(tools, agent)

    blobs = await client.get_resources(cfg["server_name"], uris=["dispute://reason-code-catalog"])
    catalog_text = blobs[0].as_string() if blobs else "{}"

    yield tools, catalog_text
