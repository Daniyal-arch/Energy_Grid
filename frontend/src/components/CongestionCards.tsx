// Redispatch and congestion: ENTSO-E's redispatch, countertrading and costs per country, NESO's
// constraint costs for GB, CAISO's curtailment for California. Monthly sums, computed and labelled.

import { useFile } from "../app/data";
import { lastMonths, type CongestionFile } from "../lib/congestion";
import { Card } from "./CountryCards";

const muted = "text-[#8d94a1]";
const ACC: [number, number, number] = [230, 150, 90];
const gwh = (mwh: number) => (Math.abs(mwh) >= 1000 ? `${(mwh / 1000).toLocaleString("en-US", { maximumFractionDigits: 1 })} GWh` : `${Math.round(mwh)} MWh`);
const money = (v: number, cur: string) => `${cur}${(v / 1e6).toLocaleString("en-US", { maximumFractionDigits: 1 })} M`;

function Bars({ rows, fmt }: { rows: [string, number][]; fmt: (v: number) => string }) {
  const top = Math.max(1, ...rows.map((r) => Math.abs(r[1])));
  return (
    <div className="space-y-0.5">
      {rows.map(([m, v]) => (
        <div key={m} className="grid grid-cols-[3.2rem_1fr_4.6rem] items-center gap-1.5 text-[10px] tabular-nums text-slate-300">
          <span className={muted}>{m}</span>
          <span className="h-[3px] rounded-full bg-white/[0.06]">
            <span className="block h-full rounded-full" style={{ width: `${(Math.abs(v) / top) * 100}%`, background: "rgb(230,150,90)" }} />
          </span>
          <span className="text-right">{fmt(v)}</span>
        </div>
      ))}
    </div>
  );
}

export function CongestionCard({ iso }: { iso: string }) {
  const f = useFile<CongestionFile>("congestion");
  if (!f) return null;
  if (iso === "GB" && f.gb) {
    const rows = Object.entries(f.gb.months).sort((a, b) => a[0].localeCompare(b[0])).slice(-12);
    const cost = rows.map(([m, d]) => [m, Object.entries(d).filter(([k]) => k.endsWith("cost")).reduce((a, [, v]) => a + v, 0)] as [string, number]);
    return (
      <Card title="Constraint costs" note="NESO · monthly" accent={ACC}>
        <Bars rows={cost} fmt={(v) => money(v, "£")} />
        <div className={`mt-1.5 text-[9px] ${muted}`}>Thermal, voltage, inertia and largest-loss constraint costs, daily figures summed per month (computed). {f.gb.source} ({f.gb.licence}).</div>
      </Card>
    );
  }
  const c = f.entsoe?.countries[iso];
  if (!c) return null;
  const red = lastMonths({ ...(c.redispatch_internal?.by_direction ?? {}) });
  const cross = lastMonths(c.redispatch_cross_border?.by_direction);
  const ct = lastMonths(c.countertrading?.by_direction);
  const costs = c.costs ? Object.entries(c.costs.months).sort((a, b) => a[0].localeCompare(b[0])).slice(-12) : [];
  return (
    <Card title="Redispatch and congestion" note="ENTSO-E · monthly" accent={ACC}>
      {red.length > 0 && (
        <>
          <div className={`mb-1 text-[10px] uppercase tracking-wide ${muted}`}>Redispatch inside the country</div>
          <Bars rows={red} fmt={gwh} />
        </>
      )}
      {cross.length > 0 && (
        <>
          <div className={`mb-1 mt-2 text-[10px] uppercase tracking-wide ${muted}`}>Cross-border redispatch</div>
          <Bars rows={cross} fmt={gwh} />
        </>
      )}
      {ct.length > 0 && (
        <>
          <div className={`mb-1 mt-2 text-[10px] uppercase tracking-wide ${muted}`}>Countertrading</div>
          <Bars rows={ct} fmt={gwh} />
        </>
      )}
      {costs.length > 0 && (
        <>
          <div className={`mb-1 mt-2 text-[10px] uppercase tracking-wide ${muted}`}>Costs of congestion management</div>
          <Bars rows={costs} fmt={(v) => money(v, "€")} />
        </>
      )}
      <div className={`mt-1.5 text-[9px] ${muted}`}>
        MWh = the published MW × each interval's length, up and down summed per month (computed); costs as published, summed per month. {f.entsoe?.source}.
      </div>
    </Card>
  );
}

export function UsCurtailmentCard() {
  const f = useFile<CongestionFile>("congestion");
  if (!f?.caiso) return null;
  const rows = Object.entries(f.caiso.months).sort((a, b) => a[0].localeCompare(b[0])).slice(-12);
  const total = rows.map(([m, d]) => [m, Object.values(d).reduce((a, v) => a + v, 0)] as [string, number]);
  const solar = rows.reduce((a, [, d]) => a + (d.solar_local_mwh ?? 0) + (d.solar_system_mwh ?? 0), 0);
  const wind = rows.reduce((a, [, d]) => a + (d.wind_local_mwh ?? 0) + (d.wind_system_mwh ?? 0), 0);
  return (
    <Card title="Wind and solar curtailed, California" note="CAISO · monthly" accent={ACC}>
      <Bars rows={total} fmt={gwh} />
      <div className={`mt-1.5 text-[10px] text-slate-300`}>
        These months: solar {gwh(solar)}, wind {gwh(wind)}
      </div>
      <div className={`mt-1 text-[9px] ${muted}`}>5-minute curtailment (MW) × 5/60, summed per month (computed); local and system reasons together. {f.caiso.source}.</div>
    </Card>
  );
}
