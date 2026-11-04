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
