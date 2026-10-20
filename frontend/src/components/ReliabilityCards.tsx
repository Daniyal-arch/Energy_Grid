// United States, reliability and demand: OE-417 disturbance events (the "US power outages"
// layer's card) and FERC 714 planning-area demand (the US region card). Counts and daily means
// are computed and say so.

import { useState, type ReactNode } from "react";

import { useFile } from "../app/data";
import { Card } from "./CountryCards";

const muted = "text-[#8d94a1]";
const Note = ({ children }: { children: ReactNode }) => <div className={`mt-2 text-[10px] leading-snug ${muted}`}>{children}</div>;

export interface Oe417File {
  fetched: string;
  source: string;
  years: number[];
  states: Record<string, Record<string, number>>;
  types: Record<string, Record<string, number>>;
  /** [began, area, event type, demand loss MW, customers] */
  recent: [string, string | null, string | null, number | null, number | null][];
}
export interface Ferc714File {
  fetched: string;
  year: number;
  start: string;
  source: string;
  computed: string;
  areas: Record<string, { name: string | null; ba: string | null; region: string | null; daily_mw: (number | null)[] }>;
}

export function Oe417Card({ state }: { state?: string }) {
  const f = useFile<Oe417File>("oe417");
  if (!f) return null;
  const last = String(f.years[f.years.length - 1]);
  const types = Object.entries(f.types[last] ?? {}).sort((a, b) => b[1] - a[1]);
  const total = types.reduce((a, [, n]) => a + n, 0);
  const topStates = Object.entries(f.states)
    .map(([s, by]) => [s, by[last] ?? 0] as const)
    .filter(([, n]) => n > 0)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8);
  return (
    <Card title="Electric disturbances" note={`DOE OE-417 · ${last}`} accent={[230, 120, 80]}>
      <div className="text-[22px] font-light text-slate-50">
        {(state ? (f.states[state]?.[last] ?? 0) : total).toLocaleString("en-US")}{" "}
        <span className={`text-[11px] ${muted}`}>events reported in {last}{state ? ` naming ${state}` : ""} (count, computed)</span>
      </div>
      <div className="mt-1 space-y-0.5">
        {types.slice(0, 6).map(([t, n]) => (
          <div key={t} className="flex justify-between gap-2 text-[11px]">
            <span className="truncate text-slate-300">{t}</span>
            <span className="tabular-nums text-slate-100">{n}</span>
          </div>
        ))}
      </div>
      {!state && <div className={`mt-1 text-[10px] ${muted}`}>Most named: {topStates.map(([s, n]) => `${s} ${n}`).join(" · ")}</div>}
      <div className="mt-2 space-y-0.5">
        {f.recent.slice(0, 5).map((e, i) => (
          <div key={i} className="text-[10.5px] leading-snug">
            <span className="text-slate-200">{e[0]}</span> <span className={muted}>{e[2]}</span>
            <div className={`truncate ${muted}`}>
              {e[1]}
              {e[4] != null ? ` · ${e[4].toLocaleString("en-US")} customers` : ""}
              {e[3] != null ? ` · ${e[3].toLocaleString("en-US")} MW` : ""}
            </div>
          </div>
        ))}
      </div>
      <Note>Utilities' and grid operators' reports to DOE within hours of an event, as the annual summaries publish them; states matched from the area text (computed), an event naming several states counts in each.</Note>
    </Card>
  );
}

