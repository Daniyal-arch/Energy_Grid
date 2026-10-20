"""Redispatch, countertrading, congestion-management costs and curtailment (brief 22, family 4).

    python scripts/build_congestion.py entsoe|gb|caiso|all [--days N] [--out DIR] [--lake lake-out] [--upload]

New months are merged into the existing file (`--days 35` daily keeps the year built before).

entsoe  ENTSO-E Transparency Platform (`ENTSOE_API_KEY`), per control area, one request at a time:
        redispatching internal (documentType A63, businessType A85) and cross-border (A63, A46),
        countertrading (A91) and costs of congestion management (A92). Germany is asked per TSO
        control area. One request per calendar month (the API answers a year at most), split further
        where the API holds more than 100 instances for the window. Passed through: every point (MW, or EUR for costs) with its time,
        resolution, direction and business type. Computed: MWh = MW × the point's duration, summed
        per month and country; costs summed per month and country.
gb      NESO "Constraint Breakdown Costs and Volume" (NESO Open Data Licence): daily costs (GBP) and
        volumes (MWh) of thermal, voltage, inertia and largest-loss constraints; summed per month.
caiso   CAISO production and curtailments data (5-min wind and solar curtailment, MW, with the
        reason: local or system): MWh = MW × 5/60, summed per month, wind and solar, local and system.

Writes frontend/public/data/eu/congestion.json (per country: months and sums, with the source) and
lake tables entsoe/congestion_* (every point), neso/constraint_breakdown, caiso/curtailment.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import entsoe  # noqa: E402
import httpx  # noqa: E402
import wave5_common as w  # noqa: E402
import wave7_common as w7  # noqa: E402

OUT = w.EU / "congestion.json"
SCRIPT = "scripts/build_congestion.py"
DE_AREAS = {
    "50Hertz": "10YDE-VE-------2",
    "Amprion": "10YDE-RWENET---I",
    "TenneT DE": "10YDE-EON------1",
    "TransnetBW": "10YDE-ENBW-----N",
}
# (key, documentType, businessType or None, same area in and out)
QUERIES = [
    ("redispatch_internal", "A63", "A85", True),
    ("redispatch_cross_border", "A63", "A46", False),
    ("countertrading", "A91", None, False),
    ("costs", "A92", None, True),
]
RES_H = {"PT15M": 0.25, "PT30M": 0.5, "PT60M": 1.0, "P1D": 24.0, "P7D": 168.0}
ACKS: dict[str, int] = defaultdict(int)


def areas() -> dict[str, list[tuple[str, str]]]:
    """Country -> [(area label, EIC)]: the control areas the requests are made for."""
    out: dict[str, list[tuple[str, str]]] = {}
    for cc, eic in entsoe.AREA_EIC.items():
        if cc in ("UA", "MD", "XK", "BA", "ME", "RS", "AL", "MK", "GB", "NO", "CH"):
            continue
        out[cc] = list(DE_AREAS.items()) if cc == "DE" else [(cc, eic)]
    return out


def neighbours(cc: str) -> list[str]:
    return sorted({b if a == cc else a for a, b in entsoe.BORDERS if cc in (a, b)})


def fetch(client: httpx.Client, params: dict[str, str]) -> tuple[list[ET.Element], str]:
    """(documents, acknowledgement text) of one query: zipped or plain XML; acknowledgements
    (no data, or a refusal) give no document and their text."""
    q = {"securityToken": os.environ["ENTSOE_API_KEY"].strip(), **params}
    for attempt in range(4):
        try:
            r = client.get(entsoe.BASE, params=q)
        except httpx.TransportError:
            time.sleep(10 * (attempt + 1))
            continue
        if r.status_code == 429:
            print(f"  HTTP 429: {r.text[:160]}", flush=True)
            time.sleep(60 * (attempt + 1))
            continue
        if r.status_code >= 500:
            time.sleep(15 * (attempt + 1))
            continue
        if r.content[:2] == b"PK":
            z = zipfile.ZipFile(io.BytesIO(r.content))
            return [ET.fromstring(z.read(n)) for n in z.namelist()], ""
        if b"Acknowledgement" in r.content[:400] or r.status_code != 200:
            m = re.search(rb"<text>([^<]*)</text>", r.content)
            text = m.group(1).decode() if m else f"HTTP {r.status_code}"
            return [], text
        return [ET.fromstring(r.content)], ""
    return [], "gave up"


TOO_MANY = re.compile(r"number of instances \((\d+)\) exceeds the allowed maximum \((\d+)\)")


def windows(start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    """Calendar months from start to end (the API takes at most a year per request)."""
    out, t = [], start
    while t < end:
        nxt = (t.replace(day=1) + timedelta(days=32)).replace(day=1, hour=0)
        out.append((t, min(nxt, end)))
        t = nxt
    return out


def fetch_window(
    client: httpx.Client, params: dict[str, str], t0: datetime, t1: datetime
) -> list[ET.Element]:
    """Documents of one window; split into parts when the API answers that it holds more
    instances than it returns at once (100), down to one hour."""
    docs, ack = fetch(
        client,
        params | {"periodStart": t0.strftime("%Y%m%d%H00"), "periodEnd": t1.strftime("%Y%m%d%H00")},
    )
    m = TOO_MANY.search(ack)
    if m and t1 - t0 > timedelta(hours=1):
        parts = max(2, -(-int(m.group(1)) // (int(m.group(2)) - 10)))
        step = max(timedelta(hours=1), (t1 - t0) / parts)
        out, t = [], t0
        while t < t1:
            u = min(t + step, t1)
            u = u.replace(minute=0, second=0, microsecond=0) if u < t1 else u
            if u <= t:
                u = min(t + timedelta(hours=1), t1)
            out += fetch_window(client, params, t, u)
            t = u
        return out
    if ack:
        ACKS[ack[:100] if not ack.startswith("No matching data") else "No matching data"] += 1
    return docs


def points(root: ET.Element) -> list[dict]:
    """Every point of every TimeSeries: time, resolution, the series' flat fields and the point's
    numeric fields (quantity in MW; for costs, the amount fields in EUR)."""
    ns = {"n": root.tag.split("}")[0].strip("{")}
    doc = {"doc_type": root.findtext("n:type", namespaces=ns), "mrid": root.findtext("n:mRID", namespaces=ns),
           "revision": root.findtext("n:revisionNumber", namespaces=ns)}  # fmt: skip
    out = []
    for ts in root.findall("n:TimeSeries", ns):
        meta = {
            c.tag.split("}")[1]: (c.text or "").strip()
            for c in ts
            if not len(c) and (c.text or "").strip()
        }
        for period in ts.findall("n:Period", ns):
            res = period.findtext("n:resolution", default="", namespaces=ns)
            start = period.findtext("n:timeInterval/n:start", default="", namespaces=ns)
            t0 = datetime.strptime(start, "%Y-%m-%dT%H:%MZ").replace(tzinfo=UTC) if start else None
            hours = RES_H.get(res)
            for p in period.findall("n:Point", ns):
                pos = int(p.findtext("n:position", default="1", namespaces=ns))
                vals = {}
                for el in p.iter():
                    tag = el.tag.split("}")[1]
                    if (
                        tag != "position"
                        and el.text
                        and re.fullmatch(r"-?\d+(\.\d+)?", el.text.strip())
                    ):
                        vals[tag] = float(el.text)
                at = t0 + timedelta(hours=hours * (pos - 1)) if t0 and hours else t0
                out.append(
                    {
                        **doc,
                        **meta,
                        "resolution": res,
                        "time": at.isoformat() if at else None,
                        "hours": hours,
                        **vals,
                    }
                )
    return out


def monthly(rows: list[dict], value: str, scale_hours: bool) -> dict[str, float]:
    """{YYYY-MM: sum} of `value` (× the point's hours for MWh when `scale_hours`)."""
    out: dict[str, float] = defaultdict(float)
    for r in rows:
        v = r.get(value)
        if v is None or not r.get("time"):
            continue
        out[r["time"][:7]] += v * (r["hours"] or 0) if scale_hours else v
    return {k: round(v, 1) for k, v in sorted(out.items())}


def build_entsoe(args: argparse.Namespace) -> dict:
    end = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=args.days)
    rows_by: dict[str, list[dict]] = defaultdict(list)
    countries: dict[str, dict] = {}
    ars = areas()
    with httpx.Client(timeout=120) as client:
        for cc, own in ars.items():
            res: dict[str, dict] = {}
            for key, doc, btype, same in QUERIES:
                if same:
                    pairs = [(label, eic, eic) for label, eic in own]
                else:  # cross-border: one request per border and direction, this country's side in In_Domain
                    pairs = [
                        (f"{label}>{n}", eic, neic)
                        for n in neighbours(cc)
                        if n in ars
                        for label, eic in own
                        for _, neic in ars[n]
                    ]
                found: list[dict] = []
                for label, i_dom, o_dom in pairs:
                    params = {"documentType": doc, "In_Domain": i_dom, "Out_Domain": o_dom}
                    if btype:
                        params["businessType"] = btype
                    for t0, t1 in windows(start, end):
                        for root in fetch_window(client, params, t0, t1):
                            found += [
                                {**p, "iso2": cc, "area": label, "query": key} for p in points(root)
                            ]
                rows_by[key] += found
                if found:
                    if key == "costs":
                        amount = next(
                            (k for k in found[0] if k.endswith("amount") or k == "costs"), None
                        )
                        res[key] = {
                            "months": monthly(found, amount, False) if amount else {},
                            "unit": "EUR",
                            "field": amount,
                            "n": len(found),
                        }
                    else:
                        dirs = defaultdict(list)
                        for p in found:
                            dirs[
                                p.get("flowDirection.direction") or p.get("direction") or "all"
                            ].append(p)
                        res[key] = {"unit": "MWh (MW × duration, computed)", "n": len(found),
                                    "by_direction": {d: monthly(v, "quantity", True) for d, v in dirs.items()}}  # fmt: skip
                print(f"  {cc} {key}: {len(pairs)} requests, {len(found)} points", flush=True)
            if res:
                countries[cc] = res
    print(f"  acknowledgements: {dict(ACKS)}", flush=True)
    for key, rows in rows_by.items():
        if rows:
            w7.lake_rows("entsoe", [(f"congestion_{key}", rows, ["iso2", "time"], None)], lake_dir=args.lake, upload=args.upload,
                         source=entsoe.SOURCE, licence="ENTSO-E terms of use", script=SCRIPT)  # fmt: skip
    return {"source": "ENTSO-E Transparency Platform: redispatching (A63), countertrading (A91), costs of congestion management (A92)",
            "window": [start.isoformat(), end.isoformat()], "countries": countries, "acks": dict(ACKS)}  # fmt: skip


