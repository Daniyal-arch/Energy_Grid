"""Supabase client factory shared by backend and ingestion (service-role key)."""

from functools import lru_cache

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
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
