"""Probe IRENA's statistics API (IRENASTAT, PxWeb, no key): the dimensions of the country
table and one query for a few countries, technologies and years."""

from __future__ import annotations

import json
import ssl
from pathlib import Path

import certifi
import httpx

TABLE = "https://pxweb.irena.org/api/v1/en/IRENASTAT/Power%20Capacity%20and%20Generation/Country_ELECSTAT_2026_H2_PX.px"


def tls() -> ssl.SSLContext:
    """IRENA's certificate chains to GoDaddy's 2025 root, which certifi lacks yet."""
    ctx = ssl.create_default_context(cafile=certifi.where())
    ctx.load_verify_locations(
        cafile=str(Path(__file__).parent / "certs" / "godaddy-tls-root-r1.pem")
    )
    return ctx


def main() -> None:
    with httpx.Client(timeout=120, verify=tls()) as client:
        meta = client.get(TABLE).json()
        print("title:", meta.get("title"))
        for v in meta["variables"]:
            print(
                f"- {v['code']}: {len(v['values'])} values; e.g. {list(zip(v['values'][:6], v['valueTexts'][:6], strict=False))}"
            )
        q = {
            "query": [
                {
                    "code": meta["variables"][0]["code"],
                    "selection": {"filter": "item", "values": ["DEU", "CHN", "PAK"]},
                },
                {
                    "code": meta["variables"][-1]["code"],
                    "selection": {"filter": "top", "values": ["2"]},
                },
            ],
            "response": {"format": "json-stat2"},
        }
        r = client.post(TABLE, json=q)
        print("query:", r.status_code, len(r.content), "bytes")
        if r.status_code == 200:
            d = r.json()
            print("dims:", d.get("id"), "sizes:", d.get("size"))
            print("first values:", d.get("value", [])[:40])
            print(
                json.dumps(
                    {k: d["dimension"][k]["category"].get("label") for k in d.get("id", [])},
                    ensure_ascii=False,
                )[:1500]
            )
        else:
            print(r.text[:500])


if __name__ == "__main__":
    main()
