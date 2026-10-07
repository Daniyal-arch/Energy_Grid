// Country (and EU) cards for the side panel / phone sheet. Every value is passed
// through from a named source; the few derived numbers say so on the card.

import { useMemo, useState, type ReactNode } from "react";

import { EMBER_COLOR, EMBER_ORDER, FUEL_COLOR, FUEL_LABEL, STACK_ORDER, gw, power } from "../lib/energy";
import { rgbCss, type RGB } from "../lib/theme";

type Series = (number | null)[];

export interface NowFigures {
  ts: string;
  load_mw: number;
  renewable_share_of_generation: number | null;
  generation_mw: Record<string, number>;
}
export interface WeekFile {
  days: string[];
  start: string;
  step_s: number;
  load: Series;
  renewable_share: Series;
  generation: Record<string, Series>;
  prices: Record<string, Series>;
}
export interface GasRow {
  date: string;
  full: number | null;
  in_storage_twh: number | null;
  capacity_twh: number | null;
  trend_pp: number | null;
  series: [string, number | null][];
}
export interface EmberRow {
  years: string[];
  series: Record<string, Series>;
  renewable_pct: Series;
  intensity: Series;
}
export interface TradeRow {
  /** neighbour */
  other: string;
  /** MW, positive = import into the country */
  mw: number;
}

const ACCENT: RGB = [214, 168, 112];
const muted = "text-[#8d94a1]";

/** A card: thin coloured rule on the left, small-caps title, source note on the right. */
export function Card({
  title,
  note,
  accent = ACCENT,
  children,
}: {
  title: string;
  note?: ReactNode;
  accent?: RGB;
  children: ReactNode;
}) {
  return (
    <section className="relative overflow-hidden rounded-xl border border-white/[0.07] bg-[#0b0f16]/90 px-4 py-3">
      <span className="absolute inset-y-3 left-0 w-[2px] rounded-r" style={{ background: rgbCss(accent, 0.8) }} />
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-300">{title}</h3>
        {note && <span className={`truncate text-[9px] ${muted}`}>{note}</span>}
      </div>
      <div className="mt-2.5">{children}</div>
    </section>
  );
}

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg bg-white/[0.03] px-2.5 py-2">
      <div className={`text-[9px] uppercase tracking-[0.16em] ${muted}`}>{label}</div>
      <div className="mt-0.5 text-[19px] font-light tabular-nums text-slate-100">{value}</div>
      {sub && <div className={`text-[9px] ${muted}`}>{sub}</div>}
    </div>
  );
}

/** Right now: four tiles and the generation mix as one bar. */
export function NowCard({
  now,
  time,
  price,
  netMw,
  footnote,
}: {
  now: NowFigures;
  time: string;
  price?: { label: string; value: number } | null;
  netMw?: number | null;
  footnote?: string;
}) {
  const parts = STACK_ORDER.map((g) => [g, now.generation_mw[g] ?? 0] as [string, number]).filter(([, v]) => v > 0);
  const total = parts.reduce((a, [, v]) => a + v, 0) || 1;
  const top = [...parts].sort((a, b) => b[1] - a[1]).slice(0, 6);
  return (
    <Card title="Right now" note={time}>
      <div className="grid grid-cols-2 gap-1.5">
        <Tile label="Load" value={power(now.load_mw)} />
        <Tile
          label="Renewable"
          value={now.renewable_share_of_generation != null ? `${now.renewable_share_of_generation.toFixed(0)} %` : "–"}
          sub="share of generation"
        />
        {price && <Tile label="Day-ahead price" value={`${price.value.toFixed(0)} €`} sub={`per MWh · ${price.label}`} />}
        {netMw != null && (
          <Tile
            label={netMw >= 0 ? "Net import" : "Net export"}
            value={power(netMw)}
            sub="sum of measured border flows"
          />
        )}
      </div>
      <div className="mt-3 flex h-2.5 overflow-hidden rounded-full">
        {parts.map(([g, v]) => (
          <div key={g} title={`${FUEL_LABEL[g]} ${power(v)}`} style={{ width: `${(v / total) * 100}%`, background: rgbCss(FUEL_COLOR[g]) }} />
        ))}
      </div>
      <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1">
        {top.map(([g, v]) => (
          <div key={g} className="flex items-center justify-between gap-2 text-[11px] tabular-nums">
            <span className="flex min-w-0 items-center gap-1.5 text-slate-300">
              <span className="h-2 w-2 shrink-0 rounded-sm" style={{ background: rgbCss(FUEL_COLOR[g]) }} />
              <span className="truncate">{FUEL_LABEL[g]}</span>
            </span>
            <span className="text-slate-100">{Math.round((v / total) * 100)} %</span>
          </div>
        ))}
      </div>
      {footnote && <div className={`mt-2 text-[10px] ${muted}`}>{footnote}</div>}
    </Card>
  );
}

