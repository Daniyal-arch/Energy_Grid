"""Plan documents behind the zoning layers: keep the PDFs privately and their text for the agent.

Reads the document links of the zoning lake (`zoning.zones.doc_url`, and for France every
file of each plan from the Géoportail de l'Urbanisme document API), then:

  --measure N   HEAD a random sample of N links per source and report count, mean size and the
                projected total, without downloading anything (rule 4: explain large downloads
                first; the full archive is an owner decision, docs/owner-questions.md).
  --fetch N     download up to N PDFs per source, store each on R2 under
                `infraatlas-raw/zoning-docs/<source>/<sha256>.pdf` (private: plan PDFs carry
                their authors' copyright even where the data is open), and write
                lake tables `zoning.documents` (one row per file: url, plan, bytes, sha256,
                pages, r2 key) and `zoning.document_pages` (one row per page: text as the PDF
                holds it; scanned pages without a text layer stay empty and are counted).

    uv run python scripts/zoning_documents.py --zones lake-out/zoning --measure 200
    uv run python scripts/zoning_documents.py --zones lake-out/zoning --fetch 50 --upload
"""

from __future__ import annotations

import argparse
import hashlib
import io
import logging
import random
import time
from pathlib import Path
from typing import Any

import duckdb
import httpx
from lake import Lake, wrangler
from pypdf import PdfReader

logging.getLogger("pypdf").setLevel(logging.ERROR)  # font warnings, not errors
UA = {"User-Agent": "Europe-InfraAtlas zoning documents"}
GPU = "https://www.geoportail-urbanisme.gouv.fr/api/document"


def links(con: duckdb.DuckDBPyConnection, zones: str) -> dict[str, list[tuple[str, str]]]:
    """(plan_id, url) per source: the zones' own document links, PDFs and pages alike."""
    rows = con.execute(
        f"SELECT DISTINCT source, plan_id, doc_url FROM read_parquet('{zones}/zones/*/*.parquet', "
        "hive_partitioning=true) WHERE doc_url LIKE 'http%'"
    ).fetchall()
    out: dict[str, list[tuple[str, str]]] = {}
    for src, plan, url in rows:
        out.setdefault(src, []).append((plan or "", url))
    return out


def france_files(c: httpx.Client, con: duckdb.DuckDBPyConnection, zones: str, n: int) -> list:
    """Files of a random sample of n French plans (gpu_doc_id from the zones' attributes)."""
    ids = con.execute(
        f"SELECT DISTINCT attributes->>'gpu_doc_id', attributes->>'partition', plan_id "
        f"FROM read_parquet('{zones}/zones/source=fr_gpu/*.parquet')"
    ).fetchall()
    out = []
    for gid, part, plan in random.sample(ids, min(n, len(ids))):
        r = c.get(f"{GPU}/{gid}/files")
        if r.status_code != 200:
            continue
        for f in r.json():
            url = f"https://data.geopf.fr/annexes/gpu/documents/{part}/{gid}/{f['depot_path']}"
            out.append((plan, url))
    return out


def head_size(c: httpx.Client, url: str) -> tuple[int | None, str]:
    try:
        r = c.head(url)
        if r.status_code >= 400 or "content-length" not in r.headers:
            r = c.get(url, headers={"Range": "bytes=0-0"})
            total = r.headers.get("content-range", "").split("/")[-1]
            return (int(total) if total.isdigit() else None), r.headers.get("content-type", "")
        return int(r.headers["content-length"]), r.headers.get("content-type", "")
    except httpx.HTTPError:
        return None, ""


