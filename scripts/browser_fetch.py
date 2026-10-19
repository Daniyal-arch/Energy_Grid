"""Files behind a browser check (Cloudflare "Just a moment..."), fetched with a real browser.

Some publishers answer scripts with a JavaScript challenge (the Energy Institute review answered
HTTP 403 "Just a moment..." to httpx twice in Actions). This opens the source's page in Chromium
(Playwright, run headed under xvfb in Actions), waits for the challenge to pass, finds the file link
on the page, downloads it with the browser's cookies and keeps it in the private R2 bucket:

    r2://infraatlas-raw/sources/<name>/<file>         the file as published
    r2://infraatlas-raw/sources/<name>/latest.json    {file, url, sha256, bytes, fetched, how}

A file whose sha256 matches latest.json is not uploaded again and the build is skipped (unless
--force). If the browser cannot pass the check either, the owner downloads the file in their own
browser and uploads it to `r2://infraatlas-raw/sources/<name>/manual/` (Cloudflare dashboard >
R2 > infraatlas-raw > Upload): the newest file there is used instead.

A new source is one entry in SOURCES: the pages to open, a regex for the file link, how often it
changes, and the build command run on the file ({file} is its local path).
Workflow: .github/workflows/browser-fetch.yml (monthly, and by hand).

    python scripts/browser_fetch.py ei [--force] [--no-build]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import lake  # noqa: E402

BUCKET = "infraatlas-raw"
OUT = Path(tempfile.gettempdir()) / "sources"

SOURCES: dict[str, dict] = {
    "ei": {
        "title": "Energy Institute Statistical Review of World Energy, consolidated dataset",
        "pages": [
            "https://www.energyinst.org/statistical-review/resources-and-data-downloads",
            "https://www.energyinst.org/statistical-review/home",
        ],
        # the consolidated "panel" file first (one row per country and year), else the workbook
        "links": [
            r"[^\"'\s>]*[Pp]anel[^\"'\s>]*\.(?:csv|xlsx)",
            r"[^\"'\s>]*(?:[Cc]onsolidated|ALL[-_ ]data|all-data)[^\"'\s>]*\.(?:csv|xlsx)",
            r"[^\"'\s>]*Stats[-_ ]Review[^\"'\s>]*\.xlsx",
        ],
        "refresh": "yearly (the review appears in June); checked monthly",
        "build": "python scripts/build_profiles.py ei --file {file} --upload",
    },
    "nyiso_queue": {
        "title": "NYISO interconnection queue (xlsx)",
        "pages": ["https://www.nyiso.com/interconnections"],
        "links": [r"[^\"'\s>]*NYISO-Interconnection-Queue[^\"'\s>]*\.xlsx"],
        "refresh": "monthly (NYISO updates the file monthly)",
        "build": "python scripts/fetch_us_queues.py --nyiso-file {file} --lake lake-out --upload",
    },
    "elia_capacity": {
        "title": "Elia, capacity of the grid for new decentralised generation (brief 21, dataset 3)",
        "pages": [
            "https://www.elia.be/en/infrastructure-and-projects/our-infrastructure/capacity-of-decentralized-production",
            "https://www.elia.be/infrastructure-and-projects/our-infrastructure/capacity-of-decentralized-production",
        ],
        "links": [r"[^\"'\s>]*\.xlsx", r"[^\"'\s>]*\.csv"],
        "refresh": "quarterly; checked monthly",
        "build": "python scripts/build_connect_more.py be --file {file} --upload",
    },
    "irena_costs": {
        "title": "IRENA Renewable Power Generation Costs, data file (brief 21, dataset 16)",
        "pages": [
            "https://www.irena.org/Publications/2025/Jul/Renewable-Power-Generation-Costs-in-2024",
            "https://www.irena.org/Data/View-data-by-topic/Costs/Global-LCOE-and-Auction-values",
        ],
        "links": [r"[^\"'\s>]*(?:[Dd]ata|DATA)[^\"'\s>]*\.xlsx", r"[^\"'\s>]*\.xlsx"],
        "refresh": "yearly (the report appears in July); checked monthly",
        "build": "python scripts/build_coming.py irena --file {file}",
    },
}


def find_link(html: str, patterns: list[str], base: str) -> str | None:
    """The first link on the page matching a pattern, in pattern order; made absolute."""
    hrefs = re.findall(r"""(?:href|data-href|src)\s*=\s*["']([^"']+)["']""", html, re.I)
    for pat in patterns:
        for h in hrefs:
            if re.fullmatch(pat, h.split("?")[0]):
                h = h.replace("&amp;", "&")
                if h.startswith("http"):
                    return h
                origin = re.match(r"https?://[^/]+", base).group(0)  # type: ignore[union-attr]
                return origin + ("" if h.startswith("/") else "/") + h
    return None


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def browser_fetch(name: str, src: dict) -> tuple[Path, str]:
    """The file via Chromium: page -> challenge passes -> link -> download with its cookies."""
    from playwright.sync_api import sync_playwright

    out = OUT / name
    out.mkdir(parents=True, exist_ok=True)
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False, args=["--disable-blink-features=AutomationControlled"]
        )
        ctx = browser.new_context(accept_downloads=True, locale="en-GB")
        page = ctx.new_page()
        for url in src["pages"]:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=90_000)
                for _ in range(45):  # the challenge reloads the page when it passes
                    if "just a moment" not in page.title().lower():
                        break
                    time.sleep(2)
                try:  # pages with endless analytics never go idle: read what has loaded
                    page.wait_for_load_state("networkidle", timeout=60_000)
                except Exception:  # noqa: BLE001
                    print(f"  {url}: not idle after 60 s, reading the page as loaded", flush=True)
            except Exception as e:  # noqa: BLE001 - report every page's failure, try the next
                errors.append(f"{url}: {type(e).__name__}: {str(e)[:120]}")
                continue
            title = page.title()
            link = find_link(page.content(), src["links"], url)
            files = sorted(
                set(re.findall(r"""["']([^"'\s]+\.(?:xlsx|csv|zip))["']""", page.content()))
            )
            print(f"  data links on the page: {files[:20]}", flush=True)
            print(f"  {url}: title {title!r}; file link {link}", flush=True)
            if not link:
                errors.append(f"{url}: no file link (title {title!r})")
                continue
            path = out / Path(link.split("?")[0]).name.replace("%20", "_")
            r = ctx.request.get(link, timeout=600_000)
            body = r.body()
            if r.ok and not body[:200].lstrip().lower().startswith((b"<!doctype", b"<html")):
                path.write_bytes(body)
            else:  # the file host challenges too: let the page itself download it
                with page.expect_download(timeout=600_000) as dl:
                    page.evaluate("u => { const a = document.createElement('a'); a.href = u; a.download = ''; document.body.appendChild(a); a.click(); }", link)  # fmt: skip
                dl.value.save_as(path)
            browser.close()
            return path, link
        browser.close()
    raise RuntimeError("; ".join(errors))


def r2_get(key: str, path: Path) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    return lake.wrangler("r2", "object", "get", f"{BUCKET}/{key}", "--file", str(path), "--remote")


def r2_put(path: Path, key: str) -> None:
    if not lake.wrangler("r2", "object", "put", f"{BUCKET}/{key}", "--file", str(path), "--remote"):
        raise SystemExit(f"upload of {key} to R2 failed")
    print(f"  r2://{BUCKET}/{key}: {path.stat().st_size / 1e6:.1f} MB", flush=True)


def manual_file(name: str) -> Path | None:
    """The newest file the owner uploaded to sources/<name>/manual/ (S3 listing, aws CLI)."""
    import os

    acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    ls = subprocess.run(
        ["aws", "s3", "ls", f"s3://{BUCKET}/sources/{name}/manual/",
         "--endpoint-url", f"https://{acct}.r2.cloudflarestorage.com"],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    rows = sorted(line.split(None, 3) for line in ls.stdout.splitlines() if line[:4].isdigit())
    if not rows:
        return None
    fname = rows[-1][3]
    path = OUT / name / "manual" / fname
    return path if r2_get(f"sources/{name}/manual/{fname}", path) else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*", default=list(SOURCES), help=f"of {list(SOURCES)}")
    ap.add_argument("--force", action="store_true", help="build even if the file did not change")
    ap.add_argument("--no-build", action="store_true")
    args = ap.parse_args()
    failed = []
    for name in args.names:
        src = SOURCES[name]
        print(f"{name}: {src['title']}", flush=True)
        try:
            path, url = browser_fetch(name, src)
            how = "browser"
        except Exception as e:  # noqa: BLE001 - fall back to the owner's upload
            print(f"  browser: {e}", flush=True)
            path = manual_file(name)
            if not path:
                print(f"  no file in r2://{BUCKET}/sources/{name}/manual/ either", flush=True)
                failed.append(name)
                continue
            url, how = f"r2://{BUCKET}/sources/{name}/manual/{path.name}", "uploaded by hand"
        digest = sha256(path)
        print(
            f"  {path.name}: {path.stat().st_size / 1e6:.1f} MB, sha256 {digest[:16]}", flush=True
        )
        prev_path = OUT / name / "previous.json"
        prev = (
            json.loads(prev_path.read_text())
            if r2_get(f"sources/{name}/latest.json", prev_path)
            else {}
        )
        if prev.get("sha256") == digest and not args.force:
            print("  unchanged since the last fetch: no upload, no build", flush=True)
            continue
        if how == "browser":
            r2_put(path, f"sources/{name}/{path.name}")
        meta = OUT / name / "latest.json"
        meta.write_text(json.dumps({
            "file": path.name, "url": url, "sha256": digest, "bytes": path.stat().st_size,
            "fetched": datetime.now(UTC).isoformat(timespec="seconds"), "how": how,
        }, indent=1))  # fmt: skip
        if not args.no_build:
            cmd = src["build"].format(file=shlex.quote(str(path)))
            print(f"  build: {cmd}", flush=True)
            if subprocess.run(cmd, shell=True, cwd=ROOT, check=False).returncode:
                failed.append(name)
                continue  # latest.json not written: the next run builds again
        r2_put(meta, f"sources/{name}/latest.json")
    if failed:
        raise SystemExit(f"failed: {failed}")


if __name__ == "__main__":
    main()
