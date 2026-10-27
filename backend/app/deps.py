"""Shared singletons per container: settings, the lake, the catalogue, stores, limits."""

from __future__ import annotations

from functools import lru_cache

from fastapi import Header, HTTPException

from app.settings import Settings, get_settings
from data.duck import Lake, get_lake
from data.r2 import Store, get_store


def settings() -> Settings:
    return get_settings()


def lake() -> Lake:
    return get_lake(get_settings())


@lru_cache
def store() -> Store:
    return get_store(get_settings())


def require_admin(x_admin_key: str | None = Header(default=None)) -> None:
    key = get_settings().admin_api_key
    if not key:
        raise HTTPException(404, "admin is off (ADMIN_API_KEY not set)")
    if x_admin_key != key:
        raise HTTPException(401, "admin key required (X-Admin-Key)")
