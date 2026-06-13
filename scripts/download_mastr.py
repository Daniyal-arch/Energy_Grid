"""Resumable, progress-reporting download of the full MaStR dataset from the Zenodo mirror.

The official marktstammdatenregister.de bulk server is throttled to ~6 KB/s (unusable).
The open-mastr team publishes a processed snapshot on Zenodo that serves at ~340 KB/s.
We pull the FULL boxed dataset (all technologies, all of Germany) — one zip of CSVs.

Run:   uv run python scripts/download_mastr.py
Resumes automatically if interrupted (HTTP Range). Prints MB / % / rate / ETA.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx

# Boxed full open-mastr snapshot 2025-02-09 (all technologies, ~1.4 GB single zip).
URL = "https://zenodo.org/records/14783581/files/bnetza_open_mastr_2025-02-09.zip?download=1"
DEST = Path(__file__).resolve().parent.parent / "data" / "bnetza_open_mastr_2025-02-09.zip"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
CHUNK = 1024 * 1024  # 1 MiB


def _total_size(client: httpx.Client) -> int | None:
    r = client.head(URL, headers=UA, follow_redirects=True, timeout=60)
    cl = r.headers.get("content-length")
    return int(cl) if cl else None


def main() -> int:
    DEST.parent.mkdir(parents=True, exist_ok=True)
    already = DEST.stat().st_size if DEST.exists() else 0

    with httpx.Client(follow_redirects=True) as client:
        total = _total_size(client)
        if total and already >= total:
            print(f"Already complete: {DEST} ({already / 1024 / 1024:.0f} MB)")
            return 0

        headers = dict(UA)
        mode = "wb"
        if already:
            headers["Range"] = f"bytes={already}-"
            mode = "ab"
            print(f"Resuming from {already / 1024 / 1024:.0f} MB")

        t0 = time.perf_counter()
        got = already
        last_report = 0.0
        with (
            client.stream("GET", URL, headers=headers, timeout=httpx.Timeout(300, read=120)) as r,
            open(DEST, mode) as f,
        ):
            if r.status_code not in (200, 206):
                print(f"HTTP {r.status_code}: {r.text[:200]}")
                return 1
            for chunk in r.iter_bytes(chunk_size=CHUNK):
                f.write(chunk)
                got += len(chunk)
                now = time.perf_counter()
                if now - last_report >= 5:
                    last_report = now
                    elapsed = now - t0
                    rate = (got - already) / 1024 / elapsed if elapsed else 0  # KB/s this session
                    mb = got / 1024 / 1024
                    if total:
                        pct = 100 * got / total
                        eta = (total - got) / 1024 / rate if rate else 0
                        print(
                            f"  {mb:.0f}/{total / 1024 / 1024:.0f} MB ({pct:.1f}%) "
                            f"{rate:.0f} KB/s  ETA {eta / 60:.0f} min",
                            flush=True,
                        )
                    else:
                        print(f"  {mb:.0f} MB  {rate:.0f} KB/s", flush=True)

    final = DEST.stat().st_size
    print(f"DONE: {DEST} ({final / 1024 / 1024:.0f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
