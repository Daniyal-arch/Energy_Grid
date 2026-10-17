"""Probe the Marktstammdatenregister's bulk export without downloading it (HTTP range reads).

Prints the newest export's URL, size and date, the licence named on the download page, the
XML files inside the zip (summed per table), and the first record of the tables asked for.

    python scripts/probe_mastr.py [EinheitenWind.xml EinheitenSolar_1.xml ...]

Findings 2026-10-13: Gesamtdatenexport_20261013_26.2.zip, 3.23 GB, daily (Last-Modified
01:37 UTC); licence "Datenlizenz Deutschland – Namensnennung – Version 2.0" (dl-de/by-2-0);
~66 GB of UTF-16 XML inside: EinheitenSolar 66 files 23.2 GB, EinheitenStromSpeicher 29 files
9.2 GB, Netzanschlusspunkte 60 files 8.7 GB, Lokationen 69 files 5.0 GB, Marktakteure 58 files
4.0 GB, EinheitenVerbrennung 0.29 GB, EinheitenWind 0.21 GB, Katalogwerte (the codes' names).
One flat element per unit (`<EinheitWind>`: EinheitMastrNummer, Gemeindeschluessel,
Postleitzahl, Laengengrad/Breitengrad where public, Bruttoleistung/Nettonennleistung in kW,
Inbetriebnahmedatum, EinheitBetriebsstatus (code), Energietraeger (code), ...). Small units
(solar on houses) carry no coordinates, only postcode and municipality key.
"""

from __future__ import annotations

import io
import re
import sys
import zipfile
from collections import defaultdict

import httpx

PAGE = "https://www.marktstammdatenregister.de/MaStR/Datendownload"


class RangeFile(io.RawIOBase):
    """A remote file read by HTTP range requests (zipfile reads only the parts it needs)."""

    def __init__(self, client: httpx.Client, url: str) -> None:
        self.c, self.url = client, url
        self.size = int(client.head(url).headers["content-length"])
        self.pos = 0

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, offset: int, whence: int = 0) -> int:
        self.pos = (
            offset if whence == 0 else self.pos + offset if whence == 1 else self.size + offset
        )
        return self.pos

    def read(self, n: int = -1) -> bytes:
        if n < 0:
            n = self.size - self.pos
        if n == 0:
            return b""
        r = self.c.get(self.url, headers={"Range": f"bytes={self.pos}-{self.pos + n - 1}"})
        self.pos += len(r.content)
        return r.content


def newest_export(client: httpx.Client) -> str:
    html = client.get(PAGE).text
    url = re.search(
        r'https://download\.marktstammdatenregister\.de/Gesamtdatenexport_[^"]+\.zip', html
    )
    if not url:
        raise SystemExit("no export link on the download page: has it changed?")
    lic = sorted(set(re.findall(r"Datenlizenz Deutschland[^<\"]*|dl-de/[a-z0-9-]+", html)))
    print("licence on the page:", lic)
    return url.group(0)


def main() -> None:
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        url = newest_export(client)
        head = client.head(url).headers
        print(url, f"{int(head['content-length']) / 1e9:.2f} GB", head.get("last-modified"))
        z = zipfile.ZipFile(RangeFile(client, url))
        tables: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for i in z.infolist():
            name = re.sub(r"(_\d+)?\.xml$", "", i.filename)
            tables[name][0] += 1
            tables[name][1] += i.file_size
        for name, (n, size) in sorted(tables.items()):
            print(f"  {name}: {n} file(s), {size / 1e6:,.0f} MB")
        for name in sys.argv[1:]:
            with z.open(name) as f:
                raw = f.read(8000)
            text = raw.decode(
                "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8", "replace"
            )
            print(f"===== {name}\n" + text.replace("><", ">\n<")[:4000])


if __name__ == "__main__":
    main()
