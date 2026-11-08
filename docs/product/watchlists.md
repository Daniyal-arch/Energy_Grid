# Watchlists and change feeds

**Problem.** A developer or analyst following a few regions wants to know what changed there
(new plants, more capacity, new substations, coverage that came online) without checking the
map every week.

**Who it serves.** Analysts with a portfolio of areas; teams who want a feed in their own tools
(RSS readers, Slack, email digests).

**What it shows.** For an area (any name the area resolver takes): a feed of changes, one item
per row of the instant-answer profile whose published values differ between two daily
snapshots ("Plants of 20 MW and more by fuel, solar: plants 12 to 14; mw 340.5 to 410.2"), with
both dates and the sources' as-of dates. In the app, a saved area (URL `?watch=` and this
browser's storage; no accounts) shows a "since your last visit" card from the same feed.

**Its data.** The app tables through `tools/quick.py` (`profile`), kept once a day per area in
the object store (`agent/feeds/<key>/<date>.json`); the feed is the diff of consecutive
snapshots.

**Limits.** An area starts its history the first time its feed is read (or the scheduled run
reads it); changes before that are not known. Only what the profile measures is watched
(queues and outages are next, from the history tables). No accounts, so no e-mail: RSS or JSON.

**Where.** `GET /api/feed/{area}.json` and `.rss`; `backend/tools/feeds.py`,
`backend/app/routes/feeds.py`, `backend/tests/test_feeds.py`.