def measure(c: httpx.Client, per: dict[str, list[tuple[str, str]]], n: int) -> None:
    print("| source | links | sampled | answered | PDF | mean MB | projected GB |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for src, items in sorted(per.items()):
        sample = random.sample(items, min(n, len(items)))
        sizes, pdf = [], 0
        for _plan, url in sample:
            size, ctype = head_size(c, url)
            if size is not None:
                sizes.append(size)
                pdf += "pdf" in ctype.lower() or url.lower().endswith(".pdf")
        mean = sum(sizes) / len(sizes) if sizes else 0
        print(
            f"| {src} | {len(items):,} | {len(sample)} | {len(sizes)} | {pdf} | "
            f"{mean / 1e6:.2f} | {mean * len(items) / 1e9:,.1f} |"
        )


def pages(data: bytes) -> list[str]:
    try:
        return [(p.extract_text() or "").strip() for p in PdfReader(io.BytesIO(data)).pages]
    except Exception:  # noqa: BLE001 - a broken PDF is recorded with no pages
        return []


def fetch(
    c: httpx.Client, per: dict[str, list[tuple[str, str]]], n: int, out: Path, upload: bool
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    docs, texts = [], []
    seen: set[str] = set()  # one file linked from several plans: its pages once
    for src, items in sorted(per.items()):
        got = 0
        for plan, url in random.sample(items, len(items)):
            if got >= n:
                break
            try:
                r = c.get(url)
            except httpx.HTTPError:
                continue
            if r.status_code != 200 or not r.content.startswith(b"%PDF"):
                continue
            sha = hashlib.sha256(r.content).hexdigest()
            if sha in seen:
                docs.append({**next(d for d in docs if d["doc_id"] == sha), "plan_id": plan,
                             "url": url, "source": src})  # fmt: skip
                continue
            seen.add(sha)
            key = f"zoning-docs/{src}/{sha}.pdf"
            path = out / f"{sha}.pdf"
            path.write_bytes(r.content)
            if upload and not wrangler(
                "r2", "object", "put", f"infraatlas-raw/{key}", "--file", str(path), "--remote"
            ):
                raise SystemExit(f"upload of {key} failed")
            path.unlink()
            ps = pages(r.content)
            docs.append({"doc_id": sha, "source": src, "plan_id": plan, "url": url,
                         "bytes": len(r.content), "pages": len(ps),
                         "pages_with_text": sum(bool(p) for p in ps), "r2_key": key})  # fmt: skip
            texts += [{"doc_id": sha, "page": i + 1, "text": t} for i, t in enumerate(ps)]
            got += 1
            time.sleep(0.2)
        print(f"  {src}: {got} PDFs", flush=True)
    return docs, texts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zones", type=Path, required=True, help="local lake-out/zoning folder")
    ap.add_argument("--measure", type=int, default=0)
    ap.add_argument("--fetch", type=int, default=0)
    ap.add_argument("--lake", type=Path, default=Path("lake-out"))
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--seed", type=int, default=32)
    a = ap.parse_args()
    random.seed(a.seed)
    con = duckdb.connect()
    zones = str(a.zones)
    per = links(con, zones)
    with httpx.Client(timeout=120, headers=UA, follow_redirects=True) as c:
        if (a.zones / "zones" / "source=fr_gpu").exists():
            per["fr_gpu (plan files)"] = france_files(c, con, zones, max(a.measure, a.fetch, 50))
        if a.measure:
            measure(c, per, a.measure)
        if a.fetch:
            tmp = a.lake / "_docs"
            tmp.mkdir(parents=True, exist_ok=True)
            docs, texts = fetch(c, per, a.fetch, tmp, a.upload)
            lake = Lake("zoning", a.lake, source="plan documents linked by the zoning sources",
                        licence="each publisher's own terms; PDFs kept private",
                        script="scripts/zoning_documents.py")  # fmt: skip
            if a.upload:
                lake.pull_catalog()
            con.execute("CREATE TABLE d AS SELECT * FROM (SELECT unnest($1, recursive := true))",
                        [docs])  # fmt: skip
            con.execute("CREATE TABLE t AS SELECT * FROM (SELECT unnest($1, recursive := true))",
                        [texts])  # fmt: skip
            lake.write(con, "documents", "SELECT * FROM d", sort=["source", "plan_id"],
                       bloom=["doc_id", "plan_id"])  # fmt: skip
            lake.write(con, "document_pages", "SELECT * FROM t", sort=["doc_id", "page"],
                       bloom=["doc_id"])  # fmt: skip
            lake.finish()
            if a.upload:
                lake.upload()


if __name__ == "__main__":
    main()
