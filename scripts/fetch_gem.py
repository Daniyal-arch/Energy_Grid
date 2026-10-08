"""Global Energy Monitor trackers: download the ones this project uses, and only again
when GEM publishes a new release.

GEM's download page (globalenergymonitor.org/download-data) lists every tracker with its
"Last update" month in its page script; a download goes through GEM's own form: the
form's fields are posted to GEM's submissions API, which answers with a one-time token;
the token is exchanged for signed links to the files (the same requests the browser
form makes, scripts/probe in docs/DATA_SOURCES.md). The form fields are the user's own,
read from .env (GEM_NAME, GEM_EMAIL, GEM_ORGANIZATION, GEM_SECTOR, GEM_COUNTRY), and the
form is only submitted for a tracker whose release changed since the last download, so
GEM sees one request per new release.

Files go to data/world/gem/<tracker>/ (gitignored); a tracker's older files are removed
when its new release arrives. scripts/gem_releases.json (committed) records each tracker's
release and files, so the weekly workflow (.github/workflows/gem.yml) knows what the site
was built from. GEM's data is CC BY 4.0.

The workflow also keeps the raw files in the private R2 bucket infraatlas-raw (no public
access: the files are not republished), under gem/<tracker>/<slug><ext>, one key per GEM
file so a new release replaces the old one. --pull-r2 copies them to this computer without
going through GEM's form again (needs CLOUDFLARE_API_TOKEN; uses wrangler via npx).

    uv run python scripts/fetch_gem.py --check          # list trackers with a new release
    uv run python scripts/fetch_gem.py                  # download those (and missing ones)
    uv run python scripts/fetch_gem.py --only gas-infrastructure
    uv run python scripts/fetch_gem.py --pull-r2        # the workflow's downloads, from R2
    python scripts/fetch_gem.py --by-release --push-r2  # the workflow
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "world" / "gem"
PAGE_JS = "https://api.globalenergymonitor.org/static/gem-download-page.js"
RAW_BUCKET = "infraatlas-raw"  # private: no public access
ACCOUNT_ID = "a8ebfc5ad3d6228569de28c66a5f6367"  # the Cloudflare account (not a secret)
SUBMIT = "https://auxunjnrktkmeqyoyngm.supabase.co/rest/v1/rpc/mint_submission"
PRESIGN = "https://auxunjnrktkmeqyoyngm.supabase.co/functions/v1/presign"
# GEM's public (publishable) key, as embedded in its download form
PUBLISHABLE_KEY = "sb_publishable_8mQAV8B2HhveNc5T8VGqPQ_1lgsFAvz"
LICENSE_TEXT = (
    "Creative Commons Attribution 4.0 International (CC BY 4.0) — /creative-commons-license"
)
SECTORS = [
    "Academic / Research",
    "Civil Society / NGO",
    "Financial / Investor",
    "Government",
    "Industry",
    "Journalism / Media",
    "Other",
]
# the trackers this project uses (PLAN.md); GEM's ids
WANTED = [
    "integrated-power",
    "gas-infrastructure",
    "oil-infrastructure",
    "oil-gas-extraction",
    "coal-mines",
    "coal-terminals",
    "iron-steel",
    "cement",
    "iron-ore-mines",
    "chemicals",
    "energy-ownership",
    "coal-finance",
    "gas-finance",
    "methane-emitters",
]
USE_CASE = (
    "I am building InfraAtlas, an interactive web map of the world's energy infrastructure "
    "(power plants, transmission grids, gas and oil pipelines, LNG terminals) alongside live "
    "grid data from public sources. I use the tracker data to show each asset on the map by "
    "type, status and capacity, and to compute country and world totals for summary panels. "
    "The raw files are processed into simplified files for web display and are not "
    "republished as downloads. Every view credits Global Energy Monitor, the tracker and its "
    "release under CC BY 4.0. The map is shared publicly, including on LinkedIn, and may "
    "later be offered as a paid service under the CC BY 4.0 terms."
)
ITEM = re.compile(
    r'(?:"([a-z-]+)"|\b([a-z]+)):\{desc:"([^"]*)",updated:"Last update: ([A-Za-z]+ \d{4})",slugs:\[([^\]]*)\]'
)


def releases(client: httpx.Client) -> dict[str, dict]:
    """Every tracker on GEM's download page: description, release month, file slugs."""
    js = client.get(PAGE_JS).text
    out = {}
    for quoted, bare, desc, updated, slugs in ITEM.findall(js):
        out[quoted or bare] = {
            "desc": desc,
            "updated": updated,
            "slugs": re.findall(r'"([^"]+)"', slugs),
        }
    if not out:
        raise SystemExit("GEM's download page changed: no trackers found in its script")
    return out


