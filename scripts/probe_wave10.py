"""Wave 10 gathering (docs/tasks/29-wave10.md): probe the big catalogues before building.

    python scripts/probe_wave10.py eurostat   # Eurostat energy, climate, transport tables
    python scripts/probe_wave10.py wdi        # World Bank WDI energy and climate indicators
    python scripts/probe_wave10.py registry   # scripts/wave10_sources.yaml from the results

Eurostat: the table of contents gives the candidates (energy, environment accounts, the SDG
energy and climate tables, vehicles by fuel, rail electrification, circular economy), minus
the tables an earlier wave already holds. Each candidate's newest period is read as JSON-stat
(`lastTimePeriod=1`, labels included) and one published series is chosen for the map's
country colouring: a dimension with one code keeps it; otherwise the code labelled as a total
when one exists, else the code that covers the most countries. Nothing is computed: the series
is a filter on the published table.

WDI: every indicator of the topics Energy & Mining (5), Environment (6), Infrastructure (9) and
Climate change (19) in the WDI source (2), its licence from the series metadata and the number
of countries with a value in the newest year (`mrnev=1`).

Results go to `data/wave10_gather.json` (committed: the evidence behind the registry).
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import io
import json
import re
import sys
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wave5_common as w  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "wave10_gather.json"
TOC = "https://ec.europa.eu/eurostat/api/dissemination/catalogue/toc/txt?lang=en"
JSONSTAT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{}?lang=EN&lastTimePeriod=1"
# energy, climate and the infrastructure that uses energy; port, safety and labour tables left out
KEEP = re.compile(
    r"^(nrg_|env_ac_|env_air|env_wat|env_esst|env_epea|sdg_06|sdg_07|sdg_09|sdg_11|sdg_12|"
    r"sdg_13|ten0|road_eqs|road_eqr|rail_eq|rail_if|tran_hv|iww_eq|cei_|t2020_)"
)
TOTAL = re.compile(r"^(TOTAL|TOT|T|ALL|TOT_.*|TOTAL_.*)$")
ISO2 = re.compile(r"^[A-Z]{2}$")
WB_TOPICS = (5, 6, 9, 19)


def earlier_codes() -> set[str]:
    """The Eurostat codes the catalogue, registries and docs already name."""
    text = " ".join(
        p.read_text(encoding="utf-8", errors="ignore").lower()
        for d in ("agent/catalog", "scripts", "docs")
        for p in (ROOT / d).rglob("*")
        if p.is_file() and p.suffix in (".yaml", ".py", ".md") and "wave10" not in p.name
    )
    return set(re.findall(r"\b[a-z0-9]+_[a-z0-9_]+\b", text))


def candidates() -> list[dict[str, str]]:
    text = httpx.get(TOC, timeout=120, headers=w.UA).text
    have = earlier_codes()
    seen: dict[str, dict[str, str]] = {}
    for r in list(csv.reader(io.StringIO(text), delimiter="\t"))[1:]:
        if len(r) < 7 or r[2].strip() not in ("table", "dataset"):
            continue
        code = r[1].strip()
        end = re.match(r"(\d{4})", r[6].strip())
        if code in seen or not KEEP.match(code) or code in have or not end or int(end[1]) < 2022:
            continue
        seen[code] = {
            "code": code,
            "title": r[0].strip(),
            "updated": r[3].strip(),
            "end": r[6].strip(),
        }
    return list(seen.values())


def choose(d: dict[str, Any]) -> dict[str, Any]:
    """One series of a JSON-stat answer: the filter, its labels and the countries it covers."""
    ids, size = d["id"], d["size"]
    dims = {k: d["dimension"][k]["category"] for k in ids}
    index = {k: sorted(dims[k]["index"], key=lambda c: dims[k]["index"][c]) for k in ids}
    geo = [i for i, c in enumerate(index.get("geo", [])) if ISO2.match(c) and c != "EA"]
    vals = d.get("value") or {}
    stride = [1] * len(ids)
    for i in range(len(ids) - 2, -1, -1):
        stride[i] = stride[i + 1] * size[i + 1]
    free = [k for k in ids if k not in ("geo", "time", "freq") and len(index[k]) > 1]

    def covered(pick: dict[str, int]) -> int:
        n = 0
        for g in geo:
            pos = {**pick, "geo": g}
            off = sum(stride[i] * pos.get(k, 0) for i, k in enumerate(ids))
            n += str(off) in vals or off in vals
        return n

    pick: dict[str, int] = {}
    for k in free:
        best = None
        for j, code in enumerate(index[k]):
            label = dims[k]["label"].get(code, "")
            total = bool(TOTAL.match(code)) or label.lower().startswith(("total", "all "))
            score = (covered({**pick, k: j}), total, -j)
            if best is None or score > best[0]:
                best = (score, j)
        pick[k] = best[1] if best else 0
    filt = {k: index[k][pick.get(k, 0)] for k in ids if k not in ("geo", "time")}
    labels = {k: dims[k]["label"].get(filt[k], filt[k]) for k in free}
    unit = dims["unit"]["label"].get(filt["unit"], "") if "unit" in filt else ""
    return {
        "dims": {k: len(index[k]) for k in ids},
        "filter": filt,
        "labels": labels,
        "unit": unit,
        "countries": covered(pick) if geo else 0,
        "period": index["time"][-1] if "time" in index else None,
        "label": d.get("label", ""),
    }


def eurostat_one(c: dict[str, str]) -> dict[str, Any]:
    try:
        r = httpx.get(JSONSTAT.format(c["code"]), timeout=180, headers=w.UA)
        if r.status_code != 200:
            return {**c, "error": f"HTTP {r.status_code}: {r.text[:160]}"}
        return {**c, **choose(r.json())}
    except Exception as e:  # noqa: BLE001 - recorded per table
        return {**c, "error": f"{type(e).__name__}: {str(e)[:160]}"}


def eurostat(_: argparse.Namespace) -> None:
    cands = candidates()
    print(f"{len(cands)} Eurostat candidates", flush=True)
    out = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    res: dict[str, Any] = {}
    with cf.ThreadPoolExecutor(4) as ex:
        for i, r in enumerate(ex.map(eurostat_one, cands)):
            res[r["code"]] = r
            if i % 25 == 0:
                print(
                    f"  {i}/{len(cands)} {r['code']}: {r.get('countries', r.get('error'))}",
                    flush=True,
                )
    out["eurostat"] = {"checked": w.now()[:10], "tables": res}
    w.write_json(OUT, out)
    ok = [r for r in res.values() if r.get("countries", 0) >= 15]
    print(f"{len(ok)} of {len(res)} tables have a series covering 15 or more countries")


def wdi_one(ind: dict[str, Any]) -> dict[str, Any]:
    base = "https://api.worldbank.org/v2"
    try:
        meta = httpx.get(
            f"{base}/sources/2/series/{ind['id']}/metadata?format=json", timeout=60
        ).json()
        mt = {
            m["id"]: m["value"] for m in meta["source"][0]["concept"][0]["variable"][0]["metatype"]
        }
        data = httpx.get(
            f"{base}/country/all/indicator/{ind['id']}?format=json&mrnev=1&per_page=400",
            timeout=60,
        ).json()
        rows = [x for x in (data[1] or []) if x.get("value") is not None]
        iso = [x for x in rows if len(x["countryiso3code"]) == 3 and x["country"]["id"].isalpha()]
        years = sorted({x["date"] for x in iso})
        return {
            **ind,
            "licence": mt.get("License_Type"),
            "licence_url": mt.get("License_URL"),
            "source_org": (mt.get("Source") or "")[:300],
            "unit": mt.get("Unit of measure") or "",
            "areas": len(iso),
            "years": [years[0], years[-1]] if years else [],
        }
    except Exception as e:  # noqa: BLE001 - recorded per indicator
        return {**ind, "error": f"{type(e).__name__}: {str(e)[:160]}"}


def wdi(_: argparse.Namespace) -> None:
    inds: dict[str, dict[str, Any]] = {}
    for t in WB_TOPICS:
        d = httpx.get(
            f"https://api.worldbank.org/v2/topic/{t}/indicator?format=json&per_page=1000",
            timeout=60,
        ).json()
        for i in d[1]:
            if (i.get("source") or {}).get("id") == "2" and i["id"] not in inds:
                inds[i["id"]] = {"id": i["id"], "name": i["name"], "topic": t}
    print(f"{len(inds)} WDI indicators", flush=True)
    with cf.ThreadPoolExecutor(6) as ex:
        res = {r["id"]: r for r in ex.map(wdi_one, inds.values())}
    out = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    out["wdi"] = {"checked": w.now()[:10], "indicators": res}
    w.write_json(OUT, out)
    ok = [r for r in res.values() if r.get("areas", 0) >= 30 and r.get("licence") == "CC BY-4.0"]
    print(f"{len(ok)} of {len(res)} indicators: CC BY 4.0 and 30 or more countries")


# tables Eurostat refused as SDMX-CSV from 2010 (HTTP 413 EXTRACTION_TOO_BIG, more than 5 million
# rows; the wave 10 build of 2026-11-03): read from the API's TSV form, which has no row cap
TOO_BIG = set(
    "nrg_bal_cv nrg_cb_oil nrg_cb_oilm nrg_stk_oam nrg_stk_oilm nrg_stk_oom nrg_te_gasm "
    "nrg_te_oilm nrg_ti_coifpm nrg_ti_gasm nrg_ti_oilm env_ac_aeint_r2 env_ac_ainah_r2 "
    "env_ac_ch4fp env_ac_co2fp env_ac_egss2 env_ac_ghgfp env_ac_hfcfp env_ac_n2ofp "
    "env_ac_nf3sf6fp env_ac_pefasu env_ac_pfcfp".split()
)


def eurostat_place(code: str) -> tuple[int, str]:
    """The wave-10 category and family of a Eurostat table, by its code."""
    rules = [
        (r"^nrg_(pc|prc)", 2, "energy_prices_taxes"),
        (r"^env_ac_tax", 2, "energy_prices_taxes"),
        (r"^nrg_(inf|dhdc|chp)", 1, "energy_infrastructure_stats"),
        (r"^nrg_", 1, "energy_balances"),
        (r"^env_ac_(m|rme)", 5, "water_materials"),
        (r"^env_(ac|air|epea|esst)", 3, "emission_accounts"),
        (r"^(road|rail|tran|iww)_", 4, "vehicle_fleet"),
        (r"^(env_wat|cei_)", 5, "water_materials"),
    ]
    return next(((c, f) for rx, c, f in rules if re.match(rx, code)), (6, "sdg_indicators"))


def registry(_: argparse.Namespace) -> None:
    """scripts/wave10_sources.yaml: the hand-picked sources, then one source per Eurostat table
    and per WDI indicator the gathering found (a colouring when 15 or more countries publish the
    chosen series, or 30 or more for WDI; the table goes to the lake either way)."""
    import yaml

    g = json.loads(OUT.read_text(encoding="utf-8"))
    manual = yaml.safe_load((ROOT / "scripts" / "wave10_manual.yaml").read_text(encoding="utf-8"))
    out = list(manual["sources"])
    es_url = (
        "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/{}/"
        "?format=SDMX-CSV&compressed=false&startPeriod=2010"
    )
    es_tsv = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/{}/?format=TSV&compressed=true"
    for code, t in sorted(g["eurostat"]["tables"].items()):
        cat, fam = eurostat_place(code)
        src: dict[str, Any] = {
            "id": f"eu_{code}",
            "title": f"Eurostat {t['title']} ({code})",
            "cat": cat,
            "fam": fam,
            "places": ["EU27"],
            "level": "country",
            "kind": "csv",
            "url": es_url.format(code),
            "licence": "CC BY 4.0 (Eurostat)",
            "lic_url": "https://ec.europa.eu/eurostat/about-us/policies/copyright",
            "status": "build",
        }
        if code in TOO_BIG:
            src["kind"] = "eurostat_tsv"
            src["url"] = es_tsv.format(code)
            src["note"] = "over Eurostat's 5 million row cap for SDMX-CSV: read from the TSV form"
        if "error" in t:
            src["note"] = f"probe: {t['error'][:120]} (built from the full table)"
        elif t.get("countries", 0) >= 15:
            series = "; ".join(v for v in t["labels"].values() if v)
            src["choro"] = {
                "filter": t["filter"],
                "label": f"{t['label'] or t['title']}" + (f": {series}" if series else ""),
                "unit": t["unit"],
            }
        out.append(src)
    for ind, t in sorted(g["wdi"]["indicators"].items()):
        if t.get("licence") != "CC BY-4.0":
            continue
        sid = "wb_" + re.sub(r"[^0-9a-z]+", "_", ind.lower()).strip("_")
        src = {
            "id": sid,
            "title": f"World Bank WDI {t['name']} ({ind})",
            "cat": 7,
            "fam": "world_indicators",
            "places": ["WORLD"],
            "level": "country",
            "kind": "wdi",
            "url": f"https://api.worldbank.org/v2/country/all/indicator/{ind}?format=json&date=1990:2026",
            "licence": "CC BY 4.0 (World Bank WDI)",
            "lic_url": t.get("licence_url") or "https://datacatalog.worldbank.org/public-licenses",
            "status": "build",
            "note": f"original source: {t.get('source_org', '')[:160]}",
        }
        if t.get("areas", 0) >= 30:
            src["choro"] = {
                "key": "iso2",
                "value": "value",
                "period": "year",
                "filter": {"aggregate": "false"},
                "label": t["name"],
                "unit": t.get("unit") or "",
            }
        out.append(src)
    path = ROOT / "scripts" / "wave10_sources.yaml"
    head = (
        "# Generated by `python scripts/probe_wave10.py registry` from scripts/wave10_manual.yaml\n"
        "# and data/wave10_gather.json (edit those, not this file).\n"
    )
    body = yaml.safe_dump({"sources": out}, sort_keys=False, allow_unicode=True, width=10_000)
    path.write_text(head + body, encoding="utf-8")
    print(f"{len(out)} sources -> {path.relative_to(ROOT)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(required=True)
    sub.add_parser("eurostat").set_defaults(fn=eurostat)
    sub.add_parser("wdi").set_defaults(fn=wdi)
    sub.add_parser("registry").set_defaults(fn=registry)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
