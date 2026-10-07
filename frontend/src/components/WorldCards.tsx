import { useState } from "react";

import { stopColor } from "../lib/prices";
import { rgbCss } from "../lib/theme";
import { FUEL_COLOR, FUEL_LABEL, STACK_ORDER } from "../lib/energy";
import { ACCESS_STOPS, NEM_NAME, latest, type AemoFile, type DataCentresFile, type UsFile, type WorldStatsFile } from "../lib/world";
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
  monthly,
}: {
  code: string;
  name: string;
  stats: WorldStatsFile | null;
  dc: DataCentresFile | null;
  renewables: { value: number; year: string } | null;
  /** Ember's monthly shares of generation, last 24 months */
  monthly?: { months: string[]; renewables: (number | null)[]; wind_solar: (number | null)[] } | null;
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
      {monthly && <MonthlyShares {...monthly} />}
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

const UTC_HOUR = new Intl.DateTimeFormat("en-GB", { timeZone: "UTC", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
const hourLabel = (h: string) => `${UTC_HOUR.format(new Date(`${h}:00:00Z`))} UTC`;

/** The US grid (EIA-930): demand now, the generation mix and flows as EIA has published them. */
export function UsCard({ us }: { us: UsFile }) {
  const all = us.regions.US48;
  const regions = Object.entries(us.regions).filter(([id]) => id !== "US48");
  // the Lower-48 mix: the regions' newest mixes do not share one hour, so the card shows
  // the largest region-level mixes next to each other instead of adding them up
  const mixRows = regions
    .filter(([, r]) => r.mix)
    .sort((a, b) => (b[1].demand?.[1] ?? 0) - (a[1].demand?.[1] ?? 0));
  const pts = us.us48_demand;
  const max = Math.max(1, ...pts.map((p) => p[1]));
  const min = Math.min(...pts.map((p) => p[1]));
  const x = (i: number) => (i / Math.max(1, pts.length - 1)) * W;
  const y = (v: number) => 40 - ((v - min) / (max - min || 1)) * 36;
  return (
    <Card title="United States" note="EIA-930" accent={[255, 196, 120]}>
      {all?.demand && (
        <>
          <div className="text-[26px] font-light leading-none tabular-nums text-slate-100">{(all.demand[1] / 1000).toFixed(0)} GW</div>
          <div className={`mt-1 text-[10px] ${muted}`}>Lower-48 demand, {hourLabel(all.demand[0])}</div>
          {pts.length > 2 && (
            <svg viewBox={`0 0 ${W} 42`} className="mt-1.5 w-full" aria-label="Lower-48 demand, last 48 hours">
              <path d={pts.map(([, v], i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("")} fill="none" stroke="#ffc478" strokeWidth={1.4} />
            </svg>
          )}
        </>
      )}
      <div className={`mt-3 mb-1 text-[9px] uppercase tracking-[0.14em] ${muted}`}>Generation by source, per region</div>
      <div className="space-y-1">
        {mixRows.map(([id, r]) => {
          const parts = STACK_ORDER.map((g) => [g, r.mix?.mw[g] ?? 0] as [string, number]).filter(([, v]) => v > 0);
          const total = parts.reduce((a, [, v]) => a + v, 0) || 1;
          return (
            <div key={id} className="flex items-center gap-2 text-[10.5px] tabular-nums" title={`${r.name}, ${r.mix ? hourLabel(r.mix.hour) : ""}`}>
              <span className="w-10 text-slate-300">{id}</span>
              <div className="flex h-[7px] flex-1 overflow-hidden rounded-sm">
                {parts.map(([g, v]) => (
                  <div key={g} title={`${FUEL_LABEL[g] ?? g} ${Math.round(v).toLocaleString("en-US")} MW`} style={{ width: `${(v / total) * 100}%`, background: rgbCss(FUEL_COLOR[g] ?? FUEL_COLOR.other) }} />
                ))}
              </div>
              <span className="w-12 text-right text-slate-200">{r.demand ? `${(r.demand[1] / 1000).toFixed(0)} GW` : "–"}</span>
            </div>
          );
        })}
      </div>
      <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
        Bars: generation mix of EIA's newest hour per region (about a day behind). GW: demand now. Flows on the map:{" "}
        {us.flows.hour ? hourLabel(us.flows.hour) : "–"} (EIA publishes them about two days later).
      </div>
    </Card>
  );
}

/** Renewable and wind + solar share of generation, month by month (Ember). */
function MonthlyShares({ months, renewables, wind_solar }: { months: string[]; renewables: (number | null)[]; wind_solar: (number | null)[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const n = months.length;
  const x = (i: number) => (i / Math.max(1, n - 1)) * W;
  const y = (v: number) => 56 - (v / 100) * 52;
  const line = (vals: (number | null)[]) =>
    vals.map((v, i) => (v == null ? "" : `${i && vals[i - 1] != null ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`)).join("");
  const last = (() => {
    for (let i = n - 1; i >= 0; i--) if (renewables[i] != null) return i;
    return -1;
  })();
  const i = hover ?? last;
  if (last < 0) return null;
  const label = (m: string) => new Date(`${m}-15T12:00:00Z`).toLocaleDateString("en-GB", { month: "short", year: "2-digit" });
  return (
    <>
      <div className={`mt-3 mb-1 flex justify-between text-[9px] uppercase tracking-[0.16em] ${muted}`}>
        <span>Share of generation, by month</span>
        <span className="normal-case tracking-normal tabular-nums">
          <span className="text-[#5fd6b8]">{renewables[i] != null ? `${Math.round(renewables[i] as number)} % renewable` : "–"}</span>
          <span className="text-[#ffd648]"> · {wind_solar[i] != null ? `${Math.round(wind_solar[i] as number)} % wind+solar` : "–"}</span>
          <span className={muted}> · {label(months[i])}</span>
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
        <path d={line(renewables)} fill="none" stroke="#5fd6b8" strokeWidth={1.6} />
        <path d={line(wind_solar)} fill="none" stroke="#ffd648" strokeWidth={1.4} />
        <line x1={x(i)} x2={x(i)} y1={0} y2={60} stroke="rgba(255,255,255,0.35)" />
      </svg>
      <div className={`flex justify-between text-[9px] ${muted}`}>
        <span>{label(months[0])}</span>
        <span>Ember monthly</span>
        <span>{label(months[n - 1])}</span>
      </div>
    </>
  );
}