def form_fields() -> dict:
    load_dotenv(ROOT / ".env")
    need = ["GEM_NAME", "GEM_EMAIL", "GEM_ORGANIZATION", "GEM_SECTOR", "GEM_COUNTRY"]
    missing = [k for k in need if not os.environ.get(k, "").strip()]
    if missing:
        raise SystemExit(f"set {', '.join(missing)} in .env (see .env.example)")
    sector = os.environ["GEM_SECTOR"].strip()
    if sector not in SECTORS:
        raise SystemExit(f"GEM_SECTOR must be one of: {'; '.join(SECTORS)}")
    return {
        "name": os.environ["GEM_NAME"].strip(),
        "email": os.environ["GEM_EMAIL"].strip(),
        "organization": os.environ["GEM_ORGANIZATION"].strip(),
        "sector": sector,
        "country": os.environ["GEM_COUNTRY"].strip(),
        "use_case": USE_CASE,
    }


def download(
    client: httpx.Client, tracker: str, slugs: list[str], fields: dict
) -> list[tuple[str, str]]:
    """GEM's form for one tracker: submit, exchange the token, fetch the files."""
    headers = {
        "content-type": "application/json",
        "apikey": PUBLISHABLE_KEY,
        "authorization": f"Bearer {PUBLISHABLE_KEY}",
    }
    payload = {
        **fields,
        "license_text": LICENSE_TEXT,
        "email_optin": False,
        "request_mode": "slugs",
        "useragent": "InfraAtlas fetch_gem.py",
        "page_url": "https://globalenergymonitor.org/download-data",
        "requested_slugs": slugs,
    }
    r = client.post(SUBMIT, headers=headers, json=payload)
    r.raise_for_status()
    token = r.json().get("capability_token")
    if not token:
        raise RuntimeError(f"{tracker}: GEM answered without a download token: {r.text[:200]}")
    r = client.post(
        PRESIGN, headers={"content-type": "application/json", "authorization": f"Bearer {token}"}
    )
    r.raise_for_status()
    urls = r.json().get("urls") or []
    folder = OUT / tracker
    folder.mkdir(parents=True, exist_ok=True)
    saved = []
    for u in urls:
        name = Path(u.get("filename") or u["slug"]).name
        tmp = folder / f".{name}.part"
        with client.stream("GET", u["url"]) as resp, tmp.open("wb") as f:
            resp.raise_for_status()
            size = 0
            for chunk in resp.iter_bytes(1 << 20):
                f.write(chunk)
                size += len(chunk)
                print(f"\r  {name}: {size / 1e6:.0f} MB", end="", flush=True)
        print(flush=True)
        tmp.replace(folder / name)
        saved.append((name, u.get("slug") or Path(name).stem))
    # the previous release's files go
    names = {n for n, _ in saved}
    for old in folder.iterdir():
        if old.is_file() and old.name not in names and not old.name.startswith("."):
            old.unlink()
    return saved


def r2_key(tracker: str, name: str, slug: str) -> str:
    """One key per GEM file (its slug), so a new release overwrites the old one."""
    return f"gem/{tracker}/{slug}{Path(name).suffix}"


