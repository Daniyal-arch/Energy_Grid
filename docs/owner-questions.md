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

## 3. The Crown Estate offshore wind sites: accept the licence? (2026-11-05, Track 2.1)

**Decision.** The Crown Estate's open data licence for its offshore wind site layers is
revocable and bars reuse "on a similar website or portal". Entry `gb_tce_offshore_wind` is left
out.

**Options.** 1. Keep it out. 2. Ask The Crown Estate for permission to show the layer in the
atlas.

**Recommendation.** Option 2 (the layer would fill GB's offshore zones cell); until then, out.

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
