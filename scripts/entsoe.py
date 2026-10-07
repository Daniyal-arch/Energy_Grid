"""ENTSO-E Transparency client for the app's time series: prices, load, generation, flows.

Energy-Charts (which republished these ENTSO-E series) has been unreachable since
2026-09-24 (HTTP 503 "No server is available"), so the scripts now ask ENTSO-E itself
(scripts/probe_entsoe_core.py, scripts/probe_entsoe_coverage.py). Needs ENTSOE_API_KEY.

  A44  day-ahead prices per bidding zone. Where a zone has several series (EXAA for
       DE-LU and AT, Spain's intraday auctions), the coupled day-ahead auction is the
       series without a classification sequence, else sequence 1 (probe: DE-LU seq. 1
       tracks NL/FR, AT seq. 1 tracks SI).
  A65  actual total load per country (MW)
  A75  actual generation per production type per country (MW); consumption series
       (pumping, battery charging: outBiddingZone_Domain) are left out
  A11  physical flows per border direction (MW)

Every series is put on a 15-min grid; a coarser value (30 or 60 min) fills each slot it
covers, unchanged. Results are shaped like the Energy-Charts answers the scripts used
to read, so their parsing (`power`, `power_series`, `day_payload`) stays the same.
Computed here and documented in docs/DATA_SOURCES.md:
  - "Renewable share of generation": renewable types / all generation types x 100,
    over the types reported for that interval
  - border net flow: flow one way minus flow the other way (both measured)
  - EU: per interval, the sum over the member states with data (listed in "sum_of"),
    only where every one of them reports load and generation
"""

from __future__ import annotations

import os
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import httpx
from dotenv import load_dotenv

load_dotenv()
BASE = "https://web-api.tp.entsoe.eu/api"
SOURCE = "ENTSO-E Transparency Platform"
STEP = 900
WORKERS = 4  # ENTSO-E allows 400 requests a minute; four at a time stays far below

# bidding zones with day-ahead prices -> EIC code
ZONE_EIC = {
    "AL": "10YAL-KESH-----5", "AT": "10YAT-APG------L", "BE": "10YBE----------2",
    "BG": "10YCA-BULGARIA-R", "CH": "10YCH-SWISSGRIDZ", "CZ": "10YCZ-CEPS-----N",
    "DE-LU": "10Y1001A1001A82H", "DK1": "10YDK-1--------W", "DK2": "10YDK-2--------M",
    "EE": "10Y1001A1001A39I", "ES": "10YES-REE------0", "FI": "10YFI-1--------U",
    "FR": "10YFR-RTE------C", "GR": "10YGR-HTSO-----Y", "HR": "10YHR-HEP------M",
    "HU": "10YHU-MAVIR----U", "IT-North": "10Y1001A1001A73I",
    "IT-Centre-North": "10Y1001A1001A70O", "IT-Centre-South": "10Y1001A1001A71M",
    "IT-South": "10Y1001A1001A788", "IT-Calabria": "10Y1001C--00096J",
    "IT-Sicily": "10Y1001A1001A75E", "IT-Sardinia": "10Y1001A1001A74G",
    "LT": "10YLT-1001A0008Q", "LV": "10YLV-1001A00074", "ME": "10YCS-CG-TSO---S",
    "MK": "10YMK-MEPSO----8", "NL": "10YNL----------L", "NO1": "10YNO-1--------2",
    "NO2": "10YNO-2--------T", "NO3": "10YNO-3--------J", "NO4": "10YNO-4--------9",
    "NO5": "10Y1001A1001A48H", "PL": "10YPL-AREA-----S", "PT": "10YPT-REN------W",
    "RO": "10YRO-TEL------P", "RS": "10YCS-SERBIATSOV", "SE1": "10Y1001A1001A44P",
    "SE2": "10Y1001A1001A45N", "SE3": "10Y1001A1001A46L", "SE4": "10Y1001A1001A47J",
    "SI": "10YSI-ELES-----O", "SK": "10YSK-SEPS-----K", "UA-IPS": "10Y1001C--000182",
}  # fmt: skip

