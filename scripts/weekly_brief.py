"""The weekly brief (brief 30, Track 6.5): what changed this week, written from fixed templates
over the app's own data files, with no language model.

Reads
  the day archive      eu-days branch, eu/day/index.json and eu/day/<YYYY-MM-DD>.json
                       (scripts/build_eu_day.py), falling back to frontend/public/data/eu/day/
  prices.json          eu-days branch (scripts/build_prices.py), twelve months per zone
  outages.json         eu-data branch (scripts/fetch_eu_snapshot.py), ENTSO-E A80 now
  us/queues_live.json  bundled (scripts/fetch_us_queues.py), the markets' own queues
  us/plants.json       bundled (scripts/fetch_us_grid.py), EIA-860M
  eu/plants.json       bundled (scripts/build_eu_grid.py), powerplantmatching >= 20 MW
  frontend/public/brief/latest.json, the previous brief (its snapshot figures, for comparison)

Writes frontend/public/brief/latest.json (structured) and latest.html (a standalone page).

Every sentence comes from a template in TEMPLATES, names its source, links the file it was read
from and gives that file's "as of" date. Computed values say how (weekly mean = mean of the
15-minute day-ahead prices of the seven days; sums are sums of the rows named). A section whose
data is missing is skipped and the brief says why.

    uv run python scripts/weekly_brief.py            # remote archive, local fallback
    uv run python scripts/weekly_brief.py --local    # bundled files only
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "frontend" / "public" / "data"
OUT = ROOT / "frontend" / "public" / "brief"
ARCHIVE = "https://raw.githubusercontent.com/Daniyal-arch/Energy_Grid/eu-days/eu"
SNAPSHOT = "https://raw.githubusercontent.com/Daniyal-arch/Energy_Grid/eu-data/eu"
USER_AGENT = {"User-Agent": "InfraAtlas weekly brief (github.com/Daniyal-arch/Energy_Grid)"}

WEEK = 7
# a zone's weekly mean is used only when this share of its 15-minute slots has a price
MIN_COVERAGE = 0.95
TOP = 3

ENTSOE_DA = "ENTSO-E Transparency Platform, A44 day-ahead prices"
ENTSOE_A80 = "ENTSO-E Transparency Platform, A80 unavailability of generation units"

# The only sentences the brief writes. {source} and {as_of} are filled from the figure's file.
TEMPLATES: dict[str, str] = {
    "price_rise": (
        "The {rank}largest weekly rise in the mean day-ahead price was in {zone}: "
        "{prev} to {now} EUR/MWh ({delta:+} EUR/MWh)."
    ),
    "price_fall": (
        "The {rank}largest weekly fall in the mean day-ahead price was in {zone}: "
        "{prev} to {now} EUR/MWh ({delta:+} EUR/MWh)."
    ),
    "price_zones": (
        "{n} bidding zones had prices in at least {cov} % of the 15-minute slots of both weeks; "
        "the weekly mean is the mean of those prices."
    ),
    "price_high": "The highest 15-minute day-ahead price of the week was {eur} EUR/MWh in {zone} at {at}.",
    "price_low": "The lowest 15-minute day-ahead price of the week was {eur} EUR/MWh in {zone} at {at}.",
    "above_year": (
        "{zone} went above its highest price of the period {p0} to {p1} ({old} EUR/MWh): "
        "{eur} EUR/MWh at {at}."
    ),
    "below_year": (
        "{zone} went below its lowest price of the period {p0} to {p1} ({old} EUR/MWh): "
        "{eur} EUR/MWh at {at}."
    ),
    "no_year_record": (
        "No zone went above its highest or below its lowest price of the period {p0} to {p1}."
    ),
    "record": (
        "The week's highest EU {what} was {gw} GW on {day} (sum of the member states "
        "reporting{pct}); {verdict} ({n} days in the archive, {first} to {last})."
    ),
    "no_change": "No zone's weekly mean {dir} against the week before.",
    "offline_now": (
        "{mw} MW of generation was reported offline: {planned} MW planned and {forced} MW "
        "forced (sum of the units reporting)."
    ),
    "offline_change": "The week before, the brief read {prev} MW offline ({delta:+} MW).",
    "offline_top": "Most offline: {list}.",
    "queue": "{market}: {active} active requests, {mw} MW (queue read {read}).",
    "queue_change": "{market}: {active_delta:+} active requests and {mw_delta:+} MW since the previous brief (read {prev_read}).",
    "queue_missing": "{market}: not read ({why}).",
    "us_added": (
        "Plants in operation whose earliest unit of a fuel group entered service in {year} "
        "(EIA-860M points with coordinates): {mw} MW (sum of net summer capacity; largest: {list})."
    ),
    "us_added_change": "The previous brief, from the {prev_release} release, read {prev} MW ({delta:+} MW).",
    "eu_added": (
        "Operating units of at least 20 MW commissioned in {year}: {n} units, {mw} MW "
        "(sum; largest: {list}); {prev_year}: {prev_n} units, {prev_mw} MW."
    ),
}

ORDINAL = ["", "second ", "third "]


@dataclass
class Cite:
    source: str
    url: str
    as_of: str


@dataclass
class Sentence:
    template: str
    values: dict[str, Any]
    cite: Cite

    @property
    def text(self) -> str:
        return TEMPLATES[self.template].format(**self.values)

    def to_json(self) -> dict[str, Any]:
        return {
            "template": self.template,
            "text": self.text,
            "values": self.values,
            "source": self.cite.source,
            "url": self.cite.url,
            "as_of": self.cite.as_of,
        }


@dataclass
class Section:
    id: str
    title: str
    sentences: list[Sentence] = field(default_factory=list)
    skipped: str | None = None
    notes: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "status": "skipped" if self.skipped else "ok",
            "reason": self.skipped,
            "notes": self.notes,
            "sentences": [s.to_json() for s in self.sentences],
        }


# --- reading -------------------------------------------------------------------------------


class Reader:
    """Remote first (the branches the app reads), the bundled copy when that fails."""

    def __init__(self, local_only: bool) -> None:
        self.local_only = local_only
        self.client = httpx.Client(timeout=60, headers=USER_AGENT, follow_redirects=True)

    def get(self, remote: str | None, local: Path) -> tuple[Any, str] | None:
        if remote and not self.local_only:
            try:
                r = self.client.get(remote)
                if r.status_code == 200:
                    return r.json(), remote
                print(f"  {remote}: HTTP {r.status_code}, trying {local.name}", file=sys.stderr)
            except (httpx.HTTPError, ValueError) as e:
                print(f"  {remote}: {e}, trying {local.name}", file=sys.stderr)
        if local.exists():
            rel = local.relative_to(DATA).as_posix()
            return json.loads(local.read_text(encoding="utf-8")), f"/data/{rel}"
        return None


def fmt_num(v: float, digits: int = 1) -> str:
    """Thousands separators, the given decimals, trailing zeros of a whole number dropped."""
    s = f"{v:,.{digits}f}"
    return s[: -digits - 1] if digits and s.endswith("." + "0" * digits) else s


def fmt_price(v: float) -> str:
    return f"{v:.2f}"


def slot_time(day: dict[str, Any], slot: int) -> str:
    t = datetime.fromisoformat(day["start"]) + timedelta(seconds=slot * int(day["step_s"]))
    return t.strftime("%Y-%m-%d %H:%M UTC")


def load_days(reader: Reader) -> tuple[list[dict[str, Any]], str]:
    got = reader.get(f"{ARCHIVE}/day/index.json", DATA / "eu" / "day" / "index.json")
    if not got:
        return [], ""
    index, index_url = got
    base = index_url.rsplit("/", 1)[0]
    days: list[dict[str, Any]] = []
    for d in index.get("days", []):
        remote = f"{base}/{d}.json" if base.startswith(ARCHIVE) else None
        one = reader.get(remote, DATA / "eu" / "day" / f"{d}.json")
        if one:
            payload, url = one
            payload["_url"] = url
            days.append(payload)
    days.sort(key=lambda x: x["date"])
    return days, base


def consecutive(days: list[dict[str, Any]]) -> bool:
    ds = [date.fromisoformat(d["date"]) for d in days]
    return all((b - a).days == 1 for a, b in zip(ds, ds[1:], strict=False))


# --- sections ------------------------------------------------------------------------------


def week_means(days: list[dict[str, Any]]) -> dict[str, tuple[float, float]]:
    """Per zone: (mean of the 15-minute prices of the days, share of slots with a price)."""
    sums: dict[str, list[float]] = {}
    total = sum(int(d["slots"]) for d in days)
    for d in days:
        for zone, z in d.get("prices", {}).items():
            s = sums.setdefault(zone, [0.0, 0.0])
            for v in z.get("values") or []:
                if v is not None:
                    s[0] += float(v)
                    s[1] += 1
    return {z: (s[0] / s[1], s[1] / total) for z, s in sums.items() if s[1]}


def price_section(days: list[dict[str, Any]], base: str) -> tuple[Section, dict[str, Any]]:
    sec = Section("prices", "Day-ahead prices: this week against the week before")
    meta: dict[str, Any] = {}
    if len(days) < 2 * WEEK:
        sec.skipped = (
            f"the day archive holds {len(days)} days; two full weeks ({2 * WEEK}) are needed"
        )
        return sec, meta
    now, prev = days[-WEEK:], days[-2 * WEEK : -WEEK]
    if not consecutive(prev + now):
        sec.skipped = "the newest 14 days of the archive are not consecutive"
        return sec, meta
    meta = {
        "week": [now[0]["date"], now[-1]["date"]],
        "previous_week": [prev[0]["date"], prev[-1]["date"]],
    }
    m_now, m_prev = week_means(now), week_means(prev)
    rows = []
    for zone in sorted(set(m_now) & set(m_prev)):
        (a, ca), (b, cb) = m_now[zone], m_prev[zone]
        if ca >= MIN_COVERAGE and cb >= MIN_COVERAGE:
            rows.append((zone, round(b, 2), round(a, 2)))
    if not rows:
        sec.skipped = "no zone has prices in both weeks"
        return sec, meta
    as_of = f"days {prev[0]['date']} to {now[-1]['date']}"
    cite = Cite(f"{ENTSOE_DA}, the app's day archive", f"{base}/index.json", as_of)
    sec.sentences.append(
        Sentence("price_zones", {"n": len(rows), "cov": round(MIN_COVERAGE * 100)}, cite)
    )
    rows.sort(key=lambda r: r[2] - r[1])
    for kind, picked in (("price_rise", rows[::-1][:TOP]), ("price_fall", rows[:TOP])):
        picked = [r for r in picked if (r[2] - r[1] > 0) == (kind == "price_rise") and r[2] != r[1]]
        if not picked:
            word = "rose" if kind == "price_rise" else "fell"
            sec.sentences.append(Sentence("no_change", {"dir": word}, cite))
        for i, (zone, b, a) in enumerate(picked):
            delta = round(a - b, 2)
            sec.sentences.append(
                Sentence(
                    kind,
                    {
                        "rank": ORDINAL[i],
                        "zone": zone,
                        "prev": fmt_price(b),
                        "now": fmt_price(a),
                        "delta": delta,
                    },
                    cite,
                )
            )
    meta["means"] = {z: {"previous": b, "this": a} for z, b, a in rows}
    return sec, meta


def extremes_section(days: list[dict[str, Any]], prices: tuple[Any, str] | None) -> Section:
    sec = Section("extremes", "Price extremes this week")
    if len(days) < WEEK:
        sec.skipped = f"the day archive holds {len(days)} days; a full week is needed"
        return sec
    now = days[-WEEK:]
    hi: tuple[float, str, str, str] | None = None
    lo: tuple[float, str, str, str] | None = None
    per_zone: dict[str, dict[str, tuple[float, str]]] = {}
    for d in now:
        for zone, z in d.get("prices", {}).items():
            for i, v in enumerate(z.get("values") or []):
                if v is None:
                    continue
                at = slot_time(d, i)
                pz = per_zone.setdefault(zone, {})
                if "max" not in pz or v > pz["max"][0]:
                    pz["max"] = (v, at)
                if "min" not in pz or v < pz["min"][0]:
                    pz["min"] = (v, at)
                if hi is None or v > hi[0]:
                    hi = (v, zone, at, d["_url"])
                if lo is None or v < lo[0]:
                    lo = (v, zone, at, d["_url"])
    if hi is None or lo is None:
        sec.skipped = "the week's day files hold no prices"
        return sec
    for key, (v, zone, at, url) in (("price_high", hi), ("price_low", lo)):
        sec.sentences.append(
            Sentence(
                key,
                {"eur": fmt_price(v), "zone": zone, "at": at},
                Cite(ENTSOE_DA, url, at[:10]),
            )
        )
    if not prices:
        sec.notes.append("not compared with the twelve months: prices.json was not available")
        return sec
    pj, url = prices
    p0, p1 = pj["period"]
    cite = Cite(
        f"{ENTSOE_DA} (the week's day files) and prices.json (twelve months)",
        url,
        f"{pj['fetched'][:10]} (prices.json), {now[-1]['date']} (day files)",
    )
    found = False
    for zone in sorted(per_zone):
        year = pj["zones"].get(zone)
        if not year:
            continue
        mx, mn = year.get("max"), year.get("min")
        if mx and per_zone[zone]["max"][0] > mx[0]:
            v, at = per_zone[zone]["max"]
            sec.sentences.append(
                Sentence(
                    "above_year",
                    {
                        "zone": zone,
                        "p0": p0,
                        "p1": p1,
                        "old": fmt_price(mx[0]),
                        "eur": fmt_price(v),
                        "at": at,
                    },
                    cite,
                )
            )
            found = True
        if mn and per_zone[zone]["min"][0] < mn[0]:
            v, at = per_zone[zone]["min"]
            sec.sentences.append(
                Sentence(
                    "below_year",
                    {
                        "zone": zone,
                        "p0": p0,
                        "p1": p1,
                        "old": fmt_price(mn[0]),
                        "eur": fmt_price(v),
                        "at": at,
                    },
                    cite,
                )
            )
            found = True
    if not found:
        sec.sentences.append(Sentence("no_year_record", {"p0": p0, "p1": p1}, cite))
    return sec


RECORDS = [("solar_peak", "solar output"), ("wind_peak", "wind output"), ("load_max", "load")]


def records_section(days: list[dict[str, Any]], base: str) -> Section:
    sec = Section("records", "Records in the day archive")
    if len(days) < WEEK:
        sec.skipped = f"the day archive holds {len(days)} days; a full week is needed"
        return sec
    for kind, what in RECORDS:
        hits = [
            (h["gw"], d["date"], h.get("pct"), d["_url"])
            for d in days
            for h in d.get("highlights", [])
            if h.get("kind") == kind and h.get("gw") is not None
        ]
        week = [x for x in hits if x[1] >= days[-WEEK]["date"]]
        if not week:
            continue
        gw, day, pct, url = max(week, key=lambda x: x[0])
        best = max(x[0] for x in hits)
        best_day = max(hits, key=lambda x: x[0])[1]
        if gw < best:
            verdict = f"the archive's highest is {fmt_num(best)} GW on {best_day}"
        elif sum(1 for x in hits if x[0] == best) > 1:
            verdict = "equal to the highest in the archive"
        else:
            verdict = "the highest in the archive"
        sec.sentences.append(
            Sentence(
                "record",
                {
                    "what": what,
                    "gw": fmt_num(gw),
                    "day": day,
                    "pct": f", {pct} % of their generation" if pct is not None else "",
                    "verdict": verdict,
                    "n": len(days),
                    "first": days[0]["date"],
                    "last": days[-1]["date"],
                },
                Cite(
                    "ENTSO-E Transparency Platform, the day files' highlights (scripts/build_eu_day.py)",
                    url,
                    day,
                ),
            )
        )
    if not sec.sentences:
        sec.skipped = "the week's day files carry no highlights"
    return sec


def outage_section(
    outages: tuple[Any, str] | None, prev: dict[str, Any]
) -> tuple[Section, dict[str, Any]]:
    sec = Section("outages", "Plants offline")
    if not outages:
        sec.skipped = "outages.json was not available"
        return sec, {}
    o, url = outages
    tot = o.get("total") or {}
    if tot.get("offline_mw") is None:
        sec.skipped = "outages.json holds no total"
        return sec, {}
    at = o.get("at") or o.get("fetched", "")
    cite = Cite(ENTSOE_A80, url, at[:16].replace("T", " ") + " UTC")
    sec.sentences.append(
        Sentence(
            "offline_now",
            {
                "mw": fmt_num(tot["offline_mw"]),
                "planned": fmt_num(tot.get("planned_mw", 0.0)),
                "forced": fmt_num(tot.get("forced_mw", 0.0)),
            },
            cite,
        )
    )
    p = prev.get("offline_mw")
    if p is not None and prev.get("offline_at") != at:
        sec.sentences.append(
            Sentence(
                "offline_change",
                {"prev": fmt_num(p), "delta": round(tot["offline_mw"] - p, 1)},
                Cite(
                    ENTSOE_A80 + " (the previous brief)", url, str(prev.get("offline_at", ""))[:10]
                ),
            )
        )
    top = sorted(
        ((c, v.get("offline_mw") or 0.0) for c, v in (o.get("countries") or {}).items()),
        key=lambda x: -x[1],
    )[:TOP]
    if top:
        sec.sentences.append(
            Sentence(
                "offline_top",
                {"list": ", ".join(f"{c} {fmt_num(v)} MW" for c, v in top)},
                cite,
            )
        )
    return sec, {"offline_mw": tot["offline_mw"], "offline_at": at}


def queue_section(
    queues: tuple[Any, str] | None, prev: dict[str, Any]
) -> tuple[Section, dict[str, Any]]:
    sec = Section("queues", "US interconnection queues")
    if not queues:
        sec.skipped = "us/queues_live.json was not available"
        return sec, {}
    q, url = queues
    carry: dict[str, Any] = {}
    src = q.get("source", "the markets' interconnection queues")
    for market, m in (q.get("markets") or {}).items():
        cite = Cite(src, url, str(m.get("read") or q.get("fetched", ""))[:10])
        if "active" not in m:
            sec.sentences.append(
                Sentence(
                    "queue_missing", {"market": market, "why": m.get("missing", "no figures")}, cite
                )
            )
            continue
        sec.sentences.append(
            Sentence(
                "queue",
                {
                    "market": market,
                    "active": f"{m['active']:,}",
                    "mw": fmt_num(m["active_mw"]),
                    "read": m.get("read", ""),
                },
                cite,
            )
        )
        carry[market] = {"active": m["active"], "active_mw": m["active_mw"], "read": m.get("read")}
        p = (prev.get("queues") or {}).get(market)
        if p and p.get("read") != m.get("read"):
            sec.sentences.append(
                Sentence(
                    "queue_change",
                    {
                        "market": market,
                        "active_delta": m["active"] - p["active"],
                        "mw_delta": round(m["active_mw"] - p["active_mw"], 1),
                        "prev_read": p.get("read", ""),
                    },
                    cite,
                )
            )
    if not carry:
        sec.skipped = "no market queue was read"
    return sec, {"queues": carry}


def capacity_section(
    us: tuple[Any, str] | None, eu: tuple[Any, str] | None, prev: dict[str, Any]
) -> tuple[Section, dict[str, Any]]:
    sec = Section("capacity", "Capacity added")
    carry: dict[str, Any] = {}
    if us:
        u, url = us
        types, statuses = u["types"], u["statuses"]
        year = int(str(u.get("release", ""))[-4:] or 0)
        op = statuses.index("operating")
        rows = [p for p in u.get("points", []) if p[3] == op and p[5] == year]
        if year and rows:
            mw = round(sum(p[4] for p in rows), 1)
            by_type: dict[str, float] = {}
            for p in rows:
                by_type[types[p[2]]] = by_type.get(types[p[2]], 0.0) + p[4]
            biggest = sorted(by_type.items(), key=lambda x: -x[1])[:TOP]
            cite = Cite(u["source"], url, str(u.get("release")))
            sec.sentences.append(
                Sentence(
                    "us_added",
                    {
                        "year": year,
                        "mw": fmt_num(mw),
                        "list": ", ".join(f"{t} {fmt_num(v)} MW" for t, v in biggest),
                    },
                    cite,
                )
            )
            p = prev.get("us_added")
            if p and p.get("release") != u.get("release") and p.get("year") == year:
                sec.sentences.append(
                    Sentence(
                        "us_added_change",
                        {
                            "prev_release": p["release"],
                            "prev": fmt_num(p["mw"]),
                            "delta": round(mw - p["mw"], 1),
                        },
                        cite,
                    )
                )
            carry["us_added"] = {"year": year, "mw": mw, "release": u.get("release")}
    if eu:
        e, url = eu
        groups = e["groups"]
        years = sorted({p[6] for p in e.get("plants", []) if isinstance(p[6], int)})
        if years:
            y = years[-1]
            sums: dict[int, tuple[int, float, dict[str, float]]] = {}
            for yy in (y, y - 1):
                rows = [p for p in e["plants"] if p[6] == yy]
                g: dict[str, float] = {}
                for p in rows:
                    g[groups[p[0]]] = g.get(groups[p[0]], 0.0) + p[1]
                sums[yy] = (len(rows), float(sum(p[1] for p in rows)), g)
            n, mw, g = sums[y]
            pn, pmw, _ = sums[y - 1]
            biggest = sorted(g.items(), key=lambda x: -x[1])[:TOP]
            sec.sentences.append(
                Sentence(
                    "eu_added",
                    {
                        "year": y,
                        "n": n,
                        "mw": fmt_num(mw, 0),
                        "list": ", ".join(f"{k} {fmt_num(v, 0)} MW" for k, v in biggest),
                        "prev_year": y - 1,
                        "prev_n": pn,
                        "prev_mw": fmt_num(pmw, 0),
                    },
                    Cite(e["source"], url, "the bundled build"),
                )
            )
    if not sec.sentences:
        sec.skipped = "neither us/plants.json nor eu/plants.json was available"
    return sec, carry


# --- output --------------------------------------------------------------------------------

CSS = """
:root{--bg:#070910;--panel:#0b0e15;--line:rgba(150,162,182,.14);--text:#dce1e9;--dim:#8d94a1;
--faint:#59616f;--accent:#4f8fca;--mono:ui-monospace,"SF Mono",Menlo,monospace}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--text)}
body{font:14px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif;padding:0 16px}
main{max-width:760px;margin:0 auto;padding:28px 0 48px}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.brand{font:600 12px var(--mono);letter-spacing:.2em;color:var(--text)}
h1{font-size:20px;font-weight:600;margin:10px 0 2px}.sub{color:var(--dim);font-size:12px;margin:0}
section{border-top:1px solid var(--line);margin-top:22px;padding-top:12px}
h2{font-size:13px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:var(--dim);margin:0 0 6px}
p.s{margin:6px 0}.cite{color:var(--faint);font-size:12px}.skip{color:var(--faint);font-style:italic}
footer{border-top:1px solid var(--line);margin-top:28px;padding-top:10px;color:var(--faint);font-size:12px}
"""


def render_html(brief: dict[str, Any]) -> str:
    e = html.escape
    parts = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>Weekly brief {e(brief['week_label'])}</title>",
        f"<style>{CSS}</style></head><body><main>",
        '<a class="brand" href="/">INFRAATLAS</a>',
        f"<h1>Weekly brief: {e(brief['week_label'])}</h1>",
        f'<p class="sub">Built {e(brief["built"][:16].replace("T", " "))} UTC from the map\'s own data '
        "files, sentence by sentence from fixed templates. Every figure names its source and its "
        '"as of" date. <a href="latest.json">JSON</a></p>',
    ]
    for s in brief["sections"]:
        parts.append(f"<section><h2>{e(s['title'])}</h2>")
        if s["status"] == "skipped":
            parts.append(f'<p class="s skip">Skipped: {e(s["reason"])}.</p>')
        for n in s.get("notes", []):
            parts.append(f'<p class="s skip">{e(n[0].upper() + n[1:])}.</p>')
        for t in s["sentences"]:
            src = e(t["source"])
            link = f'<a href="{e(t["url"])}">{src}</a>' if t["url"] else src
            as_of = f", as of {e(t['as_of'])}" if t["as_of"] else ""
            parts.append(
                f'<p class="s">{e(t["text"])} <span class="cite">({link}{as_of})</span></p>'
            )
        parts.append("</section>")
    parts.append(
        "<footer>Written by scripts/weekly_brief.py with no language model. Weekly means are "
        "means of the 15-minute day-ahead prices; totals are sums of the rows named. "
        "Sources are listed in docs/DATA_SOURCES.md.</footer></main></body></html>"
    )
    return "\n".join(parts) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--local", action="store_true", help="read the bundled files only")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    reader = Reader(args.local)

    old: dict[str, Any] = {}
    old_path = args.out / "latest.json"
    if old_path.exists():
        try:
            old = json.loads(old_path.read_text(encoding="utf-8"))
        except ValueError:
            old = {}

    print("reading the day archive ...")
    days, base = load_days(reader)
    print(f"  {len(days)} days" + (f", {days[0]['date']} to {days[-1]['date']}" if days else ""))
    prices = reader.get(f"{ARCHIVE}/prices.json", DATA / "eu" / "prices.json")
    outages = reader.get(f"{SNAPSHOT}/outages.json", DATA / "eu" / "outages.json")
    queues = reader.get(None, DATA / "us" / "queues_live.json")
    us_plants = reader.get(None, DATA / "us" / "plants.json")
    eu_plants = reader.get(None, DATA / "eu" / "plants.json")

    week_to = days[-1]["date"] if days else ""
    # a second run in the same week compares with what the first one compared with
    prev = (
        old.get("carry", {})
        if old.get("week", [None, None])[1] != week_to
        else old.get("carry_previous", {})
    )

    s_prices, meta = price_section(days, base)
    s_out, c_out = outage_section(outages, prev)
    s_q, c_q = queue_section(queues, prev)
    s_cap, c_cap = capacity_section(us_plants, eu_plants, prev)
    sections = [
        s_prices,
        extremes_section(days, prices),
        records_section(days, base),
        s_out,
        s_q,
        s_cap,
    ]
    week = meta.get("week") or (
        [days[-WEEK]["date"], week_to] if len(days) >= WEEK else ["", week_to]
    )
    brief = {
        "title": "InfraAtlas weekly brief",
        "built": datetime.now(UTC).isoformat(timespec="seconds"),
        "week": week,
        "previous_week": meta.get("previous_week"),
        "week_label": f"{week[0]} to {week[1]}" if week[0] else "no full week in the archive",
        "method": (
            "Fixed templates over the app's data files, no language model. Weekly mean = mean of "
            "the 15-minute day-ahead prices of the seven days (zones with prices in at least "
            f"{round(MIN_COVERAGE * 100)} % of the slots of both weeks). Outages, queues and US "
            "capacity are compared with the previous brief's stored figures."
        ),
        "templates": TEMPLATES,
        "sections": [s.to_json() for s in sections],
        "means": meta.get("means", {}),
        "carry": {**c_out, **c_q, **c_cap},
        "carry_previous": prev,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "latest.json").write_text(
        json.dumps(brief, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (args.out / "latest.html").write_text(render_html(brief), encoding="utf-8")
    for s in sections:
        state = f"skipped ({s.skipped})" if s.skipped else f"{len(s.sentences)} sentences"
        print(f"  {s.id}: {state}")
    print(f"wrote {args.out / 'latest.json'} and latest.html, week {brief['week_label']}")


if __name__ == "__main__":
    main()
