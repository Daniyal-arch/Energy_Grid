import { useEffect, useMemo, useRef, useState } from "react";

import { CARPET_KEY, carpetColor, monthLabel, type CarpetFile, type PriceMetric, type ZoneStats } from "../lib/prices";
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
        <Tile label="Average price" value={`${Math.round(z.mean)} €`} sub="per MWh, every 15 min weighted equally" />
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

const CELL_W = 3; // px per quarter-hour

/** Every 15-min price of the year: one row per day, one column per quarter-hour. */
export function CarpetCard({ carpet, until }: { carpet: CarpetFile | null; until: string }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [hover, setHover] = useState<{ d: number; q: number } | null>(null);
  const rows = carpet?.values.length ?? 0;
  useEffect(() => {
    const c = canvas.current;
    if (!c || !carpet) return;
    c.width = 96;
    c.height = rows;
    const ctx = c.getContext("2d");
    if (!ctx) return;
    const img = ctx.createImageData(96, rows);
    carpet.values.forEach((row, d) =>
      row.forEach((v, q) => {
        const at = (d * 96 + q) * 4;
        const col = v == null ? ([16, 18, 24] as const) : carpetColor(v / 10);
        img.data[at] = col[0];
        img.data[at + 1] = col[1];
        img.data[at + 2] = col[2];
        img.data[at + 3] = 255;
      }),
    );
    ctx.putImageData(img, 0, 0);
  }, [carpet, rows]);
  // the first day of each month, labelled at its row
  const months = useMemo(
    () => (carpet?.days ?? []).flatMap((d, i) => (d.endsWith("-01") ? [{ i, label: monthLabel(d.slice(0, 7)) }] : [])),
    [carpet],
  );
  const v = hover && carpet ? carpet.values[hover.d]?.[hover.q] : null;
  return (
    <Card title="Every 15 minutes" note={carpet ? `to ${until}` : "loading…"}>
      <div className={`mb-1.5 h-4 text-[10px] tabular-nums ${muted}`}>
        {hover && carpet
          ? `${new Date(`${carpet.days[hover.d]}T12:00:00Z`).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", year: "numeric" })} · ${String(Math.floor(hover.q / 4)).padStart(2, "0")}:${String((hover.q % 4) * 15).padStart(2, "0")} · ${v == null ? "no price" : eur(v / 10)}`
          : "Rows: days. Columns: time of day (CET/CEST). Hover for a price."}
      </div>
      <div className="flex gap-1.5">
        <div className="relative w-[34px] shrink-0 text-[9px] text-[#8d94a1]" style={{ height: rows }}>
          {months.map((m) => (
            <span key={m.i} className="absolute right-0 -translate-y-1/2" style={{ top: m.i }}>
              {m.label}
            </span>
          ))}
        </div>
        <div>
          <canvas
            ref={canvas}
            className="block touch-none"
            style={{ width: 96 * CELL_W, height: rows, imageRendering: "pixelated" }}
            onPointerMove={(e) => {
              const r = e.currentTarget.getBoundingClientRect();
              const d = Math.floor(((e.clientY - r.top) / r.height) * rows);
              const q = Math.floor(((e.clientX - r.left) / r.width) * 96);
              setHover(d >= 0 && d < rows && q >= 0 && q < 96 ? { d, q } : null);
            }}
            onPointerLeave={() => setHover(null)}
          />
          <div className={`mt-1 flex justify-between text-[9px] ${muted}`} style={{ width: 96 * CELL_W }}>
            <span>00:00</span>
            <span>06:00</span>
            <span>12:00</span>
            <span>18:00</span>
            <span>24:00</span>
          </div>
        </div>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[9px] text-slate-400">
        {CARPET_KEY.map(([label, c]) => (
          <span key={label} className="flex items-center gap-1">
            <span className="h-2 w-2.5 rounded-sm" style={{ background: rgbCss(c) }} />
            {label}
          </span>
        ))}
        <span className={muted}>€/MWh</span>
      </div>
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
