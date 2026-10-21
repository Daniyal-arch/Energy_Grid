"""Lines out of service: ENTSO-E unavailability of transmission infrastructure (A78, brief 17, 11).

documentType A78 per border (`entsoe.BORDERS`, both directions: In_Domain and Out_Domain are the two
sides), planned (businessType A53) and forced (A54), the last 30 days and the next 30, asked in
30-day windows, four requests at a time
(ENTSO-E banned the key for a while when this ran beside the lake backfill: `wave5.yml` starts it
only when no "Lake ENTSO-E" run is active). Answers come zipped like A85
(scripts/build_imbalance.py); newer revisions of a document replace older ones; withdrawn
documents (docStatus A13) are left out.

Passed through per element: name, code (EIC), type (psrType), location, voltage where the document
names one, start and end, planned or forced, reason code and text, and the lowest available
capacity the document gives during the outage (MW). Nothing is summed.

-> frontend/public/data/eu/transmission_outages.json (card "Lines out of service" in the country
panel); lake `entsoe/transmission_outages`.

    python scripts/build_transmission_outages.py [--out DIR] [--lake lake-out] [--upload]
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import time
import xml.etree.ElementTree as ET
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import entsoe
import httpx
import wave5_common as w

KIND = {"A53": "planned", "A54": "forced"}
WINDOW_DAYS = 30
ACKS: dict[str, int] = {}  # the API's reasons for answers without documents
TMP = Path("/tmp/wave5")


# Germany publishes A78 under its TSOs' control areas and the DE-LU bidding zone, not under the
# country's code (10Y1001A1001A83F answered nothing on every German border, 2026-10-19)
DE_CODES = [
    "10Y1001A1001A82H",  # DE-LU bidding zone
    "10YDE-VE-------2",  # 50Hertz
    "10YDE-RWENET---I",  # Amprion
    "10YDE-EON------1",  # TenneT DE
    "10YDE-ENBW-----N",  # TransnetBW
]


def borders() -> list[tuple[str, str, str]]:
    """(label, in EIC, out EIC) for every border in both directions: A78 is published per
    border (In_Domain and Out_Domain, the two sides), not per area."""
    eic = entsoe.AREA_EIC

    def codes(c: str) -> list[str]:
        return DE_CODES if c == "DE" else [eic[c]]

    out = []
    for x, y in entsoe.BORDERS:
        if x in eic and y in eic:
            for cx in codes(x):
                for cy in codes(y):
                    out += [(f"{x}-{y}", cy, cx), (f"{x}-{y}", cx, cy)]
    return out


def _dt(d: str | None, t: str | None) -> str | None:
    return f"{d}T{(t or '00:00:00Z')[:5]}:00+00:00" if d else None


def parse(root: ET.Element, area: str) -> list[dict]:
    """One record per element (Asset_RegisteredResource) of each TimeSeries of an A78 document."""
    ns = {"n": root.tag.split("}")[0].strip("{")}
    mrid = root.findtext("n:mRID", namespaces=ns)
    rev = int(root.findtext("n:revisionNumber", default="0", namespaces=ns) or 0)
    status = root.findtext("n:docStatus/n:value", namespaces=ns)
    reason = root.find("n:Reason", ns)
    code = reason.findtext("n:code", namespaces=ns) if reason is not None else None
    text = reason.findtext("n:text", namespaces=ns) if reason is not None else None
    out = []
    for ts in root.findall("n:TimeSeries", ns):
        qty = [
            float(p.findtext("n:quantity", namespaces=ns) or "nan")
            for p in ts.findall("n:Available_Period/n:Point", ns)
        ]
        qty = [q for q in qty if q == q]
        volt = None
        for el in ts.iter():
            if "voltage" in el.tag.lower() and (el.text or "").strip():
                volt = el.text.strip()
                break
        base = {
            "mrid": mrid,
            "revision": rev,
            "doc_status": status,
            "area": area,
            "kind": KIND.get(
                ts.findtext("n:businessType", namespaces=ns) or "",
                ts.findtext("n:businessType", namespaces=ns),
            ),
            "start": _dt(
                ts.findtext("n:start_DateAndOrTime.date", namespaces=ns),
                ts.findtext("n:start_DateAndOrTime.time", namespaces=ns),
            ),
            "end": _dt(
                ts.findtext("n:end_DateAndOrTime.date", namespaces=ns),
                ts.findtext("n:end_DateAndOrTime.time", namespaces=ns),
            ),
            "in_domain": ts.findtext("n:in_Domain.mRID", namespaces=ns),
            "out_domain": ts.findtext("n:out_Domain.mRID", namespaces=ns),
            "reason_code": code,
            "reason_text": text,
            "voltage": volt,
            "available_mw_min": min(qty) if qty else None,
        }
        assets = ts.findall("n:Asset_RegisteredResource", ns) or [None]
        for a in assets:
            out.append(
                {
                    **base,
                    "element_eic": a.findtext("n:mRID", namespaces=ns) if a is not None else None,
                    "element": a.findtext("n:name", namespaces=ns) if a is not None else None,
                    "psr_type": a.findtext("n:asset_PSRType.psrType", namespaces=ns)
                    if a is not None
                    else None,
                    "location": a.findtext("n:location.name", namespaces=ns)
                    if a is not None
                    else None,
                }
            )
    return out


def newest_revisions(rows: list[dict]) -> list[dict]:
    """Keep each document's newest revision; drop withdrawn ones (docStatus A13)."""
    newest: dict[str, int] = {}
    for r in rows:
        newest[r["mrid"]] = max(newest.get(r["mrid"], -1), r["revision"])
    return [r for r in rows if r["revision"] == newest[r["mrid"]] and r["doc_status"] != "A13"]


