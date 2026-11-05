"""Every data request, ready for the owner to send: docs/data-requests.md (brief 30 Track 2.4).

Collects the request texts the registries hold - `request` in scripts/wave*_sources.yaml and
"Data request: ..." in the notes of data/coverage.yaml - plus the hand-written ones in
`HAND` below, grouped by publisher, each with the dataset, why it is blocked and the licence
question to ask. The owner sends them; nothing here is sent.

    uv run python scripts/data_requests.py
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "data-requests.md"
LICENCE_Q = (
    "May we redistribute the data, and show it in a commercial product, under an open licence "
    "(CC BY 4.0 or equivalent) with attribution?"
)
# requests that live in no registry (brief 30 findings); publisher, dataset, why, request
HAND = [
    (
        "Eurostat (GISCO)",
        "Administrative units: countries, NUTS 2024 and LAU outlines",
        "The GISCO terms say the data 'will not be used for commercial purposes' "
        "(docs/owner-questions.md, question 1).",
        "Eurostat GISCO, permission to use the countries, NUTS and LAU outlines in a commercial "
        "map product with attribution (© EuroGeographics), or the licence under which that is "
        "possible.",
    ),
    (
        "Elia",
        "Capacity of the grid for new decentralised generation (Belgium)",
        "elia.be keeps scripts and an automated browser on Cloudflare's check (2026-10-19, "
        "2026-11-03).",
        "Elia, the capacity file for new decentralised generation as a direct download (or on "
        "the Elia open-data portal) under an open licence.",
    ),
    (
        "JRC (European Drought Observatory)",
        "Combined Drought Indicator (CDI)",
        "The NetCDF's attributes say 'non-commercial purposes'; copyright.txt and the JRC catalogue "
        "say CC BY 4.0 (2026-11-05).",
        "JRC EDO, which licence applies to the Combined Drought Indicator files, and confirmation "
        "that commercial reuse under CC BY 4.0 is allowed.",
    ),
    (
        "The Crown Estate",
        "Offshore wind sites (England, Wales, Northern Ireland)",
        "The open data licence is revocable and bars reuse on a similar website or portal.",
        "The Crown Estate, permission to show the offshore wind site layers in the InfraAtlas map "
        "with attribution.",
    ),
    (
        "IRENA",
        "Renewable Power Generation Costs, data file",
        "irena.org answers automated browsers with its Azure WAF page (2026-11-03).",
        "IRENA, a direct download URL for the Renewable Power Generation Costs data file and its "
        "licence for reuse with attribution.",
    ),
]


def publisher_of(text: str) -> str:
    """The publisher a request text names first ('Destatis, an open ...' -> 'Destatis')."""
    return re.split(r"[,:;]", text.strip(), maxsplit=1)[0].strip()[:80] or "Other"


def collect() -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = defaultdict(list)
    seen: set[str] = set()

    def add(pub: str, item: dict[str, str]) -> None:
        key = re.sub(r"\W+", " ", item["request"].lower()).strip()
        if key not in seen:
            seen.add(key)
            out[pub].append(item)

    for reg in sorted((ROOT / "scripts").glob("wave*_sources.yaml")):
        for s in yaml.safe_load(reg.read_text(encoding="utf-8")).get("sources") or []:
            if s.get("request"):
                add(
                    publisher_of(s["request"]),
                    {
                        "dataset": s.get("title") or s["id"],
                        "why": str(s.get("why") or ""),
                        "request": s["request"],
                        "where": f"{reg.relative_to(ROOT)} `{s['id']}`",
                    },
                )
    cov = yaml.safe_load((ROOT / "data" / "coverage.yaml").read_text(encoding="utf-8"))
    for fam, f in (cov.get("families") or {}).items():
        for cc, c in (f.get("cells") or {}).items():
            note = str((c or {}).get("note") or "")
            m = re.search(r"Data request:\s*(.+)$", note, re.S)
            if not m:
                continue
            req = " ".join(m.group(1).split())
            add(
                publisher_of(req),
                {
                    "dataset": f"{f.get('name', fam)} ({cc})",
                    "why": " ".join(note[: m.start()].split())[:300],
                    "request": req,
                    "where": f"data/coverage.yaml `{fam}.{cc}`",
                },
            )
    for pub, dataset, why, req in HAND:
        add(
            pub,
            {"dataset": dataset, "why": why, "request": req, "where": "docs/owner-questions.md"},
        )
    return out


def main() -> None:
    reqs = collect()
    n = sum(len(v) for v in reqs.values())
    lines = [
        "# Data requests",
        "",
        "Generated by `scripts/data_requests.py` from the registries (`request` fields in",
        '`scripts/wave*_sources.yaml`, "Data request:" in `data/coverage.yaml` notes) and the',
        "hand-written ones in the script. Ready for the owner to send; nothing is sent by a",
        "session. Each request should also ask the licence question:",
        "",
        f"> {LICENCE_Q}",
        "",
        f"{n} requests to {len(reqs)} publishers.",
        "",
    ]
    keys = {p: v for p, v in reqs.items() if p.lower().startswith("set ")}
    for pub in sorted((p for p in reqs if p not in keys), key=str.lower):
        lines += [f"## {pub}", ""]
        for r in reqs[pub]:
            lines.append(f"- **{r['dataset']}** ({r['where']})")
            if r["why"]:
                lines.append(f"  - Why: {r['why']}")
            lines.append(f"  - Request: {r['request']}")
        lines.append("")
    if keys:
        lines += ["## Keys to set (not requests: the owner adds them as repo secrets)", ""]
        for pub, items in sorted(keys.items()):
            lines += [f"- {pub}: {', '.join(r['dataset'] for r in items)}"]
        lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {n} requests, {len(reqs)} publishers")


if __name__ == "__main__":
    main()
