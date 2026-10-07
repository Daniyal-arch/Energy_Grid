import { useState } from "react";

import { HOUR_KEY, SEASON_COLOR, hourColor, monthLabel, type PriceMetric, type ZoneStats } from "../lib/prices";
import { rgbCss } from "../lib/theme";
import { Card } from "./CountryCards";

const muted = "text-[#8d94a1]";
const CET = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Europe/Berlin",
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});
const when = (iso: string) => CET.format(new Date(iso));
const eur = (v: number) => `${v.toFixed(Math.abs(v) < 10 ? 1 : 0)} €/MWh`;

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg bg-white/[0.035] px-2.5 py-2">
      <div className={`text-[9px] uppercase tracking-[0.16em] ${muted}`}>{label}</div>
      <div className="mt-0.5 text-[19px] font-light leading-tight tabular-nums text-slate-100">{value}</div>
      {sub && <div className={`text-[9.5px] leading-snug ${muted}`}>{sub}</div>}
    </div>
  );
}

/** One zone's twelve months: average, negative hours, the extremes. */
export function ZoneCard({ zone, z, period }: { zone: string; z: ZoneStats; period: string }) {
  return (
    <Card title={`${zone} · 12 months`} note={period}>
      <div className="grid grid-cols-2 gap-1.5">
        <Tile label="Average price" value={`${Math.round(z.mean)} €`} sub="per MWh" />
        <Tile label="Below zero" value={`${Math.round(z.negative_hours)} h`} sub="hours with a negative price" />
        <Tile label="Lowest" value={eur(z.min[0])} sub={when(z.min[1])} />
        <Tile label="Highest" value={eur(z.max[0])} sub={when(z.max[1])} />
      </div>
      {z.coverage < 0.99 && (
        <div className={`mt-2 text-[10px] ${muted}`}>Prices for {Math.round(z.coverage * 100)} % of the intervals; the rest are missing at ENTSO-E.</div>
      )}
    </Card>
  );
}

const W = 300;
const HOURS = Array.from({ length: 24 }, (_, h) => h);
const SEASON_LABEL: Record<string, string> = { winter: "Winter", spring: "Spring", summer: "Summer", autumn: "Autumn" };
const hh = (h: number) => `${String(h).padStart(2, "0")}:00`;

