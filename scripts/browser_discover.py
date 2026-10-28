"""Find the data behind grid-capacity pages that answer scripts with a browser check (brief 26).

    xvfb-run -a python scripts/browser_discover.py [CODE ...] > discover.txt

For each operator page (PAGES), a real Chromium opens it the way a visitor does (brief 26,
access rule 2: a JavaScript check any visitor passes may be passed by a real browser; the
browser names the atlas in its user agent and nothing hides that it is automated). It
records, without downloading anything:

- the page title once the check has passed (or that it did not pass),
- robots.txt for the site; a path it disallows is not opened (rule 3),
- links whose text or address speaks of capacity or connection (in the local language),
- links to files (xlsx, csv, pdf, json, zip, kmz),
- the data requests the page makes (JSON, ArcGIS, GeoServer, WMS, Power BI, CartoVista).

It then follows up to FOLLOW of those capacity links one level deep and records the same.
The output decides which operators can be built (a data URL to add to scripts/browser_fetch.py
or to a builder) and which stay a data request. Workflow: browser-fetch.yml with
sources "discover" (or "discover BE-ELIA ...").
"""

from __future__ import annotations

import argparse
import json
import re
import time
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

# the atlas's name, appended to the browser's own user agent (rule 1)
NAME = "Europe-InfraAtlas/0.8 (+https://github.com/Daniyal-arch/Energy_Grid)"
FOLLOW = 6

PAGES: dict[str, list[str]] = {
    "BE-ELIA": ["https://www.elia.be/en/customers/connection/grid-hosting-capacity",
                "https://www.elia.be/en/infrastructure-and-projects/our-infrastructure/capacity-of-decentralized-production"],
    "BE-SIBELGA": ["https://www.sibelga.be/"],
    "LV-AST": ["https://www.ast.lv/"],
    "RO-TEL": ["https://www.transelectrica.ro/procesul-de-alocare-a-capacitatii-retelei-electrice"],
    "RO-DELGAZ": ["https://www.delgaz.ro/"],
    "RO-EDIS": ["https://www.e-distributie.com/"],
    "CY-TSO": ["https://www.tsoc.org.cy/"],
    "AL-OST": ["https://www.ost.al/"],
    "MD-MOLDELECTRICA": ["https://moldelectrica.md/"],
    "MD-PREMIER": ["https://premierenergy.md/"],
    "UA-UKRENERGO": ["https://ua.energy/"],
}  # fmt: skip

# capacity / connection words: en, nl, fr, lv, ro, el, sq, ro (MD), uk
KEYWORDS = re.compile(
    r"capacit|hosting|connection|aansluit|raccord|jaud|pieslēg|capacitat|racord|disponibil|"
    r"χωρητικ|σύνδεσ|kapacitet|lidhj|потужн|приєдн|потужност|ємн|map|harta|karte|χάρτ",
    re.I,
)
FILES = re.compile(r"\.(?:xlsx?|csv|pdf|json|zip|kmz|geojson)(?:\?|$)", re.I)
DATA = re.compile(
    r"FeatureServer|MapServer|arcgis|geoserver|wms|wfs|powerbi|cartovista|/api/|\.json|graphql",
    re.I,
)


def robots_for(ctx: object, url: str, cache: dict[str, RobotFileParser]) -> RobotFileParser:
    origin = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    if origin not in cache:
        rp = RobotFileParser()
        try:
            r = ctx.request.get(f"{origin}/robots.txt", timeout=30_000)  # type: ignore[attr-defined]
            text = r.text() if r.ok and "html" not in r.headers.get("content-type", "") else ""
        except Exception:  # noqa: BLE001 - no robots.txt: nothing disallowed
            text = ""
        rp.parse(text.splitlines())
        cache[origin] = rp
    return cache[origin]


def visit(page: object, url: str, requests: list[str]) -> dict:
    """Open one page, wait for the check, return what it shows and requests."""
    requests.clear()
    out: dict = {"url": url}
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=90_000)  # type: ignore[attr-defined]
    except Exception as e:  # noqa: BLE001 - every failure is a finding
        return out | {"error": f"{type(e).__name__}: {str(e)[:150]}"}
    for _ in range(30):  # the check reloads the page when it passes
        title = page.title()  # type: ignore[attr-defined]
        if not re.search(r"just a moment|attention required|checking", title, re.I):
            break
        time.sleep(2)
    try:
        page.wait_for_load_state("networkidle", timeout=30_000)  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 - pages with endless analytics never go idle
        pass
    title = page.title()  # type: ignore[attr-defined]
    out["title"] = title
    out["passed"] = not re.search(r"just a moment|attention required", title, re.I)
    links = page.eval_on_selector_all(  # type: ignore[attr-defined]
        "a[href]", "els => els.map(a => [a.href, (a.innerText || '').trim().slice(0, 80)])"
    )
    out["capacity_links"] = sorted(
        {f"{t} -> {h}" for h, t in links if KEYWORDS.search(t) or KEYWORDS.search(h)}
    )[:40]
    out["file_links"] = sorted({h for h, _ in links if FILES.search(h)})[:40]
    out["data_requests"] = sorted({r for r in requests if DATA.search(r)})[:40]
    out["_follow"] = [h for h, t in links if (KEYWORDS.search(t) or KEYWORDS.search(h))
                      and urlparse(h).netloc == urlparse(url).netloc]  # fmt: skip
    return out


def main() -> None:
    from playwright.sync_api import sync_playwright

    ap = argparse.ArgumentParser()
    ap.add_argument("codes", nargs="*", default=list(PAGES))
    args = ap.parse_args()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ua = browser.new_page().evaluate("navigator.userAgent")
        ctx = browser.new_context(user_agent=f"{ua} {NAME}", locale="en-GB")
        page = ctx.new_page()
        requests: list[str] = []
        page.on("request", lambda r: requests.append(r.url))
        robots: dict[str, RobotFileParser] = {}
        for code in args.codes:
            for url in PAGES[code]:
                if not robots_for(ctx, url, robots).can_fetch("*", url):
                    print(
                        json.dumps({"code": code, "url": url, "robots": "disallowed"}), flush=True
                    )
                    continue
                first = visit(page, url, requests)
                follow = first.pop("_follow", [])
                print(json.dumps({"code": code, **first}, ensure_ascii=False), flush=True)
                seen = {url}
                for link in follow:
                    link = urljoin(url, link.split("#")[0])
                    if link in seen or len(seen) > FOLLOW:
                        continue
                    seen.add(link)
                    if not robots_for(ctx, link, robots).can_fetch("*", link):
                        print(
                            json.dumps({"code": code, "url": link, "robots": "disallowed"}),
                            flush=True,
                        )
                        continue
                    sub = visit(page, link, requests)
                    sub.pop("_follow", None)
                    print(
                        json.dumps({"code": code, "via": url, **sub}, ensure_ascii=False),
                        flush=True,
                    )
        browser.close()


if __name__ == "__main__":
    main()
