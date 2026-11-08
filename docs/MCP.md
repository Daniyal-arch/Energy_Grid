# The InfraAtlas MCP server

The backend serves the agent's read-only tools to other agents (Claude Code, Claude Desktop,
any client that speaks the Model Context Protocol) over streamable HTTP at `/mcp`. It runs the
same code, limits and logs as the site's own agent (`backend/mcp_server/server.py`); the agent
itself is documented in `docs/AGENT.md`.

## Access

- **Keys.** Bearer keys from the `MCP_API_KEYS` setting (comma-separated; in Lambda from SSM
  `/infraatlas/mcp_api_keys`). Without keys the server is off and `/mcp` answers 404.
- **Limits.** Each key has its own budget: 600 requests an hour (HTTP 429 above it). SQL runs
  under the same guard and DuckDB lockdown as the agent's (one SELECT, files only from the lake,
  25 s, 2,000 rows returned and 100,000 kept under a result id).
- **No keys or traces leak.** Errors come back as short messages; secrets never leave the
  service (`backend/tests/test_security.py`).

## Tools

| Tool | What it does |
|---|---|
| `search_catalog(query)` | the datasets, tables, columns and map layers that answer a question |
| `describe_table(name)` | one table: columns with units, grain, keys, time range, licence, sample rows |
| `run_sql(sql)` | one read-only DuckDB SELECT over the lake and the app tables |
| `find_place(text)` | a country, US state, bidding zone, city or coordinates to codes and a box |
| `resolve_area(names, level, point, radius_km, buffer_km, intersect_with, name)` | any area to one record with an `area_id` (English and local names, groups, circles, buffers) |
| `area_stats(area_id, measures)` | rasters summed or averaged inside an area (people, built-up, land cover, slope, solar, wind, flood, and the wave rasters) |
| `site_figures(lon, lat, radius_km)` | the "Check a site" figures for a point |
| `live(source, params)` | allow-listed live reads (ENTSO-E snapshot, day archive, EIA-930) |
| `quick(template, area, n, kind)` | instant answers from SQL templates: `profile`, `top`, `totals`, `compare`, `published`, `prices` |
| `nearest(dataset, lon, lat, area, k)` | the k nearest plants, substations or data centres, with great-circle km |
| `along(dataset, line, buffer_km, name)` | assets within `buffer_km` of a route `[[lon, lat], ...]` |
| `compare_areas(areas, measures)` | the same measures for 2-6 areas |
| `trend(area, years)` | capacity of today's plants by commissioning year (the age profile of the fleet) |
| `export(result_id, format)` | a result as CSV, GeoJSON or Parquet with its sources and licence terms (refused for sources that forbid redistribution) |
| `explain_coverage(area, family)` | what is published for an area's countries, and why a cell is dark |

Resources: `catalog://index`, `catalog://{dataset}`, `skill://{name}`,
`skill://{name}/references/{file}`.

Every result has the shape `{data, sources: [{dataset, table, licence, retrieved, as_of}],
result_id?}`: cite the sources with the figures, and the `as_of` date where there is one.

## Connect

Claude Code:

```bash
claude mcp add --transport http infraatlas https://energy-grid.infraatlas.workers.dev/mcp --header "Authorization: Bearer <key>"
```

Claude Desktop (`claude_desktop_config.json`, through the `mcp-remote` bridge):

```json
{
  "mcpServers": {
    "infraatlas": {
      "command": "npx",
      "args": ["mcp-remote", "https://energy-grid.infraatlas.workers.dev/mcp",
               "--header", "Authorization: Bearer <key>"]
    }
  }
}
```

## Example (Python, the `mcp` package)

```python
import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL = "https://energy-grid.infraatlas.workers.dev/mcp"
HEADERS = {"Authorization": "Bearer <key>"}


async def main() -> None:
    async with streamablehttp_client(URL, headers=HEADERS) as (read, write, _):
        async with ClientSession(read, write) as s:
            await s.initialize()
            # an instant answer: Bavaria's plants by fuel, substations, line length
            r = await s.call_tool("quick", {"template": "profile", "area": "Bavaria"})
            print(r.content[0].text[:500])
            # any area, then SQL inside it
            area = await s.call_tool("resolve_area", {"names": ["the Ruhr"]})
            print(area.content[0].text[:300])


asyncio.run(main())
```

The URL is the site's own domain once the Cloudflare Worker routes `/mcp` to the Lambda
(`docs/AGENT.md`, hosting); until then use the Lambda function URL.
