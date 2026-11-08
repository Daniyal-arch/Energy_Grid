# Data API

**Problem.** Teams want the atlas's figures in their own models and dashboards, not only on the
map, with the sources and licences that go with them.

**Who it serves.** Analysts and developers who script; partners embedding figures in reports.

**What it serves.** The backend's read-only routes, documented with OpenAPI at
`/api/openapi.json` (browsable at `/api/docs`):
`/api/quick/{template}` (instant answers), `/api/report` and `/api/report.json` (site report),
`/api/feed/{area}.json|.rss` (change feeds), `/api/catalog/*`, `/api/places`, `/api/areas/*`,
`/api/shapes/*`, `/api/site`, `/api/exports/{file}`. Every response carries `sources`
(dataset, table, licence, retrieved, as_of): cite them with the figures.

**Keys and limits.** `X-API-Key` with a key from `DATA_API_KEYS` (SSM `/infraatlas/data_api_keys`
in Lambda) gets its own budget (`DATA_API_PER_KEY_HOUR`, default 3,600 requests an hour);
anonymous callers get a budget per address (`DATA_API_PER_IP_HOUR`, 600). Above it: 429. An
unknown key: 401. No billing; the owner decides pricing later.

**Licences.** The routes serve the app tables and the coverage registry, whose sources allow
redistribution with attribution (CC BY 4.0, ODbL with share-alike, MIT, public domain, the
publishers' reuse terms). Files from `export` refuse sources marked non-commercial or
no-redistribution and carry share-alike terms where they apply. The agent route (`/api/ask`)
is not part of the API.

**Limits.** In-process budgets (per Lambda instance until the DynamoDB limits store is set up);
keys are a list in settings, not self-service.

**Where.** `backend/app/main.py` (`DATA_ROUTES`, `data_limit`), `backend/app/settings.py`,
`backend/tests/test_security.py::test_data_api_keys_and_budget`.