# ---------------------------------------------------------------- Great Britain (NESO)

NESO = "https://api.neso.energy/api/3/action/package_show?id=constraint-breakdown"


def neso_rows(text: str) -> list[dict]:
    out = []
    for r in csv.DictReader(io.StringIO(text.lstrip("﻿"))):
        out.append(
            {k.strip(): (w7.number(v) if k.strip() != "Date" else v) for k, v in r.items() if k}
        )
    return out


def build_gb(args: argparse.Namespace) -> dict:
    pkg = w7.get(NESO).json()["result"]
    rows = []
    for res in pkg["resources"][-3:]:  # the newest three financial years
        rows += neso_rows(w7.get(res["url"]).text)
    months: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for r in rows:
        m = (r.get("Date") or "")[:7]
        for k, v in r.items():
            if k != "Date" and v is not None:
                months[m][k] += v
    w7.lake_rows("neso", [("constraint_breakdown", [{**r, "iso2": "GB"} for r in rows], ["Date"], None)], lake_dir=args.lake, upload=args.upload,
                 source="NESO Data Portal, Constraint Breakdown Costs and Volume", licence="NESO Open Data Licence", script=SCRIPT)  # fmt: skip
    return {"source": "NESO, Constraint Breakdown Costs and Volume (daily)", "licence": "NESO Open Data Licence", "url": "https://www.neso.energy/data-portal/constraint-breakdown",
            "unit": "costs GBP, volumes MWh, as published (summed per month, computed)", "months": {m: {k: round(v, 1) for k, v in d.items()} for m, d in sorted(months.items())}}  # fmt: skip


