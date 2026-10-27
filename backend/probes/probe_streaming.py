"""Probe: do /api/ask events arrive one by one (not all at the end)?

Runs against a URL (the Docker image, the Lambda Function URL, or the site's Worker), or starts
the app in-process on a free port. The fake model waits FAKE_STREAM_DELAY_S per streamed piece
so the timeline shows whether the transport buffers.

    docker run --rm -p 8080:8080 -e AGENT_MODEL=fake -e AGENT_MODEL_FAST=fake -e LAKE_DB= \
        -e FAKE_STREAM_DELAY_S=0.05 infraatlas-backend
    uv run python -m probes.probe_streaming --url http://localhost:8080
    uv run python -m probes.probe_streaming            # in-process uvicorn
"""

from __future__ import annotations

import argparse
import os
import socket
import threading
import time

import httpx


def serve() -> str:
    os.environ.setdefault("AGENT_MODEL", "fake")
    os.environ.setdefault("AGENT_MODEL_FAST", "fake")
    os.environ.setdefault("LAKE_DB", "")
    os.environ.setdefault("FAKE_STREAM_DELAY_S", "0.05")
    import uvicorn

    from app.main import app

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)
    return f"http://127.0.0.1:{port}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url")
    ap.add_argument("--question", default="Show the largest power plants in Germany on a map")
    ap.add_argument("--header", action="append", default=[], help="Name: value")
    a = ap.parse_args()
    url = a.url or serve()
    headers = dict(h.split(": ", 1) for h in a.header)
    t0 = time.perf_counter()
    times: list[tuple[float, str]] = []
    with httpx.stream(
        "POST", f"{url}/api/ask", json={"question": a.question}, headers=headers, timeout=120
    ) as r:
        print(
            "status",
            r.status_code,
            r.headers.get("content-type"),
            "trace",
            r.headers.get("x-trace-id"),
        )
        for line in r.iter_lines():
            if line.startswith("event: "):
                times.append((time.perf_counter() - t0, line[7:]))
    kinds: dict[str, int] = {}
    for _, k in times:
        kinds[k] = kinds.get(k, 0) + 1
    print("events:", kinds)
    for t, k in times[:4] + [(0, "...")] + times[-4:]:
        print(f"  {t:6.2f} s  {k}")
    first_text = next(t for t, k in times if k == "text")
    print(
        f"first event {times[0][0]:.2f} s, first text {first_text:.2f} s, last event {times[-1][0]:.2f} s"
    )
    spread = times[-1][0] - times[0][0]
    print(
        "STREAMED one by one"
        if spread > 0.5 and len({round(t, 1) for t, _ in times}) > 5
        else "BUFFERED (all at once)"
    )


if __name__ == "__main__":
    main()
