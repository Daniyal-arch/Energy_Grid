# Weekly brief

Track 6.5 of brief 30. MVP: `scripts/weekly_brief.py`, `.github/workflows/weekly-brief.yml`,
output `frontend/public/brief/latest.json` and `frontend/public/brief/latest.html`.

## Problem

The map shows the present. Someone who opens it once a week has to work out what moved since
their last visit: which prices rose, which queues grew, what came online, what is offline.

## Who it serves

Analysts, developers and journalists who follow European power markets and US interconnection
queues weekly and want a short, citable summary without opening every panel.

## What it shows

One plain page, a few sections, each a handful of sentences written from fixed templates:

1. **Day-ahead prices**: the three largest rises and falls of the weekly mean day-ahead price
   per bidding zone, this week against the week before.
2. **Price extremes**: the highest and lowest 15-minute price of the week, and the zones whose
   week went above the highest (or below the lowest) price of the twelve months in the Prices tab.
3. **Records in the day archive**: the week's highest solar, wind and load (the day files'
   highlights) and whether each is the highest of the days in the archive.
4. **Plants offline**: ENTSO-E A80 totals now (planned and forced) and the three countries with
   the most offline, against the figure in the previous brief.
5. **US interconnection queues**: active requests and MW per market, against the previous brief.
6. **Capacity added**: US units online this year (EIA-860M) and European units >= 20 MW by
   commissioning year (powerplantmatching).

Every sentence names its source, links the file it was read from and gives the "as of" date.
A section with missing data is skipped and the page says why.

## Its data

Only the app's own files: the day archive (`eu-days` branch, `eu/day/<date>.json`),
`prices.json` (eu-days), `outages.json` (eu-data), `us/queues_live.json`, `us/plants.json`
and `eu/plants.json` (bundled). No language model, no new external source. Computed values
(weekly means, sums) say how they are computed.

## Its limits

- Weekly means need both weeks complete in the archive (7 days each); a zone needs prices in at
  least 95 % of the 15-minute slots of both weeks.
- Outages and queues are snapshots: the comparison is with the previous brief's stored figure,
  so the first brief has no comparison.
- Capacity added comes from yearly or monthly registers, not from a weekly change feed.
- English only; one page per week (`latest`), no archive of past briefs yet.