const W = 300;
const H = 104;

/** Last days: generation mix (stacked), price, or load, every 15 minutes. */
export function WeekCard({ week, marker }: { week: WeekFile; marker?: number | null }) {
  const [tab, setTab] = useState<"mix" | "price" | "load">("mix");
  const [hover, setHover] = useState<number | null>(null);
  const n = week.load.length;
  const x = (i: number) => (i / Math.max(1, n - 1)) * W;
  const stamp = (i: number) => new Date(Date.parse(week.start) + i * week.step_s * 1000);
  const fmt = new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/Berlin", weekday: "short", hour: "2-digit", minute: "2-digit" });
  const dayFmt = new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/Berlin", weekday: "short", day: "numeric" });

  const chart = useMemo(() => {
    if (tab === "mix") {
      const groups = STACK_ORDER.filter((g) => week.generation[g]);
      const base = new Array<number>(n).fill(0);
      let max = 1;
      for (let i = 0; i < n; i++) max = Math.max(max, groups.reduce((a, g) => a + (week.generation[g][i] ?? 0), 0));
      const y = (v: number) => H - (v / max) * H;
      const paths = groups.map((g) => {
        const top = base.map((b, i) => b + Math.max(0, week.generation[g][i] ?? 0));
        let d = `M${x(0)},${y(top[0])}`;
        for (let i = 1; i < n; i++) d += `L${x(i).toFixed(1)},${y(top[i]).toFixed(1)}`;
        for (let i = n - 1; i >= 0; i--) d += `L${x(i).toFixed(1)},${y(base[i]).toFixed(1)}`;
        for (let i = 0; i < n; i++) base[i] = top[i];
        return { d: `${d}Z`, color: FUEL_COLOR[g] ?? FUEL_COLOR.other, key: g };
      });
      return { paths, lines: [] as { d: string; color: RGB; key: string }[], max, min: 0, unit: "GW", y };
    }
    const cols = tab === "price" ? week.prices : { load: week.load };
    const values = Object.values(cols).flat().filter((v): v is number => v != null);
    const max = values.length ? Math.max(...values) : 1;
    const min = tab === "price" ? Math.min(0, ...values) : 0;
    const y = (v: number) => H - ((v - min) / (max - min || 1)) * H;
    const palette: RGB[] = [[120, 222, 255], [240, 179, 126], [196, 160, 255], [140, 230, 150], [255, 140, 170]];
    const lines = Object.entries(cols).map(([k, col], j) => {
      let d = "";
      col.forEach((v, i) => {
        if (v == null) return;
        d += `${d && col[i - 1] != null ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
      });
      return { d, color: palette[j % palette.length], key: k };
    });
    return { paths: [], lines, max, min, unit: tab === "price" ? "€/MWh" : "GW", y };
  }, [tab, week, n]);

  const readout = (() => {
    const i = hover ?? marker ?? n - 1;
    if (i < 0 || i >= n) return "";
    if (tab === "mix") {
      const total = STACK_ORDER.reduce((a, g) => a + (week.generation[g]?.[i] ?? 0), 0);
      return `${fmt.format(stamp(i))} · ${gw(total)} generated`;
    }
    if (tab === "load") return `${fmt.format(stamp(i))} · load ${power(week.load[i] ?? 0)}`;
    const zones = Object.entries(week.prices)
      .map(([z, col]) => (col[i] != null ? `${z} ${Math.round(col[i] as number)} €` : null))
      .filter(Boolean)
      .slice(0, 3)
      .join(" · ");
    return `${fmt.format(stamp(i))} · ${zones}`;
  })();

  const dayTicks = week.days.map((_, k) => Math.round((k * n) / week.days.length));
  return (
    <Card title={week.days.length > 1 ? `Last ${week.days.length} days` : "One day"} note="every 15 min · CET/CEST">
      <div className="mb-2 flex gap-1">
        {(["mix", "price", "load"] as const)
          .filter((t) => t !== "price" || Object.keys(week.prices).length > 0)
          .map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`rounded-full px-2.5 py-0.5 text-[10px] ${tab === t ? "bg-white/15 text-slate-100" : `${muted} hover:text-slate-200`}`}
            >
              {t === "mix" ? "Generation mix" : t === "price" ? "Price" : "Load"}
            </button>
          ))}
      </div>
      <div className={`mb-1 h-4 truncate text-[10px] tabular-nums ${muted}`}>{readout}</div>
      <svg
        viewBox={`0 0 ${W} ${H + 14}`}
        className="w-full touch-none"
        onPointerMove={(e) => {
          const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
          setHover(Math.max(0, Math.min(n - 1, Math.round(((e.clientX - r.left) / r.width) * (n - 1)))));
        }}
        onPointerLeave={() => setHover(null)}
      >
        {chart.min < 0 && <line x1={0} x2={W} y1={chart.y(0)} y2={chart.y(0)} stroke="rgba(255,255,255,0.25)" strokeDasharray="2 2" />}
        {chart.paths.map((p) => (
          <path key={p.key} d={p.d} fill={rgbCss(p.color, 0.85)} />
        ))}
        {chart.lines.map((l) => (
          <path key={l.key} d={l.d} fill="none" stroke={rgbCss(l.color)} strokeWidth={1.3} />
        ))}
        {dayTicks.map((i, k) => (
          <g key={k}>
            <line x1={x(i)} x2={x(i)} y1={0} y2={H} stroke="rgba(255,255,255,0.08)" />
            <text x={x(i) + 2} y={H + 11} fontSize={8} fill="#8d94a1">
              {dayFmt.format(stamp(i))}
            </text>
          </g>
        ))}
        {(hover ?? marker) != null && (
          <line x1={x((hover ?? marker) as number)} x2={x((hover ?? marker) as number)} y1={0} y2={H} stroke="#f1f5f9" strokeWidth={1} />
        )}
        <text x={W - 2} y={9} fontSize={8} fill="#8d94a1" textAnchor="end">
          {tab === "mix" || tab === "load" ? `${(chart.max / 1000).toFixed(0)} GW` : `${Math.round(chart.max)} €/MWh`}
        </text>
      </svg>
      {tab === "price" && Object.keys(week.prices).length > 1 && (
        <div className={`mt-1 flex flex-wrap gap-x-3 text-[9px] ${muted}`}>
          {chart.lines.map((l) => (
            <span key={l.key} className="flex items-center gap-1">
              <span className="h-[2px] w-3" style={{ background: rgbCss(l.color) }} />
              {l.key}
            </span>
          ))}
        </div>
      )}
    </Card>
  );
}

/** Measured physical flows now, imports to the left, exports to the right. */
export function TradeCard({ rows, time }: { rows: TradeRow[]; time: string }) {
  const max = Math.max(1, ...rows.map((r) => Math.abs(r.mw)));
  const sorted = [...rows].sort((a, b) => b.mw - a.mw);
  return (
    <Card title="Cross-border flows" note={time} accent={[120, 222, 255]}>
      <div className={`mb-1.5 flex justify-between text-[9px] uppercase tracking-[0.16em] ${muted}`}>
        <span>← import</span>
        <span>export →</span>
      </div>
      <div className="space-y-1">
        {sorted.map((r) => {
          const w = (Math.abs(r.mw) / max) * 50;
          const imp = r.mw > 0;
          return (
            <div key={r.other} className="grid grid-cols-[28px_1fr_52px] items-center gap-2 text-[11px] tabular-nums">
              <span className="text-slate-300">{r.other}</span>
              <div className="relative h-2">
                <div className="absolute inset-y-0 left-1/2 w-px bg-white/20" />
                <div
                  className="absolute inset-y-0 rounded-sm"
                  style={{
                    left: imp ? `${50 - w}%` : "50%",
                    width: `${w}%`,
                    background: imp ? "#f0b37e" : "#78deff",
                  }}
                />
              </div>
              <span className="text-right text-slate-200">{power(r.mw)}</span>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

/** Gas storage fill (GIE AGSI+): today, the last ~13 months, and the same day a year ago. */
export function GasCard({ gas }: { gas: GasRow }) {
  const pts = gas.series.filter((p): p is [string, number] => p[1] != null);
  const n = pts.length;
  const yearAgo = (() => {
    const t = Date.parse(gas.date) - 365 * 86_400_000;
    let best: [string, number] | null = null;
    for (const p of pts) if (!best || Math.abs(Date.parse(p[0]) - t) < Math.abs(Date.parse(best[0]) - t)) best = p;
    return best && Math.abs(Date.parse(best[0]) - t) < 4 * 86_400_000 ? best : null;
  })();
  const x = (i: number) => (i / Math.max(1, n - 1)) * W;
  const y = (v: number) => 60 - (v / 100) * 60;
  let d = "";
  pts.forEach(([, v], i) => (d += `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`));
  return (
    <Card title="Gas storage" note={`GIE AGSI+ · ${gas.date}`} accent={[255, 150, 92]}>
      <div className="flex items-end justify-between">
        <div>
          <div className="text-[26px] font-light leading-none tabular-nums text-slate-100">{gas.full?.toFixed(1)} %</div>
          <div className={`mt-1 text-[10px] ${muted}`}>
            {gas.in_storage_twh != null && gas.capacity_twh != null
              ? `${gas.in_storage_twh.toFixed(0)} of ${gas.capacity_twh.toFixed(0)} TWh working gas`
              : "of working gas volume"}
          </div>
        </div>
        <div className="text-right text-[10px] tabular-nums">
          {gas.trend_pp != null && (
            <div className={gas.trend_pp >= 0 ? "text-[#7fd6a0]" : "text-[#f0a07e]"}>
              {gas.trend_pp >= 0 ? "▲" : "▼"} {Math.abs(gas.trend_pp).toFixed(2)} pp / day
            </div>
          )}
          {yearAgo && <div className={muted}>a year ago {yearAgo[1].toFixed(1)} %</div>}
        </div>
      </div>
      <svg viewBox={`0 0 ${W} 62`} className="mt-2 w-full">
        <line x1={0} x2={W} y1={y(100)} y2={y(100)} stroke="rgba(255,255,255,0.12)" strokeDasharray="2 3" />
        <path d={`${d}L${x(n - 1)},60L0,60Z`} fill="rgba(255,150,92,0.18)" />
        <path d={d} fill="none" stroke="#ff965c" strokeWidth={1.4} />
      </svg>
      <div className={`flex justify-between text-[9px] ${muted}`}>
        <span>{pts[0]?.[0]}</span>
        <span>100 % = full</span>
        <span>{gas.date}</span>
      </div>
    </Card>
  );
}

export interface LngRow {
  date: string;
  /** GWh per day sent into the grid */
  send_out: number | null;
  /** declared total reference send-out (GWh per day) */
  capacity: number | null;
  inventory_gwh: number | null;
  series: [string, number | null][];
}

/** LNG send-out (GIE ALSI): today, the last ~13 months, and the same day a year ago. */
export function LngCard({ lng }: { lng: LngRow }) {
  const pts = lng.series.filter((p): p is [string, number] => p[1] != null);
  const n = pts.length;
  const yearAgo = (() => {
    const t = Date.parse(lng.date) - 365 * 86_400_000;
    let best: [string, number] | null = null;
    for (const p of pts) if (!best || Math.abs(Date.parse(p[0]) - t) < Math.abs(Date.parse(best[0]) - t)) best = p;
    return best && Math.abs(Date.parse(best[0]) - t) < 4 * 86_400_000 ? best : null;
  })();
  const top = Math.max(1, lng.capacity ?? 0, ...pts.map((p) => p[1]));
  const x = (i: number) => (i / Math.max(1, n - 1)) * W;
  const y = (v: number) => 60 - (v / top) * 58;
  let d = "";
  pts.forEach(([, v], i) => (d += `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`));
  const fmt = (v: number) => v.toLocaleString("en-US", { maximumFractionDigits: 0 });
  return (
    <Card title="LNG send-out" note={`GIE ALSI · ${lng.date}`} accent={[120, 180, 255]}>
      <div className="flex items-end justify-between">
        <div>
          <div className="text-[26px] font-light leading-none tabular-nums text-slate-100">
            {lng.send_out != null ? fmt(lng.send_out) : "–"} <span className="text-[13px] text-slate-300">GWh/day</span>
          </div>
          <div className={`mt-1 text-[10px] ${muted}`}>
            {lng.capacity != null ? `regasified into the grid; terminals declare ${fmt(lng.capacity)} GWh/day` : "regasified into the grid"}
          </div>
        </div>
        <div className="text-right text-[10px] tabular-nums">
          {yearAgo && <div className={muted}>a year ago {fmt(yearAgo[1])}</div>}
          {lng.inventory_gwh != null && <div className={muted}>in tanks {fmt(lng.inventory_gwh)} GWh</div>}
        </div>
      </div>
      <svg viewBox={`0 0 ${W} 62`} className="mt-2 w-full">
        {lng.capacity != null && (
          <line x1={0} x2={W} y1={y(lng.capacity)} y2={y(lng.capacity)} stroke="rgba(255,255,255,0.18)" strokeDasharray="2 3" />
        )}
        <path d={`${d}L${x(n - 1)},60L0,60Z`} fill="rgba(120,180,255,0.16)" />
        <path d={d} fill="none" stroke="#78b4ff" strokeWidth={1.3} />
      </svg>
      <div className={`flex justify-between text-[9px] ${muted}`}>
        <span>{pts[0]?.[0]}</span>
        {lng.capacity != null && <span>dashed: declared send-out</span>}
        <span>{lng.date}</span>
      </div>
    </Card>
  );
}

export interface OutageUnit {
  zone: string;
  country: string;
  unit: string | null;
  plant: string | null;
  fuel: string;
  nominal_mw: number;
  available_mw: number;
  offline_mw: number;
  type: string;
  start: string;
  end: string;
}
export interface OutageTotals {
  offline_mw: number;
  planned_mw: number;
  forced_mw: number;
  left_out: number;
}

const untilLabel = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

/** Generating units offline right now (ENTSO-E unavailability), largest first. */
export function OutageCard({ totals, units, at }: { totals: OutageTotals; units: OutageUnit[]; at: string }) {
  const [all, setAll] = useState(false);
  const shown = all ? units : units.slice(0, 8);
  return (
    <Card title="Plants offline now" note={`ENTSO-E · ${new Date(at).toISOString().slice(11, 16)} UTC`} accent={[230, 96, 72]}>
      <div className="flex items-end justify-between">
        <div>
          <div className="text-[26px] font-light leading-none tabular-nums text-slate-100">{power(totals.offline_mw)}</div>
          <div className={`mt-1 text-[10px] ${muted}`}>of generating capacity unavailable, {units.length} units</div>
        </div>
        <div className="text-right text-[10px] tabular-nums">
          <div className="text-[#f0a07e]">forced {power(totals.forced_mw)}</div>
          <div className={muted}>planned {power(totals.planned_mw)}</div>
        </div>
      </div>
      <div className="mt-2.5 space-y-1">
        {shown.map((u, i) => (
          <div key={`${u.zone}-${u.unit}-${i}`} className="text-[11px] leading-tight">
            <div className="flex items-center justify-between gap-2">
              <span className="flex min-w-0 items-center gap-1.5 text-slate-200">
                <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: rgbCss(FUEL_COLOR[u.fuel] ?? FUEL_COLOR.other) }} />
                <span className="truncate">{u.plant || u.unit}</span>
              </span>
              <span className="shrink-0 tabular-nums text-slate-100">{power(u.offline_mw)}</span>
            </div>
            <div className={`pl-3.5 text-[9.5px] ${muted}`}>
              {u.type === "forced" ? <span className="text-[#f0a07e]">forced</span> : u.type} · {FUEL_LABEL[u.fuel] ?? u.fuel} · until {untilLabel(u.end)}
              {u.available_mw > 0 ? ` · ${power(u.available_mw)} of ${power(u.nominal_mw)} still available` : ""}
            </div>
          </div>
        ))}
      </div>
      {units.length > 8 && (
        <button onClick={() => setAll(!all)} className="mt-2 text-[10px] text-sky-300 hover:text-sky-200">
          {all ? "Show fewer" : `Show all ${units.length}`}
        </button>
      )}
      {totals.left_out > 0 && (
        <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
          {totals.left_out} reports left out: their nominal power exceeds any single unit in Europe (a reporting error at the source).
        </div>
      )}
    </Card>
  );
}

/** 25 years of generation by source (Ember, yearly) with the published carbon intensity. */
export function HistoryCard({ ember }: { ember: EmberRow }) {
  const [hover, setHover] = useState<number | null>(null);
  const yrs = ember.years;
  const totals = yrs.map((_, i) => EMBER_ORDER.reduce((a, s) => a + (ember.series[s]?.[i] ?? 0), 0));
  const max = Math.max(1, ...totals);
  const bw = W / yrs.length;
  const i = hover ?? yrs.length - 1;
  const ci = ember.intensity.filter((v): v is number => v != null);
  // scaled between the lowest and highest year so the trend is visible
  const ciMax = Math.max(...ci);
  const ciMin = Math.min(...ci);
  const ciY = (v: number) => 34 - ((v - ciMin) / (ciMax - ciMin || 1)) * 30;
  let ciPath = "";
  ember.intensity.forEach((v, k) => {
    if (v == null) return;
    ciPath += `${ciPath ? "L" : "M"}${(k * bw + bw / 2).toFixed(1)},${ciY(v).toFixed(1)}`;
  });
  return (
    <Card title={`${yrs[0]}–${yrs[yrs.length - 1]}`} note="Ember yearly data" accent={[72, 222, 184]}>
      <div className={`mb-1 h-4 text-[10px] tabular-nums ${muted}`}>
        {yrs[i]} · {totals[i].toFixed(0)} TWh generated
        {ember.renewable_pct[i] != null ? ` · ${ember.renewable_pct[i]?.toFixed(0)} % renewable` : ""}
      </div>
      <svg
        viewBox={`0 0 ${W} 96`}
        className="w-full touch-none"
        onPointerMove={(e) => {
          const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
          setHover(Math.max(0, Math.min(yrs.length - 1, Math.floor(((e.clientX - r.left) / r.width) * yrs.length))));
        }}
        onPointerLeave={() => setHover(null)}
      >
        {yrs.map((_, k) => {
          let y0 = 96;
          return (
            <g key={k} opacity={hover == null || hover === k ? 1 : 0.55}>
              {EMBER_ORDER.map((s) => {
                const v = ember.series[s]?.[k] ?? 0;
                if (v <= 0) return null;
                const h = (v / max) * 92;
                y0 -= h;
                return <rect key={s} x={k * bw + 0.5} y={y0} width={bw - 1} height={h} fill={rgbCss(EMBER_COLOR[s] ?? [150, 150, 150])} />;
              })}
            </g>
          );
        })}
      </svg>
      {ci.length > 1 && (
        <>
          <div className={`mt-2 flex justify-between text-[9px] uppercase tracking-[0.16em] ${muted}`}>
            <span>Carbon intensity of generation</span>
            <span className="tabular-nums normal-case tracking-normal text-slate-200">
              {ember.intensity[i] != null ? `${Math.round(ember.intensity[i] as number)} g CO₂/kWh` : ""}
            </span>
          </div>
          <svg viewBox={`0 0 ${W} 38`} className="w-full" aria-label={`from ${Math.round(ci[0])} to ${Math.round(ci[ci.length - 1])} g CO2/kWh`}>
            <path d={ciPath} fill="none" stroke="#c9b8a6" strokeWidth={1.4} />
            {hover != null && ember.intensity[hover] != null && (
              <circle cx={hover * bw + bw / 2} cy={ciY(ember.intensity[hover] as number)} r={2.5} fill="#f1f5f9" />
            )}
          </svg>
        </>
      )}
      <div className="mt-1.5 flex flex-wrap gap-x-2.5 gap-y-0.5 text-[9px] text-slate-400">
        {EMBER_ORDER.filter((s) => ember.series[s]).map((s) => (
          <span key={s} className="flex items-center gap-1">
            <span className="h-1.5 w-1.5 rounded-sm" style={{ background: rgbCss(EMBER_COLOR[s] ?? [150, 150, 150]) }} />
            {s}
          </span>
        ))}
      </div>
    </Card>
  );
}

/** Where the numbers come from, folded away. */
export function SourcesCard({ items }: { items: [string, string][] }) {
  return (
    <details className="group rounded-xl border border-white/[0.07] bg-[#0b0f16]/90 px-4 py-3">
      <summary className="flex cursor-pointer list-none items-center justify-between text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-300">
        Sources & method
        <span className={`transition-transform group-open:rotate-180 ${muted}`}>▾</span>
      </summary>
      <dl className="mt-2 space-y-1.5 text-[10px] leading-snug">
        {items.map(([k, v]) => (
          <div key={k}>
            <dt className="text-slate-300">{k}</dt>
            <dd className={muted}>{v}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}
