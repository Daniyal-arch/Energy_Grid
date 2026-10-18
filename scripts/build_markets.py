"""Live markets beyond Europe and the US (brief 17, group G): Japan (JEPX) and Mexico (CENACE).

    python scripts/build_markets.py jepx|cenace [--out DIR] [--lake lake-out] [--upload]

jepx    JEPX spot market summary `spot_summary_<year>.csv` (Shift-JIS; one row per delivery day and
        30-minute slot, 48 a day): system price and the nine area prices, JPY/kWh as published.
        The terms of use were not found (jepx.jp's site-policy page answers 404; noted in the PR).
        -> jepx.json (the newest delivery day: each area's 48 prices and their average, lowest and
        highest, computed); lake `jepx/spot` (the year's file, every column).
cenace  CENACE day-ahead local marginal prices (PML, MXN/MWh) from its public web service
        (`ws01.cenace.gob.mx:8082/SWPML/SIM/{system}/MDA/{nodes}/{date}/{date}/JSON`, no key, 20 nodes
        per request), for every node of CENACE's node catalogue, systems SIN, BCA, BCS.
        -> cenace.json (per system and hour: nodes counted, lowest, median and highest price,
        computed; nodes are counted, not placed: CENACE publishes no positions); lake `cenace/pml`.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import wave5_common as w

JEPX_URL = "https://www.jepx.jp/js/csv_read.php?dir=spot_summary&file=spot_summary_{year}.csv"
JEPX_AREAS = [
    "Hokkaido",
    "Tohoku",
    "Tokyo",
    "Chubu",
    "Hokuriku",
    "Kansai",
    "Chugoku",
    "Shikoku",
    "Kyushu",
]
CENACE_WS = "https://ws01.cenace.gob.mx:8082/SWPML/SIM/{system}/MDA/{nodes}/{d}/{d}/JSON"
CENACE_PAGES = [
    "https://www.cenace.gob.mx/Paginas/SIM/NodosP.aspx",
    "https://www.cenace.gob.mx/Paginas/SIM/Reportes/PreciosEnergiaSisMEM.aspx",
]
SYSTEMS = ["SIN", "BCA", "BCS"]
TMP = Path("/tmp/wave5")
JST = ZoneInfo("Asia/Tokyo")
MEX = ZoneInfo("America/Mexico_City")


def jepx_rows(text: str) -> list[dict]:
    """The CSV's rows: date, slot (1-48), volumes (kWh), system price and nine area prices."""
    rows = []
    for r in csv.reader(io.StringIO(text)):
        if not r or not re.match(r"\d{4}/\d{2}/\d{2}", r[0]):
            continue
        num = [float(x) if x not in ("", None) else None for x in r[2:15]]
        rows.append(
            {
                "date": r[0].replace("/", "-"),
                "slot": int(r[1]),
                "sell_kwh": num[0],
                "buy_kwh": num[1],
                "contracted_kwh": num[2],
                "system_jpy_kwh": num[3],
                **{f"{a.lower()}_jpy_kwh": num[4 + i] for i, a in enumerate(JEPX_AREAS)},
            }
        )
    return rows


def jepx(args: argparse.Namespace) -> None:
    import httpx

    year = datetime.now(JST).year
    # the CSV answers empty without the spot page as referrer
    r = httpx.get(
        JEPX_URL.format(year=year),
        headers={**w.UA, "Referer": "https://www.jepx.jp/electricpower/market-data/spot/"},
        timeout=120,
    )
    r.raise_for_status()
    rows = jepx_rows(r.content.decode("shift_jis", errors="replace"))
    day = max(x["date"] for x in rows)
    today = sorted((x for x in rows if x["date"] == day), key=lambda x: x["slot"])
    areas = {}
    for a in ["system", *[a.lower() for a in JEPX_AREAS]]:
        v = [x[f"{a}_jpy_kwh"] for x in today]
        got = [p for p in v if p is not None]
        areas[a] = {
            "prices": v,
            "avg": round(sum(got) / len(got), 2) if got else None,
            "min": min(got, default=None),
            "max": max(got, default=None),
        }
    w.write_json(
        args.out / "jepx.json",
        {
            "fetched": w.now(),
            "source": "JEPX spot market summary (jepx.jp), JPY/kWh as published",
            "date": day,
            "slots": len(today),
            "areas": areas,
        },
    )
    print(
        f"  JEPX {year}: {len(rows):,} rows; newest delivery day {day} with {len(today)} slots",
        flush=True,
    )
    if args.upload:
        import duckdb

        tmp = TMP / "jepx.json"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(rows), encoding="utf-8")
        con = duckdb.connect()
        lk = w.lake_for(
            "jepx",
            args.lake,
            "JEPX spot market summary",
            "jepx.jp (terms of use not found)",
            "scripts/build_markets.py",
        )
        lk.write(
            con,
            "spot",
            f"""SELECT date::DATE AS date, * EXCLUDE (date), 'JP' AS iso2, 'JPN' AS iso3, NULL::VARCHAR AS admin1
                FROM read_json('{tmp}', maximum_object_size = 1000000000)""",
            sort=["date", "slot"],
            partition={"year": str(year)},
        )
        w.lake_done(lk, args.upload)


