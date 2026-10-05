import { useState } from "react";

import { EMBER_COLOR, EMBER_ORDER } from "../lib/energy";
import { rgbCss } from "../lib/theme";
import { formatMetric, metricColor, type Metric, type TransitionEntity } from "../lib/transition";
import { Card } from "./CountryCards";

const muted = "text-[#8d94a1]";
const W = 300;

/** One aggregate (EU, World): the metric this year and generation by source over 25 years. */
export function AggregateCard({
  entity,
  years,
  k,
  metric,
}: {
  entity: TransitionEntity;
  years: string[];
  k: number;
  metric: Metric;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const i = hover ?? k;
  const value = entity[metric.id][i];
  const first = entity[metric.id].findIndex((v) => v != null);
  const totals = years.map((_, y) => EMBER_ORDER.reduce((a, s) => a + (entity.series[s]?.[y] ?? 0), 0));
  const max = Math.max(1, ...totals);
  const H = 92;
  const x = (y: number) => (y / Math.max(1, years.length - 1)) * W;
  // stacked areas, one path per source
  const bands: { s: string; d: string }[] = [];
  const base = years.map(() => 0);
  for (const s of EMBER_ORDER) {
    const col = entity.series[s];
    if (!col) continue;
    const top = years.map((_, y) => base[y] + (col[y] ?? 0));
    const up = top.map((v, y) => `${y ? "L" : "M"}${x(y).toFixed(1)},${(H - (v / max) * (H - 4)).toFixed(1)}`).join("");
    const down = base
      .map((v, y) => [y, v] as const)
      .reverse()
      .map(([y, v]) => `L${x(y).toFixed(1)},${(H - (v / max) * (H - 4)).toFixed(1)}`)
      .join("");
    bands.push({ s, d: `${up}${down}Z` });
    top.forEach((v, y) => (base[y] = v));
  }
  const c = metricColor(metric, value);
  return (
    <Card title={`${entity.name === "EU" ? "European Union" : entity.name}`} note="Ember yearly data" accent={c ?? undefined}>
      <div className="flex items-end justify-between">
        <div>
          <div className="text-[30px] font-light leading-none tabular-nums" style={{ color: c ? rgbCss(c) : undefined }}>
            {formatMetric(metric, value)}
          </div>
          <div className={`mt-1 text-[10px] ${muted}`}>
            {metric.note} · {years[i]}
          </div>
        </div>
        {first >= 0 && first !== i && (
          <div className={`text-right text-[10px] tabular-nums ${muted}`}>
            {years[first]}
            <div className="text-[13px] text-slate-300">{formatMetric(metric, entity[metric.id][first])}</div>
          </div>
        )}
      </div>
      <div className={`mt-3 mb-1 flex justify-between text-[9px] uppercase tracking-[0.16em] ${muted}`}>
        <span>Generation by source</span>
        <span className="normal-case tracking-normal text-slate-300">{totals[i] > 0 ? `${Math.round(totals[i]).toLocaleString("en-US")} TWh` : ""}</span>
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full touch-none"
        onPointerMove={(e) => {
          const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
          setHover(Math.max(0, Math.min(years.length - 1, Math.round(((e.clientX - r.left) / r.width) * (years.length - 1)))));
        }}
        onPointerLeave={() => setHover(null)}
      >
        {bands.map((b) => (
          <path key={b.s} d={b.d} fill={rgbCss(EMBER_COLOR[b.s] ?? [150, 150, 150])} opacity={0.9} />
        ))}
        <line x1={x(i)} x2={x(i)} y1={0} y2={H} stroke="#f1f5f9" strokeWidth={1} />
      </svg>
      <div className={`flex justify-between text-[9px] ${muted}`}>
        <span>{years[0]}</span>
        <span>{years[years.length - 1]}</span>
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-2.5 gap-y-0.5 text-[9px] text-slate-400">
        {EMBER_ORDER.filter((s) => entity.series[s]).map((s) => (
          <span key={s} className="flex items-center gap-1">
            <span className="h-1.5 w-1.5 rounded-sm" style={{ background: rgbCss(EMBER_COLOR[s] ?? [150, 150, 150]) }} />
            {s}
          </span>
        ))}
      </div>
    </Card>
  );
}

export interface RankRow {
  key: string;
  name: string;
  value: number;
}

const ROW = 19;

/** Countries ordered by the metric this year; rows glide to their new place as years pass. */
export function RankingCard({
  title,
  note,
  rows,
  metric,
  selected,
  onPick,
}: {
  title: string;
  note: string;
  rows: RankRow[];
  metric: Metric;
  selected: string | null;
  onPick: (key: string) => void;
}) {
  const sorted = [...rows].sort((a, b) => (metric.id === "intensity" ? a.value - b.value : b.value - a.value));
  const place = new Map(sorted.map((r, n) => [r.key, n]));
  const top = Math.max(1, ...rows.map((r) => r.value));
  // stable DOM order (by key) so CSS can animate each row's move
  const stable = [...rows].sort((a, b) => a.key.localeCompare(b.key));
  return (
    <Card title={title} note={note}>
      <div className="relative" style={{ height: rows.length * ROW }}>
        {stable.map((r) => {
          const c = metricColor(metric, r.value) ?? [80, 80, 80];
          return (
            <button
              key={r.key}
              onClick={() => onPick(r.key)}
              className={`absolute inset-x-0 flex items-center gap-2 rounded px-1 text-left text-[11px] tabular-nums transition-[top] duration-500 ease-out hover:bg-white/[0.05] ${
                selected === r.key ? "bg-white/[0.08]" : ""
              }`}
              style={{ top: (place.get(r.key) ?? 0) * ROW, height: ROW - 2 }}
            >
              <span className="w-[88px] truncate text-slate-300">{r.name}</span>
              <span className="relative h-[7px] flex-1 overflow-hidden rounded-sm bg-white/[0.05]">
                <span
                  className="absolute inset-y-0 left-0 rounded-sm transition-[width] duration-500 ease-out"
                  style={{ width: `${(r.value / top) * 100}%`, background: rgbCss(c) }}
                />
              </span>
              <span className="w-12 text-right text-slate-100">{formatMetric(metric, r.value)}</span>
            </button>
          );
        })}
      </div>
    </Card>
  );
}
