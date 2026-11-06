"""Probe AESO's Current Supply Demand report (Alberta, public ETS page, no key).

The ETS report servlet answers over plain HTTP (its HTTPS endpoint fails the TLS
handshake). The AESO API gateway (apimgw.aeso.ca) needs a key; this page does not.
Prints status, the section headers, the summary rows and one asset row.

    uv run python scripts/probe_aeso.py
"""

from __future__ import annotations

import re

import httpx

URL = "http://ets.aeso.ca/ets_web/ip/Market/Reports/CSDReportServlet"
LEGAL = "https://www.aeso.ca/legal/"


def text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def main() -> None:
    with httpx.Client(timeout=60, headers={"User-Agent": "Europe-InfraAtlas probe"}) as c:
        r = c.get(URL)
        print(f"CSD: HTTP {r.status_code} {r.headers.get('content-type')} {len(r.content)} bytes")
        body = r.text
        print("updated:", re.search(r"Last Update\s*:\s*([^<]+)", body).group(1).strip())
        print(
            "sections:", [text(h) for h in re.findall(r"<TH COLSPAN[^>]*>(.*?)</TH>", body, re.I)]
        )
        rows = [
            [text(c) for c in re.findall(r"<TD[^>]*>(.*?)</TD>", tr, re.I | re.S)]
            for tr in re.findall(r"<TR>(<TD>.*?)</TR>", body, re.I | re.S)
        ]
        print("first rows:", rows[:12])
        print("sample asset:", next(r for r in rows if len(r) == 4 and "(" in r[0]))
        legal = text(c.get(LEGAL).text)
        i = legal.find("All material on this Web site")
        print("terms:", legal[i : i + 330])


if __name__ == "__main__":
    main()
