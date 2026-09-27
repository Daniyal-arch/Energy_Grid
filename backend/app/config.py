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

    # MaStR registry snapshot (open-mastr Zenodo export). The official bulk server is
    # throttled to ~6 KB/s; we read the downloaded Zenodo zip directly.
    mastr_zip_path: str = "data/bnetza_open_mastr_2025-02-09.zip"

    # Phase 2
    entsoe_api_key: str = ""
    db_client_id: str = ""
    db_api_key: str = ""

    # Agent LLM — OpenAI-compatible providers (deepseek | groq | gemini).
    llm_provider: str = "deepseek"
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    chips_bucket: str = "chips"


@lru_cache
def get_settings() -> Settings:
    return Settings()
