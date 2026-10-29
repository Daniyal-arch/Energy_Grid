"""External MCP servers as extra tools for the agent (agent/mcp.yaml, empty by default), through
langchain-mcp-adapters. Loaded once per container."""

from __future__ import annotations

import logging
import os
from typing import Any

import yaml

from app.settings import Settings

log = logging.getLogger(__name__)
_tools: list[Any] | None = None


def servers(settings: Settings) -> dict[str, dict[str, Any]]:
    p = settings.agent_dir / "mcp.yaml"
    raw = (yaml.safe_load(p.read_text(encoding="utf-8")) or {}) if p.exists() else {}
    out = {}
    for name, conf in (raw.get("servers") or {}).items():
        conf = dict(conf)
        headers = {k: os.path.expandvars(v) for k, v in (conf.pop("headers", None) or {}).items()}
        if headers:
            conf["headers"] = headers
        out[name] = conf
    return out


async def external_tools(settings: Settings) -> list[Any]:
    global _tools
    if _tools is not None:
        return _tools
    conns = servers(settings)
    if not conns:
        _tools = []
        return _tools
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient

        _tools = list(await MultiServerMCPClient(conns).get_tools())
    except Exception:
        log.exception("external MCP servers not attached")
        _tools = []
    return _tools
