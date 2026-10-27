"""Probe Croatia's free grid capacity (brief 23, "room to connect"): HOPS and HEP ODS.

1. HOPS "Informacije o mogućnosti priključenja": the page lists PDFs (yearly); the newest one
   (March 2024) has Tablica 2, a class per substation (TS/RP) for new generation:
   "/" 0 MW or no free bay, A <= 50 MW, B <= 100 MW, C > 100 MW. Two name/class column pairs
   per page. pdfplumber test: header and first rows, the class counts.
2. HEP ODS: no capacity file on hep.hr/ods; the ten-year distribution plan 2025-2034 (proposal of
   1 Aug 2025, on hera.hr, 14.6 MB) has Tablica 4.4 (national totals only) and Tablica 4.5
   (the 30 TS 110/x kV where new distributed generation cannot connect under n-1, with MW
   connected / in process). pdfplumber test on Tablica 4.5.

  uv run python scripts/probe_connect_hr.py
"""

from __future__ import annotations

import collections
import io
import re
from urllib.parse import quote

import httpx
import pdfplumber

c = httpx.Client(
    timeout=180, follow_redirects=True, headers={"User-Agent": "Europe-InfraAtlas/0.2 (probe)"}
)
HOPS = "https://www.hops.hr/informacije-o-mogucnosti-prikljucenja"
HEP_ODS = "https://www.hep.hr/ods/"
PLAN = "https://www.hera.hr/hr/docs/2025/Prijedlog_2025-08-01_2.pdf"
CLASSES = {"/", "A", "B", "C"}

print(f"== 1. HOPS {HOPS}")
r = c.get(HOPS)
print("HTTP", r.status_code)
pdfs = sorted(set(re.findall(r"""href=["']([^"']+\.pdf)["']""", r.text, re.I)))
for p in pdfs:
    print("  ", p)
newest = next(p for p in pdfs if "2024" in p)  # the dated files: 2022, 2024 (undated = 2022)
url = "https://www.hops.hr" + quote(newest)
r = c.get(url)
print("newest:", url, "HTTP", r.status_code, len(r.content), "bytes")
rows: list[tuple[str, str]] = []
with pdfplumber.open(io.BytesIO(r.content)) as pdf:
    print("pages", len(pdf.pages), "created", pdf.metadata.get("CreationDate"))
    print("title page:", (pdf.pages[0].extract_text() or "").replace("\n", " | "))
    for pg in pdf.pages:
        for t in pg.extract_tables():
            for row in t:
                cells = [(x or "").strip() for x in row]
                # two (name, class) pairs per row as printed
                for name, cls in zip(cells[0::2], cells[1::2], strict=False):
                    if cls in CLASSES and name and name != "TS/RP":
                        rows.append((name, cls))
print("header as printed: ['TS/RP', 'KATEGORIJA', 'TS/RP', 'KATEGORIJA']")
print("first rows:", rows[:6])
print(
    "substations extracted:", len(rows), "classes:", dict(collections.Counter(c for _, c in rows))
)
kv = [n for n, _ in rows if re.search(r"\d+ kV$", n)]
print("names carrying a voltage:", len(kv), kv[:5])

print(f"\n== 2. HEP ODS {HEP_ODS}")
r = c.get(HEP_ODS)
files = re.findall(r"""href=["']([^"']+\.(?:pdf|xlsx|csv))["']""", r.text, re.I)
print("HTTP", r.status_code, "files on the home page:", len(files))
print(f"ten-year plan {PLAN}")
r = c.get(PLAN)
print("HTTP", r.status_code, len(r.content), "bytes, last-modified", r.headers.get("last-modified"))
with pdfplumber.open(io.BytesIO(r.content)) as pdf:
    print(
        "pages", len(pdf.pages), "|", (pdf.pages[0].extract_text() or "")[:120].replace("\n", " ")
    )
    for i, pg in enumerate(pdf.pages):
        txt = pg.extract_text() or ""
        if "Tablica 4-5" not in txt and "Tablica 4.5 TS" not in txt[:300]:
            continue
        for t in pg.extract_tables():
            if not t or "nemogućnosti" not in (t[0][0] or ""):
                continue
            print(f"-- page {i + 1}: Tablica 4.5, {len(t)} rows")
            print("   header:", [(x or "").replace("\n", " ") for x in t[1]])
            print("   units: ", t[3])
            data = [row for row in t if row[0] and row[0].startswith("TS ")]
            for row in data[:3]:
                print("   row:", row)
            print("   substations:", len(data))
