"""The agent's tools (docs/AGENT.md section 3) as LangChain tools with Pydantic arguments.

The same functions serve the MCP server (mcp_server/server.py). Every result is
`{data, sources: [{dataset, table, licence, retrieved}], result_id?}`. The list is sorted by
name so the prompt prefix (tools, then the system prompt) stays identical between requests.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from agent.skills import get_skills
from tools.area_stats import AreaStatsArgs, area_stats
from tools.areas import ResolveAreaArgs, resolve_area
from tools.catalog import APP_TABLES
from tools.context import ToolContext, result
from tools.live import LiveArgs, live
from tools.maps import MakeChartArgs, MakeMapArgs, make_chart, make_map
from tools.places import FindPlaceArgs, find_place
from tools.site import SiteArgs, site_figures
from tools.sql import DescribeTableArgs, RunSqlArgs, describe_table, run_sql


class SearchArgs(BaseModel):
    query: str = Field(
        description="What the question needs: topic, place, measure "
        "(e.g. 'solar capacity Germany states')"
    )


class NoArgs(BaseModel):
    pass


class SkillArgs(BaseModel):
    name: str


class SkillFileArgs(BaseModel):
    name: str
    path: str = Field(description="A file listed by load_skill, e.g. references/units.md")


def search_catalog(ctx: ToolContext, query: str) -> dict[str, Any]:
    hits = ctx.catalogue.search(query)
    queryable = set(ctx.lake.tables())
    for h in hits:
        if h["kind"] in ("lake table", "app table"):
            h["queryable"] = h["name"] in queryable
    return result(
        {"matches": hits, "note": "describe_table(name) for columns, units and examples"},
        [
            {
                "dataset": "catalog",
                "table": "agent/catalog",
                "licence": "InfraAtlas",
                "retrieved": "agent/catalog/*.yaml, datasets.json",
            }
        ],
    )


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    args: type[BaseModel]
    run: Callable[..., dict[str, Any]]
    mcp: bool = True


def specs() -> list[ToolSpec]:
    def skills(ctx: ToolContext) -> Any:
        return get_skills(ctx.settings.agent_dir)

    out = [
        ToolSpec(
            "search_catalog",
            "Find datasets, tables, columns, units, keys and map layers that answer a question "
            "(top 10).",
            SearchArgs,
            search_catalog,
        ),
        ToolSpec(
            "describe_table",
            "One table: columns with types and units, grain, keys, time range, row count, "
            "licence, 5 sample rows, example queries.",
            DescribeTableArgs,
            describe_table,
        ),
        ToolSpec(
            "run_sql",
            "Run one read-only DuckDB SELECT over the lake (dataset.table) and the app tables ("
            + ", ".join(APP_TABLES)
            + "). At most 2,000 rows come back; the full result is kept under result_id for maps "
            "and charts. 25 s limit.",
            RunSqlArgs,
            run_sql,
        ),
        ToolSpec(
            "find_place",
            "Resolve a country, US state, bidding zone, city or coordinates to codes, centre and "
            "bounding box.",
            FindPlaceArgs,
            find_place,
        ),
        ToolSpec(
            "resolve_area",
            "Resolve the area a question means into one record with an area_id: a country, "
            "group (EU-27, Nordics...), region, county, city, neighbourhood, bidding zone, the "
            "drawn polygon or circle (from_view='drawn'), the map on screen, several names "
            "(union), a circle around a point or place (radius_km), a buffer (buffer_km) or an "
            "intersection. Returns its outline's source, area_km2, people, and candidates when "
            "a name is ambiguous. Use the area_id in run_sql's in_area(), area_stats and MapSpec "
            "area.",
            ResolveAreaArgs,
            resolve_area,
        ),
        ToolSpec(
            "area_stats",
            "Rasters inside an area (resolve_area first): people and built-up surface (sums of "
            "GHSL cells whose centre lies inside), land cover and slope class shares, solar "
            "PVOUT and 100 m wind speed means, river flood depth class shares. Each figure names "
            "its raster, cell size and rule.",
            AreaStatsArgs,
            area_stats,
        ),
        ToolSpec(
            "site_figures",
            "The 'Check a site' figures for a point: substations, power plants by status and "
            "type, day-ahead prices, water risk, each with its source.",
            SiteArgs,
            site_figures,
        ),
        ToolSpec(
            "live",
            "Allow-listed live reads: the live snapshot (ENTSO-E newest interval) and day archive "
            "files, EIA-930. Cached 10 minutes.",
            LiveArgs,
            live,
        ),
        ToolSpec(
            "make_map",
            "Validate a MapSpec and send it to the map; returns the map id and link. Prefer "
            "switching on existing app layers.",
            MakeMapArgs,
            make_map,
            mcp=False,
        ),
        ToolSpec(
            "make_chart",
            "Validate a ChartSpec (line, bar or stacked; at most 2 series of 2,000 points) and "
            "send it to the panel.",
            MakeChartArgs,
            make_chart,
            mcp=False,
        ),
        ToolSpec(
            "list_skills",
            "List the agent's skills (name and description).",
            NoArgs,
            lambda ctx: result(skills(ctx).index(), []),
            mcp=False,
        ),
        ToolSpec(
            "load_skill",
            "Load a skill's instructions (and the list of its reference files).",
            SkillArgs,
            lambda ctx, name: result(skills(ctx).load(name), []),
            mcp=False,
        ),
        ToolSpec(
            "read_skill_file",
            "Read one reference file of a skill.",
            SkillFileArgs,
            lambda ctx, name, path: result(skills(ctx).read_file(name, path), []),
            mcp=False,
        ),
    ]
    return sorted(out, key=lambda t: t.name)


def langchain_tools(ctx: ToolContext) -> list[StructuredTool]:
    tools = []
    for spec in specs():

        def bound(_spec: ToolSpec = spec, **kwargs: Any) -> dict[str, Any]:
            return _spec.run(ctx, **kwargs)

        tools.append(
            StructuredTool.from_function(
                bound, name=spec.name, description=spec.description, args_schema=spec.args
            )
        )
    return tools


def by_name() -> dict[str, ToolSpec]:
    return {s.name: s for s in specs()}
