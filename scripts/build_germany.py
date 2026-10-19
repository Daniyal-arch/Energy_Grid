"""German redispatch from netztransparenz.de's open archive (brief 17, dataset 8).

The four TSOs publish every redispatch measure on netztransparenz.de. Measures since 2021 (and
costs and curtailment, "EinsMan") come only through its API, which needs a free client
registration (NETZTRANSPARENZ_CLIENT_ID / _SECRET, api-portal.netztransparenz.de); the open
archive `redispatch export 2013-2020.zip` (CSV, one row per measure) has no key.

Passed through per measure: start and end (UTC), reason, direction, mean and maximum MW, energy
(MWh), the instructing and the requesting TSO, the plants affected, primary energy. Computed:
energy per month (by the measure's start, UTC), split by direction and by requesting TSO (sums).

-> frontend/public/data/eu/de_redispatch.json (a card in Germany's panel); lake
`netztransparenz/redispatch`.

    python scripts/build_germany.py [--lake lake-out] [--upload]
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import wave5_common as w

URL = (
    "https://www.netztransparenz.de/xspproxy/api/staticfiles/ntp-relaunch/dokumente/"
    "systemdienstleistungen/betriebsf%C3%BChrung/redispatch/archiv/"
    "2025-09-17%20redispatch%20export%202013-2020.zip"
)
TMP = Path("/tmp/wave5")
DIRECTION = {
    "Wirkleistungseinspeisung reduzieren": "reduce",
    "Wirkleistungseinspeisung erhöhen": "increase",
}


def num(s: str | None) -> float | None:
    """German or plain numbers: "1.234,5" and "1234.5" and "267" (None when empty)."""
    s = (s or "").strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parse(row: dict) -> dict:
    """One CSV row (German column names, dd.mm.yyyy dates, UTC) as a record."""

    def ts(d: str, t: str) -> str:
        return datetime.strptime(f"{d} {t}", "%d.%m.%Y %H:%M").isoformat() + "+00:00"

    return {
        "start": ts(row["BEGINN_DATUM"], row["BEGINN_UHRZEIT"]),
        "end": ts(row["ENDE_DATUM"], row["ENDE_UHRZEIT"]),
        "tz_start": row["ZEITZONE_VON"],
        "reason": row["GRUND_DER_MASSNAHME"],
        "direction": DIRECTION.get(row["RICHTUNG"], row["RICHTUNG"]),
        "mean_mw": num(row["MITTLERE_LEISTUNG_MW"]),
        "max_mw": num(row["MAXIMALE_LEISTUNG_MW"]),
        "mwh": num(row["GESAMTE_ARBEIT_MWH"]),
        "instructing_tso": row["ANWEISENDER_UENB"],
        "requesting_tso": row["ANFORDERNDER_UENB"],
        "plants": row["BETROFFENE_ANLAGE"],
        "primary_energy": row["PRIMAERENERGIEART"],
    }


def monthly(rows: list[dict]) -> dict:
    """MWh per month (by start) and direction, and per month and requesting TSO."""
    months = sorted({r["start"][:7] for r in rows})
    k = {m: i for i, m in enumerate(months)}
    by_dir: dict[str, list[float]] = defaultdict(lambda: [0.0] * len(months))
    by_tso: dict[str, list[float]] = defaultdict(lambda: [0.0] * len(months))
    for r in rows:
        if r["mwh"] is None:
            continue
        by_dir[r["direction"]][k[r["start"][:7]]] += r["mwh"]
        by_tso[r["requesting_tso"]][k[r["start"][:7]]] += r["mwh"]

    def rnd(d: dict) -> dict:
        return {a: [round(x) for x in v] for a, v in sorted(d.items())}

    return {"months": months, "by_direction": rnd(by_dir), "by_requesting_tso": rnd(by_tso)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lake", type=Path, default=Path("lake-out"))
    ap.add_argument("--upload", action="store_true")
    args = ap.parse_args()
    src = w.download(URL, TMP / "redispatch_2013_2020.zip")
    with zipfile.ZipFile(src) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        text = z.read(name).decode("utf-8-sig")
    rows = [parse(r) for r in csv.DictReader(io.StringIO(text), delimiter=";")]
    m = monthly(rows)
    w.write_json(
        w.EU / "de_redispatch.json",
        {
            "fetched": w.now(),
            "source": "netztransparenz.de (50Hertz, Amprion, TenneT, TransnetBW), redispatch export 2013-2020 (open archive)",
            "measures": len(rows),
            **m,
        },
    )
    print(f"  {len(rows):,} measures, {m['months'][0]} .. {m['months'][-1]}", flush=True)
    import duckdb

    tmp = TMP / "redispatch.json"
    tmp.write_text(json.dumps(rows), encoding="utf-8")
    con = duckdb.connect()
    lk = w.lake_for(
        "netztransparenz", args.lake, "netztransparenz.de redispatch export 2013-2020",
        "netztransparenz.de terms (data of the German TSOs, re-use with attribution)",
        "scripts/build_germany.py", "2025-09-17 export",
    )  # fmt: skip
    lk.write(
        con,
        "redispatch",
        f"""SELECT start::TIMESTAMPTZ AS start, "end"::TIMESTAMPTZ AS "end", * EXCLUDE (start, "end"),
                   'DE' AS iso2, 'DEU' AS iso3, NULL::VARCHAR AS admin1
            FROM read_json('{tmp}', maximum_object_size = 1000000000)""",
        sort=["start", "requesting_tso"],
    )
    w.lake_done(lk, args.upload)


if __name__ == "__main__":
    main()
