"""Probe the Global Solar Atlas and Global Wind Atlas downloads without downloading them
(HTTP range reads): sizes, dates, what the solar zip holds (its readme and style files), and
the wind GeoTIFF's header (size, tiles, overviews, data type, no-data value).

    uv run python scripts/probe_atlas.py
"""

from __future__ import annotations

import io
import re
import struct
import zipfile

import httpx

GSA_LIST = "https://api.globalsolaratlas.info/download/World"
GSA_FILE = "World_PVOUT_GISdata_LTAy_AvgDailyTotals_GlobalSolarAtlas-v2_GEOTIFF.zip"
GWA = "https://globalwindatlas.info/api/gis/global/wind-speed/100"
# globalwindatlas.info redirects to figshare.com, which answers a bot check (AWS WAF, HTTP 202);
# the same file through ndownloader.figshare.com answers
GWA_FIGSHARE = "https://ndownloader.figshare.com/files/{id}?private_link={link}"


class RangeFile(io.RawIOBase):
    """A remote file read by HTTP range requests; the redirect is followed on every read
    (the signed URLs behind both atlases expire within seconds to minutes)."""

    def __init__(self, client: httpx.Client, url: str, size: int) -> None:
        self.c, self.url, self.size, self.pos = client, url, size, 0

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, offset: int, whence: int = 0) -> int:
        base = {0: 0, 1: self.pos, 2: self.size}[whence]
        self.pos = base + offset
        return self.pos

    def read(self, n: int = -1) -> bytes:
        if n < 0:
            n = self.size - self.pos
        if n == 0:
            return b""
        r = self.c.get(self.url, headers={"Range": f"bytes={self.pos}-{self.pos + n - 1}"})
        self.pos += len(r.content)
        return r.content


def solar(c: httpx.Client) -> None:
    files = c.get(GSA_LIST).json()
    for f in files:
        if "PVOUT" in f["name"] and "GISdata" in f["name"]:
            print(f"  {f['name']}: {f['size'] / 1e6:,.0f} MB, {f['lastModified']}")
    size = next(f["size"] for f in files if f["name"] == GSA_FILE)
    z = zipfile.ZipFile(RangeFile(c, f"{GSA_LIST}/{GSA_FILE}", size))
    print(f"{GSA_FILE}:")
    for i in z.infolist():
        print(f"  {i.filename}: {i.file_size / 1e6:,.1f} MB")
    for i in z.infolist():
        if (
            re.search(r"\.(txt|qml|xml|sld|clr|md|lyr|lyrx)$", i.filename, re.I)
            and i.file_size < 200_000
        ):
            text = z.read(i.filename).decode("utf-8", "replace")
            if i.filename.endswith(".xml"):  # ISO 19139: the lines that say what the values are
                keep = re.findall(r"<gco:CharacterString>([^<]{12,})</gco:CharacterString>", text)
                text = "\n".join(k for k in keep if not k.startswith("http"))
            print(f"===== {i.filename}\n{text[:4000]}")


def tiff_header(head: bytes) -> None:
    """TIFF / BigTIFF first IFD: the tags that tell size, tiling, type and no-data."""
    order = "<" if head[:2] == b"II" else ">"
    big = struct.unpack(order + "H", head[2:4])[0] == 43
    names = {
        256: "width",
        257: "height",
        258: "bits",
        259: "compression",
        322: "tile_w",
        323: "tile_h",
        339: "sample_format",
        33550: "pixel_scale",
        33922: "tiepoint",
        42113: "nodata",
    }
    if big:
        off = struct.unpack(order + "Q", head[8:16])[0]
        n = struct.unpack(order + "Q", head[off : off + 8])[0]
        entry, start = 20, off + 8
    else:
        off = struct.unpack(order + "I", head[4:8])[0]
        n = struct.unpack(order + "H", head[off : off + 2])[0]
        entry, start = 12, off + 2
    print(f"  {'BigTIFF' if big else 'TIFF'}, first IFD at {off}, {n} tags")
    sizes = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 11: 4, 12: 8, 16: 8}
    fmt = {1: "B", 2: "s", 3: "H", 4: "I", 11: "f", 12: "d", 16: "Q"}
    for k in range(n):
        e = head[start + k * entry : start + (k + 1) * entry]
        tag, typ = struct.unpack(order + "HH", e[:4])
        count = struct.unpack(order + ("Q" if big else "I"), e[4:12] if big else e[4:8])[0]
        raw = e[12:20] if big else e[8:12]
        nbytes = sizes.get(typ, 1) * count
        if nbytes > len(raw):
            ptr = struct.unpack(order + ("Q" if big else "I"), raw)[0]
            raw = head[ptr : ptr + nbytes] if ptr + nbytes <= len(head) else b""
        if tag in names and raw:
            if typ == 2:
                val = raw[:count].decode(errors="replace").strip("\x00")
            else:
                val = struct.unpack(
                    order + fmt.get(typ, "B") * min(count, 8),
                    raw[: sizes.get(typ, 1) * min(count, 8)],
                )
            print(f"    {names[tag]}: {val}")


def wind(c: httpx.Client) -> None:
    r = c.get(GWA, follow_redirects=False)
    loc = r.headers.get("location", "")
    print(f"{GWA}: HTTP {r.status_code} -> {loc}")
    m = re.search(r"files/(\d+)\?private_link=(\w+)", loc)
    if not m:
        raise SystemExit("the wind atlas download has moved: look at globalwindatlas.info/download")
    fig = c.get(loc, headers={"Range": "bytes=0-0"})
    print(f"  figshare.com: HTTP {fig.status_code}, WAF {fig.headers.get('x-amzn-waf-action')}")
    url = GWA_FIGSHARE.format(id=m.group(1), link=m.group(2))
    head = c.get(url, headers={"Range": "bytes=0-1048575"})
    total = int(head.headers["content-range"].split("/")[1])
    print(
        f"  {url}: HTTP {head.status_code}, {total / 1e9:.2f} GB, {head.headers.get('content-disposition')}"
    )
    tiff_header(head.content)
    text = head.content[:65536].decode("latin-1")
    for key in ("LAYOUT=COG", "GDAL_STRUCTURAL_METADATA", "<GDALMetadata>"):
        if key in text:
            i = text.index(key)
            print(f"  {text[i : i + 200].split(' ')[0]!r}")


def licences(c: httpx.Client) -> None:
    """Both sites are JavaScript apps: the solar terms come from the atlas's CMS API, the wind
    licence from the app's own script."""
    cc = r"CC[ -]BY[ -][0-9.]+|Creative Commons Attribution [0-9.]+[^<,.]{0,30}"
    terms = c.get("https://api.globalsolaratlas.info/cms/terms-of-use", timeout=30).json()
    body = re.sub(r"<[^>]+>", " ", str(terms.get("data", {}).get("body", "")))
    print("Global Solar Atlas terms of use:", sorted(set(re.findall(cc, body))))
    page = c.get("https://globalwindatlas.info/en/about/license", timeout=30).text
    found: set[str] = set()
    for src in re.findall(r'src="([^"]+\.js)"', page):
        url = src if src.startswith("http") else "https://globalwindatlas.info/" + src.lstrip("./")
        try:
            found |= set(re.findall(cc, c.get(url, timeout=60).text))
        except httpx.HTTPError:
            continue
    print("Global Wind Atlas licence (app script):", sorted(found))


def main() -> None:
    with httpx.Client(timeout=120, follow_redirects=True) as c:
        print("== Global Solar Atlas")
        solar(c)
        print("== Global Wind Atlas")
        wind(c)
        licences(c)


if __name__ == "__main__":
    main()
