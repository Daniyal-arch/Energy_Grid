"""Brazil's interconnected grid (SIN), live, from ONS "Energia Agora" (no key).

ONS publishes every few minutes (scripts/probe_more_grids.py), per subsystem (Southeast /
Centre-West, South, Northeast, North): generation by source, verified load, import and
export; and the flows between subsystems and abroad. Values are passthrough (MW).

Flows keep ONS's names and sign: positive = from the first subsystem in the name to the
second (checked against the subsystems' own import and export figures). "norteFic" is
ONS's fictitious node at the Imperatriz substation, where the North, Northeast and
Southeast lines meet; "internacional" is the link with Argentina and Uruguay in the
south.

Writes frontend/public/data/eu/brazil.json:
  {"source", "fetched", "at", "subsystems": {ID: {"name", "load", "import", "export",
   "generation": {source: MW}}}, "flows": [{"id", "from", "to", "mw"}],
   "international": {country: MW}}

    uv run python scripts/fetch_brazil.py [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu"
URL = "https://integra.ons.org.br/api/energiaagora/GetBalancoEnergetico/null"
SUBSYSTEMS = {
    "sudesteECentroOeste": ("SE", "Southeast / Centre-West"),
    "sul": ("S", "South"),
    "nordeste": ("NE", "Northeast"),
    "norte": ("N", "North"),
}
NODE = {
    "sul": "S",
    "sudeste": "SE",
    "nordeste": "NE",
    "norte": "N",
    "norteFic": "IMP",
    "internacional": "INT",
}
SOURCES = {
    "hidraulica": "hydro",
    "termica": "thermal",
    "eolica": "wind",
    "nuclear": "nuclear",
    "solar": "solar",
    "mmgd": "distributed",
    "itaipu50HzBrasil": "itaipu",
    "itaipu60Hz": "itaipu",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT)
    out: Path = parser.parse_args().out
    headers = {"User-Agent": "Mozilla/5.0 (Europe-InfraAtlas)"}
    with httpx.Client(timeout=60, follow_redirects=True, headers=headers) as client:
        for attempt in range(4):
            try:
                r = client.get(URL)
                if r.status_code == 200 and r.content.lstrip().startswith(b"{"):
                    break
            except httpx.TransportError:
                pass
            time.sleep(15 * (attempt + 1))
        else:
            raise RuntimeError("ONS: no answer")
    d = r.json()
    subsystems: dict[str, dict] = {}
    for key, (sid, name) in SUBSYSTEMS.items():
        s = d.get(key) or {}
        gen: dict[str, float] = {}
        for src, v in (s.get("geracao") or {}).items():
            if src in SOURCES and v is not None:
                gen[SOURCES[src]] = round(gen.get(SOURCES[src], 0.0) + float(v), 1)
        subsystems[sid] = {
            "name": name,
            "load": round(float(s["cargaVerificada"]), 1)
            if s.get("cargaVerificada") is not None
            else None,
            "import": round(float(s.get("importacao") or 0), 1),
            "export": round(float(s.get("exportacao") or 0), 1),
            "generation": gen,
        }
    flows = []
    for name, v in (d.get("intercambio") or {}).items():
        a, _, b = name.partition("_")
        if a in NODE and b in NODE and v is not None:
            flows.append({"id": name, "from": NODE[a], "to": NODE[b], "mw": round(float(v), 1)})
    payload = {
        "source": "ONS Energia Agora, balanco energetico (Operador Nacional do Sistema Eletrico)",
        "fetched": datetime.now(UTC).isoformat(timespec="seconds"),
        "at": d.get("Data"),
        "subsystems": subsystems,
        "flows": flows,
        "international": {
            k: round(float(v), 1)
            for k, v in (d.get("internacional") or {}).items()
            if v is not None
        },
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "brazil.json").write_text(
        json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    print(f"brazil.json: {len(subsystems)} subsystems, {len(flows)} flows, at {payload['at']}")


if __name__ == "__main__":
    main()
