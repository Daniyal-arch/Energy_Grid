"""Probe alternative MaStR access paths that avoid the throttled bulk download.

A) Zenodo mirror — retry with a browser-like UA, just check headers (HEAD/range).
B) ds.marktstammdatenregister.dev Datasette — can we run a filtered SQL query over
   HTTP and get only ground-mounted solar >=5 MW in BW+BY as JSON?
"""

import time

import httpx

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def probe_zenodo() -> None:
    url = "https://zenodo.org/records/14843222/files/bnetza_mastr_solar_raw.csv.zip?download=1"
    print("=== A) Zenodo solar snapshot (range read) ===")
    t0 = time.perf_counter()
    try:
        r = httpx.get(
            url,
            headers={**UA, "Range": "bytes=0-2097151"},
            follow_redirects=True,
            timeout=60,
        )
        dt = time.perf_counter() - t0
        kb = len(r.content) / 1024
        print(f"  HTTP {r.status_code}, {kb:.0f} KB in {dt:.1f}s = {kb / dt:.0f} KB/s")
        if r.status_code >= 400:
            print("  body:", r.text[:200])
    except Exception as e:  # noqa: BLE001
        print("  FAILED:", type(e).__name__, e)


def probe_datasette() -> None:
    print("\n=== B) ds.marktstammdatenregister.dev Datasette ===")
    base = "https://ds.marktstammdatenregister.dev/Marktstammdatenregister"
    # First: list tables/metadata
    try:
        r = httpx.get(base + ".json", headers=UA, timeout=30, follow_redirects=True)
        print(f"  db metadata: HTTP {r.status_code}")
        if r.status_code == 200:
            tables = r.json().get("tables") if isinstance(r.json(), dict) else None
            if isinstance(tables, dict):
                solar = [t for t in tables if "solar" in t.lower() or "einheit" in t.lower()]
                print("  solar/unit tables:", solar[:10])
    except Exception as e:  # noqa: BLE001
        print("  metadata FAILED:", type(e).__name__, e)

    # Second: try a filtered SQL query for our exact target (table name guessed)
    sql = (
        "select count(*) as n from EinheitenSolar "
        "where Bundesland in ('Bayern','Baden-Württemberg') "
        "and Nettonennleistung >= 5000 and Lage like '%Freifl%'"
    )
    try:
        r = httpx.get(
            base + ".json",
            params={"sql": sql, "_shape": "array"},
            headers=UA,
            timeout=60,
            follow_redirects=True,
        )
        print(f"  filtered query: HTTP {r.status_code}")
        print("  body:", r.text[:300])
    except Exception as e:  # noqa: BLE001
        print("  query FAILED:", type(e).__name__, e)


if __name__ == "__main__":
    probe_zenodo()
    probe_datasette()
