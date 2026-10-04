"""Key moments of a built day, for the time-lapse captions (?day=).

Reads frontend/public/data/eu/day/<date>.json and adds "highlights": the moments a
viewer should notice, each computed from the day's own values (min/max over the
day's 15-min slots; shares are value / total of the same slot). The frontend only
words them; every number comes from here.

  load_min      EU load at its lowest            {gw}
  load_max      EU load at its highest           {gw}
  solar_peak    EU solar at its highest          {gw, pct: share of EU generation}
  wind_peak     EU wind at its highest           {gw}
  gas_peak      EU gas generation at its highest {gw}
  price_low     lowest zone price of the day     {zone, country, eur}
  price_high    highest zone price of the day    {zone, country, eur}
  flow_max      largest cross-border flow        {from, to, gw}
  greenest      highest renewable share at the solar peak {country, pct}

    uv run python scripts/day_highlights.py 2026-09-24
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

DAY_DIR = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu" / "day"


def _argmax(values: list, pick: str = "max") -> int | None:
    pairs = [(v, i) for i, v in enumerate(values) if v is not None]
    if not pairs:
        return None
    return (max(pairs) if pick == "max" else min(pairs))[1]


def highlights(day: dict) -> list[dict]:
    out: list[dict] = []
    eu = day.get("eu") or {}
    gen = eu.get("generation", {})
    slots = day["slots"]

    def eu_total(k: int) -> float:
        return sum(col[k] for col in gen.values() if col[k] is not None)

    load = eu.get("load", [])
    for kind, pick in (("load_min", "min"), ("load_max", "max")):
        k = _argmax(load, pick)
        if k is not None:
            out.append({"slot": k, "kind": kind, "gw": round(load[k] / 1000, 1)})

    for kind, group in (("solar_peak", "solar"), ("wind_peak", "wind"), ("gas_peak", "gas")):
        col = gen.get(group, [])
        k = _argmax(col)
        if k is None:
            continue
        item = {"slot": k, "kind": kind, "gw": round(col[k] / 1000, 1)}
        if group == "solar" and eu_total(k) > 0:
            item["pct"] = round(100 * col[k] / eu_total(k))
        out.append(item)

    prices = [
        (z["values"][k], k, zone, z["country"])
        for zone, z in day["prices"].items()
        for k in range(slots)
        if z["values"][k] is not None
    ]
    if prices:
        lo = min(prices)
        hi = max(prices)
        out.append(
            {
                "slot": lo[1],
                "kind": "price_low",
                "zone": lo[2],
                "country": lo[3],
                "eur": round(lo[0], 1),
            }
        )
        out.append(
            {
                "slot": hi[1],
                "kind": "price_high",
                "zone": hi[2],
                "country": hi[3],
                "eur": round(hi[0], 1),
            }
        )

    flows = [
        (abs(v), k, b["a"] if v > 0 else b["b"], b["b"] if v > 0 else b["a"])
        for b in day["borders"]
        for k, v in enumerate(b["values"])
        if v is not None
    ]
    if flows:
        mw, k, src, dst = max(flows)
        out.append(
            {"slot": k, "kind": "flow_max", "from": src, "to": dst, "gw": round(mw / 1000, 1)}
        )

    solar_peak = next((h["slot"] for h in out if h["kind"] == "solar_peak"), None)
    if solar_peak is not None:
        shares = [
            (c["renewable_share"][solar_peak], iso)
            for iso, c in day["countries"].items()
            if c["renewable_share"][solar_peak] is not None
        ]
        if shares:
            pct, iso = max(shares)
            out.append({"slot": solar_peak, "kind": "greenest", "country": iso, "pct": round(pct)})

    # one caption per moment: when two fall on the same slot, keep both but in a stable order
    return sorted(out, key=lambda h: (h["slot"], h["kind"]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("day", help="YYYY-MM-DD of a built day")
    args = parser.parse_args()
    path = DAY_DIR / f"{args.day}.json"
    day = json.loads(path.read_text(encoding="utf-8"))
    day["highlights"] = highlights(day)
    path.write_text(json.dumps(day, separators=(",", ":")), encoding="utf-8")
    for h in day["highlights"]:
        k = h["slot"]
        print(f"{k // 4:02d}:{(k % 4) * 15:02d}  {h}")


if __name__ == "__main__":
    main()
