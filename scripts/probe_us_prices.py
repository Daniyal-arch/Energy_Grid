"""Probe the US markets' public day-ahead prices (no keys) for one day: what each serves,
in what format, and the price at one trading hub at 12:00 local market time.

  CAISO   OASIS PRC_LMP (DAM), zip of CSV                  hub TH_SP15_GEN-APND
  ISO-NE  day-ahead LMP CSV per day                        .H.INTERNAL_HUB
  NYISO   damlbmp zone CSV per day                         N.Y.C. (zone J)
  MISO    day-ahead ex-post LMP CSV per day                ILLINOIS.HUB
  SPP     marketplace file browser, DA LMP by settlement location  SPPSOUTH_HUB
  ERCOT   MIS public reports, DAM settlement point prices  HB_HUBAVG
  PJM     Data Miner 2 needs a subscription key (not probed here)

    uv run python scripts/probe_us_prices.py [YYYY-MM-DD]
"""

from __future__ import annotations

import csv
import io
import sys
import zipfile
from datetime import date, datetime, timedelta

import httpx

DAY = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today() - timedelta(days=2)
D = DAY.strftime("%Y%m%d")
UA = {"User-Agent": "Europe-InfraAtlas/0.3 (research; contact via GitHub)"}


def show(name: str, fn) -> None:
    try:
        print(f"{name}: {fn()}")
    except Exception as err:  # noqa: BLE001 - a probe reports every failure and goes on
        print(f"{name}: FAILED {err.__class__.__name__}: {str(err)[:200]}")


def caiso() -> str:
    start = datetime(DAY.year, DAY.month, DAY.day, 7)  # 00:00 PDT = 07:00 UTC
    url = "http://oasis.caiso.com/oasisapi/SingleZip"
    params = {
        "queryname": "PRC_LMP",
        "market_run_id": "DAM",
        "startdatetime": start.strftime("%Y%m%dT%H:%M-0000"),
        "enddatetime": (start + timedelta(days=1)).strftime("%Y%m%dT%H:%M-0000"),
        "version": "1",
        "node": "TH_SP15_GEN-APND",
        "resultformat": "6",
    }
    r = httpx.get(url, params=params, timeout=120, headers=UA)
    z = zipfile.ZipFile(io.BytesIO(r.content))
    rows = list(csv.DictReader(io.TextIOWrapper(z.open(z.namelist()[0]), encoding="utf-8")))
    lmp = [x for x in rows if x.get("LMP_TYPE") == "LMP"]
    noon = [x for x in lmp if x.get("OPR_HR") == "13"]
    return f"{r.status_code}, {len(rows)} rows, {len(lmp)} LMP rows; HE13 {noon[0]['MW'] if noon else '-'} $/MWh; columns {list(rows[0])[:12] if rows else []}"


def isone() -> str:
    url = f"https://www.iso-ne.com/static-transform/csv/histRpts/da-lmp/WW_DALMP_ISO_{D}.csv"
    r = httpx.get(url, timeout=120, headers=UA, follow_redirects=True)
    lines = r.text.splitlines()
    hub = [ln for ln in lines if "INTERNAL_HUB" in ln]
    return f"{r.status_code}, {len(lines)} lines; hub rows {len(hub)}; HE13 row {hub[12] if len(hub) > 12 else hub[:1]}"


def nyiso() -> str:
    url = f"http://mis.nyiso.com/public/csv/damlbmp/{D}damlbmp_zone.csv"
    r = httpx.get(url, timeout=120, headers=UA)
    rows = list(csv.DictReader(io.StringIO(r.text)))
    nyc = [x for x in rows if x.get("Name") == "N.Y.C."]
    return f"{r.status_code}, {len(rows)} rows; N.Y.C. 13:00 {nyc[13] if len(nyc) > 13 else '-'}"


def miso() -> str:
    url = f"https://docs.misoenergy.org/marketreports/{D}_da_expost_lmp.csv"
    r = httpx.get(url, timeout=120, headers=UA, follow_redirects=True)
    lines = r.text.splitlines()
    hub = [ln for ln in lines if ln.startswith("ILLINOIS.HUB")]
    return f"{r.status_code}, {len(lines)} lines; header {lines[4][:120] if len(lines) > 4 else ''}; hub {hub[:1]}"


def spp() -> str:
    path = f"/{DAY.year}/{DAY.month:02d}/By_Day/DA-LMP-SL-{D}0100.csv"
    url = "https://portal.spp.org/file-browser-api/download/da-lmp-by-location"
    r = httpx.get(url, params={"path": path}, timeout=120, headers=UA)
    lines = r.text.splitlines()
    hub = [ln for ln in lines if "SPPSOUTH_HUB" in ln]
    return f"{r.status_code}, {len(lines)} lines; header {lines[0][:150] if lines else ''}; hub rows {len(hub)} first {hub[:1]}"


def ercot() -> str:
    lst = httpx.get(
        "https://www.ercot.com/misapp/servlets/IceDocListJsonWS",
        params={"reportTypeId": "12331"},
        timeout=120,
        headers=UA,
    )
    docs = lst.json()["ListDocsByRptTypeRes"]["DocumentList"]
    names = [d["Document"]["ConstructedName"] for d in docs[:3]]
    doc = next(
        (d["Document"] for d in docs if D in d["Document"]["ConstructedName"]), docs[0]["Document"]
    )
    z = httpx.get(
        "https://www.ercot.com/misdownload/servlets/mirDownload",
        params={"doclookupId": doc["DocID"]},
        timeout=120,
        headers=UA,
    )
    zf = zipfile.ZipFile(io.BytesIO(z.content))
    rows = list(csv.DictReader(io.TextIOWrapper(zf.open(zf.namelist()[0]), encoding="utf-8")))
    hub = [x for x in rows if x.get("SettlementPoint") == "HB_HUBAVG"]
    return f"list {lst.status_code}, {len(docs)} docs e.g. {names}; file {doc['ConstructedName']}: {len(rows)} rows; hub HE13 {hub[12] if len(hub) > 12 else hub[:1]}"


if __name__ == "__main__":
    print(f"day {DAY}")
    for name, fn in [
        ("CAISO", caiso),
        ("ISO-NE", isone),
        ("NYISO", nyiso),
        ("MISO", miso),
        ("SPP", spp),
        ("ERCOT", ercot),
    ]:
        show(name, fn)
