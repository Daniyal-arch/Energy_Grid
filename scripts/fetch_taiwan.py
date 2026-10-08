"""Taiwan's grid, live: every generating unit, every 10 minutes (Taipower open data).

Taipower publishes the net output of each unit it owns or buys from (data.gov.tw
dataset 8931, no key; scripts/probe_taipower.py): type, unit name, installed capacity
(MW), net generation (MW) and a status note (overhaul, fault, test run...). Each type
ends with a "小計" (subtotal) row with Taipower's own totals; those are passed through.
Battery charging is listed as its own type (儲能負載) and kept apart from generation.

Taiwan's grid is an island without interconnectors, so the sum of net generation is
the island's supply at that moment. Computed here: the total of the subtotals (MW).
Type names and status notes are translated to English; unit names are kept as
published, with the plant's English name where it is listed in PLANT_EN.

Writes frontend/public/data/eu/taiwan.json:
  {"source", "fetched", "at" (Taipei time, UTC+8), "total_mw",
   "types": [{"key", "label", "group", "installed_mw", "net_mw"}],
   "charging_mw", "units": [{"type", "name", "plant", "installed_mw", "net_mw", "note"}]}

    uv run python scripts/fetch_taiwan.py [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu"
URL = "https://service.taipower.com.tw/data/opendata/apply/file/d006001/001.json"
SOURCE = "Taipower open data (data.gov.tw dataset 8931), net generation per unit"

# Taipower's unit types -> (English label, colour group of the app's fuel palette)
TYPES: dict[str, tuple[str, str]] = {
    "核能": ("Nuclear", "nuclear"),
    "燃煤": ("Coal (Taipower)", "coal"),
    "民營電廠-燃煤": ("Coal (independent)", "coal"),
    "燃氣": ("Gas (Taipower)", "gas"),
    "民營電廠-燃氣": ("Gas (independent)", "gas"),
    "燃料油": ("Fuel oil", "oil"),
    "輕油": ("Diesel", "oil"),
    "汽電共生": ("Cogeneration", "other"),
    "水力": ("Hydro", "hydro"),
    "風力": ("Wind", "wind"),
    "太陽能": ("Solar", "solar"),
    "其它再生能源": ("Other renewables", "bio"),
    "儲能": ("Battery and pumped storage", "storage"),
}
CHARGING = "儲能負載"
NOTES = {
    "歲修": "annual overhaul",
    "部分歲修": "partial annual overhaul",
    "檢修": "maintenance",
    "部分檢修": "partial maintenance",
    "故障": "fault",
    "部分故障": "partial fault",
    "環保停機": "stopped for air quality",
    "友善降載減排": "reduced to cut emissions",
    "測試運轉": "test run",
    "新增設備測試運轉": "new equipment test run",
    "新機組試俥": "new unit trial run",
    "通訊異常": "communication fault",
    "配合綠電先行": "reduced to give way to renewables",
    "運轉限制": "operating limit",
    "停機": "stopped",
    "備轉": "standby",
}
# plants by the Chinese name at the start of a unit name (Taipower's English names)
PLANT_EN = {
    "核三": "Maanshan nuclear",
    "大潭": "Datan",
    "台中": "Taichung",
    "興達": "Hsinta",
    "通霄": "Tunghsiao",
    "林口": "Linkou",
    "大林": "Talin",
    "協和": "Hsieh-ho",
    "南部": "Nanbu",
    "麥寮": "Mailiao",
    "和平": "Ho-Ping",
    "和歐": "Ho-Ping",
    "長生": "Chang-Sheng",
    "新桃": "Hsin-Tao",
    "國光": "Kuo-Kuang",
    "星能": "Star Energy",
    "星元": "Star Buck",
    "嘉惠": "Chia-Hui",
    "森霸": "Sun Ba",
    "豐德": "Fong-Der",
    "海湖": "Hai-Hu",
    "明潭": "Mingtan",
    "明湖": "Minghu",
    "大觀": "Takuan",
    "德基": "Techi",
    "青山": "Chinshan",
    "谷關": "Kukuan",
    "天輪": "Tienlun",
    "馬鞍": "Ma-An",
    "萬大": "Wanta",
    "碧海": "Pi-Hai",
    "立霧": "Li-Wu",
    "龍澗": "Lung-Chien",
    "卓蘭": "Cholan",
    "尖山": "Chienshan",
    "塔山": "Tashan",
    "離岸": "Offshore (Taipower)",
    "海洋竹南": "Formosa 1",
    "海能": "Formosa 2",
    "沃": "Changhua (Ørsted)",
    "允": "Yunlin",
    "芳": "Changfang",
    "中能": "Zhong Neng",
    "龍": "Hai Long",
}
NUM = re.compile(r"-?\d+(?:\.\d+)?")


def mw(text: object) -> float | None:
    """The first number in a cell ("15918.1(26.525%)" -> 15918.1); None if there is none."""
    m = NUM.search(str(text or ""))
    return round(float(m.group()), 1) if m else None


def plant_of(name: str) -> str | None:
    for zh in sorted(PLANT_EN, key=len, reverse=True):
        if name.startswith(zh):
            return PLANT_EN[zh]
    return None


def note_of(text: str) -> str:
    t = re.sub(r"<[^>]+>", "", text or "").strip()
    return NOTES.get(t, t)


def build(raw: dict) -> dict:
    rows = raw["aaData"]
    types: dict[str, dict] = {}
    units: list[dict] = []
    charging = 0.0
    for row in rows:
        zh_type = re.sub(r"<[^>]+>|\(.*\)", "", row.get("機組類型", "")).strip()
        name = str(row.get("機組名稱", "")).strip()
        installed = mw(row.get("裝置容量(MW)"))
        net = mw(row.get("淨發電量(MW)"))
        if zh_type.startswith(CHARGING):
            if not name.startswith("小計") and net is not None:
                charging += net
            continue
        label, group = TYPES.get(zh_type, (zh_type, "other"))
        if name.startswith("小計"):
            # Taipower's own subtotal for the type
            types[zh_type] = {
                "key": zh_type,
                "label": label,
                "group": group,
                "installed_mw": installed,
                "net_mw": net,
            }
            continue
        units.append(
            {
                "type": label,
                "group": group,
                "name": re.sub(r"\(註\d+\)", "", name).strip(),
                "plant": plant_of(name),
                "installed_mw": installed,
                "net_mw": net,
                "note": note_of(str(row.get("備註", ""))),
            }
        )
    total = round(sum(t["net_mw"] or 0.0 for t in types.values()), 1)
    return {
        "source": SOURCE,
        "fetched": datetime.now(UTC).isoformat(timespec="seconds"),
        "at": f"{raw['DateTime']}+08:00",
        "total_mw": total,
        "types": sorted(types.values(), key=lambda t: -(t["net_mw"] or 0.0)),
        "charging_mw": round(charging, 1),
        "units": units,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT)
    out: Path = parser.parse_args().out
    r = httpx.get(URL, timeout=60, headers={"User-Agent": "Europe-InfraAtlas/0.3"})
    r.raise_for_status()
    data = build(json.loads(r.content.decode("utf-8-sig")))
    if not data["types"]:
        raise SystemExit("Taipower answered without generation types; keeping the old file")
    out.mkdir(parents=True, exist_ok=True)
    path = out / "taiwan.json"
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(
        f"{path.name}: {data['at']}, {data['total_mw']:.0f} MW from {len(data['units'])} units, "
        f"{len(data['types'])} types, charging {data['charging_mw']:.0f} MW",
        flush=True,
    )


if __name__ == "__main__":
    main()
