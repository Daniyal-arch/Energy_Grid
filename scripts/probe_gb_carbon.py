"""Probe the NESO Carbon Intensity API (api.carbonintensity.org.uk, no key).

Prints for each endpoint the fields, the number of periods and the newest period, and how far
behind the newest *actual* national value is (the update cadence); then the licence named on
the API's home page.

    uv run python scripts/probe_gb_carbon.py
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

import httpx

API = "https://api.carbonintensity.org.uk"


def main() -> None:
    now = datetime.now(UTC)
    stamp = now.strftime("%Y-%m-%dT%H:%MZ")
    with httpx.Client(timeout=30, headers={"Accept": "application/json"}) as c:
        for path in (
            "/intensity",
            f"/intensity/{stamp}/pt24h",
            f"/intensity/{stamp}/fw48h",
            "/generation",
            "/regional",
            "/intensity/factors",
        ):
            r = c.get(API + path)
            data = r.json()["data"]
            rows = data if isinstance(data, list) else [data]
            first = rows[0]
            print(
                f"{path}: HTTP {r.status_code}, {len(r.content):,} bytes, {len(rows)} period(s); "
                f"keys {sorted(first)}; first {first.get('from')} .. last {rows[-1].get('to')}"
            )
            if path.endswith("pt24h"):
                actual = [p for p in rows if p["intensity"].get("actual") is not None]
                newest = actual[-1]["to"] if actual else None
                print(
                    f"  {len(actual)} of {len(rows)} periods have an actual value; newest actual "
                    f"ends {newest} ({now.strftime('%H:%MZ')} now)"
                )
            if path == "/regional":
                regs = first["regions"]
                print(f"  {len(regs)} regions: " + ", ".join(x["shortname"] for x in regs))
                print(
                    f"  region keys {sorted(regs[0])}, intensity keys {sorted(regs[0]['intensity'])}"
                )
            if path == "/generation":
                print("  mix:", {m["fuel"]: m["perc"] for m in first["generationmix"]})
        home = c.get("https://carbonintensity.org.uk/").text
        lic = re.findall(r"creativecommons\.org/licenses/[a-z-]+/[0-9.]+", home)
        print("licence links on carbonintensity.org.uk:", sorted(set(lic)))
        old = c.get(f"{API}/intensity/date/{(now - timedelta(days=400)).date().isoformat()}")
        print(
            f"history: a day 400 days back answers HTTP {old.status_code}, "
            f"{len(old.json().get('data', []))} periods"
        )


if __name__ == "__main__":
    main()