# country areas (load, generation, flows) -> EIC code
AREA_EIC = {
    "AL": "10YAL-KESH-----5", "AT": "10YAT-APG------L", "BA": "10YBA-JPCC-----D",
    "BE": "10YBE----------2", "BG": "10YCA-BULGARIA-R", "CH": "10YCH-SWISSGRIDZ",
    "CZ": "10YCZ-CEPS-----N", "DE": "10Y1001A1001A83F", "DK": "10Y1001A1001A65H",
    "EE": "10Y1001A1001A39I", "ES": "10YES-REE------0", "FI": "10YFI-1--------U",
    "FR": "10YFR-RTE------C", "GB": "10YGB----------A", "GR": "10YGR-HTSO-----Y",
    "HR": "10YHR-HEP------M", "HU": "10YHU-MAVIR----U", "IE": "10YIE-1001A00010",
    "IT": "10YIT-GRTN-----B", "LT": "10YLT-1001A0008Q", "LU": "10YLU-CEGEDEL-NQ",
    "LV": "10YLV-1001A00074", "ME": "10YCS-CG-TSO---S", "MK": "10YMK-MEPSO----8",
    "NL": "10YNL----------L", "NO": "10YNO-0--------C", "PL": "10YPL-AREA-----S",
    "PT": "10YPT-REN------W", "RO": "10YRO-TEL------P", "RS": "10YCS-SERBIATSOV",
    "SE": "10YSE-1--------K", "SI": "10YSI-ELES-----O", "SK": "10YSK-SEPS-----K",
    "UA": "10Y1001C--00003F", "MD": "10Y1001A1001A990", "XK": "10Y1001C--00100H",
}  # fmt: skip

# EU member states on the map (Cyprus and Malta are not mapped)
EU_MEMBERS = [
    "AT", "BE", "BG", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GR", "HR", "HU", "IE",
    "IT", "LT", "LU", "LV", "NL", "PL", "PT", "RO", "SE", "SI", "SK",
]  # fmt: skip

# ENTSO-E production type -> the name the scripts group by (fetch_eu_snapshot.FUEL_GROUP)
PSR_NAME = {
    "B01": "Biomass",
    "B02": "Fossil brown coal / lignite",
    "B03": "Fossil coal-derived gas",
    "B04": "Fossil gas",
    "B05": "Fossil hard coal",
    "B06": "Fossil oil",
    "B07": "Fossil oil shale",
    "B08": "Fossil peat",
    "B09": "Geothermal",
    "B10": "Hydro pumped storage",
    "B11": "Hydro Run-of-River",
    "B12": "Hydro water reservoir",
    "B13": "Marine",
    "B14": "Nuclear",
    "B15": "Other renewables",
    "B16": "Solar",
    "B17": "Waste",
    "B18": "Wind offshore",
    "B19": "Wind onshore",
    "B20": "Others",
    "B25": "Battery",
}
RENEWABLE = {
    "Biomass",
    "Geothermal",
    "Hydro Run-of-River",
    "Hydro water reservoir",
    "Marine",
    "Other renewables",
    "Solar",
    "Wind offshore",
    "Wind onshore",
    "Wind",  # Great Britain (Elexon) reports onshore and offshore together
}
RESOLUTION_S = {"PT15M": 900, "PT30M": 1800, "PT60M": 3600}

Series = list[float | None]


