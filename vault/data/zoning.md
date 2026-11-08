---
title: Zoning
tags: [data, lake, zoning]
updated: 2026-11-08
paths: [scripts/build_zoning.py, scripts/zoning_documents.py, scripts/zoning_discover.py, scripts/probe_zoning.py, docs/research/zoning.md]
---

# Zoning

Zoning and land-use plans for the EU, UK and US, in the [[lake]] as dataset `zoning`. The owner-facing
record is `docs/DATA_SOURCES.md` (section "Zoning and land-use plans"); the research log, every lead and
the blocked sources are in `docs/research/zoning.md`; open decisions are owner questions 8 and 9.

## Where
- `scripts/build_zoning.py`: one fetcher per source (WFS 2.0 paging, ArcGIS FeatureServer paging,
  bulk CSV) into NDJSON, then one SQL mapping per source to the standard columns; writes
  `zoning/zones/source=<id>/`. `CLASSES` holds the documented code lookups, `VOCAB` the harmonised classes.
- `scripts/zoning_documents.py`: `--measure N` sizes the linked PDFs, `--fetch N` keeps N per source
  privately (`infraatlas-raw/zoning-docs/<source>/<sha256>.pdf`) with page text (`documents`,
  `document_pages`, partitioned by source).
- `scripts/zoning_discover.py`: finds more sources. data.europa.eu search per country in its own
  plan terms (whole-word title match, geodata or PDF distributions); `--hub` sweeps ArcGIS Hub
  in 2-degree tiles for US counties and cities and UK councils.
- Workflow: `lake-catalog.yml` input `zoning` = all, a source list, or discover. One source at a time.

## How it works
- Each row keeps the source's own code and label plus `attributes` (all fields, JSON): nothing is
  dropped; `class` is only a lookup, unmapped codes are `other`.
- England brownfield sites are points (the register has no polygons); rows with no geometry stay.
- Plan PDFs carry their authors' copyright even when the data is open: kept private, the agent cites
  the publisher's link.

> [!warning] Gotchas
> - A new workflow file cannot be dispatched before it reaches `main`: zoning jobs live in `lake-catalog.yml`.
> - wrangler answered "The specified bucket does not exist" on 2026-11-08; `scripts/lake.py`
>   `wrangler()` uploads over R2's S3 API when `scripts/r2_creds.sh` has set the keys.
> - The INSPIRE geoportal's TLS certificate had expired (2026-11-08); use data.europa.eu, which harvests it.
> - The National Zoning Atlas bucket no longer exists and mercatus.org refuses scripted downloads.
