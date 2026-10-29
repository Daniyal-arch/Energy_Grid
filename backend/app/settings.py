"""Settings: the environment first, then (in Lambda) SSM Parameter Store.

Every variable is documented in backend/.env.example. In Lambda, secrets live in SSM
SecureString parameters under `SSM_PREFIX` (default `/infraatlas/`); they are read once per cold
start and fill only the variables the environment does not already set.
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
log = logging.getLogger(__name__)


def _default_root() -> Path:
    """The repository root (agent/ and frontend/public/data/ live there); /var/task in the image."""
    return Path(os.environ.get("ATLAS_ROOT", BACKEND_DIR.parent))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    environment: str = "development"
    version: str = "0.1.0"
    git_sha: str = "dev"

    # where the agent's files and the app's public map files are
    atlas_root: Path = Field(default_factory=_default_root)
    public_data_remote: str = (
        "https://raw.githubusercontent.com/Daniyal-arch/Energy_Grid/eu-days/eu/"
    )
    snapshot_remote: str = "https://raw.githubusercontent.com/Daniyal-arch/Energy_Grid/eu-data/eu/"

    # CORS: the site and the dev server (CORS_ORIGINS; template parameter SiteOrigins)
    cors_origins: Annotated[list[str], NoDecode] = [
        "https://energy-grid.infraatlas.workers.dev",
        "http://localhost:5173",
    ]

    # models (agent/models.yaml); "fake:*" runs the scripted test model
    agent_model: str = "anthropic:claude-opus-5-5"
    agent_model_fast: str = "anthropic:claude-haiku-5-5"
    agent_models_allowed: Annotated[list[str], NoDecode] = []
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    google_api_key: str | None = None
    groq_api_key: str | None = None
    # an Amazon Bedrock API key (bearer token); boto3 reads it as AWS_BEARER_TOKEN_BEDROCK
    bedrock_api_key: str | None = None

    # the lake: a lake.duckdb (local path or r2://...) or a local directory of Parquet files
    lake_db: str | None = "r2://infraatlas-raw/lake/lake.duckdb"
    lake_dir: Path | None = None
    r2_account_id: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_lake_bucket: str = "infraatlas-raw"
    r2_agent_bucket: str = "infraatlas-raw"
    duckdb_extension_dir: Path | None = None
    duckdb_memory_limit: str = "2GB"
    sql_timeout_s: float = 25.0
    sql_rows_returned: int = 200
    sql_rows_kept: int = 100_000

    # local stand-ins when R2 is not configured
    results_dir: Path = Path("/tmp/atlas-results")
    local_store_dir: Path = Path("/tmp/atlas-store")

    # limits and caps
    max_tool_calls: int = 12
    soft_deadline_s: float = 60.0
    max_output_tokens: int = 8000
    max_question_chars: int = 2000
    max_history_messages: int = 20
    max_body_bytes: int = 64_000
    daily_spend_cap_usd: float = 20.0
    ip_requests_per_hour: int = 30
    dynamodb_table: str | None = None
    aws_region: str = "eu-central-1"

    # keys (SSM in Lambda)
    admin_api_key: str | None = None
    mcp_api_keys: Annotated[list[str], NoDecode] = []
    proxy_secret: str | None = None
    require_proxy: bool = False
    ip_hash_salt: str = "infraatlas"

    # live sources
    eia_api_key: str | None = None

    # observability
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"
    otel_exporter_otlp_endpoint: str | None = None
    otel_console: bool = False
    run_records: bool = True

    @field_validator("cors_origins", "agent_models_allowed", "mcp_api_keys", mode="before")
    @classmethod
    def _list(cls, v: object) -> object:
        """A JSON list or a comma-separated string (SAM parameters, SSM values)."""
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                return json.loads(v)
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    @property
    def agent_dir(self) -> Path:
        return self.atlas_root / "agent"

    @property
    def public_dir(self) -> Path:
        return self.atlas_root / "frontend" / "public" / "data"

    @property
    def r2_configured(self) -> bool:
        return bool(self.r2_account_id and self.r2_access_key_id and self.r2_secret_access_key)

    @property
    def langfuse_configured(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)

    def models_allowed(self) -> list[str]:
        """Models a request may pick: the configured list, else the two defaults."""
        return self.agent_models_allowed or [self.agent_model, self.agent_model_fast]


SSM_NAMES = {
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GOOGLE_API_KEY",
    "GROQ_API_KEY",
    "BEDROCK_API_KEY",
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_HOST",
    "MCP_API_KEYS",
    "ADMIN_API_KEY",
    "PROXY_SECRET",
    "EIA_API_KEY",
    "IP_HASH_SALT",
}


def load_ssm(prefix: str) -> int:
    """Copy SSM parameters under `prefix` into the environment (upper-cased); returns a count."""
    import boto3  # only in Lambda

    client = boto3.client("ssm")
    n = 0
    for page in client.get_paginator("get_parameters_by_path").paginate(
        Path=prefix, Recursive=True, WithDecryption=True
    ):
        for p in page["Parameters"]:
            name = p["Name"].rsplit("/", 1)[-1].upper()
            if name in SSM_NAMES and name not in os.environ:
                os.environ[name] = p["Value"]
                n += 1
    return n


@lru_cache
def get_settings() -> Settings:
    prefix = os.environ.get("SSM_PREFIX")
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME") and prefix:
        try:
            log.info("ssm parameters loaded", extra={"count": load_ssm(prefix)})
        except Exception:  # a missing parameter must not stop the data service
            log.exception("ssm parameters not loaded")
    return Settings()