def node_catalogue() -> dict[str, list[str]]:
    """CENACE's node catalogue (NodosP): system -> node keys, from the xlsx its pages link."""
    import httpx
    import openpyxl

    tried = []
    for page in CENACE_PAGES:
        try:
            html = httpx.get(page, headers=w.UA, timeout=60, follow_redirects=True).text
        except httpx.HTTPError as e:
            tried.append(f"{page}: {type(e).__name__}")
            continue
        links = re.findall(r"""href=["']([^"']*Nodos[^"']*\.xlsx?)["']""", html, re.I)
        tried.append(f"{page}: {len(links)} catalogue links")
        for link in links:
            url = (
                link
                if link.startswith("http")
                else "https://www.cenace.gob.mx"
                + ("" if link.startswith("/") else "/")
                + link.replace("\\", "/").lstrip("./")
            )
            src = w.download(url.replace(" ", "%20"), TMP / "cenace_nodos.xlsx")
            wb = openpyxl.load_workbook(src, read_only=True)
            out: dict[str, list[str]] = {}
            for ws in wb.worksheets:
                rows = list(ws.iter_rows(values_only=True))
                head_i = next(
                    (
                        i
                        for i, r in enumerate(rows[:20])
                        if r and any(re.search(r"CLAVE", str(c or ""), re.I) for c in r)
                    ),
                    None,
                )
                if head_i is None:
                    continue
                head = [str(c or "").upper() for c in rows[head_i]]
                k_col = next(i for i, c in enumerate(head) if "CLAVE" in c)
                s_col = next((i for i, c in enumerate(head) if "SISTEMA" in c), None)
                for r in rows[head_i + 1 :]:
                    if r and r[k_col]:
                        sysname = str(r[s_col]).strip() if s_col is not None and r[s_col] else "SIN"
                        out.setdefault(sysname, []).append(str(r[k_col]).strip())
            if out:
                print(f"  catalogue {url}: {[(k, len(v)) for k, v in out.items()]}", flush=True)
                return out
    raise SystemExit("CENACE node catalogue not found: " + "; ".join(tried))


def cenace_values(answer: dict) -> list[tuple[str, int, float]]:
    """(node, hour 1-24, PML) from a SWPML answer (`Resultados[].clv_nodo`, `Valores[].hora`, `.pml`)."""
    out = []
    for res in answer.get("Resultados") or []:
        node = res.get("clv_nodo")
        for v in res.get("Valores") or []:
            try:
                out.append((node, int(v["hora"]), float(v["pml"])))
            except (KeyError, TypeError, ValueError):
                continue
    return out


def spread(prices: list[float]) -> list[float | int]:
    """[nodes, lowest, median, highest] of one hour's prices."""
    return [
        len(prices),
        round(min(prices), 2),
        round(statistics.median(prices), 2),
        round(max(prices), 2),
    ]


def cenace(args: argparse.Namespace) -> None:
    import httpx

    nodes = node_catalogue()
    day = datetime.now(MEX).date() + timedelta(days=1)
    rows: list[dict] = []
    systems = {}
    with httpx.Client(timeout=120, headers=w.UA) as client:
        for d in (day, day - timedelta(days=1)):  # tomorrow's day-ahead prices, else today's
            ds = f"{d.year}/{d.month:02d}/{d.day:02d}"
            for system in SYSTEMS:
                keys = nodes.get(system, [])
                vals: list[tuple[str, int, float]] = []
                for i in range(0, len(keys), 20):
                    url = CENACE_WS.format(system=system, nodes=",".join(keys[i : i + 20]), d=ds)
                    try:
                        r = client.get(url)
                        if i == 0:
                            print(
                                f"  {system} {ds}: HTTP {r.status_code} {r.text[:300]!r}",
                                flush=True,
                            )
                        vals += cenace_values(r.json())
                    except (httpx.HTTPError, ValueError) as e:
                        print(f"  {system} {ds} nodes {i}: {type(e).__name__}", flush=True)
                by_hour: dict[int, list[float]] = {}
                for node, h, p in vals:
                    by_hour.setdefault(h, []).append(p)
                    rows.append(
                        {
                            "date": d.isoformat(),
                            "hour": h,
                            "system": system,
                            "node": node,
                            "pml_mxn_mwh": p,
                        }
                    )
                if by_hour:
                    systems[system] = {
                        "nodes": len({v[0] for v in vals}),
                        "hours": [spread(by_hour[h]) for h in sorted(by_hour)],
                    }
            if systems:
                break
    if not systems:
        raise SystemExit("CENACE answered no prices")
    w.write_json(
        args.out / "cenace.json",
        {
            "fetched": w.now(),
            "source": "CENACE day-ahead market (MDA), local marginal prices (PML), MXN/MWh, SWPML web service",
            "date": rows[0]["date"],
            "fields": ["nodes", "lowest", "median", "highest"],
            "systems": systems,
        },
    )
    print(
        f"  CENACE {rows[0]['date']}: {[(k, v['nodes']) for k, v in systems.items()]}", flush=True
    )
    if args.upload:
        import duckdb

        tmp = TMP / "cenace.json"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(rows), encoding="utf-8")
        con = duckdb.connect()
        lk = w.lake_for(
            "cenace",
            args.lake,
            "CENACE SWPML web service (MDA)",
            "CENACE public information",
            "scripts/build_markets.py",
        )
        lk.write(
            con,
            "pml",
            f"""SELECT date::DATE AS date, * EXCLUDE (date), 'MX' AS iso2, 'MEX' AS iso3, NULL::VARCHAR AS admin1
                FROM read_json('{tmp}', maximum_object_size = 1000000000)""",
            sort=["system", "node", "hour"],
            partition={"date": rows[0]["date"]},
        )
        w.lake_done(lk, args.upload)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["jepx", "cenace"])
    ap.add_argument("--out", type=Path, default=w.EU)
    ap.add_argument("--lake", type=Path, default=Path("lake-out"))
    ap.add_argument("--upload", action="store_true")
    args = ap.parse_args()
    {"jepx": jepx, "cenace": cenace}[args.what](args)


if __name__ == "__main__":
    main()
