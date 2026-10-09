// Installed capacity cards (IRENA): one country by technology, and the world's ranking.

import { useState } from "react";

import { FUEL_COLOR } from "../lib/energy";
import { IRENA_METRICS, formatGw, irenaValue, type IrenaFile, type IrenaMetricId } from "../lib/irena";
import { rgbCss, type RGB } from "../lib/theme";
import { Card } from "./CountryCards";

const muted = "text-[#8d94a1]";
const W = 300;
const TOTALS = new Set(["Total Renewable", "Total Non-Renewable"]);

/** IRENA's technology names -> the app's fuel colours */
function techColor(label: string): RGB {
  const l = label.toLowerCase();
  if (l.includes("solar")) return FUEL_COLOR.solar;
  if (l.includes("wind")) return FUEL_COLOR.wind;
  if (l.includes("pumped")) return FUEL_COLOR.storage;
  if (l.includes("hydro") || l.includes("marine")) return FUEL_COLOR.hydro;
  if (l.includes("nuclear")) return FUEL_COLOR.nuclear;
  if (l.includes("coal") || l.includes("peat")) return FUEL_COLOR.coal;
  if (l.includes("natural gas")) return FUEL_COLOR.gas;
  if (l.includes("oil") || l.includes("fossil")) return FUEL_COLOR.oil;
  if (l.includes("bio") || l.includes("waste")) return FUEL_COLOR.bio;
  if (l.includes("geothermal")) return [255, 140, 110];
  return FUEL_COLOR.other;
}

/** One country: capacity by technology in a year, and solar and wind since 2000. */
export function IrenaCountryCard({ f, iso3, year }: { f: IrenaFile; iso3: string; year?: string }) {
  const [hover, setHover] = useState<number | null>(null);
  const c = f.capacity_mw[iso3];
  if (!c) {
    return (
      <Card title="Installed capacity" note="IRENA">
        <div className={`text-[11px] ${muted}`}>IRENA has no capacity figures for this country.</div>
      </Card>
    );
  }
  const last = f.years.length - 1;
  const k0 = year ? Math.max(0, f.years.indexOf(year)) : last;
  const k = hover ?? k0;
  const label = (code: string) => f.techs[code] ?? code;
  const rows = Object.entries(c)
    .filter(([code]) => !TOTALS.has(label(code)))
    .map(([code, s]) => ({ code, name: label(code), mw: s[k] }))
    .filter((r): r is { code: string; name: string; mw: number } => r.mw != null && r.mw > 0)
    .sort((a, b) => b.mw - a.mw);
  const top = rows[0]?.mw ?? 1;
  const total = (name: string) => {
    const code = Object.keys(c).find((x) => label(x) === name);
    return code ? (c[code][k] ?? null) : null;
  };
  const series = IRENA_METRICS.map((m) => ({ m, values: f.years.map((_, y) => irenaValue(f, iso3, m, y)) }));
  const max = Math.max(1, ...series.flatMap((s) => s.values.map((v) => v ?? 0)));
  const H = 64;
  const x = (y: number) => (y / Math.max(1, last)) * W;
  const yv = (v: number) => H - (v / max) * H;
  return (
    <Card title="Installed capacity" note={`IRENA · ${f.years[k]}`} accent={[170, 210, 150]}>
      <div className="grid grid-cols-2 gap-1.5">
        {["Total Renewable", "Total Non-Renewable"].map((n) => (
          <div key={n} className="rounded-lg bg-white/[0.035] px-2.5 py-2">
            <div className={`text-[9px] uppercase tracking-[0.16em] ${muted}`}>{n.replace("Total ", "")}</div>
            <div className="text-[19px] font-light tabular-nums text-slate-100">{formatGw(total(n))}</div>
          </div>
        ))}
      </div>
      <div className="mt-2.5 space-y-1">
        {rows.slice(0, 10).map((r) => (
          <div key={r.code}>
            <div className="flex justify-between text-[11px] tabular-nums text-slate-200">
              <span className="truncate">{r.name}</span>
              <span>{formatGw(r.mw)}</span>
            </div>
            <div className="mt-0.5 h-[3px] rounded-full bg-white/[0.06]">
              <div className="h-full rounded-full" style={{ width: `${(r.mw / top) * 100}%`, background: rgbCss(techColor(r.name)) }} />
            </div>
          </div>
        ))}
      </div>
      <div className={`mt-3 mb-1 flex justify-between text-[9px] uppercase tracking-[0.14em] ${muted}`}>
        <span>Solar and wind since {f.years[0]}</span>
        <span className="normal-case tracking-normal text-slate-200">
          {f.years[k]}: {series.map((s) => `${s.m.id} ${formatGw(s.values[k])}`).join(" · ")}
        </span>
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full touch-none"
        onPointerMove={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          setHover(Math.max(0, Math.min(last, Math.round(((e.clientX - r.left) / r.width) * last))));
        }}
        onPointerLeave={() => setHover(null)}
      >
        {series.map((s) => (
          <path
            key={s.m.id}
            d={s.values.map((v, y) => (v == null ? "" : `${y && s.values[y - 1] != null ? "L" : "M"}${x(y).toFixed(1)},${yv(v).toFixed(1)}`)).join("")}
            fill="none"
            stroke={rgbCss(s.m.id === "solar" ? FUEL_COLOR.solar : FUEL_COLOR.wind)}
            strokeWidth={1.6}
          />
        ))}
        <line x1={x(k)} x2={x(k)} y1={0} y2={H} stroke="rgba(241,245,249,0.6)" strokeWidth={1} />
      </svg>
      <div className={`flex justify-between text-[9px] ${muted}`}>
        <span>{f.years[0]}</span>
        <span>{f.years[last]}</span>
      </div>
      <div className={`mt-2 text-[10px] ${muted}`}>
        IRENA's own technology categories (all grid connections). Wind = onshore + offshore (summed here).
      </div>
    </Card>
  );
}

