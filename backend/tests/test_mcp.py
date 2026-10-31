"""The MCP server through the official client over streamable HTTP (a real server on a port)."""

import asyncio
import socket
import threading
import time

import pytest
import uvicorn
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


@pytest.fixture(scope="module")
def base_url():
    from app.main import app

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    t.join(5)


async def session_do(url, key, fn):
    async with streamablehttp_client(f"{url}/mcp", headers={"Authorization": f"Bearer {key}"}) as (
        r,
        w,
        _,
    ):
        async with ClientSession(r, w) as s:
            await s.initialize()
            return await fn(s)


def test_lists_tools_and_runs_search_catalog(base_url):
    async def go(s):
        tools = [t.name for t in (await s.list_tools()).tools]
        res = await s.call_tool("search_catalog", {"query": "negative prices"})
        sql = await s.call_tool("run_sql", {"sql": "SELECT count(*) AS n FROM registers.gb"})
        templates = [
            str(t.uriTemplate) for t in (await s.list_resource_templates()).resourceTemplates
        ]
        skill = await s.read_resource("skill://prices")
        return tools, res, sql, templates, skill

    tools, res, sql, templates, skill = asyncio.run(session_do(base_url, "test-mcp", go))
    assert set(tools) == {
        "area_stats",
        "search_catalog",
        "describe_table",
        "run_sql",
        "find_place",
        "resolve_area",
        "site_figures",
        "live",
    }
    assert "app.eu_prices" in res.content[0].text
    assert '"rows": [\n      [\n        4' in sql.content[0].text or "[[4]]" in sql.content[
        0
    ].text.replace(" ", "").replace("\n", "")
    assert "catalog://{dataset}" in templates
    assert "Zones, not countries" in skill.contents[0].text


def test_needs_a_key(base_url):
    import httpx

    r = httpx.post(f"{base_url}/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert r.status_code == 401
    assert httpx.get(f"{base_url}/no-such-path").status_code == 404