def fetch(
    client: httpx.Client, eic_in: str, eic_out: str, btype: str, a: datetime, b: datetime
) -> tuple[list[ET.Element], bool]:
    q = {
        "securityToken": os.environ["ENTSOE_API_KEY"].strip(),
        "documentType": "A78",
        "BusinessType": btype,
        "In_Domain": eic_in,
        "Out_Domain": eic_out,
        "periodStart": a.strftime("%Y%m%d%H00"),
        "periodEnd": b.strftime("%Y%m%d%H00"),
    }
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
            return [ET.fromstring(z.read(n)) for n in z.namelist()], True
        if r.status_code == 200 or b"Acknowledgement" in r.content:
            m = re.search(rb"<text>([^<]*)</text>", r.content)
            why = m.group(1).decode()[:120] if m else f"HTTP {r.status_code}, no text"
            ACKS[why] = ACKS.get(why, 0) + 1
            return [], True
        print(f"  HTTP {r.status_code}: {r.text[:160]}", flush=True)
        return [], False
    return [], False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=w.EU)
    ap.add_argument("--lake", type=Path, default=Path("lake-out"))
    ap.add_argument("--upload", action="store_true")
    args = ap.parse_args()
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    start, end = now - timedelta(days=30), now + timedelta(days=30)
    rows: list[dict] = []
    failed: list[str] = []
    windows = []
    a = start
    while a < end:
        windows.append((a, min(end, a + timedelta(days=WINDOW_DAYS))))
        a = windows[-1][1]
    # one at a time took ~75 min (about 900 requests), longer than the day archive's budget:
    # four at a time like scripts/entsoe.py, still only when no lake backfill runs (wave5.yml)
    sides = borders()
    jobs = [(k, btype, a, b) for k in range(len(sides)) for btype in KIND for a, b in windows]
    with (
        httpx.Client(timeout=120, headers=w.UA) as client,
        ThreadPoolExecutor(entsoe.WORKERS) as pool,
    ):
        answers = pool.map(lambda j: fetch(client, sides[j[0]][1], sides[j[0]][2], *j[1:]), jobs)
        for n, ((k, btype, a, _), (docs, ok)) in enumerate(zip(jobs, answers, strict=True), 1):
            area, eic_in, _ = sides[k]
            if not ok:
                failed.append(f"{area} {btype} {a:%Y-%m-%d}")
            for d in docs:
                rows += parse(d, area)
            if n == len(jobs) or jobs[n][0] != k:
                print(f"  {area} (in {eic_in}): {len(rows):,} rows so far", flush=True)
    print(f"  answers without documents, by reason: {ACKS}", flush=True)
    if len(failed) > 20:
        raise SystemExit(
            f"ENTSO-E did not answer {len(failed)} requests: {failed[:10]} ...; nothing written"
        )
    rows = newest_revisions(rows)
    # a border's outage often comes back from both directions under two report ids with the same
    # fields: the card lists each published line once
    items = [
        [
            r["area"], r["element"], r["psr_type"], r["voltage"], r["start"], r["end"],
            r["kind"], r["reason_code"], r["reason_text"], r["available_mw_min"],
        ]
        for r in sorted(rows, key=lambda r: (r["area"], r["start"] or "", r["element"] or ""))
    ]  # fmt: skip
    items = list({tuple(i): i for i in items}.values())
    w.write_json(
        args.out / "transmission_outages.json",
        {
            "fetched": w.now(),
            "source": "ENTSO-E Transparency Platform, unavailability of transmission infrastructure (A78), planned (A53) and forced (A54)",
            "window": [start.isoformat(), end.isoformat()],
            "fields": [
                "border",
                "element",
                "psr type",
                "voltage",
                "start",
                "end",
                "planned/forced",
                "reason code",
                "reason",
                "lowest available MW",
            ],
            "failed": failed,
            "items": items,
        },
    )
    print(
        f"  {len(items):,} elements out of service; requests not answered: {len(failed)}",
        flush=True,
    )
    if not rows:
        return
    import duckdb

    tmp = TMP / "a78.json"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(rows), encoding="utf-8")
    con = duckdb.connect()
    import lake

    lake.iso_codes(con)
    lk = w.lake_for(
        "entsoe",
        args.lake,
        "ENTSO-E Transparency Platform (web-api.tp.entsoe.eu)",
        "ENTSO-E Transparency Platform terms of use (re-use with attribution)",
        "scripts/build_transmission_outages.py",
    )
    lk.write(
        con,
        "transmission_outages",
        f"""SELECT r.* EXCLUDE (start, "end"), r.start::TIMESTAMPTZ AS start, r."end"::TIMESTAMPTZ AS "end",
                   left(r.area, 2) AS iso2, i.iso3, NULL::VARCHAR AS admin1
            FROM read_json('{tmp}', maximum_object_size = 1000000000, sample_size = -1) r
            LEFT JOIN iso_codes i ON i.iso2 = left(r.area, 2)""",
        sort=["area", "start"],
        partition={"fetched": now.date().isoformat()},
    )
    w.lake_done(lk, args.upload)


if __name__ == "__main__":
    main()