class Grid:
    """A window of 15-min slots: slot k starts at start + k * STEP (unix seconds)."""

    def __init__(self, start: datetime, end: datetime) -> None:
        self.start = int(start.timestamp()) // STEP * STEP
        self.slots = max(0, (int(end.timestamp()) - self.start) // STEP)

    def seconds(self) -> list[int]:
        return [self.start + STEP * k for k in range(self.slots)]

    def empty(self) -> Series:
        return [None] * self.slots

    def params(self) -> dict[str, str]:
        def stamp(sec: int) -> str:
            return datetime.fromtimestamp(sec, tz=UTC).strftime("%Y%m%d%H%M")

        return {
            "periodStart": stamp(self.start),
            "periodEnd": stamp(self.start + STEP * self.slots),
        }

    def windows(self, days: int = 180) -> list[dict[str, str]]:
        """The grid's period in pieces (ENTSO-E answers at most one year per request)."""

        def stamp(sec: int) -> str:
            return datetime.fromtimestamp(sec, tz=UTC).strftime("%Y%m%d%H%M")

        end = self.start + STEP * self.slots
        cuts = [*range(self.start, end, days * 86400), end]
        return [
            {"periodStart": stamp(a), "periodEnd": stamp(b)}
            for a, b in zip(cuts, cuts[1:], strict=False)
        ]


def _ts(text: str) -> int:
    return int(datetime.strptime(text, "%Y-%m-%dT%H:%MZ").replace(tzinfo=UTC).timestamp())


def request(client: httpx.Client, params: dict[str, str]) -> ET.Element | None:
    """One API call; None when ENTSO-E has no data (it answers with an acknowledgement)."""
    query = {"securityToken": os.environ["ENTSOE_API_KEY"], **params}
    for attempt in range(5):
        try:
            r = client.get(BASE, params=query)
        except httpx.TransportError:
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(float(r.headers.get("retry-after") or 10 * (attempt + 1)))
            continue
        if r.status_code != 200:
            return None
        root = ET.fromstring(r.content)
        return None if root.tag.endswith("Acknowledgement_MarketDocument") else root
    return None


def series_of(root: ET.Element | None, value_tag: str, grid: Grid) -> list[tuple[dict, Series]]:
    """Every TimeSeries of a document on the grid, with its metadata (flat text fields)."""
    if root is None:
        return []
    ns = {"n": root.tag.split("}")[0].strip("{")}
    out: list[tuple[dict, Series]] = []
    for ts in root.findall("n:TimeSeries", ns):
        meta = {
            child.tag.split("}")[1]: (child.text or "").strip()
            for child in ts
            if not len(child) and child.text and child.text.strip()
        }
        psr = ts.find("n:MktPSRType/n:psrType", ns)
        if psr is not None:
            meta["psrType"] = psr.text or ""
        variable = ts.findtext("n:curveType", default="A01", namespaces=ns) == "A03"
        values = grid.empty()
        for period in ts.findall("n:Period", ns):
            step = RESOLUTION_S.get(period.findtext("n:resolution", default="", namespaces=ns))
            if not step:
                continue
            t0 = _ts(period.findtext("n:timeInterval/n:start", namespaces=ns) or "")
            t1 = _ts(period.findtext("n:timeInterval/n:end", namespaces=ns) or "")
            points = sorted(
                (
                    int(p.findtext("n:position", namespaces=ns) or 0),
                    float(p.findtext(f"n:{value_tag}", namespaces=ns) or 0),
                )
                for p in period.findall("n:Point", ns)
            )
            n_steps = (t1 - t0) // step
            for i, (pos, value) in enumerate(points):
                # A03 curves leave out points equal to the one before: a value holds
                # until the next point, the last one to the end of the period
                last = (
                    (points[i + 1][0] - 1 if i + 1 < len(points) else n_steps) if variable else pos
                )
                for k in range(pos, last + 1):
                    sec = t0 + (k - 1) * step
                    for sub in range(0, step, STEP):
                        slot = (sec + sub - grid.start) // STEP
                        if 0 <= slot < grid.slots:
                            values[slot] = round(value, 2)
        out.append((meta, values))
    return out


def run(jobs: Iterable[tuple[str, Callable[[], object]]]) -> dict[str, object]:
    """Run labelled requests a few at a time; results keyed by label."""
    jobs = list(jobs)
    with ThreadPoolExecutor(WORKERS) as pool:
        futures = {label: pool.submit(job) for label, job in jobs}
        return {label: f.result() for label, f in futures.items()}


def price(client: httpx.Client, zone: str, grid: Grid) -> dict | None:
    """Day-ahead price of one zone: {"unix_seconds", "price"} (EUR/MWh)."""
    eic = ZONE_EIC[zone]
    found = []
    for window in grid.windows():
        root = request(
            client, {"documentType": "A44", "in_Domain": eic, "out_Domain": eic, **window}
        )
        found += series_of(root, "price.amount", grid)
    seq = "classificationSequence_AttributeInstanceComponent.position"
    # EUR only (Ukraine's market publishes in UAH)
    found = [(m, v) for m, v in found if m.get("currency_Unit.name") == "EUR"]
    pick = [v for m, v in found if seq not in m] or [v for m, v in found if m.get(seq) == "1"]
    if not pick:
        return None
    merged = grid.empty()
    for values in pick:  # one series per day; days do not overlap
        for k, v in enumerate(values):
            if v is not None:
                merged[k] = v
    return {"unix_seconds": grid.seconds(), "price": merged}


def zone_generation(
    client: httpx.Client, zone: str, psr_types: list[str], grid: Grid
) -> Series | None:
    """Actual generation (MW) of the given production types in one bidding zone, summed
    per slot over the types reported for it (A75 with a psrType filter)."""
    total = grid.empty()
    for psr in psr_types:
        for window in grid.windows():
            root = request(
                client,
                {
                    "documentType": "A75",
                    "processType": "A16",
                    "in_Domain": ZONE_EIC[zone],
                    "psrType": psr,
                    **window,
                },
            )
            for meta, values in series_of(root, "quantity", grid):
                if "outBiddingZone_Domain.mRID" in meta:
                    continue
                for k, v in enumerate(values):
                    if v is not None:
                        total[k] = (total[k] or 0.0) + v
    return total if any(v is not None for v in total) else None


def power(client: httpx.Client, iso: str, grid: Grid) -> dict | None:
    """Load, generation per type and the computed renewable share of one country."""
    eic = AREA_EIC[iso]
    load_doc = request(
        client,
        {
            "documentType": "A65",
            "processType": "A16",
            "outBiddingZone_Domain": eic,
            **grid.params(),
        },
    )
    gen_doc = request(
        client, {"documentType": "A75", "processType": "A16", "in_Domain": eic, **grid.params()}
    )
    load = grid.empty()
    for _, values in series_of(load_doc, "quantity", grid):
        load = [v if v is not None else old for v, old in zip(values, load, strict=True)]
    generation: dict[str, Series] = {}
    for meta, values in series_of(gen_doc, "quantity", grid):
        name = PSR_NAME.get(meta.get("psrType", ""))
        if not name or "outBiddingZone_Domain.mRID" in meta:
            continue
        col = generation.setdefault(name, grid.empty())
        for k, v in enumerate(values):
            if v is not None:
                col[k] = v
    if not generation and all(v is None for v in load):
        return None
    return shaped(grid.seconds(), load, generation)


def shaped(seconds: list[int], load: Series, generation: dict[str, Series]) -> dict:
    """Energy-Charts-shaped power answer, with the renewable share computed per slot
    over the production types reported for that slot."""
    share: Series = [None] * len(seconds)
    for k in range(len(seconds)):
        present = [(name, col[k]) for name, col in generation.items() if col[k] is not None]
        total = sum(v or 0.0 for _, v in present)
        green = sum(v or 0.0 for name, v in present if name in RENEWABLE)
        share[k] = round(100.0 * green / total, 1) if total > 0 else None
    types = [{"name": name, "data": col} for name, col in sorted(generation.items())]
    types += [
        {"name": "Load", "data": load},
        {"name": "Renewable share of generation", "data": share},
    ]
    return {"unix_seconds": seconds, "production_types": types}


def eu_sum(countries: dict[str, dict], span: range | None = None) -> dict | None:
    """EU totals per slot of `span` (default: all): the sum over the member states with
    load data in the span (named in "sum_of"). All countries share one grid.

    A slot counts only where every one of those members reports load and at least one
    generation type, so a total never leaves out a member that is merely late; a
    type a member does not report for that slot adds nothing."""
    data = {iso: countries[iso] for iso in EU_MEMBERS if countries.get(iso)}
    if not data:
        return None
    seconds = next(iter(data.values()))["unix_seconds"]
    span = span if span is not None else range(len(seconds))
    cols = {iso: {t["name"]: t["data"] for t in d["production_types"]} for iso, d in data.items()}
    cols = {
        iso: c
        for iso, c in cols.items()
        if "Load" in c and any(c["Load"][k] is not None for k in span)
    }
    if not cols:
        return None
    skip = ("Load", "Renewable share of generation")
    names = sorted({n for c in cols.values() for n in c if n not in skip})
    load: Series = [None] * len(seconds)
    generation: dict[str, Series] = {n: [None] * len(seconds) for n in names}
    for k in span:
        if not all(
            "Load" in c
            and c["Load"][k] is not None
            and any(c[n][k] is not None for n in c if n not in skip)
            for c in cols.values()
        ):
            continue
        load[k] = round(sum(c["Load"][k] or 0.0 for c in cols.values()), 1)
        for n in names:
            present = [c[n][k] or 0.0 for c in cols.values() if n in c and c[n][k] is not None]
            generation[n][k] = round(sum(present), 1) if present else None
    result = shaped(seconds, load, generation)
    result["sum_of"] = list(cols)
    return result


def flows(
    client: httpx.Client, borders: list[tuple[str, str]], grid: Grid
) -> dict[tuple[str, str], Series]:
    """Net physical flow a -> b per border (MW): measured a->b minus measured b->a."""

    def one(src: str, dst: str) -> Series | None:
        root = request(
            client,
            {
                "documentType": "A11",
                "out_Domain": AREA_EIC[src],
                "in_Domain": AREA_EIC[dst],
                **grid.params(),
            },
        )
        found = series_of(root, "quantity", grid)
        if not found:
            return None
        merged = grid.empty()
        for _, values in found:
            for k, v in enumerate(values):
                if v is not None:
                    merged[k] = v
        return merged

    jobs = []
    for a, b in borders:
        if a in AREA_EIC and b in AREA_EIC:
            jobs.append((f"{a}>{b}", lambda a=a, b=b: one(a, b)))
            jobs.append((f"{b}>{a}", lambda a=a, b=b: one(b, a)))
    got = run(jobs)
    out: dict[tuple[str, str], Series] = {}
    for a, b in borders:
        there, back = got.get(f"{a}>{b}"), got.get(f"{b}>{a}")
        if not isinstance(there, list) or not isinstance(back, list):
            continue
        out[(a, b)] = [
            None if x is None or y is None else round(x - y, 1)
            for x, y in zip(there, back, strict=True)
        ]
    return out


# borders with measured flows (the 79 Energy-Charts reported; ENTSO-E has 74 of them)
BORDERS: list[tuple[str, str]] = [
    ("AL", "GR"), ("AL", "ME"), ("AL", "XK"), ("ME", "XK"), ("AT", "CH"), ("AT", "CZ"),
    ("AT", "DE"), ("AT", "HU"), ("AT", "IT"), ("AT", "SI"), ("BA", "HR"), ("BA", "ME"),
    ("BA", "RS"), ("BE", "DE"), ("BE", "FR"), ("BE", "GB"), ("BE", "LU"), ("BE", "NL"),
    ("BG", "GR"), ("BG", "MK"), ("BG", "RO"), ("BG", "RS"), ("CH", "DE"), ("CH", "FR"),
    ("CH", "IT"), ("CZ", "DE"), ("CZ", "PL"), ("CZ", "SK"), ("DE", "DK"), ("DE", "FR"),
    ("DE", "LU"), ("DE", "NL"), ("DE", "NO"), ("DE", "PL"), ("DE", "SE"), ("DK", "GB"),
    ("DK", "NL"), ("DK", "NO"), ("DK", "SE"), ("EE", "FI"), ("EE", "LV"), ("ES", "FR"),
    ("ES", "PT"), ("FI", "NO"), ("FI", "SE"), ("FR", "GB"), ("FR", "IT"), ("GB", "IE"),
    ("GB", "NL"), ("GB", "NO"), ("GR", "IT"), ("GR", "MK"), ("HR", "HU"), ("HR", "RS"),
    ("HR", "SI"), ("HU", "RO"), ("HU", "RS"), ("HU", "SI"), ("HU", "SK"), ("HU", "UA"),
    ("IT", "ME"), ("IT", "SI"), ("LT", "LV"), ("LT", "PL"), ("LT", "SE"), ("MD", "RO"),
    ("MD", "UA"), ("ME", "RS"), ("MK", "RS"), ("MK", "XK"), ("NL", "NO"), ("NO", "SE"),
    ("PL", "SE"), ("PL", "SK"), ("PL", "UA"), ("RO", "RS"), ("RO", "UA"), ("RS", "XK"),
    ("SK", "UA"),
]  # fmt: skip
