---
title: Zoning
tags: [data, lake, zoning]
updated: 2026-11-09
paths: [scripts/build_zoning.py, scripts/build_zoning_hub.py, scripts/zoning_documents.py, scripts/zoning_discover.py, scripts/probe_zoning.py, docs/research/zoning.md]
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
- `scripts/build_zoning_hub.py`: the zoning layers of the ArcGIS services the Hub sweep found
  (`data/zoning_discovery/hub_services.csv`), partition `source=us_hub` (or `eu_hub`, `gb_hub`);
  one row per layer read in `zoning.hub_layers` (field chosen, rows, status, licence). Country from
  the GISCO outlines. 48 shards in Actions; `--merge` joins their partial catalogues.
- `_ogr` in `build_zoning.py`: any GDAL source (`WFS:`, `OAPIF:`, a file, `/vsizip/`) through
  DuckDB `st_read`, reprojected to EPSG:4326, streamed to disk with `COPY` and checked against
  GDAL's feature count. Used by LU, Berlin, Upper Austria, Estonia, Burgenland, Vienna, Riga, NL.
- `zoning_discover.py --wfs` lists INSPIRE planned-land-use and XPlanung WFS services
  (`data/zoning_discovery/wfs_services.csv`, 2,196, mostly German municipalities); the hub
  builder reads them with `--region wfs` (`hub:wfs`, partition `eu_wfs`).
- Workflow: `lake-catalog.yml` input `zoning` = all, a source list, discover, or `hub:us`
  (`hub:us@4,15` reruns only those shards). The zoning jobs pin `duckdb==1.5.6` and set
  `CURL_CA_BUNDLE` (GDAL's curl has no CA bundle on the runner otherwise).

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
> - France: `ST_MakeValid` fails on mixed-dimension rows; `make_valid()` forces 2D and repairs
>   row by row (2 of 9,345 kept as published). R2 refused the AWS CLI's multipart checksums
>   (`InvalidPart`): uploads set `AWS_REQUEST_CHECKSUM_CALCULATION=when_required`.
> - DuckDB `st_read` ran out of 12 GB on the Netherlands GML (huge geometries, 2,048 rows a chunk);
>   `fetch_nl` uses `ogr2ogr` (gdal-bin installed in the job), one feature at a time.
> - Spain SIU answers an HTML error page for big pages; `arcgis()` halves the page and retries.
> - WFS servers cap responses (Burgenland 1,000): `OGR_WFS_PAGING_ALLOWED=ON`.
> - Luxembourg OAPIF declares EPSG:3035 but returns WGS84 lat/lon (`latlon=True` swaps it).
> - The National Zoning Atlas bucket no longer exists and mercatus.org refuses scripted downloads.
