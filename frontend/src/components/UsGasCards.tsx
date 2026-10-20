// Gas on the US side (scripts/fetch_us_gas.py): EIA's weekly storage against its five-year range,
// the Henry Hub spot price, and citygate prices per state. Values as EIA publishes them.

import { useFile } from "../app/data";
import type { UsGasFile, UsGasSeries } from "../lib/usGas";
import { Card } from "./CountryCards";

const muted = "text-[#8d94a1]";
const LINE = "rgb(255,196,96)";

const last = (s?: UsGasSeries | null) => s?.points[s.points.length - 1];

function Spark({ s, days }: { s: UsGasSeries; days: number }) {
  const pts = s.points.slice(-days);
  if (pts.length < 2) return null;
  const vs = pts.map((p) => p[1]);
  const lo = Math.min(...vs);
  const hi = Math.max(...vs);
  const d = pts.map((p, i) => `${i ? "L" : "M"}${((i / (pts.length - 1)) * 100).toFixed(1)},${(30 - ((p[1] - lo) / (hi - lo || 1)) * 28).toFixed(1)}`).join("");
  return (
    <svg viewBox="0 0 100 32" preserveAspectRatio="none" className="mt-1 h-8 w-full">
      <path d={d} fill="none" stroke={LINE} strokeWidth="1.2" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

export function UsGasCard() {
  const f = useFile<UsGasFile>("usGas");
  if (!f) return null;
  const regions = Object.values(f.storage).sort((a, b) => (last(b)?.[1] ?? 0) - (last(a)?.[1] ?? 0));
  const l48 = regions.find((s) => /lower 48/i.test(s.name)) ?? regions[0];
  const n = last(l48);
  const range = n && l48.range_5y?.[n[0]];
  const prev = l48 && l48.points.length > 1 ? l48.points[l48.points.length - 2] : undefined;
  const hh = f.henry_hub;
  const h = last(hh);
  const gates = Object.values(f.citygate)
    .map((s) => ({ s, p: last(s) }))
    .filter((r) => r.p && !/U\.S\./.test(r.s.name))
    .sort((a, b) => (b.p?.[1] ?? 0) - (a.p?.[1] ?? 0));
  return (
    <Card title="Gas" note={`EIA · ${f.fetched.slice(0, 10)}`} accent={[255, 196, 96]}>
      {n && (
        <>
          <div className="text-[22px] font-light text-slate-50">
            {n[1].toLocaleString("en-US")} {l48.unit} <span className={`text-[11px] ${muted}`}>{l48.name}, week of {n[0]}</span>
          </div>
          <div className={`text-[10.5px] ${muted}`}>
            {prev ? `${n[1] - prev[1] >= 0 ? "+" : ""}${(n[1] - prev[1]).toLocaleString("en-US")} on the week (computed)` : ""}
            {range ? ` · five-year range ${range[0].toLocaleString("en-US")}–${range[1].toLocaleString("en-US")}` : ""}
          </div>
          <div className="mt-2 space-y-[2px] text-[10.5px]">
            {regions.filter((s) => s !== l48).map((s) => (
              <div key={s.name} className="flex justify-between gap-2">
                <span className={`truncate ${muted}`}>{s.name}</span>
                <span className="tabular-nums text-slate-200">{last(s)?.[1].toLocaleString("en-US")}</span>
              </div>
            ))}
          </div>
        </>
      )}
      {hh && h && (
        <>
          <div className="mt-3 flex items-baseline justify-between text-[11px]">
            <span className="text-slate-200">Henry Hub spot</span>
            <span className="tabular-nums text-slate-50">
              {h[1].toFixed(2)} {hh.unit} <span className={muted}>{h[0]}</span>
            </span>
          </div>
          <Spark s={hh} days={365} />
        </>
      )}
      {gates.length > 0 && (
        <div className="mt-2 text-[10.5px]">
          <div className={`mb-0.5 text-[9px] uppercase tracking-[0.14em] ${muted}`}>Citygate price, highest states</div>
          {gates.slice(0, 5).map(({ s, p }) => (
            <div key={s.name} className="flex justify-between gap-2">
              <span className={`truncate ${muted}`}>{s.name}</span>
              <span className="tabular-nums text-slate-200">
                {p?.[1].toFixed(2)} {s.unit} <span className={muted}>{p?.[0]}</span>
              </span>
            </div>
          ))}
        </div>
      )}
      <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
        {f.source}. Storage: working gas, weekly; {f.range_note}. EIA publishes no regional hub price besides Henry Hub as open data; the citygate price is what distribution
        companies pay, monthly.
      </div>
    </Card>
  );
}
