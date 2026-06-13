"""Probe: is the MaStR download server reachable, and how fast is it?

Run with: uv run python scripts/probe_mastr_server.py
"""

import re
import time

import httpx

UA = {"User-Agent": "Mozilla/5.0"}


def main() -> None:
    t0 = time.perf_counter()
    try:
        r = httpx.get(
            "https://www.marktstammdatenregister.de/MaStR/Datendownload",
            timeout=20,
            headers=UA,
            follow_redirects=True,
        )
        print(f"download page: HTTP {r.status_code} in {time.perf_counter() - t0:.1f}s")
        links = re.findall(r"https://download\.marktstammdatenregister\.de/[^\"\s]+\.zip", r.text)
        print(f"{len(links)} export links found; newest:", links[:2])
    except Exception as e:  # noqa: BLE001 — probe script
        print("download page FAILED:", type(e).__name__, e)
        return

    if not links:
        print("no links found — page structure may have changed")
        return

    url = links[0]
    t0 = time.perf_counter()
    try:
        r = httpx.get(url, headers={**UA, "Range": "bytes=0-1048575"}, timeout=30)
        dt = time.perf_counter() - t0
        kb = len(r.content) / 1024
        print(f"ranged read: HTTP {r.status_code}, {kb:.0f} KB in {dt:.1f}s = {kb / dt:.0f} KB/s")
        print(
            "accept-ranges:",
            r.headers.get("accept-ranges"),
            "| size:",
            r.headers.get("content-range"),
        )
    except Exception as e:  # noqa: BLE001
        print("ranged read FAILED:", type(e).__name__, e)


if __name__ == "__main__":
    main()
