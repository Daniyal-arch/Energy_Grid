import { useState } from "react";

import { stopColor } from "../lib/prices";
import { rgbCss } from "../lib/theme";
import { ACCESS_STOPS, NEM_NAME, latest, type AemoFile, type DataCentresFile, type WorldStatsFile } from "../lib/world";
import { Card } from "./CountryCards";

const muted = "text-[#8d94a1]";
const W = 300;
const AEST = new Intl.DateTimeFormat("en-GB", { timeZone: "Australia/Brisbane", hour: "2-digit", minute: "2-digit", day: "numeric", month: "short" });

/** Access to electricity: the world's share and the countries furthest behind. */
export function AccessCard({
  stats,
  names,
  onPick,
}: {
  stats: WorldStatsFile;
  names: (iso3: string) => string;
  onPick: (iso3: string) => void;
}) {
  const world = latest(stats.access.WLD, stats.years);
  const rows = Object.entries(stats.access)
    .filter(([code]) => code !== "WLD")
    .map(([code, s]) => ({ code, l: latest(s, stats.years) }))
    .filter((r): r is { code: string; l: { value: number; year: string } } => r.l != null)
    .sort((a, b) => a.l.value - b.l.value)
    .slice(0, 12);
  return (
    <Card title="Access to electricity" note="World Bank" accent={[222, 134, 66]}>
      {world && (
        <>
          <div className="text-[30px] font-light leading-none tabular-nums text-slate-100">{world.value.toFixed(1)} %</div>
          <div className={`mt-1 text-[10px] ${muted}`}>of the world's people had electricity in {world.year}</div>
        </>
      )}
      <div className={`mt-3 mb-1 text-[9px] uppercase tracking-[0.16em] ${muted}`}>Lowest access, newest year</div>
      <div className="space-y-[3px]">
        {rows.map((r) => (
          <button
            key={r.code}
            onClick={() => onPick(r.code)}
            className="flex w-full items-center gap-2 rounded px-1 text-left text-[11px] tabular-nums hover:bg-white/[0.05]"
          >
            <span className="w-[104px] truncate text-slate-300">{names(r.code)}</span>
            <span className="relative h-[6px] flex-1 overflow-hidden rounded-sm bg-white/[0.05]">
              <span
                className="absolute inset-y-0 left-0 rounded-sm"
                style={{ width: `${r.l.value}%`, background: rgbCss(stopColor(ACCESS_STOPS, r.l.value) ?? [90, 90, 90]) }}
              />
            </span>
            <span className="w-11 text-right text-slate-100">{Math.round(r.l.value)} %</span>
          </button>
        ))}
      </div>
    </Card>
  );
}