/** A small line of daily values (SVG), gaps where a day has no value. */
function Spark({ values, h = 44 }: { values: (number | null)[]; h?: number }) {
  const v = values.filter((x): x is number => x != null);
  if (!v.length) return null;
  const lo = Math.min(...v);
  const hi = Math.max(...v);
  const W = 300;
  let d = "";
  values.forEach((x, i) => {
    if (x == null) return;
    const px = (i / Math.max(1, values.length - 1)) * W;
    const py = h - 2 - ((x - lo) / Math.max(1, hi - lo)) * (h - 4);
    d += `${d && values[i - 1] != null ? "L" : "M"}${px.toFixed(1)},${py.toFixed(1)}`;
  });
  return (
    <svg viewBox={`0 0 ${W} ${h}`} className="mt-1 h-11 w-full" preserveAspectRatio="none">
      <path d={d} fill="none" stroke="rgb(120,222,255)" strokeWidth={1.2} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

export function Ferc714Card({ region }: { region: string }) {
  const f = useFile<Ferc714File>("ferc714");
  const areas = f ? Object.entries(f.areas).filter(([, a]) => region === "US48" || a.region === region) : [];
  const ranked = areas
    .map(([id, a]) => {
      const v = a.daily_mw.filter((x): x is number => x != null);
      return { id, a, mean: v.reduce((s, x) => s + x, 0) / Math.max(1, v.length), peak: Math.max(...v) };
    })
    .sort((p, q) => q.mean - p.mean);
  const [pick, setPick] = useState<string | null>(null);
  if (!f || !ranked.length) return null;
  const sel = ranked.find((r) => r.id === pick) ?? ranked[0];
  return (
    <Card title="Demand per planning area" note={`FERC Form 714 · ${f.year}`} accent={[120, 222, 255]}>
      <select value={sel.id} onChange={(e) => setPick(e.target.value)} className="mb-1 w-full rounded bg-white/[0.06] px-2 py-1 text-[11px] text-slate-200">
        {ranked.map((r) => (
          <option key={r.id} value={r.id}>
            {r.a.name ?? r.id}
            {r.a.ba ? ` (${r.a.ba})` : ""}
          </option>
        ))}
      </select>
      <div className="flex justify-between text-[11px] tabular-nums">
        <span className="text-slate-300">Average of the daily means</span>
        <span className="text-slate-100">{Math.round(sel.mean).toLocaleString("en-US")} MW</span>
      </div>
      <div className="flex justify-between text-[11px] tabular-nums">
        <span className="text-slate-300">Highest daily mean</span>
        <span className="text-slate-100">{Math.round(sel.peak).toLocaleString("en-US")} MW</span>
      </div>
      <Spark values={sel.a.daily_mw} />
      <Note>
        Daily mean of the hourly demand each planning area reports to FERC ({f.year}, computed; PUDL's imputed values not used). {region === "US48" ? "All planning areas" : `Planning areas whose balancing authority EIA places in this region`}; a utility
        without its own balancing authority is listed under the whole country only.
      </Note>
    </Card>
  );
}

/** World Bank Doing Business SAIDI and SAIFI (scripts/fetch_reliability.py). */
export interface ReliabilityFile {
  source: string;
  fetched: string;
  units: { saidi: string; saifi: string };
  note: string;
  countries: Record<string, { saidi?: [number, number][]; saifi?: [number, number][] }>;
}

/** Power cuts in one country: SAIDI and SAIFI per year, as the World Bank published them. */
export function PowerCutsCard({ iso2 }: { iso2: string }) {
  const f = useFile<ReliabilityFile>("reliability");
  const c = f?.countries[iso2];
  if (!f || !c?.saidi?.length) return null;
  const top = Math.max(...c.saidi.map((p) => p[1]), 0.01);
  const lastD = c.saidi[c.saidi.length - 1];
  const lastF = c.saifi?.[c.saifi.length - 1];
  return (
    <Card title="Power cuts" note={`World Bank · ${c.saidi[0][0]}–${lastD[0]}`}>
      <div className="text-[22px] font-light text-slate-50">
        {lastD[1].toLocaleString("en-US")} h <span className={`text-[11px] ${muted}`}>without power per customer in {lastD[0]} (SAIDI)</span>
      </div>
      {lastF && <div className={`text-[10.5px] ${muted}`}>{lastF[1].toLocaleString("en-US")} interruptions per customer (SAIFI)</div>}
      <div className="mt-2 flex h-10 items-end gap-[3px]">
        {c.saidi.map(([y, v]) => (
          <div key={y} className="flex-1 rounded-t-sm" title={`${y}: ${v} h`} style={{ height: `${(100 * v) / top}%`, background: "rgb(240,160,126)" }} />
        ))}
      </div>
      <div className={`flex justify-between text-[9.5px] ${muted}`}>
        <span>{c.saidi[0][0]}</span>
        <span>{lastD[0]}</span>
      </div>
      <Note>
        {f.source}. {f.note}. No newer national series is published as data (CEER benchmarks are PDF tables).
      </Note>
    </Card>
  );
}