def wrangler(*args: str) -> bool:
    npx = shutil.which("npx")
    if not npx:
        raise SystemExit("npx (Node.js) is needed for R2")
    load_dotenv(ROOT / ".env")
    env = {**os.environ}
    env.setdefault("CLOUDFLARE_ACCOUNT_ID", ACCOUNT_ID)
    if not env.get("CLOUDFLARE_API_TOKEN"):
        raise SystemExit("set CLOUDFLARE_API_TOKEN (.env or the workflow's secret)")
    done = subprocess.run([npx, "--yes", "wrangler@4", *args], env=env, check=False)
    return done.returncode == 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="only list what changed")
    parser.add_argument("--only", nargs="*", help="these trackers (GEM ids) instead of all used")
    parser.add_argument("--force", action="store_true", help="download even if unchanged")
    parser.add_argument(
        "--by-release",
        action="store_true",
        help="decide by GEM's release only, not by the files here (a fresh workflow machine)",
    )
    parser.add_argument("--push-r2", action="store_true", help="also store downloads in R2")
    parser.add_argument("--pull-r2", action="store_true", help="copy the files from R2 to here")
    args = parser.parse_args()
    manifest_path = ROOT / "scripts" / "gem_releases.json"
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    )
    if args.pull_r2:
        for t in args.only or list(manifest):
            for name, key in manifest.get(t, {}).get("keys", {}).items():
                path = OUT / t / name
                if path.exists():
                    print(f"{t}/{name}: here already", flush=True)
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                print(f"{t}/{name} <- r2://{RAW_BUCKET}/{key}", flush=True)
                wrangler(
                    "r2", "object", "get", f"{RAW_BUCKET}/{key}", "--file", str(path), "--remote"
                )
        return
    with httpx.Client(timeout=600, follow_redirects=True) as client:
        live = releases(client)
        wanted = args.only or WANTED
        unknown = [t for t in wanted if t not in live]
        if unknown:
            print(f"not on GEM's page (renamed?): {', '.join(unknown)}", flush=True)
        todo = []
        for t in wanted:
            if t not in live:
                continue
            have = manifest.get(t, {})
            files_ok = have.get("files") and all((OUT / t / f).exists() for f in have["files"])
            changed = have.get("updated") != live[t]["updated"]
            state = (
                "new release" if have and changed else "missing" if not files_ok else "up to date"
            )
            print(
                f"{t:22s} GEM {live[t]['updated']:9s} here {have.get('updated', '-'):9s} {state}",
                flush=True,
            )
            if args.force or changed or (not files_ok and not args.by_release):
                todo.append(t)
        gh = os.environ.get("GITHUB_OUTPUT")
        if args.check or not todo:
            if gh:
                with open(gh, "a", encoding="utf-8") as f:
                    f.write(f"changed={' '.join(todo) if args.check else ''}\n")
            return
        fields = form_fields()
        if args.push_r2:
            wrangler("r2", "bucket", "create", RAW_BUCKET)  # fails harmlessly if it exists
        done = []
        for t in todo:
            print(f"downloading {t} ({live[t]['updated']})", flush=True)
            try:
                files = download(client, t, live[t]["slugs"], fields)
            except (httpx.HTTPError, RuntimeError) as err:
                print(f"  {t} failed: {err}", file=sys.stderr, flush=True)
                continue
            keys = {name: r2_key(t, name, slug) for name, slug in files}
            if args.push_r2:
                for name, key in keys.items():
                    print(f"  r2://{RAW_BUCKET}/{key}", flush=True)
                    path = str(OUT / t / name)
                    if not wrangler(
                        "r2", "object", "put", f"{RAW_BUCKET}/{key}", "--file", path, "--remote"
                    ):
                        raise SystemExit(f"upload of {t}/{name} to R2 failed")
            manifest[t] = {
                "desc": live[t]["desc"],
                "updated": live[t]["updated"],
                "files": [name for name, _ in files],
                "keys": keys if args.push_r2 else manifest.get(t, {}).get("keys", {}),
                "downloaded": datetime.now(UTC).isoformat(timespec="seconds"),
            }
            manifest_path.write_text(
                json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8"
            )
            done.append(t)
        # for workflows: which trackers were downloaded
        if gh:
            with open(gh, "a", encoding="utf-8") as f:
                f.write(f"changed={' '.join(done)}\n")


if __name__ == "__main__":
    main()
