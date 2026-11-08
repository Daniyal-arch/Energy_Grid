# Owner questions

Decisions only the owner can take, each with the options, a recommendation and the evidence.
Kept current by every session (brief 30); answered ones move to `vault/decisions.md`.

## 1. GISCO country outlines: switch the default to Natural Earth? (2026-11-04, Track 1.8)

**Decision.** Eurostat GISCO's administrative-units terms say the data "will not be used for
commercial purposes". The app's country outlines (`countries.json`, `world.json`), the NUTS
regions behind the bidding-zone outlines (`zones.json`, lake `shapes.nuts`) and the NUTS 3
population figures come from GISCO.

**Built behind a flag.** `scripts/build_open_shapes.py` builds the same two files from Natural
Earth admin-0 countries 1:10m v5.1.2 (public domain) into `frontend/public/data/eu/open/`;
`?shapes=open` reads them (the sources text and credits then name Natural Earth). The default
is unchanged.

**Evidence** (`docs/research/gisco-replacement.md`): every atlas country has a Natural Earth
outline; overlap with GISCO (intersection over union, full detail) is 0.94-0.98 for the large
countries, lowest for Serbia 0.848 (GISCO's Serbia includes Kosovo; Natural Earth draws Kosovo
as its own feature, which GISCO does not have), Luxembourg 0.860, Denmark 0.867, Norway 0.887,
Croatia 0.892 (coastlines and islands). The open `countries.json` is 664 kB against 147 kB.

**Options.**
1. Switch countries to Natural Earth now (public domain, no attribution needed); keep NUTS until
   a replacement with NUTS codes exists.
2. Switch to Overture divisions (country level): finer, but ODbL share-alike for the derived
   database.
3. Keep GISCO and ask Eurostat for commercial-use permission (request in
   `docs/data-requests.md`).

**Recommendation.** Option 1 for the country outlines (a one-line change in
`frontend/src/app/data.ts`), plus option 3 for NUTS: no open dataset carries the NUTS codes the
Eurostat series join on (geoBoundaries ADM1/ADM2 are CC BY 4.0 but carry their own codes, so
every NUTS join would need a crosswalk by overlap).

## 2. European Drought Observatory CDI: is the licence CC BY 4.0? (2026-11-05, Track 2.1)

**Decision.** The Combined Drought Indicator NetCDF says in its own attributes that it is for
"non-commercial purposes", while the file's `copyright.txt` and the JRC data catalogue entry
both say CC BY 4.0. Evidence: `docs/research/page-only-batch-a.md` (`eu_edo_cdi`).

