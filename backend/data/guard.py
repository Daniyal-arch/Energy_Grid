"""The SQL guard: what `run_sql` lets through to DuckDB (docs/AGENT.md section 3).

One SELECT (or WITH ... SELECT, or a set operation of them); no DDL, DML, PRAGMA, ATTACH, COPY,
INSTALL, LOAD, SET or other commands; file-reading functions and quoted file paths only under
the allowed prefixes; functions that run SQL from strings or reveal settings and secrets are
refused; licensed tables (Global Energy Monitor) only inside aggregates. A LIMIT is added so a
query never keeps more than `max_rows` rows. DuckDB's own lockdown (data/duck.py) is the second
wall: even a query the guard misreads cannot reach files outside the allowed paths.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

# table functions that read files or URLs: their first argument must be an allowed path
FILE_FUNCTIONS = {
    "read_parquet",
    "parquet_scan",
    "read_csv",
    "read_csv_auto",
    "read_json",
    "read_json_auto",
    "read_json_objects",
    "read_ndjson",
    "read_ndjson_auto",
    "read_ndjson_objects",
    "read_text",
    "read_blob",
    "st_read",
    "parquet_metadata",
    "parquet_schema",
    "parquet_file_metadata",
    "parquet_kv_metadata",
    "glob",
    "sniff_csv",
}
# functions never allowed: dynamic SQL, environment, secrets, settings, extensions, files
DENIED_FUNCTIONS = {
    "query",
    "query_table",
    "getenv",
    "current_setting",
    "duckdb_secrets",
    "which_secret",
    "duckdb_settings",
    "duckdb_extensions",
    "duckdb_temporary_files",
    "duckdb_databases",
    "load_extension",
    "install_extension",
    "iceberg_scan",
    "delta_scan",
    "read_xlsx",
    "sqlite_scan",
    "postgres_scan",
    "mysql_scan",
    "st_drivers",
    "pragma_database_list",
    "pragma_storage_info",
}
DENIED_NODES = tuple(
    c
    for c in (
        getattr(exp, n, None)
        for n in (
            "Insert",
            "Update",
            "Delete",
            "Merge",
            "Create",
            "Drop",
            "Alter",
            "AlterTable",
            "Command",
            "Pragma",
            "Set",
            "SetItem",
            "Copy",
            "Attach",
            "Detach",
            "Use",
            "Transaction",
            "Commit",
            "Rollback",
            "Install",
            "Load",
            "Describe",
            "Kill",
            "Export",
            "Into",
            "LoadData",
            "Refresh",
            "Summarize",
        )
    )
    if c is not None
)
AGGREGATE = exp.AggFunc


class GuardError(ValueError):
    """The query was refused; the message says why (it goes back to the model)."""


@dataclass
class Checked:
    sql: str
    tables: list[str] = field(default_factory=list)
    limited: bool = False


def _func_name(node: exp.Expression) -> str:
    if isinstance(node, exp.Anonymous):
        return str(node.this).lower()
    name = node.sql_name() if hasattr(node, "sql_name") else type(node).__name__
    return name.lower()


def _literal_paths(node: exp.Expression) -> list[str] | None:
    """String literals of a path argument (a string or a list of strings); None if not literal."""
    if isinstance(node, exp.Literal) and node.is_string:
        return [node.this]
    if isinstance(node, exp.Array):
        out: list[str] = []
        for e in node.expressions:
            if not (isinstance(e, exp.Literal) and e.is_string):
                return None
            out.append(e.this)
        return out
    return None


def _path_ok(path: str, allowed: list[str]) -> bool:
    if ".." in path:
        return False
    return any(path.startswith(a) for a in allowed)


def _first_arg(node: exp.Expression) -> exp.Expression | None:
    if isinstance(node, exp.Anonymous):
        return node.expressions[0] if node.expressions else None
    return node.this if isinstance(node.this, exp.Expression) else None


def _table_name(t: exp.Table) -> str:
    return ".".join(p for p in (t.catalog, t.db, t.name) if p)


def _check_licensed(select: exp.Select, licensed: tuple[str, ...]) -> None:
    """A SELECT that reads a licensed table directly returns only aggregates (and group keys)."""
    from_tables = [
        t
        for t in select.find_all(exp.Table)
        if t.find_ancestor(exp.Select) is select and t.db and t.db.lower().startswith(licensed)
    ]
    if not from_tables:
        return
    groups = {g.sql().lower() for g in (select.args.get("group") or exp.Group()).expressions}
    for proj in select.expressions:
        inner = proj.this if isinstance(proj, exp.Alias) else proj
        if inner.find(AGGREGATE):
            continue
        if inner.sql().lower() in groups:
            continue
        name = _table_name(from_tables[0])
        raise GuardError(
            f"{name} is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) "
            f"with GROUP BY keys may be returned, not rows; offending column: {proj.sql()}"
        )
    if isinstance(select.find(exp.Star), exp.Star) and select.find(exp.Star).parent is select:
        raise GuardError("licensed tables may not be read with SELECT *")


def check(
    sql: str,
    *,
    allowed_paths: list[str],
    max_rows: int,
    licensed_prefixes: tuple[str, ...] = ("gem",),
) -> Checked:
    """Parse, check and limit one query; raise GuardError with the reason when refused."""
    text = sql.strip().rstrip(";").strip()
    if not text:
        raise GuardError("empty query")
    if len(text) > 20_000:
        raise GuardError("query longer than 20,000 characters")
    try:
        statements = [s for s in sqlglot.parse(text, read="duckdb") if s is not None]
    except ParseError as e:
        raise GuardError(f"could not parse the query: {str(e).splitlines()[0]}") from e
    if len(statements) != 1:
        raise GuardError("exactly one statement is allowed")
    stmt = statements[0]
    if not isinstance(stmt, exp.Query):
        raise GuardError(f"only SELECT or WITH queries are allowed, not {stmt.key.upper()}")

    for node in stmt.walk():
        if isinstance(node, DENIED_NODES):
            raise GuardError(f"{node.key.upper()} is not allowed")
        if isinstance(node, exp.Func):
            name = _func_name(node)
            if name in DENIED_FUNCTIONS or name.startswith(("pragma_", "duckdb_")):
                raise GuardError(f"function {name}() is not allowed")
            if name in FILE_FUNCTIONS:
                arg = _first_arg(node)
                paths = _literal_paths(arg) if arg is not None else None
                if not paths or not all(_path_ok(p, allowed_paths) for p in paths):
                    raise GuardError(
                        f"{name}() may read only literal paths under: {', '.join(allowed_paths)}"
                    )
        if isinstance(node, exp.Table):
            # FROM 'file.parquet' (a quoted path used as a table)
            ident = node.this
            name = ident.this if isinstance(ident, exp.Identifier) and ident.quoted else ""
            if any(c in name for c in "/.:") and not _path_ok(name, allowed_paths):
                raise GuardError(f"file {name!r} is outside the allowed paths")
    for select in stmt.find_all(exp.Select):
        _check_licensed(select, licensed_prefixes)

    tables = sorted(
        {_table_name(t) for t in stmt.find_all(exp.Table) if t.name and not t.find(exp.Func)}
        - {cte.alias for cte in stmt.find_all(exp.CTE)}
    )
    limit = stmt.args.get("limit")
    current = None
    if isinstance(limit, exp.Limit):
        expr = limit.expression
        if isinstance(expr, exp.Literal) and not expr.is_string:
            current = int(float(expr.this))
    if current is not None and current <= max_rows:
        return Checked(sql=text, tables=tables)
    # wrap rather than regenerate, so DuckDB runs the text that was checked
    return Checked(
        sql=f"SELECT * FROM (\n{text}\n) AS q LIMIT {max_rows}", tables=tables, limited=True
    )
