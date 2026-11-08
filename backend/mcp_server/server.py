"""The MCP server: the agent's read-only tools for Claude Code, Claude Desktop and other agents.

FastMCP over streamable HTTP at `/mcp` with `search_catalog`, `describe_table`, `run_sql`,
`find_place`, `resolve_area`, `area_stats`, `site_figures`, `live`, `quick`, `nearest`, `along`,
`compare_areas`, `trend`, `export` and `explain_coverage` (the same code, limits and logs as
the agent; docs/MCP.md), and the
catalogue entries and skill files as resources. Bearer keys from `MCP_API_KEYS`; off (404) when
unset. Connect from Claude Code:

    claude mcp add --transport http infraatlas https://<site>/mcp \
        --header "Authorization: Bearer <key>"
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
from collections.abc import AsyncIterator, Callable
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.types import ASGIApp, Receive, Scope, Send

from agent.skills import get_skills
from app.settings import Settings
from tools import registry
from tools.context import ToolContext, get_catalogue

INSTRUCTIONS = (
    "InfraAtlas: Europe's (and the world's) power system as data. Find tables with search_catalog, "
    "read their columns and units with describe_table, query with run_sql (DuckDB, read-only). "
    "Every result carries its sources; cite them."
)


async def _send(send: Send, status: int, body: dict[str, Any]) -> None:
    data = json.dumps(body).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": data})


class BearerAuth:
    """Only /mcp paths, and only with one of the keys."""

    def __init__(self, app: ASGIApp, keys: list[str], per_hour: int = 600) -> None:
        self.app = app
        self.keys = [k.encode() for k in keys]
        # per key (brief 30): each key has its own budget of requests per hour
        from agent.limits import MemoryLimits

        self.limits = MemoryLimits(per_hour)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        if not scope["path"].startswith("/mcp"):
            return await _send(send, 404, {"detail": "Not Found"})
        auth = dict(scope.get("headers") or []).get(b"authorization", b"")
        token = auth[7:] if auth.lower().startswith(b"bearer ") else b""
        if not any(hmac.compare_digest(token, k) for k in self.keys):
            return await _send(send, 401, {"detail": "MCP needs a bearer key"})
        if not self.limits.take("key:" + hashlib.sha256(token).hexdigest()[:16]):
            return await _send(send, 429, {"detail": "too many requests for this key; try later"})
        await self.app(scope, receive, send)


class Off:
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            await _send(
                send,
                404,
                {
                    "detail": "Not Found"
                    if not scope["path"].startswith("/mcp")
                    else "MCP is off (MCP_API_KEYS not set)"
                },
            )


def build_server(settings: Settings) -> FastMCP:
    ctx = ToolContext(settings)
    mcp = FastMCP(
        "InfraAtlas",
        instructions=INSTRUCTIONS,
        stateless_http=True,
        streamable_http_path="/mcp",
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    specs = registry.by_name()

    def doc(name: str) -> str:
        return specs[name].description

    @mcp.tool(name="search_catalog", description=doc("search_catalog"))
    def search_catalog(query: str) -> dict[str, Any]:
        return registry.search_catalog(ctx, query)

    @mcp.tool(name="describe_table", description=doc("describe_table"))
    def describe_table(name: str) -> dict[str, Any]:
        return specs["describe_table"].run(ctx, name=name)

    @mcp.tool(name="run_sql", description=doc("run_sql"))
    def run_sql(sql: str) -> dict[str, Any]:
        return specs["run_sql"].run(ctx, sql=sql)

    @mcp.tool(name="find_place", description=doc("find_place"))
    def find_place(text: str) -> dict[str, Any]:
        return specs["find_place"].run(ctx, text=text)

    @mcp.tool(name="resolve_area", description=doc("resolve_area"))
    def resolve_area(
        names: list[str] | None = None,
        level: str | None = None,
        point: list[float] | None = None,
        radius_km: float | None = None,
        buffer_km: float | None = None,
        intersect_with: str | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        args = registry.ResolveAreaArgs.model_validate(
            {
                "names": names or [],
                "level": level,
                "point": point,
                "radius_km": radius_km,
                "buffer_km": buffer_km,
                "intersect_with": intersect_with,
                "name": name,
            }
        )
        return specs["resolve_area"].run(ctx, **args.model_dump(exclude={"from_view"}))

    @mcp.tool(name="area_stats", description=doc("area_stats"))
    def area_stats(area_id: str, measures: list[str]) -> dict[str, Any]:
        args = registry.AreaStatsArgs.model_validate({"area_id": area_id, "measures": measures})
        return specs["area_stats"].run(ctx, **args.model_dump())

    @mcp.tool(name="site_figures", description=doc("site_figures"))
    def site_figures(lon: float, lat: float, radius_km: int = 50) -> dict[str, Any]:
        return specs["site_figures"].run(ctx, lon=lon, lat=lat, radius_km=radius_km)

    @mcp.tool(name="live", description=doc("live"))
    def live(source: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        args = registry.LiveArgs.model_validate({"source": source, "params": params or {}})
        return specs["live"].run(ctx, source=args.source, params=args.params)

    # brief 30: instant answers and the six tools of Track 4.6, validated by their own models
    def run(name: str, model: Any, **kw: Any) -> dict[str, Any]:
        args = model.model_validate({k: v for k, v in kw.items() if v is not None})
        return specs[name].run(ctx, **args.model_dump())

    @mcp.tool(name="quick", description=doc("quick"))
    def quick(template: str, area: str, n: int = 10, kind: str = "plants") -> dict[str, Any]:
        return run("quick", registry.QuickArgs, template=template, area=area, n=n, kind=kind)

    @mcp.tool(name="nearest", description=doc("nearest"))
    def nearest(
        dataset: str,
        lon: float | None = None,
        lat: float | None = None,
        area: str | None = None,
        k: int = 10,
    ) -> dict[str, Any]:
        return run(
            "nearest", registry.NearestArgs, dataset=dataset, lon=lon, lat=lat, area=area, k=k
        )

    @mcp.tool(name="along", description=doc("along"))
    def along(
        dataset: str, line: list[list[float]], buffer_km: float, name: str = "route"
    ) -> dict[str, Any]:
        return run(
            "along", registry.AlongArgs, dataset=dataset, line=line, buffer_km=buffer_km, name=name
        )

    @mcp.tool(name="compare_areas", description=doc("compare_areas"))
    def compare_areas(areas: list[str], measures: list[str] | None = None) -> dict[str, Any]:
        return run("compare_areas", registry.CompareArgs, areas=areas, measures=measures)

    @mcp.tool(name="trend", description=doc("trend"))
    def trend(area: str, years: list[int] | None = None) -> dict[str, Any]:
        return run("trend", registry.TrendArgs, area=area, years=years)

    @mcp.tool(name="export", description=doc("export"))
    def export(result_id: str, format: str = "csv") -> dict[str, Any]:
        return run("export", registry.ExportArgs, result_id=result_id, format=format)

    @mcp.tool(name="explain_coverage", description=doc("explain_coverage"))
    def explain_coverage(area: str, family: str = "") -> dict[str, Any]:
        return run("explain_coverage", registry.CoverageArgs, area=area, family=family)

    @mcp.resource("catalog://index", mime_type="application/json")
    def catalog_index() -> str:
        return json.dumps(get_catalogue(settings).dataset_list())

    @mcp.resource("catalog://{dataset}", mime_type="application/json")
    def catalog_entry(dataset: str) -> str:
        return json.dumps(get_catalogue(settings).table_entry(dataset), default=str)

    @mcp.resource("skill://{name}", mime_type="text/markdown")
    def skill(name: str) -> str:
        s = get_skills(settings.agent_dir).load(name)
        return str(s.get("body", s.get("error")))

    @mcp.resource("skill://{name}/references/{file}", mime_type="text/markdown")
    def skill_file(name: str, file: str) -> str:
        r = get_skills(settings.agent_dir).read_file(name, f"references/{file}")
        return str(r.get("text", r.get("error")))

    return mcp


def mcp_app(
    settings: Settings,
) -> tuple[ASGIApp, Callable[[], contextlib.AbstractAsyncContextManager[None]]]:
    """The ASGI app to mount and the lifespan the host app must run."""
    if not settings.mcp_api_keys:

        @contextlib.asynccontextmanager
        async def nothing() -> AsyncIterator[None]:
            yield

        return Off(), nothing
    mcp = build_server(settings)
    auth = BearerAuth(mcp.streamable_http_app(), settings.mcp_api_keys)

    @contextlib.asynccontextmanager
    async def lifespan() -> AsyncIterator[None]:
        # a session manager runs once; a new one per lifespan (tests start the app twice)
        mcp._session_manager = None
        auth.app = mcp.streamable_http_app()
        async with mcp.session_manager.run():
            yield

    return auth, lifespan
