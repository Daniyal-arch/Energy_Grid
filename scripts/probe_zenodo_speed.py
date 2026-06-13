"""Probe: measure Zenodo solar-snapshot download throughput (alternative to throttled MaStR)."""

import time

import httpx

# open-mastr unboxed snapshot 2025-02-09, solar raw CSV (723 MB)
URL = "https://zenodo.org/records/14843222/files/bnetza_mastr_solar_raw.csv.zip?download=1"


def main() -> None:
    got = 0
    t0 = time.perf_counter()
    try:
        with httpx.stream(
            "GET",
            URL,
            headers={"User-Agent": "Mozilla/5.0"},
            follow_redirects=True,
            timeout=httpx.Timeout(180, connect=60, read=120),
        ) as r:
            print(f"HTTP {r.status_code}, content-length: {r.headers.get('content-length')}")
            for chunk in r.iter_bytes(chunk_size=65536):
                got += len(chunk)
                elapsed = time.perf_counter() - t0
                if got % (2 * 1024 * 1024) < 65536:
                    print(
                        f"  {got / 1024 / 1024:.1f} MB in {elapsed:.0f}s = {got / 1024 / elapsed:.0f} KB/s"
                    )
                if elapsed > 30 or got > 30 * 1024 * 1024:
                    break
    except Exception as e:  # noqa: BLE001 — probe script
        elapsed = time.perf_counter() - t0
        print(f"FAILED after {elapsed:.0f}s with {got / 1024:.0f} KB: {type(e).__name__} {e}")
        return
    elapsed = time.perf_counter() - t0
    print(f"RESULT: {got / 1024 / 1024:.1f} MB in {elapsed:.0f}s = {got / 1024 / elapsed:.0f} KB/s")


if __name__ == "__main__":
    main()
