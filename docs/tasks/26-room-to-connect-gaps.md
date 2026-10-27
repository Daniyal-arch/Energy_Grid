# 26. Room to connect: the countries and operators still missing

## Goal

Room to connect is one of the atlas's most important datasets. Since brief 23 it is one schema
(`frontend/public/data/eu/connect/harmonised.json`, 39 operators in 25 countries), and the map
darkens every European country with no operator data and says why on hover (the coverage
registry, `data/coverage.yaml`). Fill as many of those gaps as published sources allow, and the
missing operators inside covered countries, with the same schema and symbology.

## Read first

`vault/index.md`, `vault/data/coverage-and-gaps.md`, `docs/tasks/23-grid-capacity-harmonised.md`
(the schema, the class mapping rules, the summable rule), `scripts/build_connect_harmonised.py`
and `scripts/build_connect_h23.py` (how an operator becomes rows), `scripts/browser_fetch.py`
(files behind a browser check, run in Actions), the `connect` cells of `data/coverage.yaml`.

## What is missing (2026-10-27)

Countries with no rows (the probe `scripts/probe_connect_gaps.py`, run from a laptop, and the
registry notes):

| Country | What the operators do | Route to try |
|---|---|---|
| BE | Elia (hosting capacity map, 2026 and 2031; Wallonia: remaining capacity per substation feeding a distribution grid) and Sibelga answer a Cloudflare JavaScript check (HTTP 403 "Just a moment..."); Fluvius and ORES pages 404 | browser fetch in Actions; find the map's own data request (JSON) and the Wallonia file |
| LV | AST: Cloudflare (403); Sadales tīkls' free-capacity map (`karte.sadalestikls.lv/lv/briva-jauda`) answers HTTP 451 to a script that names itself | AST by browser fetch; Sadales tīkls: **do not bypass a 451**; draft a data request for the owner |
| RO | Transelectrica's capacity pages 404; Delgaz Grid and E-Distribuție behind Cloudflare; ANRE requires the DSOs to publish the available capacity at 110 kV weekly | find the DSOs' weekly 110 kV publications (PDF or XLSX) and Transelectrica's current allocation page; browser fetch where challenged |
| CY | TSO Cyprus behind Cloudflare; EAC's hosting-capacity page resets the connection | browser fetch |
| NO | Statnett's and Elvia's capacity pages answer 404 (moved); capacity is reserved by the local grid companies | probe Statnett's current pages, NVE, and the largest grid companies (Elvia, BKK, Glitre, Tensio, Lede) |
| CH | Swissgrid publishes connection forms only | probe the largest DSOs (EKZ, BKW, CKW, Groupe E); record not published if none |
| RS, BA, ME, MK, AL, MD, UA | EMS, CGES, MEPSO reachable, nothing found yet; NOS BiH timed out; OST, Moldelectrica and Ukrenergo behind Cloudflare | probe connection pages and development-plan annexes; record what is published |

Operators missing inside covered countries (registry notes): DE TenneT and the E.ON DSOs
(Westnetz, E.DIS, Bayernwerk, Avacon) behind Cloudflare; ES i-DE (503) and UFD (403); FI Fingrid
(Grid Scope, no download) and Caruna (404); GR IPTO (403/404); AT the DSOs (ebutilities.at script
page); SK SEPS (Power BI only) and SSD (resets); HU OPUS TITÁSZ (side not stated) and E.ON; GB
ENWL, SPEN and UKPN (keys `ENWL_API_KEY`, `SPEN_API_KEY`, `UKPN_API_KEY`, blocked).

## Rules for access

- Name the client honestly, as every probe does. A browser in Actions (`scripts/browser_fetch.py`,
  Playwright) may pass a JavaScript check that any visitor passes; record that it was used.
- **Never bypass an explicit refusal**: HTTP 451, a `robots.txt` disallow for the path, terms that
  forbid automated access, or a login. For those, write a short data request the owner can send
  (who, what dataset, licence question) into the PR, and note the manual upload path
  (`r2://infraatlas-raw/sources/<name>/manual/`, see `scripts/browser_fetch.py`).
- Prefer the map's own data request (a JSON or ArcGIS service the operator's map loads) over
  reading a page; read PDFs as printed (`pdfplumber`), never estimate a value.
- Probe first (`scripts/probe_connect_*.py`), show the output in the PR.

## Files

- New operators as harmonised rows (`scripts/build_connect_h23.py` or a sibling script), each with
  its class mapping documented (operator classes to the four, one to one), MW as published, the
  summable flag, `as_of`, licence.
- `scripts/browser_fetch.py` entries for each challenged source; `.github/workflows/browser-fetch.yml`
  runs them.
- `data/coverage.yaml`: every changed cell (status, source, url, note, checked). If Norway,
  Switzerland and the non-EU countries are to be listed, extend `scripts/coverage.py`'s countries
  with an "other Europe" group (NO, CH, RS, BA, ME, MK, AL, MD, UA, XK) and render it.
- `docs/DATA_SOURCES.md`, `docs/DATA_LAKE.md` (the lake table), `vault/data/coverage-and-gaps.md`,
  `vault/log.md`.

## Map and panels

Nothing new to design: rows join `harmonised.json` and appear in the Grid capacity layer, the
style menu, the Room to connect card and the share bar. A country that gains rows stops being
dark; the gap label and its hover text come from the registry, so update the cells.

## Done-check

- A table in the PR: per country and operator, before and after (rows, placed, classes, MW
  published), the route used, or why it stays missing with the evidence.
- The data requests for refused sources, ready to send.
- `uv run ruff check . && uv run ruff format .`, `uv run pytest`, `cd frontend && npm run build`.

## Out of scope

New symbology; estimating capacity where none is published; sources behind a login.
