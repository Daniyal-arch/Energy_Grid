"""Probe Grid-India (POSOCO) and its national dashboards: are they reachable?

grid-india.in, report.grid-india.in, posoco.in, vidyutpravah.in and meritindia.in.
From GitHub runners (brief 17) and from cloud sessions the hosts reset the connection
or answer 503, so nothing can be fetched in Actions.

    uv run python scripts/probe_grid_india.py
"""

from __future__ import annotations

import httpx

URLS = [
    "https://grid-india.in/",
    "https://report.grid-india.in/",
    "https://posoco.in/",
    "https://vidyutpravah.in/",
    "http://vidyutpravah.in/",
    "https://meritindia.in/",
]


def main() -> None:
    with httpx.Client(
        timeout=30, follow_redirects=True, headers={"User-Agent": "Europe-InfraAtlas probe"}
    ) as c:
        for url in URLS:
            try:
                r = c.get(url)
                print(f"{url}: HTTP {r.status_code} {len(r.content)} bytes")
            except httpx.HTTPError as err:
                print(f"{url}: {err.__class__.__name__} {err}")


if __name__ == "__main__":
    main()
