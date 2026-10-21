// CO₂ per kWh as the operators publish it: France and Ireland every 15 min, Spain's daily factor,
// the US regions every hour (EIA-930). Values as published; only unit conversions.

import { useFile } from "../app/data";
import { US_CO2_REGION, type LiveCo2File, type UsCo2File } from "../lib/liveCo2";
import { Card } from "./CountryCards";
import { Big, Lines } from "./LiveCards";

const muted = "text-[#8d94a1]";
const CO2: [number, number, number] = [120, 200, 160];
const hhmm = (t: string) => t.replace("T", " ").slice(5, 16);

export function OperatorCo2Card({ iso }: { iso: string }) {
  const f = useFile<LiveCo2File>(["FR", "ES", "IE"].includes(iso) ? "liveCo2" : null);
  if (!f) return null;
  if (iso === "FR" && f.fr?.series.length) {
    const s = f.fr.series;
    const last = s[s.length - 1];
    const vals = s.map((r) => r[1]);
    return (
      <Card title="CO₂ per kWh (RTE)" note={`éCO2mix · ${hhmm(last[0])}`} accent={CO2}>
        <div className="grid grid-cols-2 gap-1.5">
          <Big label="Now" value={`${last[1]} g`} sub="per kWh generated in France, RTE's estimate" />
          <Big label="Last 48 h" value={`${Math.min(...vals)}–${Math.max(...vals)} g`} sub="lowest – highest" />
        </div>
        <div className="mt-2">
          <Lines lines={[{ key: "g CO₂/kWh", color: CO2, values: vals }]} n={vals.length} label={(k) => hhmm(s[k][0])} unit="" />
        </div>
        <div className={`mt-1 text-[9px] ${muted}`}>
          Every 15 min, as RTE publishes it ({f.fr.source}, {f.fr.licence}).
        </div>
      </Card>
    );
  }
  if (iso === "ES" && f.es?.factor.length) {
    const s = f.es.factor.filter((r) => r[1] != null);
    const last = s[s.length - 1];
    const vals = s.map((r) => Math.round(r[1] * 1000));
    return (
      <Card title="CO₂ per kWh (REE)" note={`REData · ${last[0]}`} accent={CO2}>
        <div className="grid grid-cols-2 gap-1.5">
          <Big label={last[0]} value={`${Math.round(last[1] * 1000)} g`} sub="per kWh generated, the day so far (REE's factor)" />
          <Big label="Last 30 days" value={`${Math.min(...vals)}–${Math.max(...vals)} g`} sub="lowest – highest daily factor" />
        </div>
        <div className="mt-2">
          <Lines lines={[{ key: "g CO₂/kWh", color: CO2, values: vals }]} n={vals.length} label={(k) => s[k][0]} unit="" />
        </div>
        <div className={`mt-1 text-[9px] ${muted}`}>REE's daily emission factor of the national system, t CO₂-eq per MWh × 1000 ({f.es.licence}).</div>
      </Card>
    );
  }
  if (iso === "IE" && f.ie) {
    const roi = f.ie.series.ROI?.length ? "ROI" : "ALL";
    const s = f.ie.series[roi] ?? [];
    if (!s.length) return null;
    const last = s[s.length - 1];
    const vals = s.map((r) => r[1]);
    return (
      <Card title="CO₂ per kWh (EirGrid)" note={`Smart Grid Dashboard · ${last[0].slice(0, 17)}`} accent={CO2}>
        <div className="grid grid-cols-2 gap-1.5">
          <Big label="Now" value={`${last[1]} g`} sub={`per kWh, ${f.ie.regions[roi]}`} />
          <Big label="Last 24 h" value={`${Math.min(...vals)}–${Math.max(...vals)} g`} sub="lowest – highest" />
        </div>
        <div className="mt-2">
          <Lines lines={[{ key: "g CO₂/kWh", color: CO2, values: vals }]} n={vals.length} label={(k) => s[k][0].slice(0, 17)} unit="" />
        </div>
        <div className={`mt-1 text-[9px] ${muted}`}>Every 15 min, as EirGrid publishes it ({f.ie.licence}).</div>
      </Card>
    );
  }
  return null;
}

/** The US regions' CO₂ per kWh generated, newest hour EIA has the figure for. */
export function UsCo2RegionsCard() {
  const f = useFile<UsCo2File>("usCo2");
  if (!f) return null;
  const rows = Object.entries(f.regions)
    .map(([r, s]) => {
      const last = [...s].reverse().find((x) => x[1] != null);
      return last ? { r, t: last[0], g: Math.round((last[1] as number) * f.lb_to_g_kwh) } : null;
    })
    .filter((x): x is { r: string; t: string; g: number } => x != null)
    .sort((a, b) => a.g - b.g);
  if (!rows.length) return null;
  const top = Math.max(...rows.map((x) => x.g));
  return (
    <Card title="CO₂ per kWh generated" note={`EIA-930 · ${rows[0].t.replace("T", " ")} UTC`} accent={CO2}>
      <div className="space-y-0.5">
        {rows.map((x) => (
          <div key={x.r}>
            <div className="flex justify-between text-[11px] tabular-nums text-slate-200">
              <span>{US_CO2_REGION[x.r] ?? x.r}</span>
              <span>{x.g} g</span>
            </div>
            <div className="mt-0.5 h-[3px] rounded-full bg-white/[0.06]">
              <div className="h-full rounded-full" style={{ width: `${(x.g / top) * 100}%`, background: "rgb(120,200,160)" }} />
            </div>
          </div>
        ))}
      </div>
      <div className={`mt-1.5 text-[9px] ${muted}`}>
        EIA's hourly estimate from its fuel emission factors, lb per kWh × 453.592 = g per kWh; the newest hour each region has ({f.source}).
      </div>
    </Card>
  );
}
