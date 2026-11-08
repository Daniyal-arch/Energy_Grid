# Site report

**Problem.** A developer screening a site (data centre, battery, solar or wind, offshore,
industrial) needs the evidence for one place on one page, criterion by criterion, to file or
share, without asking the agent each time.

**Who it serves.** Site-selection analysts, developers' grid teams, consultants writing a
first screening.

**What it shows.** For a point and a radius (5-100 km) and a task: the task skill's checklist
(`agent/skills/<task skill>/SKILL.md`), in its order. Each step lists the figures computed
inside the circle (plants by fuel, substations by voltage, line length, data centres; rasters
where the step names flood, slope, land cover, solar or wind), each with its method, source and
as-of date, and the coverage cells the step names for the point's country (what is published,
or why not, with the date checked). Steps the service cannot compute say so and point to Ask.

**Its data.** The app tables and the lake through the same tools as the agent (`run_sql` via the
quick templates, `area_stats`, `site_figures`, the coverage registry). No model is called.

**Limits.** No score, no ranking, no weighting: the reader weighs the criteria. The circle is a
circle (a drawn area comes later). PDF is the browser's "Save as PDF" of the printable page.
Rasters on R2 need the service's R2 keys; without them the step says so.

**Where.** `GET /api/report?lon=&lat=&radius_km=&task=` (HTML) and `/api/report.json`;
`backend/tools/report.py`, `backend/app/routes/report.py`, `backend/tests/test_report.py`.
Tasks: `data_centre`, `battery`, `solar_wind`, `offshore`, `industrial`.
