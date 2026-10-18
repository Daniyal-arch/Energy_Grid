"""Probe NREL's Alternative Fuels Data Center station API for public US EV charging stations.

NREL keys are api.data.gov keys: NREL_API_KEY (in Actions the repo secret EPA_API_KEY is passed
as NREL_API_KEY). developer.nrel.gov is now an alias of developer.nlr.gov; the first host that
answers is used. Prints: the host, whether the key is accepted (and its rate limit), the count of
public open ELEC stations and of DC fast ones, the fields of a station, the size and time of
`limit=all`, and the terms named on the API's documentation pages.

    NREL_API_KEY=... uv run python scripts/probe_nrel_afdc.py
"""

from __future__ import annotations

import os
import re
import time

import httpx

HOSTS = ["https://developer.nlr.gov", "https://developer.nrel.gov"]
PATH = "/api/alt-fuel-stations/v1.json"
QUERY = {"fuel_type": "ELEC", "status": "E", "access": "public", "country": "US"}


def main() -> None:
    key = os.environ["NREL_API_KEY"].strip()
    with httpx.Client(timeout=300, follow_redirects=True) as c:
        host = None
        for h in HOSTS:
            try:
                r = c.get(h + PATH, params={**QUERY, "limit": "1", "api_key": key})
            except httpx.HTTPError as err:
                print(f"{h}: {type(err).__name__}")
                continue
            print(
                f"{h}: HTTP {r.status_code}, rate limit {r.headers.get('x-ratelimit-limit')}, "
                f"remaining {r.headers.get('x-ratelimit-remaining')}"
            )
            if r.status_code == 200:
                host = host or h
            else:
                print("  answer:", r.text[:300])
        if host is None:
            raise SystemExit("no host accepted the key: ask the owner for an NREL key")
        d = (
            r.json()
            if r.status_code == 200
            else c.get(host + PATH, params={**QUERY, "limit": "1", "api_key": key}).json()
        )
        print("total public open ELEC stations:", d["total_results"])
        print("station_counts:", d.get("station_counts"))
        fast = c.get(
            host + PATH,
            params={**QUERY, "ev_charging_level": "dc_fast", "limit": "1", "api_key": key},
        ).json()
        print("of them with DC fast charging:", fast["total_results"])
        s = d["fuel_stations"][0]
        print(f"{len(s)} fields per station:", ", ".join(sorted(s)))
        t = time.time()
        full = c.get(host + PATH, params={**QUERY, "limit": "all", "api_key": key})
        rows = full.json()["fuel_stations"]
        print(
            f"limit=all: HTTP {full.status_code}, {len(full.content) / 1e6:.1f} MB, "
            f"{len(rows):,} stations, {time.time() - t:.0f} s"
        )
        dc = [x for x in rows if (x.get("ev_dc_fast_num") or 0) > 0]
        print(
            f"  DC fast stations {len(dc):,}, DC ports {sum(x['ev_dc_fast_num'] for x in dc):,}, "
            f"level 2 ports {sum(x.get('ev_level2_evse_num') or 0 for x in rows):,}, "
            f"without coordinates {sum(1 for x in rows if x.get('latitude') is None)}"
        )
        for url in (
            "https://developer.nrel.gov/docs/terms/",
            "https://afdc.energy.gov/data_download",
        ):
            try:
                text = c.get(url).text
            except httpx.HTTPError as err:
                print(f"{url}: {type(err).__name__}")
                continue
            words = re.sub(r"<[^>]+>", " ", text)
            hits = re.findall(
                r"[^.]{0,160}(?:public domain|licen[cs]e|attribut|free of charge|no restriction)[^.]{0,160}\.",
                words,
                re.I,
            )
            print(f"{url}:")
            for h in hits[:6]:
                print("   ", " ".join(h.split()))


if __name__ == "__main__":
    main()
