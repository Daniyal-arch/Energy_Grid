"""Build the prepared answers of brief 32 Tier 0 (tools/prepared.py).

    python -m probes.build_prepared --shard 0 --shards 8 --out /out/prepared-0.jsonl
    python probes/build_prepared.py --merge DIR --lake lake-out --public public-out

Shard mode runs in the backend image against the real lake (the same code and data the service
answers with). It resolves the names people ask most, exactly as `resolve_area` does for them,
and stores, per area id and template key (`tools.prepared.PREPARED`), the template's answer with
its sources, the build time and the data fingerprint:

- every country;
- US states; Overture regions by their own and their English names;
- NUTS 1, 2 and 3 regions;
- GB local authority districts (ONS);
- every GHS urban centre;
- every local administrative unit (Overture `localadmin` and `locality`, GISCO LAU) with 10,000
  people or more (the outline table's own population column).

Names that resolve ambiguously are counted (the answer is stored for the area picked, by its
outline id, which is exactly what `quick` looks up); an area reached twice is stored once.

Merge mode (no backend needed) writes `lake/prepared/answers/part-0.parquet` with its catalogue,
and one public JSON per area (`answers/v1/<area_id>.json`: every prepared template) for the app.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))


def names_to_prepare(ctx: Any) -> list[tuple[str, str | None, str]]:
    """(name, level hint, set) for every area to prepare, in a fixed order."""
    out: list[tuple[str, str | None, str]] = []
    out += [(n, None, "country") for n in sorted(set(ctx.areas.country_names.values()))]
    out += [(p.name, None, "us_state") for p in ctx.gazetteer.us_states]
    cur = ctx.lake.cursor()
    queries = {
        # regions and counties by their own and their English names ("Bavaria" resolves to
        # the Overture region, not the NUTS outline "Bayern"); before the large sets, so the
        # shards' time budget reaches them
        "region": "SELECT DISTINCT name FROM outlines.names WHERE \"set\" = 'divisions' "
        "AND level = 'region' ORDER BY 1",
        "region_en": "SELECT DISTINCT alias FROM outlines.aliases WHERE language = 'en' "
        "AND level = 'region' ORDER BY 1",
        "nuts": "SELECT DISTINCT name FROM shapes.nuts WHERE level IN (1, 2, 3) ORDER BY 1",
        "lad": "SELECT DISTINCT name FROM outlines.uk_ons WHERE regexp_matches(lower(level), 'lad|district') ORDER BY 1",
        "urban_centre": "SELECT DISTINCT name FROM outlines.urban_centres ORDER BY 1",
        "localadmin": "SELECT DISTINCT name FROM outlines.divisions WHERE level IN ('localadmin', 'locality') AND population >= 10000 ORDER BY 1",
        "lau": "SELECT DISTINCT name FROM outlines.lau WHERE population >= 10000 ORDER BY 1",
    }
    for key, sql in queries.items():
        try:
            rows = [r[0] for r in cur.execute(sql).fetchall() if r[0]]
        except Exception as e:  # noqa: BLE001 - a set this lake does not hold
            print(f"  set {key}: not read ({str(e)[:120]})", flush=True)
            continue
        print(f"  set {key}: {len(rows):,} names", flush=True)
        out += [(n, None, key) for n in rows]
    seen: set[str] = set()
    uniq = []
    for n, lv, s in out:
        k = f"{n.lower()}|{lv}"
        if k not in seen:
            seen.add(k)
            uniq.append((n, lv, s))
    return uniq


def build(shard: int, shards: int, out: Path, max_minutes: float) -> None:
    from app.settings import Settings
    from tools import prepared
    from tools.areas import resolve_area
    from tools.context import ToolContext
    from tools.quick import QuickError, answer_for

    t0 = time.time()
    ctx = ToolContext(Settings())
    if hasattr(ctx.lake, "wait_hot"):
        ctx.lake.wait_hot(600)
    fp = prepared.fingerprint(ctx)
    todo = names_to_prepare(ctx)[shard::shards]
    built = datetime.now(UTC).isoformat(timespec="seconds")
    stats = {
        "names": len(todo),
        "areas": 0,
        "answers": 0,
        "ambiguous": 0,
        "unresolved": 0,
        "errors": 0,
    }
    done: set[str] = set()
    with out.open("w", encoding="utf-8") as f:
        for i, (name, level, set_key) in enumerate(todo):
            if time.time() - t0 > max_minutes * 60:
                stats["stopped_at"] = i
                break
            try:
                d = resolve_area(ctx, names=[name], level=level)["data"]
            except Exception:  # noqa: BLE001
                stats["unresolved"] += 1
                continue
            a = d.get("area")
            if not a:
                stats["unresolved"] += 1
                continue
            if d.get("ambiguous"):  # counted only: answers are keyed by the area resolved
                stats["ambiguous"] += 1  # (its outline's id), which is what quick looks up
            if a["area_id"] in done:
                continue
            done.add(a["area_id"])
            if hasattr(ctx.lake, "wait_area_cells"):  # its cells once, not 3 s in every query
                tw = time.time()
                ctx.lake.wait_area_cells([a["area_id"]], 300)
                stats["cell_wait_s"] = round(stats.get("cell_wait_s", 0) + time.time() - tw, 1)
            stats["areas"] += 1
            summary = {k: a[k] for k in ("area_id", "name", "level", "iso3")}
            for template, n, kind in prepared.PREPARED:
                try:
                    tables = answer_for(ctx, template, a, n, kind)
                except (QuickError, Exception) as e:  # noqa: BLE001 - recorded, the template runs live
                    stats["errors"] += 1
                    stats.setdefault("first_errors", {}).setdefault(
                        f"{template}:{kind}", f"{type(e).__name__}: {str(e)[:160]}"
                    )
                    continue
                sources: list[dict[str, str]] = []
                for t in tables:
                    t.pop("result_id", None)  # results live in one container; not portable
                    for s in t.pop("sources", []):
                        if s not in sources:
                            sources.append(s)
                payload = {
                    "data": {"template": template, "area": summary, "tables": tables},
                    "sources": sources,
                }
                f.write(json.dumps({
                    "area_id": a["area_id"], "key": prepared.key_of(template, n, kind), "name": a["name"],
                    "level": a["level"], "set": set_key, "payload": json.dumps(payload, default=str),
                    "built": built, "fingerprint": fp,
                }) + "\n")  # fmt: skip
                stats["answers"] += 1
            if (i + 1) % 100 == 0:
                print(
                    f"  {i + 1}/{len(todo)} names, {stats['areas']} areas, {time.time() - t0:.0f} s "
                    f"({stats.get('cell_wait_s', 0):.0f} s waiting for cells)",
                    flush=True,
                )
    stats["seconds"] = round(time.time() - t0)
    stats["fingerprint"] = fp
    print(json.dumps(stats), flush=True)
    out.with_suffix(".stats.json").write_text(json.dumps(stats), encoding="utf-8")


def merge(d: Path, lake_dir: Path, public: Path) -> None:
    import duckdb

    files = sorted(d.rglob("*.jsonl"))
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for p in files:
        for line in p.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            rows[(r["area_id"], r["key"])] = r
    if not rows:
        raise SystemExit("no prepared answers to merge")
    tbl = lake_dir / "prepared" / "answers"
    tbl.mkdir(parents=True, exist_ok=True)
    jl = d / "all.jsonl"
    jl.write_text("".join(json.dumps(r) + "\n" for r in rows.values()), encoding="utf-8")
    part = tbl / "part-0.parquet"
    con = duckdb.connect()
    con.execute(
        f"COPY (SELECT area_id, key, name, level, \"set\", payload, built, fingerprint FROM read_json('{jl}', "
        "format = 'newline_delimited', columns = {area_id: 'VARCHAR', key: 'VARCHAR', name: 'VARCHAR', "
        "level: 'VARCHAR', set: 'VARCHAR', payload: 'VARCHAR', built: 'VARCHAR', fingerprint: 'VARCHAR'}) "
        f"ORDER BY area_id, key) TO '{part}' (FORMAT parquet, COMPRESSION zstd, COMPRESSION_LEVEL 9, "
        "ROW_GROUP_SIZE 20000, KV_METADATA {source: 'computed by backend/probes/build_prepared.py "
        "(the quick templates over the app tables and the lake)', licence: 'as each answer''s sources'})"
    )
    n, b = len(rows), part.stat().st_size
    cols = {r[0]: str(r[1]) for r in con.execute(f"DESCRIBE SELECT * FROM '{part}'").fetchall()}
    built = max(r["built"] for r in rows.values())
    cat = {
        "dataset": "prepared",
        "source": "computed by backend/probes/build_prepared.py (brief 32 Tier 0)",
        "licence": "as each answer's sources",
        "script": "backend/probes/build_prepared.py",
        "updated": built,
        "tables": {"answers": {"path": "lake/prepared/answers/*.parquet", "partitions": [], "sort": ["area_id", "key"],
                               "bloom": [], "rows": n, "bytes": b, "columns": cols,
                               "files": ["answers/part-0.parquet"], "file_stats": {"answers/part-0.parquet": [n, b]}}},
    }  # fmt: skip
    (lake_dir / "prepared" / "_catalog.json").write_text(
        json.dumps(cat, indent=1), encoding="utf-8"
    )
    by_area: dict[str, dict[str, Any]] = {}
    for r in rows.values():
        e = by_area.setdefault(r["area_id"], {"area_id": r["area_id"], "name": r["name"], "level": r["level"],
                                              "built": r["built"], "fingerprint": r["fingerprint"], "answers": {}})  # fmt: skip
        e["answers"][r["key"]] = json.loads(r["payload"])
    out = public / "answers" / "v1"
    out.mkdir(parents=True, exist_ok=True)
    for aid, e in by_area.items():
        (out / f"{aid}.json").write_text(json.dumps(e, separators=(",", ":")), encoding="utf-8")
    public_bytes = sum(p.stat().st_size for p in out.iterdir())
    sets: dict[str, int] = {}
    for r in rows.values():
        if r["key"] == "profile:10:plants":
            sets[r["set"]] = sets.get(r["set"], 0) + 1
    print(f"{len(by_area):,} areas, {n:,} answers; lake table {b / 1e6:,.1f} MB; public JSON "
          f"{public_bytes / 1e6:,.1f} MB in {len(by_area):,} files; areas per set: {sets}")  # fmt: skip
    stats = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.rglob("*.stats.json"))]
    for k in ("names", "ambiguous", "unresolved", "errors"):
        print(f"  {k}: {sum(s.get(k, 0) for s in stats):,}")
    if any("stopped_at" in s for s in stats):
        print(
            "  some shards stopped at their time budget: the rest of their names are not prepared"
        )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--out", type=Path, default=Path("/tmp/prepared.jsonl"))
    ap.add_argument("--max-minutes", type=float, default=100)
    ap.add_argument("--merge", type=Path)
    ap.add_argument("--lake", type=Path, default=Path("lake-out"))
    ap.add_argument("--public", type=Path, default=Path("public-out"))
    a = ap.parse_args()
    if a.merge:
        merge(a.merge, a.lake, a.public)
    else:
        build(a.shard, a.shards, a.out, a.max_minutes)


if __name__ == "__main__":
    main()
