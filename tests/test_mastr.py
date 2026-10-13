"""MaStR builder (scripts/build_mastr.py) on a tiny export shaped like the real one."""

from __future__ import annotations

import json
import sys
import zipfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_mastr as bm  # noqa: E402

CODES = [
    (35, "In Betrieb"),
    (31, "In Planung"),
    (1405, "Hessen"),
    (1409, "Nordrhein-Westfalen"),
    (888, "Windkraft an Land"),
    (889, "Windkraft auf See"),
]
KAT = (
    "<?xml version='1.0' encoding='UTF-16'?><Katalogwerte>"
    + "".join(
        f"<Katalogwert><Id>{i}</Id><KatalogKategorieId>1</KatalogKategorieId><Wert>{w}</Wert></Katalogwert>"
        for i, w in CODES
    )
    + "</Katalogwerte>"
)


def unit(tag: str, nr: str, ags: str | None, kw: float, status: int, extra: str = "") -> str:
    a = (
        f"<Gemeindeschluessel>{ags}</Gemeindeschluessel><Bundesland>1405</Bundesland>"
        if ags
        else ""
    )
    return (
        f"<{tag}><EinheitMastrNummer>{nr}</EinheitMastrNummer>{a}"
        f"<Bruttoleistung>{kw:.3f}</Bruttoleistung><Nettonennleistung>{kw:.3f}</Nettonennleistung>"
        f"<Inbetriebnahmedatum>2026-09-01</Inbetriebnahmedatum>"
        f"<EinheitBetriebsstatus>{status}</EinheitBetriebsstatus>{extra}</{tag}>"
    )


def _export(tmp: Path) -> Path:
    wind = "".join(
        [
            unit(
                "EinheitWind",
                "SEE2",
                "06636200",
                3000,
                35,
                "<Laengengrad>9.7</Laengengrad><Breitengrad>51.2</Breitengrad><WindAnLandOderAufSee>888</WindAnLandOderAufSee>",
            ),
            unit(
                "EinheitWind",
                "SEE1",
                "06636200",
                2000,
                35,
                "<WindAnLandOderAufSee>888</WindAnLandOderAufSee>",
            ),
            unit(
                "EinheitWind",
                "SEE3",
                None,
                8000,
                35,
                "<Laengengrad>6.5</Laengengrad><Breitengrad>54.0</Breitengrad><WindAnLandOderAufSee>889</WindAnLandOderAufSee>",
            ),
            unit("EinheitWind", "SEE4", "06636200", 5000, 31),
        ]
    )
    solar = "".join(
        [
            unit("EinheitSolar", f"SEE5{i}", "05515000", 10, 35, "<Bundesland>1409</Bundesland>")
            for i in range(3)
        ]
    )
    path = tmp / "Gesamtdatenexport_20261013_26.2.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("Katalogwerte.xml", KAT.encode("utf-16"))
        for name, root, body in (
            ("EinheitenWind.xml", "EinheitenWind", wind),
            ("EinheitenSolar_1.xml", "EinheitenSolar", solar),
        ):
            xml = f"<?xml version='1.0' encoding='UTF-16'?><{root}>{body}</{root}>"
            z.writestr(name, xml.encode("utf-16"))
    return path


def test_parts_and_combine(tmp_path: Path) -> None:
    export = _export(tmp_path)
    units = bm.build_part(export, "units", tmp_path / "lake", False, tmp_path / "tmp")
    wind = units["techs"]["wind"]
    assert wind["national"] == [3, 13.0]  # the planned unit is left out
    assert wind["offshore"] == [1, 8.0] and wind["no_ags"] == [1, 8.0]
    assert wind["per_ags"]["06636200"] == [2, 5.0]
    assert [u[2] for u in wind["large"]] == [8.0, 3.0]  # placed units only, largest first
    cat = units["catalog"]["tables"]
    assert cat["units_wind"]["rows"] == 4 and "snapshot" in cat["units_wind"]["partitions"]
    solar = bm.build_part(export, "solar", tmp_path / "lake2", False, tmp_path / "tmp2")
    files = solar["catalog"]["tables"]["units_solar"]["files"]
    assert files == ["units_solar/snapshot=2026-10-13/land=nordrhein-westfalen/part-0.parquet"]
    large, muni = bm.combine([units, solar], None)
    assert muni["techs"] == ["solar", "wind"] and muni["national"]["solar"] == [3, 0.0]
    assert large["units"][0][:4] == [6.5, 54.0, 1, 8.0]
    assert muni["months"][-1] == "2026-10" and len(muni["additions"]["wind"]) == 24
    json.dumps(muni)


def test_keep_snapshots() -> None:
    snaps = ["2024-03-02", "2024-11-02", "2025-01-02", "2025-06-02", "2025-12-02", "2026-10-02"]
    assert bm.keep_snapshots(snaps, date(2026, 10, 13)) == {
        "2024-03-02",
        "2025-01-02",
        "2025-12-02",
        "2026-10-02",
    }
