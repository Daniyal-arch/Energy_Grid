"""Object storage for saved maps and run records: R2 (S3 API) when configured, else a local dir.

Keys: `agent/maps/<id>.json`, `agent/logs/<date>/<trace>.json`, `agent/results/<id>.json`.
The R2 token for these is read-write on `agent/` only (docs/tasks/25 credentials table).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from app.settings import Settings


def s3_client(s: Settings) -> Any:
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=f"https://{s.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=s.r2_access_key_id,
        aws_secret_access_key=s.r2_secret_access_key,
        region_name="auto",
    )


class Store(Protocol):
    def put_json(self, key: str, value: Any) -> None: ...
    def get_json(self, key: str) -> Any | None: ...


class LocalStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, key: str) -> Path:
        if ".." in key or key.startswith("/"):
            raise ValueError("bad key")
        return self.root / key

    def put_json(self, key: str, value: Any) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(value, default=str), encoding="utf-8")

    def get_json(self, key: str) -> Any | None:
        p = self._path(key)
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


class R2Store:
    def __init__(self, s: Settings) -> None:
        self.client = s3_client(s)
        self.bucket = s.r2_agent_bucket

    def put_json(self, key: str, value: Any) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=json.dumps(value, default=str).encode(),
            ContentType="application/json",
        )

    def get_json(self, key: str) -> Any | None:
        try:
            obj = self.client.get_object(Bucket=self.bucket, Key=key)
        except self.client.exceptions.NoSuchKey:
            return None
        return json.loads(obj["Body"].read())


def get_store(s: Settings) -> Store:
    return R2Store(s) if s.r2_configured else LocalStore(s.local_store_dir)
