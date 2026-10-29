"""run_sql and describe_table: DuckDB over the lake's views and the app tables."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from data.guard import GuardError
from tools.catalog import APP_TABLES
from tools.context import ToolContext, result


class RunSqlArgs(BaseModel):
    sql: str = Field(
        description="One DuckDB SELECT or WITH query over the lake's tables (dataset.table, e.g. "
        "registers.gb) and the app tables (app.eu_plants, app.eu_prices, ...). Read-only."
    )


class DescribeTableArgs(BaseModel):
    name: str = Field(
        description="A table name from search_catalog, e.g. app.eu_plants or registers.gb"
    )


def run_sql(ctx: ToolContext, sql: str) -> dict[str, Any]:
    s = ctx.settings
    try:
        r = ctx.lake.run(sql, timeout_s=s.sql_timeout_s)
    except GuardError as e:
        return result({"error": f"refused: {e}"}, [])
    except TimeoutError as e:
        return result({"error": str(e)}, [])
    except Exception as e:  # DuckDB errors go back to the model to fix the query
        return result({"error": f"{type(e).__name__}: {str(e).splitlines()[0][:400]}"}, [])
    cat = ctx.catalogue.entries
    sources = []
    for t in r.tables:
        src = ctx.lake.source_for(t, cat).as_dict()
        if src not in sources:
            sources.append(src)
    rid = ctx.results.save(r.columns, r.rows, sql=r.sql, sources=sources)
    shown = r.rows[: s.sql_rows_returned]
    data = {
        "columns": r.columns,
        "types": r.types,
        "rows": shown,
        "row_count": len(r.rows),
        "rows_shown": len(shown),
        "ms": round(r.ms, 1),
    }
    if r.truncated:
        data["note"] = f"stopped at {s.sql_rows_kept} rows; aggregate in SQL for complete figures"
    elif len(r.rows) > len(shown):
        data["note"] = (
            f"{len(r.rows)} rows kept under result_id (a map or chart reads all of them); "
            f"only the first {len(shown)} shown here"
        )
    ctx.emit("tool_detail", {"tool": "run_sql", "rows": len(r.rows), "ms": round(r.ms, 1)})
    return result(data, sources, rid)


def describe_table(ctx: ToolContext, name: str) -> dict[str, Any]:
    name = name.strip()
    entry = ctx.catalogue.table_entry(name)
    lake = ctx.lake
    cols: list[dict[str, Any]] = []
    sample: list[list[Any]] = []
    rows: int | None = None
    queryable = name in lake.tables()
    if queryable:
        cur = lake.cursor()
        desc = cur.execute(f"DESCRIBE {name}").fetchall()
        units = (entry or {}).get("columns") or {}
        measures = ((entry or {}).get("table") or {}).get("measures") or {}
        for c in desc:
            col = {"name": c[0], "type": c[1]}
            meaning = units.get(c[0]) or measures.get(c[0])
            if meaning:
                col["meaning"] = meaning
            cols.append(col)
        r = lake.run(f"SELECT * FROM {name} LIMIT 5", guard=False)
        sample = r.rows
        if name.startswith("app."):
            rows = lake.run(f"SELECT count(*) FROM {name}", guard=False).rows[0][0]
    if entry is None and not queryable:
        return result({"error": f"unknown table {name!r}; use search_catalog"}, [])
    data: dict[str, Any] = {
        "name": name,
        "queryable": queryable,
        "catalogue": entry,
        "columns": cols,
        "sample": sample,
    }
    if rows is not None:
        data["row_count"] = rows
    if not queryable:
        data["note"] = (
            "not in this service's DuckDB connection: the lake on R2 is not attached (R2 keys "
            "missing) or the dataset is read by API (see 'access')"
        )
    src = (
        lake.source_for(name, ctx.catalogue.entries).as_dict()
        if (queryable or name in APP_TABLES)
        else {
            "dataset": name.split(".")[0],
            "table": name,
            "licence": ctx.catalogue.licence(name.split(".")[0]),
            "retrieved": "agent/catalog",
        }
    )
    return result(data, [src])
