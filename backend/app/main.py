"""The InfraAtlas backend: the data service, the agent (/api/ask) and the MCP server (/mcp).

uv run uvicorn app.main:app --port 8080
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import logging
import threading
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry import propagate

from agent.limits import MemoryLimits
from app.routes import admin, areas, ask, catalog, feeds, health, maps, places, quick, report, site
from app.settings import get_settings
from obs import logging as jlog
from obs.tracing import current_trace_id, setup_tracing, span

log = logging.getLogger("app")
settings = get_settings()
jlog.setup_logging()
setup_tracing(settings)

from mcp_server.server import mcp_app  # noqa: E402  (after settings and tracing)

mcp_asgi, mcp_lifespan = mcp_app(settings)


def warm() -> None:
    """Brief 30: open the lake (download lake.duckdb, attach, load the app tables) and the
    catalogue index before the first question, in the background, so the cold start does not
    land on a user's first tool call. Health answers at once meanwhile."""
    t0 = time.perf_counter()
    try:
        from tools.context import ToolContext

        ctx = ToolContext(settings)
        ctx.lake.run("SELECT 1", guard=False)
        ctx.catalogue.search("solar")
        ctx.areas.search("Bavaria")  # opens the name index and its aliases (their first reads)
        log.info("warm", extra={"s": round(time.perf_counter() - t0, 2)})
    except Exception as e:  # noqa: BLE001 - a failed warm-up is retried by the first request
        log.warning("warm-up failed", extra={"error": str(e)[:200]})


@contextlib.asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if settings.warm_on_start:
        threading.Thread(target=warm, name="warm", daemon=True).start()
    async with mcp_lifespan():
        yield


app = FastAPI(
    title="InfraAtlas data API",
    version=settings.version,
    lifespan=lifespan,
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url=None,
    description="Read-only figures of the power system, each with its sources and licences "
    "(docs/product/data-api.md). Send X-API-Key for a key's own budget.",
)


# brief 30 Track 6.6: the read-only data routes as an API (OpenAPI at /api/openapi.json, docs
# at /api/docs): an X-API-Key from DATA_API_KEYS gets its own budget, anonymous callers a budget
# per address; 429 above it. Every response names its sources and licences in `sources`.
DATA_ROUTES = (
    "/api/quick", "/api/report", "/api/feed", "/api/catalog", "/api/places", "/api/areas",
    "/api/shapes", "/api/site", "/api/export",
)  # fmt: skip
_key_limits = MemoryLimits(settings.data_api_per_key_hour)
_ip_limits = MemoryLimits(settings.data_api_per_ip_hour)


def data_limit(request: Request) -> Response | None:
    key = request.headers.get("x-api-key")
    if key:
        if not any(hmac.compare_digest(key, k) for k in settings.data_api_keys):
            return JSONResponse({"error": "unknown API key"}, status_code=401)
        ok = _key_limits.take("key:" + hashlib.sha256(key.encode()).hexdigest()[:16])
    else:
        h = request.headers
        ip = h.get("cf-connecting-ip") or (h.get("x-forwarded-for") or "").split(",")[0].strip()
        ok = _ip_limits.take("ip:" + (ip or (request.client.host if request.client else "?")))
    if not ok:
        return JSONResponse({"error": "too many requests; try again later"}, status_code=429)
    return None


@app.middleware("http")
async def context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Request id, W3C trace context, the proxy secret and the body size limit."""
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    jlog.request_id.set(rid)
    path = request.url.path
    if (
        settings.require_proxy
        and path != "/api/health"
        and request.headers.get("x-atlas-proxy") != settings.proxy_secret
    ):
        return JSONResponse({"error": "requests go through the site's proxy"}, status_code=403)
    length = int(request.headers.get("content-length") or 0)
    if length > settings.max_body_bytes:
        return JSONResponse({"error": "request body too large"}, status_code=413)
    if path.startswith(DATA_ROUTES):
        limited = data_limit(request)
        if limited is not None:
            return limited
    ctx = propagate.extract(dict(request.headers))
    from opentelemetry import context as otel_context

    token = otel_context.attach(ctx)
    try:
        with span("http.request", {"http.method": request.method, "http.route": path}) as sp:
            tid = current_trace_id()
            jlog.trace_id.set(tid)
            response = await call_next(request)
            sp.set_attribute("http.status_code", response.status_code)
    finally:
        otel_context.detach(token)
    response.headers["x-request-id"] = rid
    response.headers["x-trace-id"] = tid
    if path != "/api/health" and not path.startswith("/mcp"):
        log.info("request", extra={"path": path, "status": response.status_code})
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=[
        "content-type",
        "x-request-id",
        "traceparent",
        "x-conversation-id",
        "last-event-id",
    ],
    expose_headers=["x-request-id", "x-trace-id", "x-run-id"],
)
for r in (health, catalog, places, areas, site, maps, quick, report, feeds, ask, admin):
    app.include_router(r.router)
# last: FastAPI routes match first, then the MCP app answers /mcp (and 404 elsewhere)
app.mount("/", mcp_asgi)
