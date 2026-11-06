"""Probe EPİAŞ transparency platform (Turkey): does real-time generation need a login?

Since the 2024 platform the electricity-service API asks for a TGT (ticket-granting
ticket) from an account (EPIAS_USERNAME / EPIAS_PASSWORD, PLAN.md). Without one it
answers 401 AUTH002. Prints the status and error for two endpoints.

    uv run python scripts/probe_epias.py
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

BASE = "https://seffaflik.epias.com.tr/electricity-service/v1"
ENDPOINTS = ["generation/data/realtime-generation", "consumption/data/realtime-consumption"]


def main() -> None:
    day = datetime.now(UTC).date().isoformat()
    body = {"startDate": f"{day}T00:00:00+03:00", "endDate": f"{day}T23:00:00+03:00"}
    with httpx.Client(timeout=60, headers={"User-Agent": "Europe-InfraAtlas probe"}) as c:
        for path in ENDPOINTS:
            r = c.post(f"{BASE}/{path}", json=body)
            print(f"{path}: HTTP {r.status_code}  {r.text[:240]!r}")


if __name__ == "__main__":
    main()
