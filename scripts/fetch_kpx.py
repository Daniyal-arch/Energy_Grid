"""South Korea's grid, live (KPX public real-time pages, no key; scripts/probe_kpx.py).

  실시간 전력수급현황   supply capacity, current demand (power market), supply reserve
                       and reserve rate, refreshed every 5 minutes
  발전원별 실시간       generation by source every 5 minutes for today (MW), from the
                       page's own data array; rows not yet reported carry regDate "0"
                       and are skipped (never read as zero)

KPX notes: the solar BTM (behind the meter) and PPA columns "are real-time estimates
based on the power-market solar data, not official metered figures"; ESS and pumped
storage are net (negative = charging or pumping). Since 2026-07-01 "신재생" is split
into "신e 및 기타" (new energy and other), "기타 재생e" (other renewables, excluding
solar, wind and hydro) and ESS, and domestic and bituminous coal are merged into "석탄".

Values are passthrough (rounded to 0.1 MW). Computed: total_mw = sum of the 13 source
columns at the newest reported 5-min interval (includes KPX's solar estimates);
metered_total_mw = the same without the two estimated solar columns.

Licence: KPX publishes the same generation-by-source data on data.go.kr (dataset
15106744, "한국전력거래소_발전원별 발전량") with "이용허락범위 제한 없음" (licence scope:
no restriction); the KPX site footer reads "COPYRIGHT(C) 2021 KOREA POWER EXCHANGE(KPX)
ALL RIGHTS RESERVED".

Writes frontend/public/data/eu/korea.json:
  {"source", "licence", "fetched",
   "demand": {"at", "mw", "supply_capacity_mw", "reserve_mw", "reserve_pct"},
   "generation": {"at", "total_mw", "metered_total_mw", "by_fuel": {key: MW},
                  "labels": {key: [Korean, English]}, "estimated": [key]}}

    uv run python scripts/fetch_kpx.py [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu"
BASE = "https://new.kpx.or.kr"
DEMAND = f"{BASE}/powerinfoSubmain.es?mid=a10606030000"
SOURCES = f"{BASE}/powerSource.es?mid=a10606030000"
SOURCE = "KPX (Korea Power Exchange) real-time supply and demand, new.kpx.or.kr"
LICENCE = (
    "KPX data on data.go.kr (dataset 15106744): 이용허락범위 제한 없음 (no restriction on use); "
    "KPX site: All rights reserved"
)
KST = timezone(timedelta(hours=9))
# ictArr field -> (KPX column, English); the order of KPX's table
FIELDS: dict[str, tuple[str, str]] = {
    "btm": ("태양광(BTM,추정)", "Solar, behind the meter (KPX estimate)"),
    "ppa": ("태양광(PPA,추정)", "Solar, PPA (KPX estimate)"),
    "sunlight": ("태양광(전력시장)", "Solar (power market)"),
    "windPower": ("풍력", "Wind"),
    "reneweMw": ("기타 재생e(태/풍/수력 제외)", "Other renewables"),
    "essMw": ("ESS", "Battery storage (net)"),
    "raisingWater": ("양수", "Pumped storage (net)"),
    "waterPower": ("수력", "Hydro"),
    "neweMw": ("신e및기타", "New energy and other"),
    "gas": ("가스", "Gas"),
    "oil": ("유류", "Oil"),
    "totCoal": ("석탄", "Coal"),
    "nuclearPower": ("원자력", "Nuclear"),
}
ESTIMATED = ["btm", "ppa"]


def num(text: str) -> float | None:
    try:
        return float(text.replace(",", "").replace("MW", "").replace("%", "").strip())
    except ValueError:
        return None


def demand(html: str) -> dict | None:
    m = re.search(r'class="info_top">\s*(\d{4})\.(\d{2})\.(\d{2})\([^)]*\)\s*(\d{2}):(\d{2})', html)
    cells = {k: re.search(rf'id="{k}">([^<]+)', html) for k in ("avil", "load", "supPow", "supPer")}
    if not m or not cells["load"]:
        return None
    y, mo, d, h, mi = (int(g) for g in m.groups())

    def val(key: str) -> float | None:
        c = cells[key]
        return num(c.group(1)) if c else None

    return {
        "at": datetime(y, mo, d, h, mi, tzinfo=KST).isoformat(),
        "mw": val("load"),
        "supply_capacity_mw": val("avil"),
        "reserve_mw": val("supPow"),
        "reserve_pct": val("supPer"),
    }


def generation(html: str) -> dict | None:
    m = re.search(r"var ictArr\s*=\s*(\[.*?\]);", html, re.S)
    if not m:
        return None
    rows = [r for r in json.loads(m.group(1)) if r.get("regDate") not in (None, "", "0")]
    if not rows:
        return None
    row = max(rows, key=lambda r: r["regDate"])
    by_fuel = {k: round(v, 1) for k in FIELDS if (v := num(str(row.get(k, "")))) is not None}
    if len(by_fuel) < len(FIELDS):
        return None
    at = datetime.strptime(row["regDate"], "%Y-%m-%d %H:%M").replace(tzinfo=KST)
    return {
        "at": at.isoformat(),
        "total_mw": round(sum(by_fuel.values()), 1),
        "metered_total_mw": round(sum(v for k, v in by_fuel.items() if k not in ESTIMATED), 1),
        "by_fuel": by_fuel,
        "labels": {k: list(v) for k, v in FIELDS.items()},
        "estimated": ESTIMATED,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT)
    out: Path = parser.parse_args().out
    parts: dict[str, dict | None] = {}
    with httpx.Client(timeout=60, headers={"User-Agent": "Europe-InfraAtlas/0.3"}) as client:
        for key, url, fn in [("demand", DEMAND, demand), ("generation", SOURCES, generation)]:
            try:
                r = client.get(url)
                r.raise_for_status()
                parts[key] = fn(r.text)
            except (httpx.HTTPError, json.JSONDecodeError) as err:
                print(f"{key} skipped: {err}", flush=True)
                parts[key] = None
    if not any(parts.values()):
        raise SystemExit("KPX answered nothing usable; keeping the old file")
    data = {
        "source": SOURCE,
        "licence": LICENCE,
        "fetched": datetime.now(UTC).isoformat(timespec="seconds"),
        **parts,
    }
    out.mkdir(parents=True, exist_ok=True)
    path = out / "korea.json"
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    d, g = data["demand"], data["generation"]
    print(
        f"{path.name}: demand {d and d['mw']} MW ({d and d['at']}), "
        f"generation {g and g['total_mw']} MW ({g and g['at']}), {g and g['by_fuel']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