/** When in the day power is cheap: the average price per hour, by season or by month. */
export function TimeOfDayCard({ z, months }: { z: ZoneStats; months: string[] }) {
  const [mode, setMode] = useState<"seasons" | "months">("seasons");
  const [hover, setHover] = useState<{ h: number; m?: number } | null>(null);
  const lines = Object.keys(SEASON_LABEL).filter((k) => z.by_season_hour[k]);
  const all = lines.flatMap((k) => z.by_season_hour[k]).filter((v): v is number => v != null);
  // the cheapest and dearest hour among the season averages (values as computed)
  let low: { k: string; h: number; v: number } | null = null;
  let high: { k: string; h: number; v: number } | null = null;
  for (const k of lines)
    z.by_season_hour[k].forEach((v, h) => {
      if (v == null) return;
      if (!low || v < low.v) low = { k, h, v };
      if (!high || v > high.v) high = { k, h, v };
    });
  const lo = low as { k: string; h: number; v: number } | null;
  const hi = high as { k: string; h: number; v: number } | null;
  const top = Math.max(10, ...all);
  const bottom = Math.min(0, ...all);
  const H = 120;
  const y = (v: number) => 6 + ((top - v) / (top - bottom)) * (H - 12);
  const x = (h: number) => (h / 23) * W;
  const span = (k: string) => ({ winter: "Dec–Feb", spring: "Mar–May", summer: "Jun–Aug", autumn: "Sep–Nov" })[k] ?? "";
  const pickLine = (e: React.PointerEvent<Element>) => {
    const r = e.currentTarget.getBoundingClientRect();
    setHover({ h: Math.max(0, Math.min(23, Math.round(((e.clientX - r.left) / r.width) * 23))) });
  };
  const pickCell = (e: React.PointerEvent<Element>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const h = Math.max(0, Math.min(23, Math.floor(((e.clientX - r.left) / r.width) * 24)));
    const m = Math.max(0, Math.min(months.length - 1, Math.floor(((e.clientY - r.top) / r.height) * months.length)));
    setHover({ h, m });
  };
  return (
    <Card title="Price by time of day" note="average per hour, CET/CEST">
      <div className="mb-2 flex gap-1 text-[10px]">
        {(["seasons", "months"] as const).map((m) => (
          <button
            key={m}
            onClick={() => {
              setMode(m);
              setHover(null);
            }}
            className={`rounded px-2 py-0.5 ${mode === m ? "bg-white/15 text-slate-100" : "text-slate-400 hover:text-slate-200"}`}
          >
            {m === "seasons" ? "By season" : "By month"}
          </button>
        ))}
      </div>
      {mode === "seasons" ? (
        <>
          <div className="mb-1 min-h-[30px] text-[10px] leading-snug tabular-nums text-slate-300">
            {hover ? (
              <>
                <span className={muted}>{hh(hover.h)} · </span>
                {lines.map((k) => {
                  const v = z.by_season_hour[k][hover.h];
                  return (
                    <span key={k} className="mr-2 whitespace-nowrap" style={{ color: rgbCss(SEASON_COLOR[k]) }}>
                      {SEASON_LABEL[k]} {v == null ? "–" : `${Math.round(v)} €`}
                    </span>
                  );
                })}
              </>
            ) : (
              lo &&
              hi && (
                <>
                  Cheapest on average: <b className="text-slate-100">{hh(lo.h)}</b> in {SEASON_LABEL[lo.k].toLowerCase()} ({Math.round(lo.v)}{" "}
                  €/MWh). Dearest: <b className="text-slate-100">{hh(hi.h)}</b> in {SEASON_LABEL[hi.k].toLowerCase()} ({Math.round(hi.v)} €).
                </>
              )
            )}
          </div>
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full touch-none overflow-visible" onPointerMove={pickLine} onPointerLeave={() => setHover(null)}>
            {bottom < 0 && <rect x={0} y={y(0)} width={W} height={y(bottom) - y(0)} fill="rgba(110,210,255,0.08)" />}
            <line x1={0} x2={W} y1={y(0)} y2={y(0)} stroke="rgba(255,255,255,0.35)" strokeDasharray="3 3" />
            <text x={W} y={y(0) - 3} textAnchor="end" fontSize={9} fill="#8d94a1">
              0 €
            </text>
            <text x={W} y={y(top) + 8} textAnchor="end" fontSize={9} fill="#8d94a1">
              {Math.round(top)} €
            </text>
            {lines.map((k) => (
              <path
                key={k}
                d={z.by_season_hour[k]
                  .map((v, h) => (v == null ? "" : `${h && z.by_season_hour[k][h - 1] != null ? "L" : "M"}${x(h).toFixed(1)},${y(v).toFixed(1)}`))
                  .join("")}
                fill="none"
                stroke={rgbCss(SEASON_COLOR[k])}
                strokeWidth={2}
                strokeLinejoin="round"
              />
            ))}
            {hover && <line x1={x(hover.h)} x2={x(hover.h)} y1={0} y2={H} stroke="rgba(255,255,255,0.5)" />}
          </svg>
          <div className={`mt-0.5 flex justify-between text-[9px] ${muted}`}>
            {[0, 6, 12, 18, 23].map((h) => (
              <span key={h}>{hh(h)}</span>
            ))}
          </div>
          <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-0.5 text-[10px]">
            {lines.map((k) => (
              <span key={k} className="flex items-center gap-1.5 text-slate-300">
                <span className="h-[3px] w-4 rounded" style={{ background: rgbCss(SEASON_COLOR[k]) }} />
                {SEASON_LABEL[k]} <span className={muted}>{span(k)}</span>
              </span>
            ))}
          </div>
        </>
      ) : (
        <>
          <div className="mb-1 h-4 text-[10px] tabular-nums text-slate-300">
            {hover?.m != null ? (
              <>
                {monthLabel(months[hover.m])} · {hh(hover.h)} ·{" "}
                <b>
                  {z.by_month_hour[hover.m]?.[hover.h] == null
                    ? "–"
                    : `${Math.round(z.by_month_hour[hover.m][hover.h] as number)} €/MWh on average`}
                </b>
              </>
            ) : (
              <span className={muted}>Rows: months. Columns: hours. Hover a cell.</span>
            )}
          </div>
          <div className="flex gap-1.5">
            <div className="flex w-[40px] shrink-0 flex-col gap-px text-right text-[9px] leading-[13px] text-[#8d94a1]">
              {months.map((m) => (
                <span key={m}>{monthLabel(m)}</span>
              ))}
            </div>
            <div className="flex-1">
              <div
                className="grid touch-none gap-px"
                style={{ gridTemplateColumns: "repeat(24, 1fr)" }}
                onPointerMove={pickCell}
                onPointerLeave={() => setHover(null)}
              >
                {z.by_month_hour.flatMap((row, m) =>
                  HOURS.map((h) => {
                    const v = row[h];
                    return (
                      <span
                        key={`${m}-${h}`}
                        className="h-[13px] rounded-[2px]"
                        style={{
                          background: v == null ? "#14161c" : rgbCss(hourColor(v)),
                          outline: hover?.m === m && hover.h === h ? "1px solid white" : undefined,
                        }}
                      />
                    );
                  }),
                )}
              </div>
              <div className={`mt-1 flex justify-between text-[9px] ${muted}`}>
                {[0, 6, 12, 18, 23].map((h) => (
                  <span key={h}>{hh(h)}</span>
                ))}
              </div>
            </div>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[9px] text-slate-400">
            {HOUR_KEY.map(([label, c]) => (
              <span key={label} className="flex items-center gap-1">
                <span className="h-2 w-2.5 rounded-sm" style={{ background: rgbCss(c) }} />
                {label}
              </span>
            ))}
            <span className={muted}>€/MWh</span>
          </div>
        </>
      )}
    </Card>
  );
}