/** One country: its access over the years, mapped data centres, and Ember's newest year. */
export function WorldCountryCard({
  code,
  name,
  stats,
  dc,
  renewables,
}: {
  code: string;
  name: string;
  stats: WorldStatsFile | null;
  dc: DataCentresFile | null;
  renewables: { value: number; year: string } | null;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const series = stats?.access[code];
  const pts = (series ?? []).map((v, i) => [i, v] as const).filter((p): p is readonly [number, number] => p[1] != null);
  const n = stats?.years.length ?? 1;
  const x = (i: number) => (i / Math.max(1, n - 1)) * W;
  const y = (v: number) => 56 - (v / 100) * 52;
  const now = latest(series, stats?.years ?? []);
  const i = hover ?? (pts.length ? pts[pts.length - 1][0] : 0);
  const shown = series?.[i];
  return (
    <Card title={name} note={code}>
      <div className="grid grid-cols-2 gap-1.5">
        <div className="rounded-lg bg-white/[0.035] px-2.5 py-2">
          <div className={`text-[9px] uppercase tracking-[0.16em] ${muted}`}>Electricity access</div>
          <div className="text-[19px] font-light tabular-nums text-slate-100">{now ? `${now.value.toFixed(1)} %` : "–"}</div>
          <div className={`text-[9.5px] ${muted}`}>{now ? `of people, ${now.year}` : "no World Bank figure"}</div>
        </div>
        <div className="rounded-lg bg-white/[0.035] px-2.5 py-2">
          <div className={`text-[9px] uppercase tracking-[0.16em] ${muted}`}>Renewables</div>
          <div className="text-[19px] font-light tabular-nums text-slate-100">{renewables ? `${Math.round(renewables.value)} %` : "–"}</div>
          <div className={`text-[9.5px] ${muted}`}>{renewables ? `of generation, ${renewables.year} (Ember)` : "no Ember figure"}</div>
        </div>
        <div className="col-span-2 rounded-lg bg-white/[0.035] px-2.5 py-2">
          <div className={`text-[9px] uppercase tracking-[0.16em] ${muted}`}>Data centres mapped in OpenStreetMap</div>
          <div className="text-[19px] font-light tabular-nums text-slate-100">{dc?.by_country[code] ?? 0}</div>
          <div className={`text-[9.5px] ${muted}`}>a mapped subset, not a census</div>
        </div>
      </div>
      {pts.length > 1 && stats && (
        <>
          <div className={`mt-3 mb-1 flex justify-between text-[9px] uppercase tracking-[0.16em] ${muted}`}>
            <span>Access, % of people</span>
            <span className="normal-case tracking-normal text-slate-200">
              {stats.years[i]}: {shown != null ? `${shown.toFixed(1)} %` : "–"}
            </span>
          </div>
          <svg
            viewBox={`0 0 ${W} 60`}
            className="w-full touch-none"
            onPointerMove={(e) => {
              const r = e.currentTarget.getBoundingClientRect();
              setHover(Math.max(0, Math.min(n - 1, Math.round(((e.clientX - r.left) / r.width) * (n - 1)))));
            }}
            onPointerLeave={() => setHover(null)}
          >
            <line x1={0} x2={W} y1={y(100)} y2={y(100)} stroke="rgba(255,255,255,0.15)" strokeDasharray="2 3" />
            <path d={pts.map(([k, v], j) => `${j ? "L" : "M"}${x(k).toFixed(1)},${y(v).toFixed(1)}`).join("")} fill="none" stroke="#de8642" strokeWidth={1.6} />
            {shown != null && <circle cx={x(i)} cy={y(shown)} r={2.6} fill="#f1f5f9" />}
          </svg>
          <div className={`flex justify-between text-[9px] ${muted}`}>
            <span>{stats.years[0]}</span>
            <span>{stats.years[stats.years.length - 1]}</span>
          </div>
        </>
      )}
    </Card>
  );
}

/** Australia's National Electricity Market, the latest 5-minute dispatch. */
export function NemCard({ aemo }: { aemo: AemoFile }) {
  const regions = Object.entries(aemo.regions);
  return (
    <Card title="Australia · live" note={`AEMO · ${AEST.format(new Date(aemo.settlement))} AEST`} accent={[120, 222, 255]}>
      <div className={`mb-1 grid grid-cols-[1fr_72px_64px] text-[9px] uppercase tracking-[0.14em] ${muted}`}>
        <span>Region</span>
        <span className="text-right">Price</span>
        <span className="text-right">Demand</span>
      </div>
      <div className="space-y-0.5">
        {regions.map(([id, r]) => (
          <div key={id} className="grid grid-cols-[1fr_72px_64px] text-[11px] tabular-nums text-slate-200">
            <span className="truncate">{NEM_NAME[id] ?? id}</span>
            <span className="text-right">{r.price != null ? `${Math.round(r.price)} A$` : "–"}</span>
            <span className="text-right">{r.demand != null ? `${(r.demand / 1000).toFixed(1)} GW` : "–"}</span>
          </div>
        ))}
      </div>
      <div className={`mt-3 mb-1 text-[9px] uppercase tracking-[0.14em] ${muted}`}>Interconnectors</div>
      <div className="space-y-0.5">
        {aemo.interconnectors.map((c) => {
          const there = (c.mw ?? 0) >= 0;
          return (
            <div key={c.id} className="flex justify-between text-[11px] tabular-nums text-slate-200">
              <span>
                {there ? c.from : c.to} <span className={muted}>→</span> {there ? c.to : c.from} <span className={muted}>· {c.id}</span>
              </span>
              <span>{c.mw != null ? `${Math.abs(Math.round(c.mw))} MW` : "–"}</span>
            </div>
          );
        })}
      </div>
      <div className={`mt-2 text-[10px] ${muted}`}>Price per MWh in Australian dollars, the 5-minute dispatch price.</div>
    </Card>
  );
}

/** OpenStreetMap's mapped data centres: how many, and where most are mapped. */
export function DataCentresCard({ dc, names }: { dc: DataCentresFile; names: (iso3: string) => string }) {
  const top = Object.entries(dc.by_country).slice(0, 8);
  const max = Math.max(1, ...top.map(([, n]) => n));
  return (
    <Card title="Data centres" note="OpenStreetMap" accent={[196, 150, 255]}>
      <div className="text-[26px] font-light leading-none tabular-nums text-slate-100">{dc.count.toLocaleString("en-US")}</div>
      <div className={`mt-1 text-[10px] ${muted}`}>sites mapped worldwide. OSM is incomplete: counts follow mapping effort, not capacity.</div>
      <div className="mt-2.5 space-y-[3px]">
        {top.map(([code, n]) => (
          <div key={code} className="flex items-center gap-2 text-[11px] tabular-nums">
            <span className="w-[104px] truncate text-slate-300">{names(code)}</span>
            <span className="relative h-[6px] flex-1 overflow-hidden rounded-sm bg-white/[0.05]">
              <span className="absolute inset-y-0 left-0 rounded-sm" style={{ width: `${(n / max) * 100}%`, background: "rgb(196,150,255)" }} />
            </span>
            <span className="w-10 text-right text-slate-100">{n}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}