# ---------------------------------------------------------------- California (CAISO)

CAISO_PAGE = "https://www.caiso.com/library/production-curtailments-data"


def caiso_months(path: Path) -> tuple[dict, list[dict]]:
    import openpyxl

    ws = openpyxl.load_workbook(path, read_only=True, data_only=True)["Curtailments"]
    it = ws.iter_rows(values_only=True)
    head = [str(h or "") for h in next(it)]
    i_t, i_w, i_s, i_r = (
        head.index("Date"),
        head.index("Wind Curtailment"),
        head.index("Solar Curtailment"),
        head.index("Reason"),
    )
    months: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    rows = []
    for r in it:
        if not r or r[i_t] is None:
            continue
        m = r[i_t].strftime("%Y-%m") if hasattr(r[i_t], "strftime") else str(r[i_t])[:7]
        reason = (r[i_r] or "unknown").strip().lower()
        for kind, v in (("wind", r[i_w]), ("solar", r[i_s])):
            if isinstance(v, int | float) and v:
                months[m][f"{kind}_{reason}_mwh"] += v * 5 / 60
        rows.append({"time": str(r[i_t]), "wind_mw": r[i_w], "solar_mw": r[i_s], "reason": r[i_r]})
    return {m: {k: round(v, 1) for k, v in d.items()} for m, d in sorted(months.items())}, rows


