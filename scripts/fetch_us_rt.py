"""US real-time prices at the same trading hubs as the day-ahead file (brief 22, family 5): an
imbalance-like view beside the day-ahead price, read with gridstatus (MIT) from each market.

    python scripts/fetch_us_rt.py [--out DIR]

  market  hub                 real-time market as published
  CAISO   TH_SP15_GEN-APND    15-min real-time (RTPD) LMP
  ERCOT   HB_HUBAVG           15-min real-time settlement point price
  MISO    ILLINOIS.HUB        5-min real-time LMP
  SPP     SPPSOUTH_HUB        5-min real-time LMP by settlement location
  NYISO   N.Y.C. (zone J)     5-min real-time LBMP
  ISO-NE  .H.INTERNAL_HUB     hourly real-time LMP
PJM waits for PJM_API_KEY (as the day-ahead file). Values as published (USD/MWh), today and
yesterday in Eastern Time, each with its interval start in UTC. A market that fails is listed
with the error; nothing is filled in.

Writes <out>/us_rt.json (beside us_prices.json; refreshed with it in eu-days.yml).
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "data" / "eu"
ET = ZoneInfo("America/New_York")
HUBS = {
    "CAISO": ("TH_SP15_GEN-APND", "15 min"), "ERCOT": ("HB_HUBAVG", "15 min"), "MISO": ("ILLINOIS.HUB", "5 min"),
    "SPP": ("SPPSOUTH_HUB", "5 min"), "NYISO": ("N.Y.C.", "5 min"), "ISO-NE": (".H.INTERNAL_HUB", "hour"),
}  # fmt: skip


def frame(market: str, day: str):  # noqa: ANN201 - a pandas DataFrame
    import gridstatus

    hub = HUBS[market][0]
    if market == "CAISO":
        return gridstatus.CAISO().get_lmp(date=day, market="REAL_TIME_15_MIN", locations=[hub])
    if market == "ERCOT":
        return gridstatus.Ercot().get_spp(
            date=day, market="REAL_TIME_15_MIN", locations=[hub], location_type="Trading Hub"
        )
    if market == "MISO":
        return gridstatus.MISO().get_lmp(date=day, market="REAL_TIME_5_MIN", locations=[hub])
    if market == "SPP":
        df = gridstatus.SPP().get_lmp_real_time_5_min_by_location(date=day, location_type="Hub")
        return df[df["Location"] == hub]
    if market == "NYISO":
        return gridstatus.NYISO().get_lmp(date=day, market="REAL_TIME_5_MIN", locations=[hub])
    return gridstatus.ISONE().get_lmp(date=day, market="REAL_TIME_HOURLY", locations=[hub])


def points(df) -> list[list]:  # noqa: ANN001 - a pandas DataFrame
    """[UTC interval start, USD/MWh] in time order (SPP's settlement price column is "SPP")."""
    col = "LMP" if "LMP" in df.columns else "SPP"
    out = []
    for t, v in zip(df["Interval Start"], df[col], strict=True):
        if v == v:  # not NaN
            out.append([t.tz_convert("UTC").strftime("%Y-%m-%dT%H:%MZ"), round(float(v), 2)])
    return sorted(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    markets: dict[str, dict] = {}
    for m, (hub, step) in HUBS.items():
        try:
            yesterday = (datetime.now(ET) - timedelta(days=1)).date().isoformat()
            pts = points(frame(m, yesterday)) + points(frame(m, "today"))
            markets[m] = {"hub": hub, "step": step, "points": pts}
            print(f"  {m}: {len(pts)} intervals", flush=True)
        except Exception as e:  # noqa: BLE001 - one market down must not stop the others
            markets[m] = {"hub": hub, "step": step, "error": f"{type(e).__name__}: {str(e)[:200]}"}
            print(f"  {m}: failed ({e})", flush=True)
    markets["PJM"] = {"hub": "WESTERN HUB", "missing": "needs PJM_API_KEY"}
    if not any("points" in v for v in markets.values()):
        raise SystemExit("no market answered")
    payload = {
        "source": "Real-time LMP at one trading hub per US market, read with gridstatus (MIT)",
        "unit": "USD/MWh",
        "fetched": datetime.now(UTC).isoformat(timespec="seconds"),
        "markets": markets,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "us_rt.json"
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"-> {path}")


if __name__ == "__main__":
    main()
