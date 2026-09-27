"""DB Timetables API adapter.

The Timetables product returns XML station boards. We expose a small JSON shape
for the frontend and keep DB credentials server-side.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from app.config import get_settings

BASE_URL = "https://apis.deutschebahn.com/db-api-marketplace/apis/timetables/v1"
BERLIN = ZoneInfo("Europe/Berlin")

DEFAULT_STATIONS = {
    "frankfurt_hbf": "8000105",
    "berlin_hbf": "8011160",
    "hamburg_hbf": "8002549",
    "munich_hbf": "8000261",
    "cologne_hbf": "8000207",
    "stuttgart_hbf": "8000096",
}


def _db_headers() -> dict[str, str]:
    settings = get_settings()
    if not settings.db_client_id or not settings.db_api_key:
        raise HTTPException(503, "DB Timetables credentials are not configured")
    return {
        "DB-Client-Id": settings.db_client_id,
        "DB-Api-Key": settings.db_api_key,
        "Accept": "application/xml",
        "User-Agent": "GermanyInfraAtlas/0.1",
    }


def _fetch_xml(path: str) -> ElementTree.Element:
    request = Request(f"{BASE_URL}{path}", headers=_db_headers())
    try:
        with urlopen(request, timeout=30) as response:
            return ElementTree.fromstring(response.read())
    except HTTPError as exc:
        if exc.code in (401, 403):
            raise HTTPException(
                exc.code, "DB Timetables credentials are not authorized for this product"
            ) from exc
        raise HTTPException(exc.code, f"DB Timetables request failed: {exc.reason}") from exc
    except (URLError, TimeoutError) as exc:
        raise HTTPException(502, f"DB Timetables request failed: {exc}") from exc
    except ElementTree.ParseError as exc:
        raise HTTPException(502, "DB Timetables returned invalid XML") from exc


def _time(value: str | None) -> str | None:
    if not value:
        return None
    try:
        dt = datetime.strptime(value, "%y%m%d%H%M").replace(tzinfo=BERLIN)
        return dt.isoformat()
    except ValueError:
        return value


def _text_path(value: str | None) -> list[str]:
    return [part for part in (value or "").split("|") if part]


def _entry(stop: ElementTree.Element, kind: str, node: ElementTree.Element) -> dict[str, Any]:
    train = stop.find("tl")
    return {
        "id": stop.attrib.get("id", ""),
        "station_eva": stop.attrib.get("eva"),
        "kind": kind,
        "category": train.attrib.get("c") if train is not None else None,
        "line": train.attrib.get("n") if train is not None else None,
        "operator": train.attrib.get("o") if train is not None else None,
        "planned_time": _time(node.attrib.get("pt")),
        "changed_time": _time(node.attrib.get("ct")),
        "planned_platform": node.attrib.get("pp"),
        "changed_platform": node.attrib.get("cp"),
        "planned_path": _text_path(node.attrib.get("ppth")),
        "changed_path": _text_path(node.attrib.get("cpth")),
        "status": node.attrib.get("ps") or node.attrib.get("cs"),
        "wings": node.attrib.get("wings"),
    }


def _parse_board(root: ElementTree.Element, source: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stop in root.findall("s"):
        arrival = stop.find("ar")
        departure = stop.find("dp")
        if arrival is not None:
            row = _entry(stop, "arrival", arrival)
            row["source"] = source
            rows.append(row)
        if departure is not None:
            row = _entry(stop, "departure", departure)
            row["source"] = source
            rows.append(row)
    return rows


def station_board(eva: str = "8000105", hour: str | None = None) -> dict[str, Any]:
    now = datetime.now(BERLIN)
    board_hour = hour or now.strftime("%H")
    board_date = now.strftime("%y%m%d")

    planned_root = _fetch_xml(f"/plan/{eva}/{board_date}/{board_hour}")
    full_changes_root = _fetch_xml(f"/fchg/{eva}")
    recent_changes_root = _fetch_xml(f"/rchg/{eva}")

    return {
        "eva": eva,
        "station": planned_root.attrib.get("station") or full_changes_root.attrib.get("station"),
        "date": board_date,
        "hour": board_hour,
        "generated_at": now.isoformat(),
        "planned": _parse_board(planned_root, "planned"),
        "full_changes": _parse_board(full_changes_root, "full_changes"),
        "recent_changes": _parse_board(recent_changes_root, "recent_changes"),
    }
