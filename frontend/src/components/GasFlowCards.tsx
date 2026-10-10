// Gas flows (ENTSOG): one country's gas in and out, and where Europe's gas comes from.
// Values are the file's own (sums of the operators' reports, scripts/fetch_entsog.py); the
// totals here are sums over pairs, said so on the card.

import { rgbCss } from "../lib/theme";
import { GAS_FLOW, countryFlows, endName, gwhd, latestOf, sumSeries, type GasFlowsFile } from "../lib/gasFlows";
import { Card } from "./CountryCards";

const muted = "text-[#8d94a1]";
const W = 300;
const AMBER = rgbCss(GAS_FLOW);
const OUT = "#8fb7ff";

const twh = (v: number) => `${(v / 1000).toLocaleString("en-US", { maximumFractionDigits: 1, minimumFractionDigits: 1 })} TWh`;
const sum = (v: (number | null)[]) => v.reduce<number>((a, x) => a + (x ?? 0), 0);

function Lines({ series, colors, days }: { series: (number | null)[][]; colors: string[]; days: string[] }) {
  const top = Math.max(1, ...series.flat().map((v) => v ?? 0));
  const n = days.length;
  const x = (i: number) => (i / Math.max(1, n - 1)) * W;
  const y = (v: number) => 60 - (v / top) * 56;
  return (
    <>
      <svg viewBox={`0 0 ${W} 62`} className="mt-2 w-full">
        {series.map((s, k) => {
          let d = "";
          s.forEach((v, i) => {
            if (v != null) d += `${d ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
          });
          return <path key={k} d={d} fill="none" stroke={colors[k]} strokeWidth={1.4} />;
        })}
      </svg>
      <div className={`flex justify-between text-[9px] ${muted}`}>
        <span>{days[0]}</span>
        <span>max {gwhd(top)}</span>
        <span>{days[n - 1]}</span>
      </div>
    </>
  );
}

/** A country's gas in and out on the newest gas day, per neighbour or source, and 31 days. */
export function GasInOutCard({ file, iso, countryName }: { file: GasFlowsFile; iso: string; countryName: (iso: string) => string }) {
  const rows = countryFlows(file, iso);
  const n = file.days.length;
  const inflow = sumSeries(
    rows.map((r) => r.inflow),
    n,
  );
  const outflow = sumSeries(
    rows.map((r) => r.outflow),
    n,
  );
  const list = rows
    .map((r) => ({ ...r, now: latestOf(r.net) }))
    .filter((r) => r.now != null && Math.abs(r.now) >= 0.5)
    .sort((a, b) => Math.abs(b.now!) - Math.abs(a.now!));
  const inNow = latestOf(inflow);
  const outNow = latestOf(outflow);
  return (
    <Card title="Gas in and out" note={`ENTSOG · ${file.gas_day}`} accent={GAS_FLOW}>
      <div className="flex items-end justify-between">
        <div>
          <div className="text-[22px] font-light leading-none tabular-nums text-slate-100">{gwhd(inNow)}</div>
          <div className={`mt-1 text-[10px] ${muted}`}>in · out {gwhd(outNow)}</div>
        </div>
        <div className="text-right text-[10px] tabular-nums">
          {inNow != null && outNow != null && (
            <div className="text-slate-200">
              net {inNow - outNow >= 0 ? "in" : "out"} {gwhd(Math.abs(inNow - outNow))}
            </div>
          )}
        </div>
      </div>
      {list.length > 0 && (
        <div className="mt-2 space-y-0.5">
          {list.slice(0, 10).map((r) => (
            <div key={`${r.pair.a}-${r.pair.b}`} className="flex justify-between text-[11px] tabular-nums">
              <span className="truncate text-slate-200">
                {r.now! > 0 ? "from " : "to "}
                {endName(r.other, file, countryName, iso)}
              </span>
              <span style={{ color: r.now! > 0 ? AMBER : OUT }}>{gwhd(Math.abs(r.now!))}</span>
            </div>
          ))}
        </div>
      )}
      <Lines series={[inflow, outflow]} colors={[AMBER, OUT]} days={file.days} />
      <div className={`mt-1 text-[9.5px] leading-snug ${muted}`}>
        <span style={{ color: AMBER }}>in</span> and <span style={{ color: OUT }}>out</span>, sum over the borders, sources and LNG terminals listed (computed). Each border is
        the sum of one side's operators' reports, the importing side; storage and domestic production are not included.
      </div>
    </Card>
  );
}

/** Pipeline sources outside Europe and LNG, newest gas day and the last 30 gas days. */
export function GasSourcesCard({ file }: { file: GasFlowsFile }) {
  const groups = new Map<string, (number | null)[][]>();
  for (const p of file.pairs) {
    if (p.kind === "border") continue;
    const key = p.kind === "lng" ? "LNG" : p.a;
    groups.set(key, [...(groups.get(key) ?? []), p.net]);
  }
  const n = file.days.length;
  const last30 = (s: (number | null)[]) => s.slice(Math.max(0, n - 30));
  const rows = [...groups.entries()]
    .map(([key, series]) => {
      const s = sumSeries(series, n);
      return { key, name: file.nodes[key] ?? key, now: latestOf(s), month: sum(last30(s)) };
    })
    .filter((r) => Math.abs(r.month) >= 1)
    .sort((a, b) => b.month - a.month);
  const into = rows.filter((r) => r.month > 0);
  const away = rows.filter((r) => r.month < 0);
  const total = into.reduce((a, r) => a + (r.now ?? 0), 0);
  const top = Math.max(1, ...into.map((r) => r.now ?? 0));
  return (
    <Card title="Where Europe's gas comes from" note={`ENTSOG · ${file.gas_day}`} accent={GAS_FLOW}>
      <div className="text-[22px] font-light leading-none tabular-nums text-slate-100">{gwhd(total)}</div>
      <div className={`mt-1 text-[10px] ${muted}`}>into the mapped countries by pipeline from outside and from LNG terminals (sum of the sources listed)</div>
      <div className="mt-2 grid grid-cols-[1fr_auto_auto] gap-x-2 gap-y-0.5 text-[11px] tabular-nums">
        <span className={`text-[9px] ${muted}`} />
        <span className={`text-right text-[9px] ${muted}`}>gas day</span>
        <span className={`text-right text-[9px] ${muted}`}>30 days</span>
        {into.map((r) => (
          <div key={r.key} className="contents">
            <span className="relative truncate text-slate-200">
              <span className="absolute inset-y-[3px] left-0 rounded-sm opacity-25" style={{ width: `${((r.now ?? 0) / top) * 100}%`, background: AMBER }} />
              <span className="relative">{r.name}</span>
            </span>
            <span className="text-right text-slate-100">{gwhd(r.now)}</span>
            <span className={`text-right ${muted}`}>{twh(r.month)}</span>
          </div>
        ))}
      </div>
      {away.length > 0 && (
        <div className={`mt-2 text-[10px] ${muted}`}>
          Out of Europe:{" "}
          {away.map((r, i) => (
            <span key={r.key}>
              {i ? " · " : ""}
              {r.name} {gwhd(Math.abs(r.now ?? 0))}
            </span>
          ))}
        </div>
      )}
      <div className={`mt-1.5 text-[9.5px] leading-snug ${muted}`}>
        Net physical flow per source, summed over its entry points; 30 days = sum of the last 30 gas days (computed). Sources are named by the neighbouring system, with the origin
        ENTSOG gives the point. Domestic production and storage withdrawals are not included.
      </div>
    </Card>
  );
}
