"""Probe: verify open-mastr bulk download + filters before implementing the adapter.

Run with:  uv run python scripts/probe_mastr.py
Warning: the bulk download is several GB and takes a while on first run.

What we need to learn:
  - exact table & column names open-mastr produces for solar units
  - how 'ground-mounted' is encoded (Lage / 'Freifläche')
  - capacity column (Nettonennleistung, kW vs MW)
  - coordinate availability/quality for BW + BY units >= 5 MW
"""

from open_mastr import Mastr


def main() -> None:
    db = Mastr()  # default local SQLite under $HOME/.open-MaStR
    db.download(data=["solar"])

    import pandas as pd
    from sqlalchemy import create_engine, inspect

    engine = create_engine(db.engine.url)
    tables = inspect(engine).get_table_names()
    print("tables:", tables)

    solar_tables = [t for t in tables if "solar" in t.lower()]
    for table in solar_tables:
        df = pd.read_sql(f'SELECT * FROM "{table}" LIMIT 5', engine)
        print(f"\n=== {table} ({len(df.columns)} cols) ===")
        print(list(df.columns))

    # Candidate filter — column names to be confirmed from the output above:
    table = solar_tables[0]
    query = f"""
        SELECT COUNT(*) AS n
        FROM "{table}"
        WHERE "Bundesland" IN ('Bayern', 'BadenWuerttemberg', 'Baden-Württemberg')
          AND "Nettonennleistung" >= 5000  -- kW
          AND "Lage" LIKE '%Freifl%'
    """
    try:
        print("\ncandidate site count:", pd.read_sql(query, engine))
    except Exception as exc:  # noqa: BLE001 — probe script, report and move on
        print("\nfilter query failed (adjust column names):", exc)


if __name__ == "__main__":
    main()
