// Real-time beside day-ahead at one hub per US market: the newest real-time interval each market
// has published and the day-ahead price of that hour. Values as published (USD/MWh).

import { useFile } from "../app/data";
import { dayAheadAt, usd, type UsPricesFile, type UsRtFile } from "../lib/us";
import { Card } from "./CountryCards";

const muted = "text-[#8d94a1]";
const ET = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", hour: "2-digit", minute: "2-digit", hour12: false });

export function UsRtCard() {
  const rt = useFile<UsRtFile>("usRt");
  const da = useFile<UsPricesFile>("usPrices");
  if (!rt) return null;
  const rows = Object.entries(rt.markets).flatMap(([m, v]) => {
    const last = v.points?.[v.points.length - 1];
    if (!last) return [];
    const t = Date.parse(last[0].replace("Z", ":00Z"));
    return [{ m, step: v.step, t, rt: last[1], da: dayAheadAt(da, v.hub, t) }];
  });
  const off = Object.entries(rt.markets).filter(([, v]) => !v.points?.length);
  if (!rows.length) return null;
  return (
    <Card title="Real time vs day-ahead" note="one hub per market" accent={[255, 196, 96]}>
      <div className={`grid grid-cols-[4rem_1fr_4.5rem_4.5rem] gap-1 text-[10px] ${muted}`}>
        <span>Market</span>
        <span>interval (ET)</span>
        <span className="text-right">real time</span>
        <span className="text-right">day-ahead</span>
      </div>
      {rows.map((r) => (
        <div key={r.m} className="grid grid-cols-[4rem_1fr_4.5rem_4.5rem] gap-1 text-[11px] tabular-nums text-slate-200">
          <span>{r.m}</span>
          <span className={muted}>
            {ET.format(new Date(r.t))} · {r.step}
          </span>
          <span className="text-right">{usd(r.rt)}</span>
          <span className="text-right">{r.da != null ? usd(r.da) : "–"}</span>
        </div>
      ))}
      <div className={`mt-1.5 text-[9px] ${muted}`}>
        The newest real-time interval each market has published, and the day-ahead price of that hour at the same hub (USD/MWh, as published). {rt.source}.
        {off.length > 0 && ` Not shown: ${off.map(([m, v]) => `${m} (${v.missing ?? "the download failed"})`).join(", ")}.`}
      </div>
    </Card>
  );
}
