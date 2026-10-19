import { useFile } from "../app/data";
import { useState } from "react";

import { Card } from "./CountryCards";

const muted = "text-[#8d94a1]";

export interface SedsFile {
  title: string;
  source: string;
  year: string;
  /** state postal code (and "USA") -> [item, value, unit, year] */
  rows: Record<string, [string, number, string, string][]>;
}

export interface SteoFile {
  fetched: string;
  source: string;
  /** months from this one (YYYY-MM) are STEO forecasts */
  forecast_from: string;
  series: Record<string, { name: string; unit: string; months: string[]; values: number[] }>;
}

/** EIA SEDS: a state's (or the US's) consumption and production by source, newest year. */
export function SedsCard({ f, names }: { f: SedsFile; names: (code: string) => string }) {
  const [state, setState] = useState("USA");
  const codes = ["USA", ...Object.keys(f.rows).filter((k) => k !== "USA" && k.length === 2).sort((a, b) => names(a).localeCompare(names(b)))];
  const rows = f.rows[state] ?? [];
  const util = useFile<{ year: string; utilities: Record<string, string>; states: Record<string, number> }>("usUtilities");
  const nUtil = util ? (state === "USA" ? Object.keys(util.utilities).length : util.states[state]) : undefined;
  return (
    <Card title="Energy by state" note={`EIA SEDS · ${f.year}`}>
      <select value={state} onChange={(e) => setState(e.target.value)} className="mb-2 w-full rounded bg-white/[0.06] px-2 py-1 text-[11px] text-slate-200">
        {codes.map((c) => (
          <option key={c} value={c}>
            {c === "USA" ? "United States" : names(c) || c}
          </option>
        ))}
      </select>
      <div className="space-y-0.5">
        {rows.map(([item, v, unit]) => (
          <div key={item} className="flex justify-between gap-2 text-[11px] tabular-nums">
            <span className="text-slate-300">{item}</span>
            <span className="text-slate-100">
              {Math.round(v).toLocaleString("en-US")} <span className={muted}>{unit}</span>
            </span>
          </div>
        ))}
      </div>
      {nUtil != null && (
        <div className="mt-1 flex justify-between gap-2 border-t border-white/[0.06] pt-1 text-[11px] tabular-nums">
          <span className="text-slate-300">Utilities reporting service (EIA-861, {util?.year})</span>
          <span className="text-slate-100">{nUtil.toLocaleString("en-US")}</span>
        </div>
      )}
      <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
        EIA State Energy Data System, as published (estimates for the newest year where EIA marks them so). Utilities: those reporting a service territory in the state (count, computed);
        "Check a site" names those serving its county.
      </div>
    </Card>
  );
}

/** EIA STEO: US generation and residential price, the last two years and the forecast. */
export function SteoCard({ f }: { f: SteoFile }) {
  const W = 300;
  const H = 70;
  return (
    <Card title="Short-term outlook" note="EIA STEO">
      {Object.entries(f.series).map(([id, s]) => {
        const k0 = s.months.findIndex((m) => m >= f.forecast_from);
        const lo = Math.min(...s.values);
        const hi = Math.max(...s.values);
        const x = (i: number) => (i / Math.max(1, s.values.length - 1)) * W;
        const y = (v: number) => 4 + ((hi - v) / (hi - lo || 1)) * (H - 8);
        const path = (a: number, b: number) =>
          s.values
            .slice(a, b)
            .map((v, j) => `${j ? "L" : "M"}${x(a + j).toFixed(1)},${y(v).toFixed(1)}`)
            .join("");
        const split = k0 < 0 ? s.values.length : k0;
        const last = s.values[split - 1];
        return (
          <div key={id} className="mb-2">
            <div className="flex justify-between text-[11px]">
              <span className="text-slate-200">{s.name}</span>
              <span className={`tabular-nums ${muted}`}>
                {last != null ? `${last.toLocaleString("en-US")} ${s.unit}` : ""} ({s.months[split - 1]})
              </span>
            </div>
            <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
              <path d={path(0, split)} fill="none" stroke="rgb(120,200,255)" strokeWidth={1} />
              {split < s.values.length && <path d={path(split - 1, s.values.length)} fill="none" stroke="rgb(190,196,210)" strokeWidth={1} strokeDasharray="3 2" />}
            </svg>
          </div>
        );
      })}
      <div className={`text-[10px] leading-snug ${muted}`}>
        Dashed: forecast (months from {f.forecast_from}, as EIA&apos;s Short-Term Energy Outlook gives them). Monthly values as published.
      </div>
    </Card>
  );
}
