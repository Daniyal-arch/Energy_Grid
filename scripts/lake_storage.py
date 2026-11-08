"""Lake storage (brief 32 Step 5): the audit of both R2 buckets, and deletions the owner approved.

    python scripts/lake_storage.py audit [--out data/lake_audit.json]
    python scripts/lake_storage.py apply            # only the keys in data/lake_deletions.yaml

`audit` lists every object in `infraatlas-raw` and `infraatlas-data` (the S3 API, credentials
from scripts/r2_creds.sh), and reports:

- sizes per top prefix and per lake dataset, and the monthly cost ($0.015 per GB-month above the
  free 10 GB);
- the MaStR snapshots: objects and bytes per snapshot date, and every place outside the MaStR
  tables that names a snapshot (other datasets' catalogues, the views of `lake.duckdb`, the
  history manifests), so a deletion can be checked first;
- orphans: Parquet objects under `lake/` that no dataset catalogue lists (`_catalog.json`
  `tables[].files`), each with the catalogued files next to it (a leftover of a rebuild has
  catalogued siblings written later);
- the agent cache (`agent/cache/`): objects, bytes, oldest entry.

`apply` deletes exactly the keys listed in `data/lake_deletions.yaml` (each with its reason and
the owner's approval), after checking each still exists, and for MaStR snapshots that nothing
outside the MaStR tables reads them; it then drops the deleted files from the dataset's
catalogue. Keys not in the list are never deleted. It also sets the lifecycle rule that expires
`agent/cache/` entries after 7 days (the cache's own TTL).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
BUCKETS = ("infraatlas-raw", "infraatlas-data")
FREE_GB, USD_PER_GB = 10.0, 0.015
DELETIONS = ROOT / "data" / "lake_deletions.yaml"
CACHE_PREFIX, CACHE_DAYS = "agent/cache/", 7


def endpoint() -> str:
    acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID") or os.environ.get("R2_ACCOUNT_ID")
    if not acct or not os.environ.get("AWS_ACCESS_KEY_ID"):
        raise SystemExit("R2 credentials not set (scripts/r2_creds.sh in Actions): skipped")
    return f"https://{acct}.r2.cloudflarestorage.com"


def aws(*args: str, check: bool = True) -> str:
    r = subprocess.run(
        ["aws", *args, "--endpoint-url", endpoint()], capture_output=True, text=True, check=False
    )
    if check and r.returncode:
        raise SystemExit(f"aws {' '.join(args[:3])}: {r.stderr.strip()[:300]}")
    return r.stdout


def list_objects(bucket: str) -> list[dict[str, Any]]:
    out = aws("s3api", "list-objects-v2", "--bucket", bucket, "--output", "json")
    return [
        {"key": o["Key"], "bytes": int(o["Size"]), "modified": o["LastModified"]}
        for o in (json.loads(out or "{}").get("Contents") or [])
    ]


def get_json(bucket: str, key: str, tmp: Path) -> Any:
    f = tmp / key.replace("/", "__")
    aws("s3", "cp", "--only-show-errors", f"s3://{bucket}/{key}", str(f))
    return json.loads(f.read_text(encoding="utf-8"))


def gb(b: int) -> float:
    return round(b / 1e9, 3)


def cost(total_bytes: int) -> float:
    return round(max(0.0, total_bytes / 1e9 - FREE_GB) * USD_PER_GB, 2)


def catalogues(objs: list[dict[str, Any]], tmp: Path) -> dict[str, dict[str, Any]]:
    out = {}
    for o in objs:
        m = re.fullmatch(r"lake/([^/]+)/_catalog\.json", o["key"])
        if m:
            out[m.group(1)] = get_json("infraatlas-raw", o["key"], tmp)
    return out


def view_sql(tmp: Path) -> list[str]:
    """The SQL of every view in lake.duckdb (to find what reads a given snapshot)."""
    import duckdb

    f = tmp / "lake.duckdb"
    aws("s3", "cp", "--only-show-errors", "s3://infraatlas-raw/lake/lake.duckdb", str(f))
    con = duckdb.connect(str(f), read_only=True)
    return [r[0] or "" for r in con.execute("SELECT sql FROM duckdb_views()").fetchall()]


def snapshot_readers(snapshot: str, cats: dict[str, dict[str, Any]], views: list[str]) -> list[str]:
    """Places outside the MaStR tables that name this snapshot."""
    hits = []
    for ds, c in cats.items():
        if ds == "mastr":
            continue
        if snapshot in json.dumps(c):
            hits.append(f"catalogue lake/{ds}")
    hits += [f"view: {v[:120]}" for v in views if snapshot in v]
    for p in list((ROOT / "scripts").glob("*.py")) + list((ROOT / "agent").rglob("*.yaml")):
        if p.name == "lake_storage.py":
            continue
        if snapshot in p.read_text(encoding="utf-8", errors="ignore"):
            hits.append(f"file {p.relative_to(ROOT)}")
    return hits


def audit(out: Path) -> dict[str, Any]:
    tmp = Path("/tmp/lake-storage")
    tmp.mkdir(exist_ok=True)
    rec: dict[str, Any] = {
        "audited": datetime.now(UTC).isoformat(timespec="seconds"),
        "buckets": {},
    }
    raw: list[dict[str, Any]] = []
    for b in BUCKETS:
        objs = list_objects(b)
        if b == "infraatlas-raw":
            raw = objs
        by_prefix: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for o in objs:
            parts = o["key"].split("/")
            top = (
                "/".join(parts[:2])
                if parts[0] in ("lake", "agent") and len(parts) > 2
                else parts[0]
            )
            by_prefix[top][0] += 1
            by_prefix[top][1] += o["bytes"]
        total = sum(o["bytes"] for o in objs)
        rec["buckets"][b] = {
            "objects": len(objs),
            "gb": gb(total),
            "by_prefix": {
                k: {"objects": v[0], "gb": gb(v[1])}
                for k, v in sorted(by_prefix.items(), key=lambda x: -x[1][1])
            },
        }
    all_bytes = sum(v["gb"] for v in rec["buckets"].values()) * 1e9
    rec["total_gb"] = gb(int(all_bytes))
    rec["monthly_usd"] = cost(int(all_bytes))
    cats = catalogues(raw, tmp)
    views = view_sql(tmp)
    # MaStR snapshots
    snaps: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for o in raw:
        m = re.match(r"lake/mastr/[^/]+/.*snapshot=([\d-]+)/", o["key"])
        if m:
            snaps[m.group(1)][0] += 1
            snaps[m.group(1)][1] += o["bytes"]
    rec["mastr_snapshots"] = {
        s: {"objects": v[0], "gb": gb(v[1]), "read_outside_mastr": snapshot_readers(s, cats, views)}
        for s, v in sorted(snaps.items())
    }
    # orphans: lake Parquet no catalogue lists
    listed = {
        f"lake/{ds}/{f}"
        for ds, c in cats.items()
        for t in (c.get("tables") or {}).values()
        for f in t.get("files", [])
    }
    orphans = []
    for o in raw:
        k = o["key"]
        if not (k.startswith("lake/") and k.endswith(".parquet")) or k in listed:
            continue
        folder = k.rsplit("/", 1)[0]
        siblings = sorted(x for x in listed if x.rsplit("/", 1)[0] == folder)
        orphans.append({**o, "catalogued_siblings": siblings[:5], "dataset": k.split("/")[1]})
    rec["orphans"] = {
        "objects": len(orphans),
        "gb": gb(sum(o["bytes"] for o in orphans)),
        "list": orphans,
    }
    cache = [o for o in raw if o["key"].startswith(CACHE_PREFIX)]
    rec["agent_cache"] = {
        "objects": len(cache),
        "gb": gb(sum(o["bytes"] for o in cache)),
        "oldest": min((o["modified"] for o in cache), default=None),
    }
    rec["rasters"] = sorted(
        (
            {"key": o["key"], "gb": gb(o["bytes"])}
            for o in raw
            if o["key"].endswith((".tif", ".tiff"))
        ),
        key=lambda x: -x["gb"],
    )[:25]
    out.write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8")
    print(report(rec))
    return rec


def report(rec: dict[str, Any]) -> str:
    lines = [f"Audited {rec['audited']}: {rec['total_gb']} GB, ${rec['monthly_usd']} a month.", ""]
    for b, v in rec["buckets"].items():
        lines += [
            f"### {b}: {v['objects']:,} objects, {v['gb']} GB",
            "",
            "| prefix | objects | GB |",
            "|---|---:|---:|",
        ]
        lines += [
            f"| `{k}` | {x['objects']:,} | {x['gb']} |"
            for k, x in list(v["by_prefix"].items())[:30]
        ]
        lines.append("")
    lines += [
        "### MaStR snapshots",
        "",
        "| snapshot | objects | GB | read outside the MaStR tables |",
        "|---|---:|---:|---|",
    ]
    lines += [
        f"| {s} | {v['objects']} | {v['gb']} | {'; '.join(v['read_outside_mastr']) or 'nothing'} |"
        for s, v in rec["mastr_snapshots"].items()
    ]
    o = rec["orphans"]
    lines += [
        "",
        f"### Orphans: {o['objects']} objects, {o['gb']} GB",
        "",
        "| key | MB | modified | catalogued siblings |",
        "|---|---:|---|---|",
    ]
    lines += [
        f"| `{x['key']}` | {x['bytes'] / 1e6:,.2f} | {x['modified'][:10]} | {len(x['catalogued_siblings'])} |"
        for x in o["list"]
    ]
    c = rec["agent_cache"]
    lines += ["", f"Agent cache: {c['objects']:,} objects, {c['gb']} GB, oldest {c['oldest']}."]
    lines += ["", "### Largest rasters", ""] + [
        f"- `{r['key']}`: {r['gb']} GB" for r in rec["rasters"]
    ]
    return "\n".join(lines)


def apply() -> None:
    plan = yaml.safe_load(DELETIONS.read_text(encoding="utf-8")) or {}
    items = [d for d in plan.get("delete", []) if d.get("approved")]
    raw = {o["key"]: o for o in list_objects("infraatlas-raw")}
    tmp = Path("/tmp/lake-storage")
    tmp.mkdir(exist_ok=True)
    cats = catalogues(list(raw.values()), tmp)
    views = view_sql(tmp)
    done: dict[str, list[str]] = defaultdict(list)
    for d in items:
        keys = [k for k in raw if re.fullmatch(d["match"], k)] if d.get("match") else [d["key"]]
        snap = d.get("snapshot")
        if snap:
            readers = snapshot_readers(snap, cats, views)
            if readers:
                print(f"NOT deleted ({d['reason']}): snapshot {snap} is read by {readers}")
                continue
        for k in keys:
            if k not in raw:
                print(f"gone already: {k}")
                continue
            aws("s3", "rm", "--only-show-errors", f"s3://infraatlas-raw/{k}")
            done[k.split("/")[1]].append(k)
            print(f"deleted {k} ({raw[k]['bytes'] / 1e6:,.1f} MB): {d['reason']}")
    # the catalogues forget the deleted files
    for ds, keys in done.items():
        c = cats.get(ds)
        if not c:
            continue
        rel = {k.split("/", 2)[2] for k in keys}
        for t in (c.get("tables") or {}).values():
            files = [f for f in t.get("files", []) if f not in rel]
            if len(files) != len(t.get("files", [])):
                t["files"] = files
                stats = {f: v for f, v in (t.get("file_stats") or {}).items() if f not in rel}
                t["file_stats"] = stats
                t["rows"] = sum(v[0] for v in stats.values())
                t["bytes"] = sum(v[1] for v in stats.values())
        f = tmp / f"{ds}_catalog.json"
        f.write_text(json.dumps(c, indent=1, ensure_ascii=False), encoding="utf-8")
        aws(
            "s3", "cp", "--only-show-errors", str(f), f"s3://infraatlas-raw/lake/{ds}/_catalog.json"
        )
        print(f"catalogue lake/{ds} updated ({len(keys)} files dropped)")
    rule = {
        "Rules": [
            {
                "ID": "agent-cache-expiry",
                "Status": "Enabled",
                "Filter": {"Prefix": CACHE_PREFIX},
                "Expiration": {"Days": CACHE_DAYS},
            }
        ]
    }
    existing = aws(
        "s3api", "get-bucket-lifecycle-configuration", "--bucket", "infraatlas-raw", check=False
    )
    rules = (json.loads(existing).get("Rules") if existing.strip() else []) or []
    rules = [r for r in rules if r.get("ID") != "agent-cache-expiry"] + rule["Rules"]
    f = tmp / "lifecycle.json"
    f.write_text(json.dumps({"Rules": rules}), encoding="utf-8")
    aws(
        "s3api",
        "put-bucket-lifecycle-configuration",
        "--bucket",
        "infraatlas-raw",
        "--lifecycle-configuration",
        f"file://{f}",
    )
    print(f"lifecycle: {CACHE_PREFIX} expires after {CACHE_DAYS} days")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["audit", "apply"])
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "lake_audit.json")
    a = ap.parse_args()
    if a.action == "audit":
        audit(a.out)
    else:
        apply()


if __name__ == "__main__":
    sys.exit(main())
