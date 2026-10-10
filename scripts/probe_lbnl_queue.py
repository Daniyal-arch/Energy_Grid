"""Probe LBNL's "Queued Up" interconnection queue data file before the US queue layer.

1. The newest data file: emp.lbl.gov answers Cloudflare's block page (HTTP 403) to this
   machine, eta-publications.lbl.gov's research-area page and its files answer; the file
   links are named lbnl_ix_queue_data_file_thru<YEAR>.xlsx
2. Sheets, the cover text (licence, citation), the codebook
3. The project-level sheet: columns, statuses, types, states, regions
4. Active capacity by type, for the check against the report's headline figure
   (2026 edition: ~1,312 GW of generation and ~749 GW of storage active at the end of 2025)

  uv run python scripts/probe_lbnl_queue.py [--file path.xlsx]
"""

from __future__ import annotations

import argparse
import re
import tempfile
from collections import Counter
from pathlib import Path

import httpx
from openpyxl import load_workbook

PAGE = "https://eta-publications.lbl.gov/research-areas/queued-characteristics-power-plants"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Europe-InfraAtlas/0.3"}


def newest_link(html: str) -> str:
    links = sorted(
        set(re.findall(r'href="([^"]*ix_queue_data_file_thru(\d{4})[^"]*\.xlsx)"', html)),
        key=lambda x: x[1],
    )
    print(f"data files: {[x[0] for x in links]}")
    return str(httpx.URL(PAGE).join(links[-1][0]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path)
    args = parser.parse_args()
    path = args.file
    if not path:
        with httpx.Client(timeout=180, follow_redirects=True, headers=UA) as c:
            r = c.get(PAGE)
            print(f"{PAGE}: HTTP {r.status_code}")
            url = newest_link(r.text)
            r = c.get(url)
            r.raise_for_status()
            path = Path(tempfile.mkdtemp()) / url.rsplit("/", 1)[1]
            path.write_bytes(r.content)
            print(
                f"newest: {url} ({len(r.content) / 1e6:.1f} MB, Last-Modified {r.headers.get('last-modified')})"
            )
    wb = load_workbook(path, read_only=True, data_only=True)
    print(f"sheets ({len(wb.sheetnames)}): {wb.sheetnames}")
    for name in wb.sheetnames[:3]:
        rows = list(wb[name].iter_rows(values_only=True, max_row=40))
        text = [" | ".join(str(v) for v in r if v not in (None, "")) for r in rows]
        print(f"\n[{name}] first rows:")
        for t in text:
            if t:
                print(f"  {t[:300]}")
    # the project-level sheet: the one with the most rows and a queue status column
    best = None
    for name in wb.sheetnames:
        ws = wb[name]
        if (ws.max_row or 0) > 5000:
            best = name if best is None or ws.max_row > wb[best].max_row else best
    print(f"\nproject sheet: {best} ({wb[best].max_row:,} rows)")
    rows = list(wb[best].iter_rows(values_only=True))
    h = next(i for i, r in enumerate(rows[:20]) if r and sum(isinstance(v, str) for v in r) > 10)
    head = [str(v).strip() if v is not None else "" for v in rows[h]]
    data = [r for r in rows[h + 1 :] if r and any(v not in (None, "") for v in r)]
    print(f"header on row {h + 1}: {head}")
    print(f"{len(data):,} projects")
    col = {c: i for i, c in enumerate(head) if c}
    for c in head:
        if not c:
            continue
        vals = Counter(r[col[c]] for r in data)
        if len(vals) <= 60:
            print(f"  {c}: {vals.most_common(25)}")
        else:
            print(f"  {c}: {len(vals):,} distinct, e.g. {[v for v, _ in vals.most_common(4)]}")
    print(f"\nfirst row: {dict(zip(head, data[0], strict=False))}")
    status = next(c for c in head if c.lower().startswith("q_status"))
    active = [r for r in data if str(r[col[status]]).lower() == "active"]
    print(f"\nactive projects: {len(active):,}")
    mw_cols = [c for c in head if c.lower().startswith("mw")]
    type_cols = [c for c in head if c.lower().startswith("type")]
    print(f"MW columns {mw_cols}, type columns {type_cols}")

    def mw(v: object) -> float:
        return float(v) if isinstance(v, (int, float)) else 0.0

    for c in mw_cols:
        print(f"  active sum {c}: {sum(mw(r[col[c]]) for r in active) / 1000:,.1f} GW")
    for t, m in zip(type_cols, mw_cols, strict=False):
        by = Counter()
        for r in active:
            by[r[col[t]]] += mw(r[col[m]])
        print(f"  active {m} by {t}: {[(k, round(v / 1000, 1)) for k, v in by.most_common(15)]}")


if __name__ == "__main__":
    main()
