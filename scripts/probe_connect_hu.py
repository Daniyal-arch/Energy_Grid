"""Probe Hungary's free grid capacity (brief 23, "room to connect"): MAVIR and the DSOs.

Hungarian DSOs must publish current and five-year free capacity per substation (Vet. Vhr.
8. § (7)); generation capacity is allocated by tender (11/2025. (IV. 10.) EM rendelet).

1. MAVIR "Hálózati csatlakozás": an xlsx "Csatlakozási pont kiépítésére alkalmas alállomások"
   (2030Q3) listing MAVIR and DSO substations with spare bays, the injection MVA by NAF/KÖF
   transformer and coordinates.
2. E.ON (EDE = E.ON Dél-dunántúli, EED = E.ON Észak-dunántúli, ELMŰ): one PDF each, free
   withdrawal (load) MVA per substation and voltage, current and in 5 years.
3. OPUS TITÁSZ: one PDF, free load MW per substation, current and 5-year.
4. MVM Démász and MVM Émász: one PDF each, free load MW (current and 5-year).
pdfplumber test per PDF: header, first rows, row count.

  uv run python scripts/probe_connect_hu.py
"""

from __future__ import annotations

import collections
import io
import re

import httpx
import openpyxl
import pdfplumber

c = httpx.Client(
    timeout=120, follow_redirects=True, headers={"User-Agent": "Europe-InfraAtlas/0.2 (probe)"}
)
MAVIR = "https://www.mavir.hu/web/mavir/halozati-csatlakozas"
PAGES = {
    "E.ON": "https://www.eon.hu/hu/lakossagi/ugyintezes/kiemelt-informaciok/szabad-kapacitas.html",
    "OPUS TITÁSZ": "https://www.opustitasz.hu/ugyfelek/halozati-szolgaltatas-es-termekek/alallomasok-szabad-kapacitasai",
    "MVM Démász": "https://mvmhalozat.hu/aram/oldalak/125383",
    "MVM Émász": "https://mvmemaszhalozat.hu/uzleti-partnerek/uzleti-ugyfelek-onkormanyzatok/elosztoi-szabad-kapacitasok",
}
# a data row: name ... then 2+ numbers at the end (decimal point or comma)
ROW = re.compile(r"^(?P<name>\D.*?)\s+(?P<nums>(?:\d+(?:[.,]\d+)?\s*(?:kV)?\s*){3,})$")


def links(page: str, pattern: str) -> list[str]:
    r = c.get(page)
    out = []
    for m in re.finditer(r"""<a[^>]+href=["']([^"']+)["'][^>]*>(.*?)</a>""", r.text, re.I | re.S):
        href = m.group(1).replace("&amp;", "&")
        text = re.sub(r"<[^>]+>|\s+", " ", m.group(2))
        if re.search(pattern, href + " " + text, re.I):
            base = re.match(r"https?://[^/]+", str(r.url)).group(0)  # type: ignore[union-attr]
            out.append(href if href.startswith("http") else base + href)
    print(f"   page HTTP {r.status_code}: {len(set(out))} file link(s)")
    return list(dict.fromkeys(out))


def pdf_test(url: str) -> None:
    r = c.get(url)
    print(
        f"-- {url}\n   HTTP {r.status_code}, {len(r.content)} bytes, "
        f"last-modified {r.headers.get('last-modified')}"
    )
    with pdfplumber.open(io.BytesIO(r.content)) as pdf:
        lines = [ln for pg in pdf.pages for ln in (pg.extract_text() or "").splitlines()]
        print(f"   pages {len(pdf.pages)}, created {pdf.metadata.get('CreationDate')}")
        print("   title:", lines[0], "|", lines[1] if len(lines) > 1 else "")
        tables = [t for pg in pdf.pages for t in pg.extract_tables()]
        header = next((t[0] for t in tables if t and len(t[0]) >= 4), None)
        if header:
            print("   table header:", [(x or "").replace("\n", " ") for x in header])
        rows = [m for ln in lines if (m := ROW.match(ln.strip()))]
        for m in rows[:2]:
            print("   row:", m.group("name"), "|", m.group("nums").split())
        print("   data rows (text lines name + numbers):", len(rows))


print(f"== 1. MAVIR {MAVIR}")
xl = [u for u in links(MAVIR, r"\.xlsx") if "llom" in u]
print("  ", xl)
r = c.get(xl[0])
print(
    "   HTTP", r.status_code, len(r.content), "bytes, last-modified", r.headers.get("last-modified")
)
wb = openpyxl.load_workbook(io.BytesIO(r.content), read_only=True, data_only=True)
ws = wb.worksheets[0]
rows = list(ws.iter_rows(values_only=True))
print("   sheets", wb.sheetnames)
print("   header:", rows[0])
print("   units: ", rows[1])
data = [x for x in rows[2:] if x[0] and x[2]]
for x in data[:2] + [y for y in data if y[6] is not None][:2]:
    print("   row:", x[:12])
print("   rows", len(data), "by operator", dict(collections.Counter(x[0] for x in data)))
print(
    "   with injection MVA:",
    sum(1 for x in data if x[6] is not None),
    "with coordinates:",
    sum(1 for x in data if isinstance(x[9], float)),
)

for n, (op, page) in enumerate(PAGES.items(), start=2):
    print(f"\n== {n}. {op} {page}")
    for u in links(page, r"\.pdf|attachments/4191[34]|downloadfile.*szabad|kapacit.*PDF"):
        if re.search(r"szabad|kapacit|41914|e902f961", u, re.I) and "rugalmas" not in u.lower():
            pdf_test(u)
