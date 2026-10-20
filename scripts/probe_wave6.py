"""Probe the 24 sources of brief 21 (docs/tasks/21-datasets-wave6.md) before building.

One function per dataset; each group prints at most 10 GitHub `::notice` annotations (status,
size, rows, fields, licence text found, a sample), so the run is read from its annotations
(.github/workflows/probe-wave6.yml, one step per group). Longer detail goes to the plain log.

    python scripts/probe_wave6.py A     # group A: room to connect
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx

UA = {"User-Agent": "Europe-InfraAtlas/0.3 (probe; github.com/Daniyal-arch/Energy_Grid)"}
CLIENT = httpx.Client(headers=UA, timeout=90, follow_redirects=True)
PUDL = "https://s3.us-west-2.amazonaws.com/pudl.catalyst.coop/stable"


def note(ds: str, text: str) -> None:
    print(f"::notice title={ds}::{text[:950]}".replace("\n", " "), flush=True)


def log(text: str) -> None:
    print(text[:4000], flush=True)


def size_of(url: str) -> str:
    """Status and content-length of a URL without downloading it."""
    try:
        with CLIENT.stream("GET", url) as r:
            n = int(r.headers.get("content-length") or 0)
            return (
                f"HTTP {r.status_code}, {n / 1e6:.1f} MB, {r.headers.get('content-type', '')[:40]}"
            )
    except httpx.HTTPError as e:
        return f"{type(e).__name__}: {e}"


def page(url: str, pattern: str, limit: int = 8) -> str:
    """Status of a page and the hrefs on it matching a pattern."""
    try:
        r = CLIENT.get(url)
    except httpx.HTTPError as e:
        return f"{url}: {type(e).__name__} {e}"
    found = re.findall(r'href=["\']([^"\']+)["\']', r.text)
    hits = list(dict.fromkeys(h for h in found if re.search(pattern, h, re.I)))
    log(f"{url} all matching links: {hits}")
    return f"{url}: HTTP {r.status_code}, {len(r.content) // 1000} kB, links {hits[:limit]}"


def ods(host: str, query: str, limit: int = 8) -> str:
    """Datasets of an Opendatasoft portal matching a full-text search (id, title, rows, licence)."""
    try:
        r = CLIENT.get(
            f"https://{host}/api/explore/v2.1/catalog/datasets",
            params={"where": f'search("{query}")', "limit": limit},
        )
        out = []
        for d in r.json().get("results", []):
            m = d.get("metas", {}).get("default", {})
            out.append(
                f"{d['dataset_id']} '{m.get('title')}' {m.get('records_count')} rows {m.get('license')}"
            )
        return f"{host} '{query}': HTTP {r.status_code}: " + "; ".join(out)
    except (httpx.HTTPError, ValueError) as e:
        return f"{host} '{query}': {type(e).__name__} {e}"


def ods_sample(host: str, ds: str) -> str:
    try:
        r = CLIENT.get(
            f"https://{host}/api/explore/v2.1/catalog/datasets/{ds}/records", params={"limit": 1}
        )
        d = r.json()
        return f"{host}/{ds}: HTTP {r.status_code}, {d.get('total_count')} rows, sample {json.dumps(d.get('results', [{}])[:1], ensure_ascii=False)[:700]}"
    except (httpx.HTTPError, ValueError) as e:
        return f"{host}/{ds}: {type(e).__name__} {e}"


def duck():  # noqa: ANN201
    import duckdb

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial")
    key, secret = os.environ.get("AWS_ACCESS_KEY_ID"), os.environ.get("AWS_SECRET_ACCESS_KEY")
    acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    if key and secret and acct:
        con.execute(
            f"CREATE SECRET lake (TYPE r2, KEY_ID '{key}', SECRET '{secret}', ACCOUNT_ID '{acct}')"
        )
    return con


def pudl(ds: str, table: str, date_col: str) -> None:
    import duckdb

    con = duck()
    url = f"{PUDL}/{table}.parquet"
    try:
        cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM '{url}'").fetchall()]
        n = con.execute(
            f"SELECT count(*), min({date_col}), max({date_col}) FROM '{url}'"
        ).fetchone()
        note(ds, f"{table}: {n[0]:,} rows, {n[1]} .. {n[2]}; cols {cols[:24]}")
    except duckdb.Error as e:
        note(ds, f"{table}: {str(e)[:300]}")


# A. Room to connect


def france() -> None:
    note(
        "fr_capacity",
        page("https://www.capareseau.fr/", r"csv|json|xlsx|api|export|telecharg|download"),
    )
    r = CLIENT.get(
        "https://www.data.gouv.fr/api/1/datasets/", params={"q": "capareseau", "page_size": 4}
    )
    try:
        hits = [
            f"{d['title']} ({d.get('license')}): {[(x['format'], x['url']) for x in d['resources'][:3]]}"
            for d in r.json()["data"]
        ]
    except ValueError:
        hits = [r.text[:200]]
    note("fr_capacity", f"data.gouv 'capareseau' HTTP {r.status_code}: {hits}")


def italy() -> None:
    note(
        "it_requests",
        page(
            "https://www.terna.it/it/sistema-elettrico/rete/econnextion",
            r"xlsx|csv|json|download|\.zip",
        ),
    )
    note(
        "it_requests",
        page(
            "https://www.terna.it/en/electric-system/grid/econnextion",
            r"xlsx|csv|json|download|\.zip",
        ),
    )


def belgium() -> None:
    note(
        "be_capacity",
        ods("opendata.elia.be", "connection") + " || " + ods("opendata.elia.be", "injection"),
    )
    note(
        "be_capacity",
        ods("opendata.fluvius.be", "capaciteit") + " || " + ods("opendata.fluvius.be", "injectie")
        + " || " + page("https://www.ores.be/", r"capacit|carte"),
    )  # fmt: skip


def portugal() -> None:
    note("pt_capacity", ods_sample("e-redes.opendatasoft.com", "capacidade-rececao-rnd"))
    note("pt_capacity", page("https://www.ren.pt/", r"capacidade|rececao|xlsx|csv"))


def ireland() -> None:
    note(
        "ie_capacity",
        page("https://www.eirgrid.ie/industry/customer-information/connecting-the-grid", r"heat|capacity|xlsx|csv")
        + " || " + page("https://www.esbnetworks.ie/new-connections/generator-connections-group/available-capacity-heat-maps", r"xlsx|csv|json|map"),
    )  # fmt: skip


def poland() -> None:
    note(
        "pl_capacity",
        page("https://www.pse.pl/web/pse-eng/areas-of-activity/grid-connection", r"xlsx|csv|pdf|capacit")
        + " || " + page("https://www.pse.pl/obszary-dzialalnosci/przylaczanie-do-sieci/warunki-przylaczenia-informacje", r"xlsx|csv|pdf"),
    )  # fmt: skip


# B. Grid and networks


def substations() -> None:
    import duckdb

    con = duck()
    try:
        q = (
            "SELECT class, count(*) n, count(kv) with_kv FROM "
            "read_parquet('r2://infraatlas-raw/lake/overture_power/sites/*/*.parquet', hive_partitioning=1) "
            "GROUP BY 1 ORDER BY 2 DESC LIMIT 8"
        )
        note("substations", f"lake sites: {con.execute(q).fetchall()}")
        cols = con.execute(
            "DESCRIBE SELECT * FROM read_parquet('r2://infraatlas-raw/lake/overture_power/sites/*/*.parquet', hive_partitioning=1)"
        ).fetchall()
        note("substations", f"cols {[c[0] + ':' + c[1] for c in cols]}")
    except duckdb.Error as e:
        note("substations", f"lake read failed: {str(e)[:400]}")


def mastr() -> None:
    import duckdb

    con = duck()
    try:
        q = (
            "SELECT count(*), count(grid_operator_nr), count(ags), count(DISTINCT grid_operator_nr), "
            "count(DISTINCT ags), any_value(snapshot) FROM "
            "read_parquet('r2://infraatlas-raw/lake/mastr/units_wind/*/*.parquet', hive_partitioning=1)"
        )
        note(
            "de_operators",
            f"units_wind rows, with operator, with ags, operators, municipalities, snapshot: {con.execute(q).fetchone()}",
        )
        cols = con.execute(
            "DESCRIBE SELECT * FROM read_parquet('r2://infraatlas-raw/lake/mastr/operators/*/*.parquet', hive_partitioning=1)"
        ).fetchall()
        note("de_operators", f"operators cols {[c[0] for c in cols][:30]}")
    except duckdb.Error as e:
        note("de_operators", f"lake read failed: {str(e)[:400]}")


def utilities() -> None:
    pudl("us_utilities", "core_eia861__yearly_service_territory", "report_date")


def emodnet() -> None:
    base = "https://ows.emodnet-humanactivities.eu/wfs"
    r = CLIENT.get(
        base, params={"service": "WFS", "request": "GetCapabilities", "version": "2.0.0"}
    )
    names = re.findall(r"<(?:wfs:)?Name>([^<]+)</", r.text)
    hits = [n for n in names if re.search(r"cable|pipe", n, re.I)]
    note(
        "sea_cables",
        f"capabilities HTTP {r.status_code}, {len(names)} layers; cable/pipeline layers {hits}",
    )
    for name in hits[:4]:
        try:
            g = CLIENT.get(
                base,
                params={"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": name,
                        "count": 1, "outputFormat": "application/json"},
            )  # fmt: skip
            d = g.json()
            props = d["features"][0]["properties"] if d.get("features") else {}
            note(
                "sea_cables",
                f"{name}: {d.get('totalFeatures') or d.get('numberMatched')} features; {json.dumps(props, ensure_ascii=False)[:500]}",
            )
        except (httpx.HTTPError, ValueError, KeyError) as e:
            note("sea_cables", f"{name}: {type(e).__name__} {str(e)[:200]}")


# C. What stops a build


def protected() -> None:
    r = CLIENT.get("https://bio.discomap.eea.europa.eu/arcgis/rest/services/ProtectedSites?f=json")
    note("protected", f"EEA ProtectedSites services HTTP {r.status_code}: {r.text[:400]}")
    note(
        "protected",
        page(
            "https://www.eea.europa.eu/en/datahub/datahubitem-view/6fc8ad2d-195d-40f4-bdec-576e7d1268e4",
            r"gpkg|zip|download|sdi",
        ),
    )
    r = CLIENT.get(
        "https://www.sciencebase.gov/catalog/items",
        params={"q": "PAD-US 4", "format": "json", "max": 5, "fields": "title,files"},
    )
    try:
        items = [
            f"{i['title']}: {[(f['name'], round(f.get('size', 0) / 1e6)) for f in i.get('files', [])][:6]}"
            for i in r.json().get("items", [])
        ]
    except ValueError:
        items = [r.text[:200]]
    note("protected", f"ScienceBase PAD-US HTTP {r.status_code}: {items}")


def flood() -> None:
    base = "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/FLOODS/"
    note("flood", page(base, r"/$"))
    for sub in ("EuropeanMaps/", "GlobalMaps/"):
        note("flood", page(base + sub, r"RP100|100|\.zip|\.tif"))


def roads() -> None:
    import duckdb

    sys.path.insert(0, os.path.dirname(__file__))
    from fetch_world_hv_overture import newest_release

    rel = newest_release()
    con = duck()
    con.execute("SET s3_region='us-west-2'")
    path = f"s3://overturemaps-us-west-2/release/{rel}/theme=transportation/type=segment/*"
    try:
        q = (
            f"SELECT subtype, class, count(*) FROM read_parquet('{path}', hive_partitioning=1) "
            "WHERE bbox.xmin BETWEEN 5 AND 6 AND bbox.ymin BETWEEN 50 AND 51 "
            "AND class IN ('motorway','trunk','primary','standard_gauge','rail') GROUP BY ALL ORDER BY 3 DESC"
        )
        note("roads", f"Overture {rel} segments in 5-6E 50-51N: {con.execute(q).fetchall()}")
    except duckdb.Error as e:
        note("roads", f"Overture {rel}: {str(e)[:400]}")


# D. What is coming and what it costs


def hydrogen() -> None:
    note(
        "hydrogen",
        page(
            "https://www.iea.org/data-and-statistics/data-product/hydrogen-production-and-infrastructure-projects-database",
            r"xlsx|download|licen|terms",
        ),
    )
    note(
        "hydrogen",
        page(
            "https://observatory.clean-hydrogen.europa.eu/hydrogen-landscape/production-trade-and-cost/electrolyser-installations",
            r"xlsx|csv|download|api",
        ),
    )


def auctions() -> None:
    note(
        "auctions", page("http://aures2project.eu/auction-database/", r"xlsx|csv|download|database")
    )


def costs() -> None:
    r = CLIENT.get(
        "https://oedi-data-lake.s3.amazonaws.com",
        params={"list-type": "2", "prefix": "ATB/electricity/parquet/"},
    )
    keys = re.findall(
        r"<Key>([^<]+)</Key><LastModified>[^<]+</LastModified><ETag>[^<]+</ETag><Size>(\d+)", r.text
    )
    note(
        "costs",
        f"ATB parquet HTTP {r.status_code}: {[(k, round(int(s) / 1e6, 1)) for k, s in keys][-8:]}",
    )
    note(
        "costs",
        page(
            "https://www.irena.org/Data/View-data-by-topic/Costs/Global-LCOE-and-Auction-values",
            r"xlsx|csv|download",
        ),
    )


def gas_projects() -> None:
    note("gas_projects", page("https://www.entsog.eu/tyndp", r"xlsx|annex|projects|csv"))


def ghg() -> None:
    r = CLIENT.get(
        "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/env_air_gge",
        params={"geo": "DE", "unit": "MIO_T", "airpol": "GHG", "format": "JSON", "lang": "EN"},
    )
    try:
        d = r.json()
        times = sorted(d["dimension"]["time"]["category"]["index"])
        note(
            "ghg",
            f"Eurostat env_air_gge HTTP {r.status_code}: {len(d['value'])} values, years {times[0]}..{times[-1]}, src_crf {len(d['dimension']['src_crf']['category']['index'])}",
        )
    except (ValueError, KeyError) as e:
        note("ghg", f"Eurostat env_air_gge HTTP {r.status_code}: {type(e).__name__} {r.text[:200]}")
    note(
        "ghg",
        page(
            "https://www.eea.europa.eu/en/datahub/datahubitem-view/3b7fe76c-a7ec-4426-8b7c-a4d8c9bb3a47",
            r"csv|zip|download|sdi",
        ),
    )


# E. United States


def oe417() -> None:
    note(
        "oe417", page("https://www.oe.netl.doe.gov/OE417_annual_summary.aspx", r"xls|zip|download")
    )
    note("oe417", page("https://doe417.pnnl.gov/", r"xls|csv|download|api"))


def ferc714() -> None:
    pudl("ferc714", "out_ferc714__hourly_planning_area_demand", "datetime_utc")
    pudl("ferc714", "core_ferc714__respondent_id", "respondent_id_ferc714")


# F. Regional and live


def fr_regions() -> None:
    note("fr_regions", ods_sample("odre.opendatasoft.com", "eco2mix-regional-tr"))


def es_regions() -> None:
    day = (datetime.now(UTC) - timedelta(days=2)).date()
    url = "https://apidatos.ree.es/es/datos/generacion/estructura-generacion"
    for geo in (4, 7):
        r = CLIENT.get(url, params={"start_date": f"{day}T00:00", "end_date": f"{day}T23:59", "time_trunc": "day",
                                    "geo_trunc": "electric_system", "geo_limit": "ccaa", "geo_ids": geo})  # fmt: skip
        try:
            inc = r.json()["included"]
            note(
                "es_regions",
                f"REData ccaa {geo} HTTP {r.status_code}: {[(i['attributes']['title'], i['attributes']['values'][0]['value']) for i in inc][:12]}",
            )
        except (ValueError, KeyError, IndexError) as e:
            note(
                "es_regions",
                f"REData ccaa {geo} HTTP {r.status_code}: {type(e).__name__} {r.text[:300]}",
            )


def new_zealand() -> None:
    r = CLIENT.get(
        "https://emidatasets.blob.core.windows.net/publicdata",
        params={
            "restype": "container",
            "comp": "list",
            "prefix": "Datasets/Wholesale/Generation/Generation_MD/",
        },
    )
    names = re.findall(r"<Name>([^<]+)</Name>", r.text)
    note(
        "nz_live",
        f"EMI Generation_MD HTTP {r.status_code}: {len(names)} files, newest {names[-3:]}",
    )
    note(
        "nz_live",
        page("https://www.emi.ea.govt.nz/Wholesale/Datasets", r"terms|licen|creative")
        + " || "
        + page(
            "https://www.transpower.co.nz/system-operator/live-system-and-market-data",
            r"api|json|csv|live",
        ),
    )


def south_africa() -> None:
    note("eskom", page("https://www.eskom.co.za/dataportal/", r"\.csv|xlsx|download"))
    r = CLIENT.get("https://loadshedding.eskom.co.za/LoadShedding/GetStatus")
    note("eskom", f"load-shedding GetStatus HTTP {r.status_code}: {r.text[:100]}")


GROUPS: dict[str, list[Callable[[], None]]] = {
    "A": [france, italy, belgium, portugal, ireland, poland],
    "B": [substations, mastr, utilities, emodnet],
    "C": [protected, flood, roads],
    "D": [hydrogen, auctions, costs, gas_projects, ghg],
    "E": [oe417, ferc714],
    "F": [fr_regions, es_regions, new_zealand, south_africa],
}

if __name__ == "__main__":
    for fn in GROUPS[sys.argv[1]]:
        try:
            fn()
        except Exception as e:  # noqa: BLE001 - a probe reports and moves on
            note(fn.__name__, f"failed: {type(e).__name__} {str(e)[:400]}")
