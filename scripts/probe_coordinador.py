"""Probe Coordinador Eléctrico Nacional (Chile): is real generation open without a key?

The SIP public API (sipub.api.coordinador.cl) needs a user_key issued on registration
(portal.api.coordinador.cl); without it it answers 403 "Authentication parameters
missing". The website's "operación real" charts are Qlik Sense mashups
(qap-prd.coordinador.cl), not a data API. This probe sends no key.

    uv run python scripts/probe_coordinador.py
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx

DAY = (datetime.now(UTC) - timedelta(days=1)).date().isoformat()
URLS = {
    "sip v3 generacion-real": "https://sipub.api.coordinador.cl/generacion-real/v3/findByDate"
    f"?startDate={DAY}&endDate={DAY}",
    "sip v1": "https://sipubv1.api.coordinador.cl/api/v1/",
    "sipub v1 recursos": "https://sipub.coordinador.cl/api/v1/recursos/"
    "generacion_centrales_tecnologia_horario",
    "robots.txt": "https://www.coordinador.cl/robots.txt",
}


def main() -> None:
    with httpx.Client(timeout=60, headers={"User-Agent": "Europe-InfraAtlas probe"}) as c:
        for name, url in URLS.items():
            try:
                r = c.get(url)
            except httpx.HTTPError as err:
                print(f"{name}: {err.__class__.__name__} {err}")
                continue
            text = r.text
            if name == "robots.txt":
                text = next(ln for ln in text.splitlines() if ln.startswith("Content-Signal"))
            print(f"{name}: HTTP {r.status_code}  {text[:160]!r}")


if __name__ == "__main__":
    main()