def build_caiso(args: argparse.Namespace) -> dict:
    page = w7.get(CAISO_PAGE).text
    links = sorted(
        set(
            re.findall(
                r'href="([^"]*production-?and-?curtailments-?data[-_][^"]*\.xlsx)"', page, re.I
            )
        )
    )
    year_links = [u for u in links if re.search(r"20\d\d\.xlsx$", u)]
    newest = max(year_links, key=lambda u: u[-9:-5])
    url = newest if newest.startswith("http") else "https://www.caiso.com" + newest
    w7.TMP.mkdir(parents=True, exist_ok=True)
    path = w7.TMP / "caiso_curtailment.xlsx"
    path.write_bytes(w7.get(url, timeout=300).content)
    months, rows = caiso_months(path)
    w7.lake_rows("caiso", [("curtailment", [{**r, "iso2": "US"} for r in rows], ["time"], None)], lake_dir=args.lake, upload=args.upload,
                 source="CAISO production and curtailments data", licence="CAISO, public", script=SCRIPT)  # fmt: skip
    return {"source": "CAISO, production and curtailments data (5-min wind and solar curtailment)", "licence": "CAISO, public", "url": url,
            "unit": "MWh = MW × 5/60, summed per month (computed); reason as published (local, system)", "months": months}  # fmt: skip


def merge_months(old: object, new: object) -> object:
    """New figures over old ones, month by month: a short daily window keeps the year built before."""
    if isinstance(old, dict) and isinstance(new, dict):
        return {k: merge_months(old.get(k), v) for k, v in new.items()} | {
            k: v for k, v in old.items() if k not in new
        }
    return new


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["entsoe", "gb", "caiso", "all"])
    ap.add_argument("--days", type=int, default=400)
    ap.add_argument("--lake", type=Path, default=Path("lake-out"))
    ap.add_argument("--upload", action="store_true")
    ap.add_argument(
        "--out", type=Path, default=OUT.parent, help="folder of congestion.json (merged into)"
    )
    args = ap.parse_args()
    out = args.out / "congestion.json"
    data = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    failed = []
    for what in ["entsoe", "gb", "caiso"] if args.what == "all" else [args.what]:
        print(f"== {what}", flush=True)
        try:
            data[what] = {
                **{"entsoe": build_entsoe, "gb": build_gb, "caiso": build_caiso}[what](args),
                "fetched": w.now(),
            }
        except (SystemExit, Exception) as e:  # one source failing must not stop the others
            print(f"  {what} failed: {type(e).__name__} {str(e)[:300]}", flush=True)
            failed.append(what)
    data["fetched"] = w.now()
    w.write_json(out, data)
    if failed:
        raise SystemExit(f"failed: {' '.join(failed)}")


if __name__ == "__main__":
    main()
