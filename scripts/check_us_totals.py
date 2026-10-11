"""Check the US plants build against EIA's published national total for the same month.

EIA's Electric Power Monthly, Table 6.1 ("Electric Generating Summer Capacity Changes"),
gives the total in-service net summer capacity of utility-scale facilities at the end of
its newest month, by technology. This builds plants.json's totals from the EIA-860M file
of that same month (scripts/fetch_us_grid.py, build_plants) and prints both, nationally
and per fuel group. The EPM runs a month behind EIA-860M, so the month checked is the
EPM's, not necessarily the newest one on the map.

    uv run python scripts/check_us_totals.py
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_us_grid import RAW, UA, build_plants, download  # noqa: E402

EPM = "https://www.eia.gov/electricity/monthly/epm_table_grapher.php?t=epmt_6_01"
ARCHIVE = "https://www.eia.gov/electricity/data/eia860m/archive/xls/{}_generator{}.xlsx"
CURRENT = "https://www.eia.gov/electricity/data/eia860m/xls/{}_generator{}.xlsx"
# EPM rows (technology subtotals) -> plants.json fuel groups (EIA energy source codes)
ROWS = {
    "solar": ["Solar Subtotal"],
    "wind": ["Wind (Summer Capacity)"],
    "gas": ["Natural Gas Subtotal", "Other Gases"],
    "oil": ["Petroleum Liquids", "Petroleum Coke"],
    "coal": ["Coal Subtotal"],
    "nuclear": ["Nuclear"],
    "hydro": ["Conventional Hydroelectric"],
    "storage": ["Energy Storage Subtotal"],
    "bio": ["Biomass Sources Subtotal"],
    "geothermal": ["Geothermal"],
    "other": ["All Other"],
}


def epm_table() -> tuple[str, str, dict[str, float]]:
    """(month, year, {row label: total in-service MW at the end of that month})."""
    with httpx.Client(timeout=120, headers=UA) as c:
        text = c.get(EPM).text
    s = re.sub(r"<script.*?</script>|<style.*?</style>", "", text, flags=re.S)
    s = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " | ", s)))
    s = re.sub(r"(\s*\|\s*)+", " | ", s)
    head = re.search(r"Table 6\.1\. .*?\(MW\), \w+ \d{4} to (\w+) (\d{4})", s)
    if not head:
        raise SystemExit("EPM Table 6.1: no title")
    rows: dict[str, float] = {}
    # cells: "<label> | Utility Scale Facilities | <end of last month> | <added> | <reduced> | <end of this month> | ..."
    cells = [c.strip() for c in s.split("|")]
    for i, cell in enumerate(cells):
        if cell.lower() != "utility scale facilities" or i + 4 >= len(cells):
            continue
        label = cells[i - 1].lstrip(". ")
        try:
            end_of_month = float(cells[i + 4].replace(",", ""))
        except ValueError:
            continue
        rows[label] = rows.get(label, 0.0) + end_of_month
    return head.group(1), head.group(2), rows


def main() -> None:
    month, year, epm = epm_table()
    print(f"EIA Electric Power Monthly, Table 6.1: end of {month} {year}")
    path = RAW / f"{month.lower()}_generator{year}.xlsx"
    with httpx.Client(timeout=180, follow_redirects=True, headers=UA) as c:
        for url in (ARCHIVE, CURRENT):
            try:
                download(c, url.format(month.lower(), year), path)
                break
            except httpx.HTTPStatusError:
                continue
    plants = build_plants(path, f"{month} {year}", str(path))
    ours = plants["totals"]["operating"]
    total_epm = epm.get("TOTAL", 0.0)
    total_ours = sum(ours.values())
    print(f"\n{'':12} {'EPM 6.1':>12} {'plants.json':>12} {'difference':>11}")
    for kind, labels in ROWS.items():
        e = sum(epm.get(x, 0.0) for x in labels)
        o = ours.get(kind, 0.0)
        print(f"{kind:12} {e:12,.1f} {o:12,.1f} {o - e:+11,.1f}")
    print(
        f"{'TOTAL':12} {total_epm:12,.1f} {total_ours:12,.1f} {total_ours - total_epm:+11,.1f}  ({(total_ours / total_epm - 1) * 100:+.3f} %)"
    )
    print(
        "\nplants.json: the Operating sheet (operating, standby, out of service), 50 states + DC, net summer MW, grouped by energy source code;"
    )
    print(
        "EPM rows are grouped by technology, so single fuels can differ where a unit's technology and energy source disagree."
    )


if __name__ == "__main__":
    main()
