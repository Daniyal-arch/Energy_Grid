---
title: Freshness
tags: [data, freshness]
updated: 2026-11-05
paths: [scripts/freshness.py, scripts/lake.py, scripts/wave5_common.py, .github/workflows/wave-refresh.yml]
---

# Freshness (brief 30 Track 3.1)

- Every wave source has `refresh` (daily ... yearly) and `refresh_basis`: the publisher's stated
  rhythm, or "the publisher states no rhythm: checked <interval>". Rules by kind and host in
  `scripts/freshness.py`; an entry's own `refresh` wins. Wave 10's generated registry gets them
  from `probe_wave10.py registry`; wave 9's via `freshness.py assign`.
- As of: `w.download` keeps the file's `Last-Modified` next to it; `wave9.py as_of()` takes the
  registry's `as_of` or that date; it goes into the build record and the lake catalogue's
  per-table `meta` (`scripts/lake.py` `TableInfo.meta`, also in the Parquet KV metadata).
- `wave-refresh.yml` (Mondays): lists the due sources; starts `wave9.yml` with `s:<id>` groups
  only when the repo variable `WAVE_REFRESH` is `on` (builds commit to the branch they run on).
- Tool results carry `as_of` per source (`tools/context.result`). See [[wave9]], [[lake]].
