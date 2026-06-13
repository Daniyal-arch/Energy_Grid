"""Probe: measure actual MaStR download throughput with a patient streaming read."""

import time

import httpx

URL = "https://download.marktstammdatenregister.de/Gesamtdatenexport_20260612_26.1.zip"


def main() -> None:
    got = 0
    t0 = time.perf_counter()
    try:
        with httpx.stream(
            "GET",
            URL,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=httpx.Timeout(180, connect=60, read=120),
        ) as r:
            print(f"HTTP {r.status_code}, content-length: {r.headers.get('content-length')}")
            for chunk in r.iter_bytes(chunk_size=65536):
                got += len(chunk)
                elapsed = time.perf_counter() - t0
                if got % (512 * 1024) < 65536:
                    print(
                        f"  {got / 1024:.0f} KB in {elapsed:.0f}s = {got / 1024 / elapsed:.1f} KB/s"
                    )
                if elapsed > 150 or got > 5 * 1024 * 1024:
                    break
    except Exception as e:  # noqa: BLE001 — probe script
        elapsed = time.perf_counter() - t0
        print(f"FAILED after {elapsed:.0f}s with {got / 1024:.0f} KB: {type(e).__name__} {e}")
        return
    elapsed = time.perf_counter() - t0
    print(f"RESULT: {got / 1024:.0f} KB in {elapsed:.0f}s = {got / 1024 / elapsed:.1f} KB/s")


if __name__ == "__main__":
    main()