**Options.** 1. Use it under CC BY 4.0 (the catalogue's licence). 2. Leave it out and ask JRC
which statement applies (request in `docs/data-requests.md`).

**Recommendation.** Option 2: the source is left out (`status: left_out`) until JRC confirms;
drought is still covered for the US by other sources.

**Answer (2026-11-06).** Built: the owner asked to build sources whose licence is unclear. The
registry labels it CC BY 4.0 and quotes the narrower NetCDF attribute in its note.

## 3. The Crown Estate offshore wind sites: accept the licence? (2026-11-05, Track 2.1)

**Decision.** The Crown Estate's open data licence for its offshore wind site layers is
revocable and bars reuse "on a similar website or portal". Entry `gb_tce_offshore_wind` is left
out.

**Options.** 1. Keep it out. 2. Ask The Crown Estate for permission to show the layer in the
atlas.

**Recommendation.** Option 2 (the layer would fill GB's offshore zones cell); until then, out.

**Status (2026-11-06).** Still out: the owner's instruction covers unclear licences, and this one
is clear and restrictive (revocable; bars reuse on a similar portal). Option 2 stands.

## 4. Korea (KPX) live grid: is the licence open enough? (2026-11-05, Track 3.4)

**Decision.** `scripts/fetch_kpx.py` reads KPX's public real-time pages (robots.txt allows them):
demand, supply capacity, reserve and 13 source columns every 5 minutes (a test run: demand
58,584 MW, the columns sum to 58,584.1 MW). KPX's own generation dataset on data.go.kr
(15106744) says "이용허락범위 제한 없음" (no restriction on use), but the KPX site's footer says
"ALL RIGHTS RESERVED". Evidence: `docs/research/live-grids-beyond-europe.md`.

**Options.** 1. Wire it (eu-snapshot.yml step, a `korea` loader and card) on the strength of the
data.go.kr licence. 2. Ask KPX which statement covers the real-time figures first.

**Recommendation.** Option 2; the fetcher is ready and not wired. Alberta (AESO) was built too
but its terms allow only non-commercial use, so it is left out (probe kept:
`scripts/probe_aeso.py`). Chile (CEN) and Turkey (EPİAŞ) need accounts; India (Grid-India)
answers neither the sandbox nor GitHub runners.

**Answer (2026-11-06).** Build where the licence is unclear: Korea is wired (snapshot step, `korea.json`,
a World live-grid marker and card, both licence statements named on the card and in the sources).

## 5. Romania and Serbia connection data: build on the "public notice" basis? (2026-11-06, Track 2)

**Decision.** Two connection datasets are verified and ready to read but state no licence:
Transelectrica's available capacity per grid zone and year (HTML tables, published under ANRE
Order 53/2024 art. 6; footer "Copyright © Transelectrica 2013 - 2026") and EMS's list of every
connection request (a one-page PDF published under Serbia's renewable-energy law; ems.rs has no
terms page). The Austrian and Bulgarian connection cards were built on the same "a notice the
regulator requires to be public" basis, but their sites carry no copyright line against it.
Registry rows: `ro_transelectrica_zone_capacity`, `rs_ems_connection_queue`
(`scripts/wave9_sources.yaml`, notes with the columns and an example value each).

**Options.** 1. Build both as the AT/BG cards (an HTML-table and a PDF-table reader, the zones as
the union of their counties from Transelectrica's Anexa 4). 2. Write to Transelectrica and EMS
for a reuse statement first. 3. Leave them out.

**Recommendation.** Option 2 for Transelectrica (its copyright line is explicit), option 1 for
EMS once the owner agrees the legal-notice basis is enough; until then both stay unbuilt with the
reason in the registry.

**Answer (2026-11-06).** The owner asked to build sources whose licence is not stated or could
not be read. Both are built (Transelectrica: 100 zone-year cells; EMS: 88 requests), each labelled
"licence not stated" with the legal basis it is published under. The same instruction covers
the other unclear cases (EDO drought, PSE, PJM, INS Romania, Elia balancing); sources whose terms
clearly forbid reuse, need a login or refuse the client stay out.

## 6. Tables that store coordinates as text: retype them? (2026-11-08, brief 32)

**Decision.** Thirteen lake tables hold `lon`/`lat` as text (VARCHAR), as their sources publish
them: `main.plants`, `eia860m.generators`, `co2stop.hydrocarbon_formations`,
`co2stop.hydrocarbon_storage_units`, `co2stop.hydrocarbon_traps`, `co2stop.hydrocarbon_traps1`,
`co2stop.hydrocarbon_traps_temp`, `wave9.eu_eea_aq_stats`, `wave9.eu_egdi_minerals`,
`wave9.eu_emodnet_desalination`, `wave9.gb_ssen_opendata`, `wave9.us_epa_repowering`,
`wave9.us_nyc_ll84`. A place filter on them must cast every row (`TRY_CAST`), so Parquet
statistics cannot skip row groups and each place query reads the whole table (`main.plants`:
390 MB, 3.5 s warm; `docs/research/query-speed.md`).

**Why it is a question.** Brief 32 rewrites files only when every column keeps the same
checksum. Retyping `lon`/`lat` to DOUBLE changes those two columns' values (text "8.50" becomes
8.5; blanks and unparsable text become NULL), so it is not a lossless rewrite.

**Options.**
1. Retype in each table's build script (keep the original text in `lon_text`/`lat_text`, so
   nothing is lost) and rebuild. Recommended: place queries on these tables drop from whole-table
   reads to row-group reads.
2. Keep the text; the agent keeps casting (correct, slow on the large ones).

## 7. Lossy recompression of the largest rasters (2026-11-08, brief 32 Step 5)

**Decision.** Brief 32 applies only lossless recompression (`scripts/raster_recompress.py`,
values checked bit for bit). Measured on the real files (`lake-catalog.yml` input `rasters`):

