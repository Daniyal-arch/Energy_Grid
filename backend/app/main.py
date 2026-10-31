"""The InfraAtlas backend: the data service, the agent (/api/ask) and the MCP server (/mcp).

uv run uvicorn app.main:app --port 8080
"""

from __future__ import annotations

import contextlib
import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry import propagate

from app.routes import admin, areas, ask, catalog, health, maps, places, site
from app.settings import get_settings
from obs import logging as jlog
from obs.tracing import current_trace_id, setup_tracing, span

log = logging.getLogger("app")
settings = get_settings()
jlog.setup_logging()
setup_tracing(settings)

from mcp_server.server import mcp_app  # noqa: E402  (after settings and tracing)

mcp_asgi, mcp_lifespan = mcp_app(settings)


@contextlib.asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    async with mcp_lifespan():
        yield


app = FastAPI(title="InfraAtlas backend", version=settings.version, lifespan=lifespan)


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
    allow_headers=["content-type", "x-request-id", "traceparent", "x-conversation-id"],
    expose_headers=["x-request-id", "x-trace-id"],
)
for r in (health, catalog, places, areas, site, maps, ask, admin):
    app.include_router(r.router)
# last: FastAPI routes match first, then the MCP app answers /mcp (and 404 elsewhere)
app.mount("/", mcp_asgi)
