"""EV charging in Europe (brief 22, family 9): counts per country and where the chargers are.

    python scripts/build_ev_eu.py eafo|de|fr|osm|all [--only CC,CC] [--upload]

Counts (every EU country and the UK): the European Alternative Fuels Observatory (European
Commission, EAFO), public recharging points per country from its published CSVs:
  <country>/recharging_points.csv                      AC and DC points per year (the newest is
                                                       the year so far)
  european-union-eu27/countries_overview_of_recharging_stations.csv
                                                       points per power class now (EU only)
Where (points, binned for the map): the national open registers where there is one, else
OpenStreetMap, each country labelled by its source:
  DE  Bundesnetzagentur Ladesäulenregister (CC BY 4.0): charging points ("Anzahl Ladepunkte") per
      facility in operation, with its rated power (kW)
  FR  data.gouv.fr consolidated IRVE file (Etalab open licence): one row per charging point (pdc)
  other EU countries and GB: OpenStreetMap (ODbL) amenity=charging_station via the Overpass API,
      one per mapped station (not per point: OSM's capacity tag is too often missing)
Binned (computed): the points or stations summed in 0.1° cells, [lon, lat] the cell centre; the
cell keeps its country and the source's unit. Nothing is estimated where a source has no rows.

Writes frontend/public/data/eu/ev_eu.json (each part replaces its own section); lake tables
ev_eu/<cc> (every point or station with its position).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wave5_common as w  # noqa: E402
import wave7_common as w7  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "data" / "eu" / "ev_eu.json"
SCRIPT = "scripts/build_ev_eu.py"
CELL = 0.1
EAFO = "https://alternative-fuels-observatory.ec.europa.eu/sites/default/files/csv"
EAFO_PAGE = "https://alternative-fuels-observatory.ec.europa.eu/transport-mode/road"
# EAFO's page names
SLUG = {
    "AT": "austria", "BE": "belgium", "BG": "bulgaria", "HR": "croatia", "CY": "cyprus", "CZ": "czech-republic",
    "DK": "denmark", "EE": "estonia", "FI": "finland", "FR": "france", "DE": "germany", "GR": "greece",
    "HU": "hungary", "IE": "ireland", "IT": "italy", "LV": "latvia", "LT": "lithuania", "LU": "luxembourg",
    "MT": "malta", "NL": "netherlands", "PL": "poland", "PT": "portugal", "RO": "romania", "SK": "slovakia",
    "SI": "slovenia", "ES": "spain", "SE": "sweden", "GB": "united-kingdom",
}  # fmt: skip
CLASS_NAME = {"Czech Republic": "CZ"}  # EAFO's overview table names
DE_PAGE = "https://www.bundesnetzagentur.de/DE/Fachthemen/ElektrizitaetundGas/E-Mobilitaet/Ladesaeulenkarte/start.html"
FR_DATASET = "https://www.data.gouv.fr/api/1/datasets/fichier-consolide-des-bornes-de-recharge-pour-vehicules-electriques/"
OVERPASS = "https://overpass-api.de/api/interpreter"
REGISTER = {"DE", "FR"}


def load() -> dict:
    if OUT.exists():
        return json.loads(OUT.read_text(encoding="utf-8"))
    return {"cell_deg": CELL, "eafo": {}, "maps": {}, "cells": {}}


def save(data: dict) -> None:
    data["fetched"] = w.now()
    w.write_json(OUT, data)


def cells(points: list[tuple[float, float, int]]) -> list[list]:
    """[lon, lat, count] per 0.1° cell (centre), largest first: sums of the points (computed)."""
    acc: dict[tuple[int, int], int] = {}
    for lon, lat, n in points:
        k = (int(lon // CELL), int(lat // CELL))
        acc[k] = acc.get(k, 0) + n
    return sorted(
        ([round((i + 0.5) * CELL, 2), round((j + 0.5) * CELL, 2), n] for (i, j), n in acc.items()),
        key=lambda c: -c[2],
    )


def put(data: dict, cc: str, meta: dict, pts: list[tuple[float, float, int]], rows: list[dict],
        args: argparse.Namespace) -> None:  # fmt: skip
    data["maps"][cc] = meta | {"n": sum(p[2] for p in pts), "fetched": w7.TODAY}
    data["cells"][cc] = cells(pts)
    print(
        f"  {cc}: {meta['n_rows']} rows, {data['maps'][cc]['n']} {meta['unit']}, {len(data['cells'][cc])} cells",
        flush=True,
    )
    for r in rows:
        r["iso2"] = cc
    w7.lake_rows("ev_eu", [(cc.lower(), rows, ["lat", "lon"], ("lon", "lat"))], lake_dir=args.lake,
                 upload=args.upload, source=meta["source"], licence=meta["licence"], script=SCRIPT)  # fmt: skip


# ---------------------------------------------------------------- counts (EAFO)


def eafo_series(text: str) -> dict[str, list]:
    """{years, ac, dc} from a recharging_points.csv (YEAR,AC,DC)."""
    out: dict[str, list] = {"years": [], "ac": [], "dc": []}
    for r in csv.DictReader(io.StringIO(text)):
        out["years"].append(int(r["YEAR"]))
        out["ac"].append(int(float(r["AC"]))) if r.get("AC") else out["ac"].append(None)
        out["dc"].append(int(float(r["DC"]))) if r.get("DC") else out["dc"].append(None)
    return out


def eafo_classes(text: str) -> tuple[list[str], dict[str, list]]:
    """(class labels, {ISO: points per class}) from the EU overview table (blank = none given)."""
    rows = list(csv.reader(io.StringIO(text)))
    names = {v: k for k, v in SLUG.items()}
    out = {}
    for r in rows[1:]:
        cc = CLASS_NAME.get(r[0]) or names.get(r[0].lower().replace(" ", "-"))
        if cc:
            out[cc] = [int(float(v)) if v.strip() else None for v in r[1:]]
    return rows[0][1:], out


def eafo(data: dict, args: argparse.Namespace) -> None:
    labels, classes = eafo_classes(
        w7.get(f"{EAFO}/european-union-eu27/countries_overview_of_recharging_stations.csv").text
    )
    countries = {}
    for cc, slug in SLUG.items():
        if args.only and cc not in args.only:
            continue
        try:
            text = w7.get(f"{EAFO}/{slug}/recharging_points.csv").text
            if not text.startswith("YEAR"):
                raise ValueError("not the CSV (the site answered a page)")
            countries[cc] = eafo_series(text) | {"classes": classes.get(cc)}
            print(
                f"  EAFO {cc}: {countries[cc]['years'][-1]} AC {countries[cc]['ac'][-1]} DC {countries[cc]['dc'][-1]}",
                flush=True,
            )
        except (Exception, SystemExit) as e:  # noqa: BLE001 - one country down keeps its last read
            print(f"  EAFO {cc}: failed ({e}); kept", flush=True)
        time.sleep(1.5)  # the site answers "Sorry" pages to quick series of requests
    old = data.get("eafo", {}).get("countries", {})
    data["eafo"] = {
        "source": "European Alternative Fuels Observatory (European Commission), public recharging points",
        "url": EAFO_PAGE,
        "licence": "European Commission reuse policy (CC BY 4.0)",
        "classes": labels,
        "countries": old | countries,
    }


# ---------------------------------------------------------------- Germany (BNetzA register)


def de_points(text: str) -> tuple[list[tuple[float, float, int]], list[dict]]:
    lines = text.splitlines()
    head = next(i for i, ln in enumerate(lines) if ln.startswith("Ladeeinrichtungs-ID"))
    pts, rows = [], []
    for r in csv.DictReader(lines[head:], delimiter=";"):
        if (r.get("Status") or "").strip() not in ("In Betrieb", ""):
            continue
        lat, lon = w7.number(r.get("Breitengrad")), w7.number(r.get("Längengrad"))
        n = int(w7.number(r.get("Anzahl Ladepunkte")) or 1)
        if lat is None or lon is None or not (47 <= lat <= 55.2 and 5.5 <= lon <= 15.2):
            continue
        pts.append((lon, lat, n))
        rows.append({"id": r["Ladeeinrichtungs-ID"], "operator": r.get("Betreiber"), "points": n,
                     "kw": w7.number(r.get("Nennleistung Ladeeinrichtung [kW]")), "kind": r.get("Art der Ladeeinrichtung"),
                     "since": r.get("Inbetriebnahmedatum"), "lon": lon, "lat": lat})  # fmt: skip
    return pts, rows


def de(data: dict, args: argparse.Namespace) -> None:
    page = w7.get(DE_PAGE).text
    url = sorted(
        re.findall(
            r'href="(https://data\.bundesnetzagentur\.de/[^"]+Ladesaeulenregister[^"]+\.csv)"', page
        )
    )[-1]
    raw = w7.get(url, timeout=300).content
    pts, rows = de_points(raw.decode("utf-8-sig", errors="replace"))
    put(data, "DE", {"source": "Bundesnetzagentur Ladesäulenregister", "url": url, "licence": "CC BY 4.0",
                     "unit": "charging points", "n_rows": len(rows),
                     "note": "Facilities in operation whose operators completed the BNetzA notification; points per facility as registered"},
        pts, rows, args)  # fmt: skip


# ---------------------------------------------------------------- France (IRVE consolidated)


def fr_points(text: str) -> tuple[list[tuple[float, float, int]], list[dict]]:
    pts, rows, seen = [], [], set()
    for r in csv.DictReader(io.StringIO(text)):
        pdc = r.get("id_pdc_itinerance") or r.get("id_pdc_local")
        if pdc and pdc in seen:
            continue
        seen.add(pdc)
        lon, lat = (
            w7.number(r.get("consolidated_longitude")),
            w7.number(r.get("consolidated_latitude")),
        )
        if lon is None or lat is None or not (-62 <= lon <= 56):
            continue
        pts.append((lon, lat, 1))
        rows.append({"id": pdc, "station": r.get("id_station_itinerance"), "operator": r.get("nom_operateur"),
                     "kw": w7.number(r.get("puissance_nominale")), "since": r.get("date_mise_en_service"),
                     "lon": lon, "lat": lat})  # fmt: skip
    return pts, rows


def fr(data: dict, args: argparse.Namespace) -> None:
    res = w7.get(FR_DATASET, timeout=120).json()["resources"]
    csvs = [
        r for r in res if r.get("format") == "csv" and "consolid" in (r.get("title") or "").lower()
    ]
    pick = max(
        csvs or [r for r in res if r.get("format") == "csv"],
        key=lambda r: r.get("last_modified") or "",
    )
    raw = w7.get(pick["url"], timeout=600).content
    pts, rows = fr_points(raw.decode("utf-8-sig", errors="replace"))
    put(data, "FR", {"source": "data.gouv.fr consolidated IRVE file (charging points)", "url": pick["url"],
                     "licence": "Licence Ouverte / Etalab 2.0", "unit": "charging points", "n_rows": len(rows),
                     "note": "One row per charging point (pdc), duplicates by id left out; overseas departments included"},
        pts, rows, args)  # fmt: skip


# ---------------------------------------------------------------- OpenStreetMap elsewhere


def osm_points(elements: list[dict]) -> tuple[list[tuple[float, float, int]], list[dict]]:
    pts, rows = [], []
    for e in elements:
        lon = e.get("lon", e.get("center", {}).get("lon"))
        lat = e.get("lat", e.get("center", {}).get("lat"))
        if lon is None or lat is None:
            continue
        t = e.get("tags", {})
        pts.append((lon, lat, 1))
        rows.append({"id": f"{e['type']}/{e['id']}", "operator": t.get("operator") or t.get("network"),
                     "capacity": w7.number(t.get("capacity")), "name": t.get("name"), "lon": lon, "lat": lat})  # fmt: skip
    return pts, rows


def osm(data: dict, args: argparse.Namespace) -> None:
    for cc in SLUG:
        if cc in REGISTER or (args.only and cc not in args.only):
            continue
        q = (f'[out:json][timeout:900];area["ISO3166-1"="{cc}"][admin_level=2]->.a;'
             'nwr["amenity"="charging_station"](area.a);out center tags;')  # fmt: skip
        try:
            els = w7.get(OVERPASS, params={"data": q}, timeout=960).json()["elements"]
            pts, rows = osm_points(els)
            if not pts:
                raise ValueError("no stations")
            put(data, cc, {"source": "OpenStreetMap, amenity=charging_station (Overpass API)",
                           "url": "https://www.openstreetmap.org/copyright", "licence": "ODbL 1.0",
                           "unit": "stations", "n_rows": len(rows),
                           "note": "Mapped stations, not points: one per OSM node or area, whatever its number of points"},
                pts, rows, args)  # fmt: skip
        except (Exception, SystemExit) as e:  # noqa: BLE001 - one country down keeps its last read
            print(f"  OSM {cc}: failed ({e}); kept", flush=True)
        time.sleep(20)  # Overpass asks for room between large queries


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("part", choices=["eafo", "de", "fr", "osm", "all"])
    ap.add_argument("--only", type=lambda s: set(s.split(",")), default=None)
    ap.add_argument("--lake", type=Path, default=Path("lake-out"))
    ap.add_argument("--upload", action="store_true")
    args = ap.parse_args()
    data = load()
    for part, fn in (("eafo", eafo), ("de", de), ("fr", fr), ("osm", osm)):
        if args.part in (part, "all"):
            try:
                fn(data, args)
            except (Exception, SystemExit) as e:  # noqa: BLE001 - one source down must not stop the others
                print(f"{part}: failed ({type(e).__name__}: {e})", flush=True)
            save(data)
    print(f"-> {OUT} ({OUT.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
