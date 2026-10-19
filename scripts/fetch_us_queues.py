"""The US markets' own interconnection queues, fresher than LBNL's yearly "Queued Up".

Each market publishes its queue (Excel or a web table); the open-source `gridstatus` library
(MIT) reads them into one shape (scripts/probe_us_nodes.py shows what each returns). Kept
markets: CAISO, ERCOT, MISO, SPP, ISO-NE and NYISO (its queue file answered again on
2026-10-19, wave 7; it had answered with a bot check, HTTP 202). PJM needs a key that is not set
yet: it is listed as missing, not estimated. Runs in GitHub Actions (ERCOT blocks many non-US addresses).

Passthrough per request: queue id, state, generation type, capacity (MW), queue date, status.
Computed for the map file: active requests (the market's own status "active", any case) summed
per state and resource type. Types are mapped onto LBNL's names (TYPE_RULES) so the Queue tab
reads both side by side; a hybrid ("Photovoltaic + Storage", "SUN BAT") counts under each of
its types with its full capacity, LBNL's rule, so type sums exceed the request total.

Writes frontend/public/data/us/queues_live.json and, with --lake, the full tables (every column
the market publishes) to the lake (`lake/iso_queues/requests`, snapshot partitions).

    python scripts/fetch_us_queues.py [--out DIR] [--lake lake-out --upload]
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "data" / "us"
SOURCE = "The markets' interconnection queues (CAISO, ERCOT, MISO, SPP, ISO-NE, NYISO), read with gridstatus (MIT)"
MARKETS = {
    "CAISO": "CAISO",
    "ERCOT": "Ercot",
    "MISO": "MISO",
    "SPP": "SPP",
    "ISO-NE": "ISONE",
    "NYISO": "NYISO",
}
MISSING = {
    "PJM": "needs PJM_API_KEY",
}
# (pattern, LBNL type), first match per part; a part is one technology of a hybrid
TYPE_RULES = [
    (r"offshore", "Offshore Wind"),
    (r"wind|wnd", "Wind"),
    (r"photovoltaic|solar|\bsun\b|\bpv\b", "Solar"),
    (r"batter|\bbat\b|energy storage|^storage|\bes\b", "Battery"),
    (r"pumped|storage", "Other Storage"),
    (r"nuclear|\bnuc\b", "Nuclear"),
    (r"hydrogen", "Hydrogen"),
    (r"geothermal|\bgeo\b", "Geothermal"),
    (r"hydro|\bwat\b|water", "Hydro"),
    (r"coal", "Coal"),
    (r"diesel|\bdfo\b", "Diesel"),
    (r"\boil\b", "Oil"),
    (r"gas|\bng\b|combined|combustion|turbine|steam|reciprocat|internal combustion|thermal", "Gas"),
]
STATES = {
    "alabama": "AL", "arizona": "AZ", "arkansas": "AR", "california": "CA", "colorado": "CO",
    "connecticut": "CT", "delaware": "DE", "florida": "FL", "georgia": "GA", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY",
    "louisiana": "LA", "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI",
    "minnesota": "MN", "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
    "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA",
    "washington": "WA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}  # fmt: skip


def types_of(text: str | None) -> list[str]:
    """LBNL types of a request's generation type text (several for a hybrid).

    A hybrid is split at "+", "/", ";", "," or "and" ("Photovoltaic + Storage",
    "Hybrid - Solar/Storage"), or into ISO-NE's capital codes ("SUN BAT"); each part takes the
    first matching rule, so "Wind - Wind Turbine" stays wind.
    """
    s = str(text or "").strip()
    if not s or s.lower() in ("nan", "none"):
        return ["Other"]
    tokens = s.split()
    codes = len(tokens) > 1 and all(t.isupper() and len(t) <= 4 for t in tokens)
    parts = tokens if codes else re.split(r"\s*(?:\+|/|;|,|and)\s*", s)
    found: list[str] = []
    for part in parts:
        name = next((n for pat, n in TYPE_RULES if re.search(pat, part.lower())), "Other")
        if name not in found:
            found.append(name)
    return [t for t in found if t != "Other"] or ["Other"]


def state_of(text: str | None) -> str | None:
    s = str(text or "").strip()
    if len(s) == 2 and s.isalpha():
        return s.upper()
    return STATES.get(s.lower())


def mw(v: object) -> float:
    try:
        x = float(v)  # type: ignore[arg-type]
        return x if x == x else 0.0  # NaN
    except (TypeError, ValueError):
        return 0.0


def summarise(rows: list[dict]) -> dict:
    """Active requests per state and type (MW, a hybrid under each of its types)."""
    by_state: dict[str, dict[str, float]] = {}
    by_type: dict[str, float] = {}
    statuses: dict[str, int] = {}
    active_n, active_mw = 0, 0.0
    for r in rows:
        st = str(r.get("Status") or "not given")
        statuses[st] = statuses.get(st, 0) + 1
        if st.strip().lower() != "active":
            continue
        m = mw(r.get("Capacity (MW)"))
        active_n += 1
        active_mw += m
        state = state_of(r.get("State")) or "not given"
        for t in types_of(r.get("Generation Type")):
            by_type[t] = by_type.get(t, 0) + m
            by_state.setdefault(state, {})
            by_state[state][t] = by_state[state].get(t, 0) + m
    rnd = lambda d: {k: round(v, 1) for k, v in sorted(d.items(), key=lambda kv: -kv[1])}  # noqa: E731
    return {
        "requests": len(rows),
        "active": active_n,
        "active_mw": round(active_mw, 1),
        "by_type": rnd(by_type),
        "by_state": {
            s: rnd(v) for s, v in sorted(by_state.items(), key=lambda kv: -sum(kv[1].values()))
        },
        "statuses": dict(sorted(statuses.items(), key=lambda kv: -kv[1])),
    }


def main() -> None:
    import gridstatus

    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--lake", type=Path, help="also write the full tables to this lake root")
    parser.add_argument("--upload", action="store_true", help="upload the lake files to R2")
    args = parser.parse_args()
    fetched = datetime.now(UTC).isoformat(timespec="seconds")
    markets: dict[str, dict] = {}
    frames = {}
    for name, cls in MARKETS.items():
        try:
            df = getattr(gridstatus, cls)().get_interconnection_queue()
        except Exception as e:  # noqa: BLE001 - one market down must not stop the others
            markets[name] = {"error": f"{type(e).__name__}: {str(e)[:200]}"}
            print(f"  {name}: failed ({e})", flush=True)
            continue
        frames[name] = df
        rows = df.astype(object).where(df.notna(), None).to_dict("records")
        markets[name] = summarise(rows)
        print(
            f"  {name}: {len(rows)} requests, {markets[name]['active']} active, {markets[name]['active_mw'] / 1000:.1f} GW",
            flush=True,
        )
    for name, why in MISSING.items():
        markets[name] = {"missing": why}
    out = {"fetched": fetched, "source": SOURCE, "markets": markets}
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "queues_live.json"
    path.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"-> {path}")
    if args.lake and frames:
        write_lake(frames, args.lake, fetched[:10], args.upload)


def write_lake(frames: dict, root: Path, snapshot: str, upload: bool) -> None:
    """Every market's full table, all columns as published (text), one snapshot partition each."""
    import duckdb
    from lake import Lake

    lake = Lake(
        "iso_queues",
        root,
        source=SOURCE,
        licence="each market's terms (public data)",
        script="scripts/fetch_us_queues.py",
        source_version=snapshot,
    )
    con = duckdb.connect()
    for name, df in frames.items():
        cols = list(df.columns)
        flat = df.astype(str).rename(
            columns={c: re.sub(r"[^0-9a-zA-Z]+", "_", str(c)).strip("_").lower() for c in cols}
        )
        con.register("q", flat)
        lake.write(
            con,
            "requests",
            f"SELECT '{name}' AS market, 'US' AS iso2, 'USA' AS iso3, * FROM q",
            sort=["queue_id"] if "queue_id" in flat.columns else ["market"],
            bloom=["queue_id"] if "queue_id" in flat.columns else [],
            partition={"snapshot": snapshot, "market": name.lower().replace("-", "")},
        )
        con.unregister("q")
    lake.pull_catalog() if upload else None
    lake.finish()
    if upload:
        lake.upload()


if __name__ == "__main__":
    main()
