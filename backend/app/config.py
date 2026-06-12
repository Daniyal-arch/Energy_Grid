"""Application settings, loaded from environment / .env. See .env.example for docs."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    supabase_url: str = ""
    supabase_service_role_key: str = ""

    # Google Earth Engine service account
    gee_service_account_email: str = ""
    gee_service_account_key_file: str = ""  # path to the JSON key file

    # Phase 2
    entsoe_api_key: str = ""
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"

    chips_bucket: str = "chips"


@lru_cache
def get_settings() -> Settings:
    return Settings()
