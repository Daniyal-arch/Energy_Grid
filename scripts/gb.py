"""Great Britain from Elexon's open Insights API (no key), shaped like scripts/entsoe.py.

ENTSO-E has no load or generation for Great Britain since Brexit. Elexon publishes
(scripts/probe_gb_outages.py):
  FUELINST        generation by fuel type every 5 minutes, transmission-connected units;
                  each interconnector appears as its own "fuel" (positive = import into GB)
  demand/outturn  initial national demand outturn (INDO), half-hourly

Placed on the app's 15-min grid: the 5-minute reading at the start of each quarter-hour
(passthrough); a half-hourly demand value fills both quarters. Embedded generation
(rooftop solar, small wind) is not metered here: generation and demand are the
transmission-level figures, and the renewable share is computed over them.

Borders (computed: the sum of the links between the same two countries):
  GB-FR = IFA + IFA2 + ElecLink, GB-IE = East-West + Greenlink, GB-NL = BritNed,
  GB-BE = Nemo, GB-NO = North Sea Link, GB-DK = Viking. Moyle (Scotland - Northern
  Ireland) stays inside the UK on this map and is not drawn.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import httpx
from entsoe import Grid, Series, shaped

BASE = "https://data.elexon.co.uk/bmrs/api/v1"
# Elexon fuel type -> the production-type names the scripts group by
FUEL_NAME = {
    "BIOMASS": "Biomass",
    "CCGT": "Fossil gas",
    "OCGT": "Fossil gas",
    "COAL": "Fossil hard coal",
    "NUCLEAR": "Nuclear",
    "OIL": "Fossil oil",
    "NPSHYD": "Hydro water reservoir",
    "PS": "Hydro pumped storage",
    "WIND": "Wind",
    "OTHER": "Others",
}
# neighbour -> Elexon interconnector fuel types (positive = import into GB)
LINKS = {
    "FR": ["INTFR", "INTIFA2", "INTELEC"],
    "IE": ["INTEW", "INTGRNL"],
    "NL": ["INTNED"],
    "BE": ["INTNEM"],
    "NO": ["INTNSL"],
    "DK": ["INTVKL"],
}


def _get(client: httpx.Client, path: str, params: dict[str, str]) -> list[dict]:
    for attempt in range(4):
        try:
            r = client.get(f"{BASE}{path}", params=params)
        except httpx.TransportError:
            time.sleep(10 * (attempt + 1))
            continue
        if r.status_code == 200:
            d = r.json()
            return d if isinstance(d, list) else d.get("data", [])
        time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"Elexon {path}: no answer")


def _ts(text: str) -> int:
    return int(datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp())


def fuelinst(client: httpx.Client, grid: Grid) -> dict[str, Series]:
    """Every fuel type's 5-min reading at the start of each 15-min slot (MW)."""
    start = datetime.fromtimestamp(grid.start, tz=UTC)
    end = datetime.fromtimestamp(grid.start + 900 * grid.slots, tz=UTC)
    rows = _get(
        client,
        "/datasets/FUELINST/stream",
        # published up to 5 min after the reading
        {
            "publishDateTimeFrom": start.isoformat(),
            "publishDateTimeTo": (end + timedelta(minutes=10)).isoformat(),
        },
    )
    out: dict[str, Series] = {}
    for row in rows:
        sec = _ts(row["startTime"])
        if sec % 900:
            continue  # only the reading that starts a quarter-hour
        k = (sec - grid.start) // 900
        if 0 <= k < grid.slots and row.get("generation") is not None:
            out.setdefault(row["fuelType"], grid.empty())[k] = float(row["generation"])
    return out


def power(
    client: httpx.Client, grid: Grid, readings: dict[str, Series] | None = None
) -> dict | None:
    """Load, transmission generation by type and the computed renewable share."""
    readings = readings if readings is not None else fuelinst(client, grid)
    generation: dict[str, Series] = {}
    for fuel, values in readings.items():
        name = FUEL_NAME.get(fuel)
        if not name:
            continue  # interconnectors
        col = generation.setdefault(name, grid.empty())
        for k, v in enumerate(values):
            if v is not None:
                col[k] = (col[k] or 0.0) + v
    start = datetime.fromtimestamp(grid.start, tz=UTC)
    end = datetime.fromtimestamp(grid.start + 900 * grid.slots, tz=UTC)
    demand = _get(
        client,
        "/demand/outturn/stream",
        {
            "settlementDateFrom": (start - timedelta(days=1)).date().isoformat(),
            "settlementDateTo": end.date().isoformat(),
        },
    )
    load = grid.empty()
    for row in demand:
        v = row.get("initialDemandOutturn")
        if v is None:
            continue
        first = (_ts(row["startTime"]) - grid.start) // 900
        for k in (first, first + 1):  # half-hourly: both quarters
            if 0 <= k < grid.slots:
                load[k] = float(v)
    if not generation:
        return None
    return shaped(grid.seconds(), load, generation)


def flows(
    client: httpx.Client, grid: Grid, readings: dict[str, Series] | None = None
) -> dict[tuple[str, str], Series]:
    """Net flow per border, keyed (a, b) with a -> b positive as in entsoe.BORDERS."""
    readings = readings if readings is not None else fuelinst(client, grid)
    out: dict[tuple[str, str], Series] = {}
    for other, links in LINKS.items():
        cols = [readings.get(link) for link in links]
        if any(c is None for c in cols):
            continue
        imports = [
            None if any(c[k] is None for c in cols) else sum(c[k] or 0.0 for c in cols)  # type: ignore[index]
            for k in range(grid.slots)
        ]
        a, b = sorted((other, "GB"))
        # import into GB is a flow other -> GB
        out[(a, b)] = [None if v is None else round(v if b == "GB" else -v, 1) for v in imports]
    return out