/** Negative-price hours per month. */
export function MonthsCard({ months, values }: { months: string[]; values: number[] }) {
  const max = Math.max(1, ...values);
  const [hover, setHover] = useState<number | null>(null);
  const i = hover ?? values.length - 1;
  return (
    <Card title="Hours below zero, by month" accent={[110, 210, 255]}>
      <div className={`mb-1 h-4 text-[10px] tabular-nums ${muted}`}>
        {monthLabel(months[i])}: {values[i].toFixed(values[i] % 1 ? 2 : 0)} h
      </div>
      <div className="flex h-[72px] items-end gap-[3px]" onPointerLeave={() => setHover(null)}>
        {values.map((v, k) => (
          <div key={months[k]} className="flex h-full flex-1 items-end" onPointerEnter={() => setHover(k)}>
            <div
              className="w-full rounded-t-sm"
              style={{ height: `${(v / max) * 100}%`, minHeight: v > 0 ? 2 : 0, background: hover === k ? "#d6f4ff" : "rgb(110,200,245)" }}
            />
          </div>
        ))}
      </div>
      <div className={`mt-1 flex justify-between text-[9px] ${muted}`}>
        <span>{monthLabel(months[0])}</span>
        <span>{monthLabel(months[months.length - 1])}</span>
      </div>
    </Card>
  );
}

/** What a MWh of solar and of wind earned, against the average price. */
export function CaptureCard({ z }: { z: ZoneStats }) {
  const rows = [
    { label: "Solar", color: [255, 214, 72] as const, cap: z.solar_capture, rate: z.solar_capture_rate, twh: z.solar_twh },
    { label: "Wind", color: [72, 222, 184] as const, cap: z.wind_capture, rate: z.wind_capture_rate, twh: z.wind_twh },
  ].filter((r) => r.cap != null);
  if (!rows.length) return null;
  const top = Math.max(z.mean, ...rows.map((r) => r.cap ?? 0)) * 1.05;
  return (
    <Card title="Capture prices" note="price weighted by output">
      <div className="space-y-2.5">
        {rows.map((r) => (
          <div key={r.label}>
            <div className="flex items-baseline justify-between text-[11px] tabular-nums">
              <span className="text-slate-200">{r.label}</span>
              <span className="text-slate-100">
                {Math.round(r.cap as number)} €/MWh <span className={muted}>· {Math.round(r.rate as number)} % of average</span>
              </span>
            </div>
            <div className="relative mt-1 h-[7px] rounded-sm bg-white/[0.05]">
              <div className="h-full rounded-sm" style={{ width: `${((r.cap as number) / top) * 100}%`, background: rgbCss([...r.color]) }} />
              <div className="absolute -top-0.5 h-[11px] w-px bg-white" style={{ left: `${(z.mean / top) * 100}%` }} />
            </div>
            <div className={`mt-0.5 text-[9.5px] ${muted}`}>{r.twh != null ? `over ${r.twh.toFixed(1)} TWh generated` : ""}</div>
          </div>
        ))}
      </div>
      <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
        White mark: the average price ({Math.round(z.mean)} €). Below it, the source sells mostly when prices are low.
      </div>
    </Card>
  );
}

/** Zones ordered by the map's metric. */
export function ZoneRankingCard({
  zones,
  metric,
  selected,
  onPick,
}: {
  zones: Record<string, ZoneStats>;
  metric: PriceMetric;
  selected: string;
  onPick: (zone: string) => void;
}) {
  const rows = Object.entries(zones)
    .map(([zone, z]) => ({ zone, v: metric.value(z) }))
    .filter((r): r is { zone: string; v: number } => r.v != null)
    .sort((a, b) => b.v - a.v);
  const top = Math.max(1, ...rows.map((r) => Math.abs(r.v)));
  return (
    <Card title="All zones" note={metric.label}>
      <div className="space-y-[3px]">
        {rows.map((r) => (
          <button
            key={r.zone}
            onClick={() => onPick(r.zone)}
            className={`flex w-full items-center gap-2 rounded px-1 text-left text-[11px] tabular-nums hover:bg-white/[0.05] ${
              selected === r.zone ? "bg-white/[0.08]" : ""
            }`}
          >
            <span className="w-[92px] truncate text-slate-300">{r.zone}</span>
            <span className="relative h-[6px] flex-1 overflow-hidden rounded-sm bg-white/[0.05]">
              <span className="absolute inset-y-0 left-0 rounded-sm" style={{ width: `${(Math.abs(r.v) / top) * 100}%`, background: "rgb(120,170,200)" }} />
            </span>
            <span className="w-12 text-right text-slate-100">{metric.format(r.v)}</span>
          </button>
        ))}
      </div>
    </Card>
  );
}