/** Countries with the most of a metric installed in a year. */
export function IrenaRankingCard({
  f,
  year,
  names,
  onPick,
}: {
  f: IrenaFile;
  year?: string;
  names: (iso3: string) => string;
  onPick: (iso3: string) => void;
}) {
  const [metricId, setMetricId] = useState<IrenaMetricId>("solar");
  const m = IRENA_METRICS.find((x) => x.id === metricId)!;
  const k = year ? Math.max(0, f.years.indexOf(year)) : f.years.length - 1;
  const rows = Object.keys(f.capacity_mw)
    .map((iso) => ({ iso, mw: irenaValue(f, iso, m, k) }))
    .filter((r): r is { iso: string; mw: number } => r.mw != null && r.mw > 0)
    .sort((a, b) => b.mw - a.mw)
    .slice(0, 15);
  const top = rows[0]?.mw ?? 1;
  return (
    <Card title={`Most ${metricId} installed · ${f.years[k]}`} note="IRENA" accent={[170, 210, 150]}>
      <div className="mb-2 flex gap-1">
        {IRENA_METRICS.map((x) => (
          <button
            key={x.id}
            onClick={() => setMetricId(x.id)}
            className={`rounded border px-2 py-0.5 text-[10px] ${x.id === metricId ? "border-white/30 bg-white/15 text-slate-100" : "border-white/10 text-slate-400"}`}
          >
            {x.label}
          </button>
        ))}
      </div>
      <div className="space-y-[3px]">
        {rows.map((r) => (
          <button key={r.iso} onClick={() => onPick(r.iso)} className="flex w-full items-center gap-2 rounded px-1 text-left text-[11px] tabular-nums hover:bg-white/[0.05]">
            <span className="w-[96px] truncate text-slate-300">{names(r.iso)}</span>
            <span className="relative h-[6px] flex-1 overflow-hidden rounded-sm bg-white/[0.05]">
              <span
                className="absolute inset-y-0 left-0 rounded-sm"
                style={{ width: `${(r.mw / top) * 100}%`, background: rgbCss(metricId === "solar" ? FUEL_COLOR.solar : FUEL_COLOR.wind) }}
              />
            </span>
            <span className="w-16 text-right text-slate-100">{formatGw(r.mw)}</span>
          </button>
        ))}
      </div>
    </Card>
  );
}
