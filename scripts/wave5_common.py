"""Shared helpers for the wave-5 builders (docs/tasks/17-datasets-wave5.md).

Downloads with retries and progress lines, unzipping to a temporary folder, compact JSON for
the app, simplified geometry, and the hand-over of DuckDB tables to `scripts/lake.py`.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
EU = ROOT / "frontend" / "public" / "data" / "eu"
US = ROOT / "frontend" / "public" / "data" / "us"
UA = {"User-Agent": "InfraAtlas (github.com/Daniyal-arch/Energy_Grid)"}


def download(url: str, dest: Path, *, tries: int = 4, timeout: float = 600, **kw: object) -> Path:
    """`url` to `dest` (kept when already there), streamed, with a progress line every ~50 MB."""
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, tries + 1):
        try:
            with httpx.stream(
                "GET", url, timeout=timeout, follow_redirects=True, headers=UA, **kw
            ) as r:  # type: ignore[arg-type]
                r.raise_for_status()
                total = int(r.headers.get("content-length") or 0)
                got, mark, t0 = 0, 0, time.time()
                with part.open("wb") as f:
                    for chunk in r.iter_bytes(1 << 20):
                        f.write(chunk)
                        got += len(chunk)
                        if got - mark >= 50_000_000:
                            mark = got
                            share = f" of {total / 1e6:,.0f}" if total else ""
                            print(
                                f"  {dest.name}: {got / 1e6:,.0f}{share} MB, {time.time() - t0:.0f} s",
                                flush=True,
                            )
            part.rename(dest)
            print(f"  {dest.name}: {dest.stat().st_size / 1e6:,.1f} MB", flush=True)
            return dest
        except (httpx.HTTPError, OSError) as err:
            print(f"  {url}: {type(err).__name__} {err} (try {attempt}/{tries})", flush=True)
            time.sleep(10 * attempt)
    raise SystemExit(f"download failed: {url}")


def get_json(url: str, *, tries: int = 4, timeout: float = 120, **kw: object) -> object:
    """One JSON answer, retried on network errors, 429 and 5xx."""
    last = ""
    for attempt in range(1, tries + 1):
        try:
            r = httpx.get(url, timeout=timeout, follow_redirects=True, headers=UA, **kw)  # type: ignore[arg-type]
            if r.status_code == 429 or r.status_code >= 500:
                last = f"HTTP {r.status_code}"
                time.sleep(10 * attempt)
                continue
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as err:
            last = f"{type(err).__name__} {err}"
            time.sleep(5 * attempt)
    raise SystemExit(f"{url}: {last}")


def unzip(path: Path, members: list[str] | None = None) -> Path:
    """Extract (some members of) a zip into a new temporary folder; returns the folder."""
    out = Path(tempfile.mkdtemp(prefix=path.stem + "-"))
    with zipfile.ZipFile(path) as z:
        z.extractall(out, members=members)
    return out


def write_json(path: Path, payload: dict, max_mb: float = 5.0) -> None:
    """Compact JSON for the app; refuses files over `max_mb` (bigger outputs go to R2)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    if len(text.encode()) > max_mb * 1e6:
        raise SystemExit(f"{path.name}: {len(text) / 1e6:.1f} MB, over {max_mb} MB")
    path.write_text(text, encoding="utf-8")
    print(f"  wrote {path.relative_to(ROOT)}: {path.stat().st_size / 1e6:.2f} MB", flush=True)


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def rings(geom: object, digits: int = 3) -> list[list[list[float]]]:
    """A shapely (multi)polygon as [polygon][ring] of flat lon/lat pairs (the app's format)."""
    polys = [geom] if geom.geom_type == "Polygon" else list(getattr(geom, "geoms", []))  # type: ignore[attr-defined]
    out = []
    for p in polys:
        if p.geom_type != "Polygon" or p.is_empty:
            continue
        out.append(
            [
                [round(c, digits) for xy in r.coords for c in xy[:2]]
                for r in [p.exterior, *p.interiors]
            ]
        )
    return out


def lake_for(dataset: str, root: Path, source: str, licence: str, script: str, version: str = ""):  # noqa: ANN201
    import lake

    return lake.Lake(
        dataset, root, source=source, licence=licence, script=script, source_version=version
    )


def lake_done(lk, upload: bool) -> None:  # noqa: ANN001 - a lake.Lake
    """Write the catalogue (merged into the uploaded one) and upload the run's files."""
    if upload:
        try:
            lk.pull_catalog()
        except SystemExit as e:
            print(f"  catalogue not pulled: {e}", flush=True)
    path = lk.finish()
    cat = json.loads(path.read_text(encoding="utf-8"))
    for name, t in sorted(cat["tables"].items()):
        print(f"  lake/{lk.dataset}/{name}: {t['rows']:,} rows, {t['bytes']:,} bytes", flush=True)
    if upload:
        lk.upload()


def upload_public(path: Path, key: str, content_type: str) -> None:
    """A file to the public bucket (infraatlas-data/<key>), via wrangler (Actions only)."""
    import lake

    if not lake.wrangler(
        "r2", "object", "put", f"infraatlas-data/{key}", "--file", str(path),
        "--content-type", content_type, "--remote",
    ):  # fmt: skip
        raise SystemExit(f"upload of {key} failed")
    print(f"  r2://infraatlas-data/{key}: {path.stat().st_size / 1e6:.1f} MB", flush=True)


def env(name: str) -> str:
    v = (os.environ.get(name) or "").strip()
    if not v:
        raise SystemExit(f"{name} is not set")
    return v
