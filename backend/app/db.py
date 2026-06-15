"""Supabase client factory shared by backend and ingestion (service-role key)."""

from functools import lru_cache

import httpx

from app.config import get_settings
from supabase import Client, create_client


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
    proxy recycles an HTTP/2 connection with a GOAWAY after ~10k streams, and httpx
    then raises RemoteProtocolError mid-run instead of reconnecting. Pin the
    PostgREST session to HTTP/1.1 (no per-connection stream cap) with connect
    retries so long jobs complete.
    """
    pg = getattr(client, "postgrest", None)
    old = getattr(pg, "session", None)
    if old is None:
        return
    try:
        pg.session = httpx.Client(
            base_url=old.base_url,
            headers=old.headers,
            timeout=httpx.Timeout(180.0),
            http2=False,
            transport=httpx.HTTPTransport(retries=3),
        )
        old.close()
    except Exception:  # never let hardening break client creation
        pass
