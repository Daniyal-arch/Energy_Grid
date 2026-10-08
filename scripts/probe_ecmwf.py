"""Probe ECMWF open data (IFS 0.25°, no key): are wind at 100 m and surface solar
radiation in the open catalogue, how big is one field, and does it decode?

Only the needed fields are fetched, with HTTP range requests from the run's .index
(one JSON line per field with its byte offset and length)."""

from __future__ import annotations

import json

import httpx

BASE = "https://data.ecmwf.int/forecasts"
WANT = {"100u", "100v", "ssrd"}


def newest_run(client: httpx.Client) -> tuple[str, str]:
    listing = client.get(f"{BASE}/").text
    days = sorted(
        {p.split("/")[2] for p in __import__("re").findall(r'href="(/forecasts/\d{8}/)"', listing)}
    )
    for day in reversed(days):
        for run in ("18", "12", "06", "00"):
            url = f"{BASE}/{day}/{run}z/ifs/0p25/oper/{day}{run}0000-0h-oper-fc.index"
            if client.head(url).status_code == 200:
                return day, run
    raise SystemExit("no run found")


def main() -> None:
    import eccodes  # noqa: PLC0415 (only the probe needs it)

    with httpx.Client(timeout=60) as client:
        day, run = newest_run(client)
        print(f"newest run: {day} {run}z")
        for step in (0, 3, 6):
            stem = f"{BASE}/{day}/{run}z/ifs/0p25/oper/{day}{run}0000-{step}h-oper-fc"
            lines = [
                json.loads(x) for x in client.get(f"{stem}.index").text.splitlines() if x.strip()
            ]
            params = sorted({x["param"] for x in lines})
            hits = [x for x in lines if x["param"] in WANT]
            print(
                f"step {step}h: {len(lines)} fields, params incl. {[p for p in params if p in WANT]} ({len(params)} params)"
            )
            for h in hits:
                print(
                    f"   {h['param']}: levtype {h.get('levtype')}, {h['_length'] / 1e6:.2f} MB at {h['_offset']}"
                )
            if step == 3:
                for h in hits:
                    r = client.get(
                        f"{stem}.grib2",
                        headers={
                            "Range": f"bytes={h['_offset']}-{h['_offset'] + h['_length'] - 1}"
                        },
                    )
                    gid = eccodes.codes_new_from_message(r.content)
                    ni, nj = eccodes.codes_get(gid, "Ni"), eccodes.codes_get(gid, "Nj")
                    vals = eccodes.codes_get_values(gid)
                    print(
                        f"   decoded {h['param']}: {ni}x{nj}, units {eccodes.codes_get(gid, 'units')}, "
                        f"first lat {eccodes.codes_get(gid, 'latitudeOfFirstGridPointInDegrees')}, "
                        f"first lon {eccodes.codes_get(gid, 'longitudeOfFirstGridPointInDegrees')}, "
                        f"min {vals.min():.1f} max {vals.max():.1f}"
                    )
                    eccodes.codes_release(gid)


if __name__ == "__main__":
    main()