| raster | now | lossless best | lossy option | lossy size | largest change of any cell | change of the sum over four windows |
|---|---:|---:|---|---:|---:|---:|
| `lake/atlas/atlas-wind100.tif` (Global Wind Atlas, 100 m speed, float32) | 14.075 GB | ZSTD 14.019 GB (0.4 %), not applied | int16 in 0.01 m/s steps | 2.983 GB (−78.8 %) | 0.005 m/s | 3.7e-8 to 1.6e-7 relative |
| `lake/rasters/ghsl_pop_e2025_30ss.tif` (GHSL population, float64) | 0.415 GB | none smaller | float32 | 0.376 GB (−9.6 %) | 0.0154 people | below 1e-9 relative |
| `lake/rasters/ghsl_pop_e2025_3ss/R6_C10.tif` (one 3ss tile, float64) | 0.310 GB | none smaller | float32 | 0.292 GB (−5.7 %) | 0.00006 people | below 1e-9 relative |

Applied losslessly: `lake/rasters/slope_1km_shares.tif` 650 MB to 571 MB (LERC, max error 0,
values identical). `worldcover_1km_shares.tif` would save 6 %, under the 10 % threshold: kept.

**Why it is a question.** The wind atlas is the single largest object (a third of the private
bucket). At $0.015 per GB-month above 10 GB, the int16 version saves 11.1 GB, about $0.17 a
month, and the 1 GB raster reads in area statistics get about 4.7 times smaller. The change
(at most half a step of 0.01 m/s) is below the source's own precision, but it is a change to
sourced values, which CLAUDE.md does not allow without the owner.

**Options.**
1. Convert the wind atlas to int16 (0.01 m/s, scale factor in the file's metadata, the
   original kept nowhere) and label wind figures "rounded to 0.01 m/s". Recommended: large
   saving, change below the data's precision.
2. Convert, and keep the original float32 in a cold archive outside the lake.
3. Keep everything as it is. The population float32 options save too little to be worth a
   change either way; recommended: keep them.

## 8. Zoning: plan documents (PDFs) to keep (2026-11-08, zoning request)

**Decision.** The zoning lake (`scripts/build_zoning.py`, `lake/zoning/zones`) keeps every
zone with its document link. `scripts/zoning_documents.py` measures the linked files and keeps
a sample of 25 PDFs per source privately on R2 (`infraatlas-raw/zoning-docs/`), with their page
text in `zoning.document_pages` for the agent. Measured:

| source | linked (plan, file) pairs | sampled, answered as PDF | mean size | projected total |
|---|---:|---:|---:|---:|
| Denmark Plandata (lokalplaner and kommuneplanrammer) | 88,688 | 200, 200 | 79.1 MB | at most 7.0 TB (a municipal plan PDF linked from many frames counts once per frame, so the distinct files are fewer) |
| England (conservation area appraisals) | 5,945 | 200, 126 | 3.4 MB | 20.3 GB |
| France GPU (regulation document per plan, `urlfic`) | 9,596 | 200, 79 (82 answered) | 6.93 MB | 66.5 GB |

Measured by `scripts/zoning_documents.py --measure 200` in run 42492842706 (Denmark, England) and run
42519477572 (France), both 2026-11-08. France keeps 25 PDFs (26 document rows, 2,667 pages of text).

**Why it is a question.** All of it is a large download (rule 4) and a storage cost: about
7 TB at $0.015 per GB-month would be about $105 a month for Denmark alone (an upper bound). The text, which the agent
needs, is far smaller than the PDFs (one 22 MB Danish plan gave 1,011 pages of text).

**Options.**
1. Keep the text of every document, and the PDF only for a sample; the agent cites the
   publisher's link for the PDF itself. Recommended: full-text search everywhere, small storage.
2. Keep every PDF and its text (several TB for Denmark alone).
3. Text only for the regulation documents (France `reglement`, Denmark local plans), none for
   reports and annexes.

## 9. Zoning: sources with no licence or no scripted download (2026-11-08)

- **California Statewide Zoning** (Office of Land Use and Climate Innovation): public
  access, no licence stated. In the lake, private; may it be shown on the public map?
- **National Zoning Atlas** (US, about 10 states): the S3 bucket is gone and mercatus.org
  refuses scripted downloads (HTTP 403). Options: the owner downloads the state ZIPs by hand
  into R2 (`infraatlas-raw/zoning-raw/zoning-atlas/`), or the state teams are asked for files.
- **PDF-only plan maps** (Wales, Northern Ireland, many Italian, Portuguese and Greek
  municipalities): turning a scanned map into polygons needs control points and hand tracing,
  which is an estimate of position. Options: leave these as documents with text only
  (recommended), or georeference a named list of plans and label them "digitised from the PDF
  map".
