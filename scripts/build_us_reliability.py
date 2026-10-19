"""United States: reliability and demand (brief 21, group E).

    python scripts/build_us_reliability.py oe417|ferc714 [--lake lake-out] [--upload]

oe417    DOE Form OE-417 electric emergency and disturbance events (DOE CESER, public domain): the
         annual summaries (xls/xlsx, oe.netl.doe.gov), every event as published (began, restored,
         area, NERC region, event type, demand loss MW, customers affected). Computed: the year;
         the states named in the "Area Affected" text (US state names matched); counts per state
         and per event type -> frontend/public/data/us/oe417.json, lake `oe417/events`.
ferc714  FERC Form 714 hourly demand per planning area (PUDL `out_ferc714__hourly_planning_area_demand`,
         in place, CC BY 4.0): the newest full year's daily mean demand per planning area (MW,
         computed from the hourly values as reported; PUDL's imputed values are not used), each
         planning area placed in its EIA-930 region by its balancing authority (PUDL
         `out_ferc714__respondents_with_fips`, `core_eia__codes_balancing_authorities`) ->
         frontend/public/data/us/ferc714.json. No lake copy (PUDL is the store).
"""

from __future__ import annotations

import argparse
import re
import subprocess
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

import wave5_common as w

TMP = Path("/tmp/wave6/us")
OE417_PAGE = "https://www.oe.netl.doe.gov/OE417_annual_summary.aspx"
PUDL = "https://s3.us-west-2.amazonaws.com/pudl.catalyst.coop/stable"
STATES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA", "Colorado": "CO", "Connecticut": "CT",
    "Delaware": "DE", "District of Columbia": "DC", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL",
    "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE",
    "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY", "North Carolina": "NC",
    "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI",
    "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA",
    "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY", "Puerto Rico": "PR",
}  # fmt: skip


