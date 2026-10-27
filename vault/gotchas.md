---
title: Gotchas
tags: [gotchas]
updated: 2026-10-27
---

# Gotchas

> [!warning] Windows laptop
> `uv` is not on PATH: in PowerShell prepend `$env:Path = "$env:APPDATA\Python\Python313\Scripts;$env:Path"`.
> `zoneinfo` needs `tzdata` (a dependency). Git warns about LF/CRLF; harmless.

> [!warning] r2.dev limits concurrent requests
> Read a lookup grid area in one range request (`readGrid` in `frontend/src/lib/area.ts`, up to
> 4 MB) with retries; never fire hundreds at once. The Maps view's six maps share the limit.

- **ENTSO-E** newest intervals arrive late and in parts (Italy zone by zone); pick the newest
  complete interval (rules in `docs/DATA_SOURCES.md`). Four requests at a time.
- **Day archive**: a day with fewer than 20 ENTSO-E countries is a failed fetch
  (`scripts/build_eu_day.py` `MIN_COUNTRIES`); it is rebuilt, not indexed.
- **powerplantmatching** lists German units individually: German wind sums ~12 % above the
  official capacity; panels show both.
- **EU ETS positions**: only installations the EEA register links by ETS id are placed (2,234 of
  9,668; Germany 78 of 1,818); the UK ETS has none. Brief 24. See [[coverage-and-gaps]].
- **`Math.max(...array)`** on large arrays overflows the call stack: use loops.
- **Memo keys** (`frontend/src/map/memo.ts`) are global by name: per-map values need the map's
  `scope` in the key (the Maps view draws up to six maps with the same code).
- **Interleaved deck.gl** layers are inserted before `label-names`; a map style without that
  layer drops them.
- **Range requests in Edge** need `cache: "no-store"` (else `ERR_CACHE_OPERATION_NOT_SUPPORTED`).
- **GitHub CLI** is not installed on the laptop; Actions are dispatched through the REST API with
  the git credential token.
