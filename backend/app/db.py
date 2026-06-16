"""Supabase client factory shared by backend and ingestion (service-role key)."""

import time
from functools import lru_cache
from typing import Any

import httpx

from app.config import get_settings
from supabase import Client, create_client

# transient transport failures worth retrying on a fresh connection
_TRANSIENT = (
    httpx.RemoteProtocolError,  # HTTP/2 GOAWAY after ~10k streams on a long run
    httpx.ConnectError,
    httpx.ReadError,
    httpx.WriteError,
    httpx.PoolTimeout,
)


@lru_cache
def get_db() -> Client:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError(
            "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are not set. "
            "Copy .env.example to .env and fill them in (see docs/SETUP.md)."
        )
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    _harden_session(client)
    return client


def _harden_session(client: Client) -> None:
    """Long backfills/detection make tens of thousands of REST calls. The Supabase
    proxy recycles an HTTP/2 connection with a GOAWAY after ~10k streams; httpx then
    raises RemoteProtocolError mid-run and the job dies. Wrap the exact method
    PostgREST calls (`session.request`) so a dropped connection is retried on a
    fresh one — robust regardless of HTTP/1.1 vs /2.
    """
    pg = getattr(client, "postgrest", None)
    session = getattr(pg, "session", None)
    if session is None or getattr(session, "_gw_hardened", False):
        return
    original = session.request

    def request_with_retry(*args: Any, **kwargs: Any) -> httpx.Response:
        for attempt in range(5):
            try:
                return original(*args, **kwargs)
            except _TRANSIENT:
                if attempt == 4:
                    raise
                time.sleep(0.5 * (attempt + 1))  # dead connection is dropped; next send reconnects

    try:
        session.request = request_with_retry  # type: ignore[method-assign]
        session._gw_hardened = True  # type: ignore[attr-defined]
    except Exception:  # never let hardening break client creation
        pass