def get_text(url: str) -> str:
    """A page via httpx, else curl over IPv4 (the probe saw 'Network is unreachable' from Actions)."""
    import httpx

    try:
        return httpx.get(url, headers=w.UA, timeout=90, follow_redirects=True).text
    except httpx.HTTPError as e:
        print(f"  httpx: {type(e).__name__} {e}; trying curl -4", flush=True)
    r = subprocess.run(
        ["curl", "-4", "-sSL", "--max-time", "120", "-A", w.UA["User-Agent"], url],
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode:
        raise SystemExit(f"{url}: curl -4 exit {r.returncode}: {r.stderr.strip()[:300]}")
    return r.stdout


def states_in(area: object) -> list[str]:
    """US states named in an OE-417 'Area Affected' text (whole names, longest first)."""
    t = str(area or "")
    found: list[str] = []
    for name in sorted(STATES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(name)}\b", t, re.I):
            if (
                name == "Virginia"
                and re.search(r"\bWest Virginia\b", t, re.I)
                and not re.search(r"(?<!West )\bVirginia\b", t, re.I)
            ):
                continue
            if name == "Washington" and re.search(r"Washington,? D\.?C", t):
                continue
            if STATES[name] not in found:
                found.append(STATES[name])
    return found


def oe417_events(rows: list[tuple]) -> list[dict]:
    """A summary sheet: the header row holds 'Event Type'; values as published."""
    hi = next(
        i
        for i, r in enumerate(rows)
        if any(isinstance(v, str) and v.strip().lower().startswith("event type") for v in r)
    )
    head = [re.sub(r"\s+", " ", str(v)).strip().lower() if v is not None else "" for v in rows[hi]]

    def col(*names: str) -> int | None:
        for n in names:
            for j, h in enumerate(head):
                if h.startswith(n):
                    return j
        return None

    c = {k: col(*v) for k, v in {
        "began_date": ("date event began",), "began_time": ("time event began",), "restored_date": ("date of restoration",),
        "restored_time": ("time of restoration",), "area": ("area affected", "geographic area"), "nerc": ("nerc region",),
        "criteria": ("alert criteria",), "type": ("event type",), "mw": ("demand loss",), "customers": ("number of customers",),
    }.items()}  # fmt: skip
    out = []
    for r in rows[hi + 1 :]:
        get = lambda k: r[c[k]] if c[k] is not None and c[k] < len(r) else None  # noqa: E731
        if not get("type") and not get("area"):
            continue
        ev = {k: get(k) for k in c}
        for k in ("began_date", "restored_date"):
            v = ev[k]
            ev[k] = (
                v.date().isoformat()
                if isinstance(v, datetime)
                else (v.isoformat() if isinstance(v, date) else (str(v).strip() if v else None))
            )
        for k in ("began_time", "restored_time"):
            v = ev[k]
            ev[k] = (
                v.strftime("%H:%M") if hasattr(v, "strftime") else (str(v).strip() if v else None)
            )
        for k in ("mw", "customers"):
            v = ev[k]
            ev[k] = v if isinstance(v, int | float) and not isinstance(v, bool) else None
        for k in ("area", "nerc", "criteria", "type"):
            ev[k] = re.sub(r"\s+", " ", str(ev[k])).strip() if ev[k] else None
        ev["states"] = states_in(ev["area"])
        out.append(ev)
    return out


def build_oe417(args: argparse.Namespace) -> None:
    html = get_text(OE417_PAGE)
    links = list(dict.fromkeys(re.findall(r'href="([^"]*(?:XLS|xls)[^"]*)"', html, re.I)))
    print(f"  {len(links)} spreadsheet links, e.g. {links[:3]}", flush=True)
    if not links:
        raise SystemExit("OE-417: no spreadsheet links on the page")
    import openpyxl
    import xlrd

    events: list[dict] = []
    for href in links:
        url = href if href.startswith("http") else "https://www.oe.netl.doe.gov/" + href.lstrip("/")
        path = TMP / f"oe417_{len(events)}_{abs(hash(url))}.xls"
        TMP.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(
            ["curl", "-4", "-sSL", "--max-time", "180", "-o", str(path), url],
            capture_output=True,
            text=True,
            check=False,
        )
        if r.returncode or not path.exists():
            print(f"  {url}: {r.stderr.strip()[:200]}", flush=True)
            continue
        head = path.read_bytes()[:8]
        try:
            if head.startswith(b"PK"):
                ws = openpyxl.load_workbook(path, read_only=True, data_only=True).worksheets[0]
                rows = [tuple(x) for x in ws.iter_rows(values_only=True)]
            else:
                book = xlrd.open_workbook(str(path))
                sh = book.sheet_by_index(0)
                rows = []
                for i in range(sh.nrows):
                    vals = []
                    for j, cell in enumerate(sh.row(i)):
                        v = cell.value
                        if cell.ctype == xlrd.XL_CELL_DATE:
                            v = xlrd.xldate.xldate_as_datetime(v, book.datemode)
                            v = v if j < 3 or v.year > 1900 else v.time()
                        vals.append(v if v != "" else None)
                    rows.append(tuple(vals))
            evs = oe417_events(rows)
        except Exception as e:  # noqa: BLE001 - one bad year must not stop the rest
            print(f"  {url}: {type(e).__name__} {str(e)[:160]}", flush=True)
            continue
        print(f"  {url.split('/')[-1][:60]}: {len(evs)} events", flush=True)
        events += evs
    if not events:
        raise SystemExit("OE-417: no events read")
    for e in events:
        m = re.match(r"(\d{4})", e["began_date"] or "") or re.search(
            r"(\d{4})", e["began_date"] or ""
        )
        e["year"] = int(m.group(1)) if m else None
    years = sorted({e["year"] for e in events if e["year"]})
    by_state: dict[str, Counter] = defaultdict(Counter)
    by_type: dict[int, Counter] = defaultdict(Counter)
    for e in events:
        for s in e["states"]:
            by_state[s][e["year"]] += 1
        by_type[e["year"]][e["type"] or "not given"] += 1
    recent = sorted(
        (e for e in events if e["began_date"]), key=lambda e: e["began_date"], reverse=True
    )[:60]
    w.write_json(w.US / "oe417.json", {
        "fetched": w.now(), "source": "DOE OE-417 electric emergency incident and disturbance reports, annual summaries (DOE CESER)",
        "years": years,
        # state -> {year: events naming the state}
        "states": {s: {str(y): n for y, n in sorted(c.items()) if y} for s, c in sorted(by_state.items())},
        # year -> {event type: events}
        "types": {str(y): dict(c.most_common()) for y, c in sorted(by_type.items()) if y},
        # [began, area, event type, demand loss MW, customers]
        "recent": [[e["began_date"], e["area"], e["type"], e["mw"], e["customers"]] for e in recent],
    })  # fmt: skip
    import json as _json

    import duckdb

    tmp = TMP / "oe417.json"
    tmp.write_text(_json.dumps(events, default=str), encoding="utf-8")
    con = duckdb.connect()
    lk = w.lake_for(
        "oe417",
        args.lake,
        "DOE OE-417 annual summaries",
        "public domain (US government)",
        "scripts/build_us_reliability.py",
        f"{years[0]}-{years[-1]}",
    )
    lk.write(
        con, "events",
        f"""SELECT * EXCLUDE (states), array_to_string(states, ';') AS states, 'US' AS iso2, 'USA' AS iso3, NULL::VARCHAR AS admin1
            FROM read_json('{tmp}', sample_size = -1)""",
        sort=["year", "began_date"],
    )  # fmt: skip
    w.lake_done(lk, args.upload)


# ---------------------------------------------------------------- FERC 714


def build_ferc714(args: argparse.Namespace) -> None:
    import duckdb

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs")
    dem = f"{PUDL}/out_ferc714__hourly_planning_area_demand.parquet"
    # the newest year with (nearly) every hour reported by most planning areas
    year = con.execute(
        f"""SELECT max(y) FROM (SELECT year(report_date) y, count(DISTINCT respondent_id_ferc714) n
            FROM '{dem}' WHERE demand_reported_mwh IS NOT NULL GROUP BY 1) WHERE n >= 80"""
    ).fetchone()[0]  # type: ignore[index]
    con.execute(
        f"""CREATE TABLE ba AS SELECT r.respondent_id_ferc714 AS rid, any_value(r.respondent_name_ferc714) AS name,
                   any_value(r.balancing_authority_code_eia) AS ba, any_value(c.balancing_authority_region_code_eia) AS region
            FROM '{PUDL}/out_ferc714__respondents_with_fips.parquet' r
            LEFT JOIN '{PUDL}/core_eia__codes_balancing_authorities.parquet' c ON c.code = r.balancing_authority_code_eia
            WHERE year(r.report_date) = {year} GROUP BY 1"""
    )
    rows = con.execute(
        f"""SELECT d.respondent_id_ferc714, CAST(date_trunc('day', d.datetime_utc) AS DATE) AS day,
                   avg(d.demand_reported_mwh) AS mw, count(d.demand_reported_mwh) AS hours
            FROM '{dem}' d WHERE year(d.report_date) = {year}
            GROUP BY 1, 2 ORDER BY 1, 2"""
    ).fetchall()
    names = {r[0]: r[1:] for r in con.execute("SELECT rid, name, ba, region FROM ba").fetchall()}
    resp_names = dict(
        con.execute(
            f"SELECT respondent_id_ferc714, respondent_name_ferc714 FROM '{PUDL}/core_ferc714__respondent_id.parquet'"
        ).fetchall()
    )
    start = date(year, 1, 1)
    days = (date(year + 1, 1, 1) - start).days
    areas: dict[str, dict] = {}
    for rid, day, mw, hours in rows:
        if not isinstance(day, date) or day.year != year:
            continue
        a = areas.setdefault(str(rid), {"name": (names.get(rid) or [None])[0] or resp_names.get(rid), "ba": (names.get(rid) or [None, None])[1],
                                         "region": (names.get(rid) or [None, None, None])[2], "daily_mw": [None] * days})  # fmt: skip
        a["daily_mw"][(day - start).days] = round(mw) if mw is not None and hours >= 20 else None
    areas = {k: v for k, v in areas.items() if sum(x is not None for x in v["daily_mw"]) >= 300}
    regions = Counter(v["region"] for v in areas.values())
    print(
        f"  {year}: {len(areas)} planning areas with 300+ days; regions {regions.most_common()}",
        flush=True,
    )
    w.write_json(w.US / "ferc714.json", {
        "fetched": w.now(), "year": year, "start": start.isoformat(),
        "source": "FERC Form 714, hourly demand per planning area (via PUDL out_ferc714__hourly_planning_area_demand, CC BY 4.0)",
        "computed": "daily mean of the hourly demand as reported (days with 20 or more hours); region from the planning area's balancing authority (EIA)",
        # respondent id -> {name, ba, region (EIA-930 region code), daily_mw}
        "areas": areas,
    })  # fmt: skip


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["oe417", "ferc714"])
    ap.add_argument("--lake", type=Path, default=Path("lake-out"))
    ap.add_argument("--upload", action="store_true")
    args = ap.parse_args()
    {"oe417": build_oe417, "ferc714": build_ferc714}[args.what](args)


if __name__ == "__main__":
    main()
