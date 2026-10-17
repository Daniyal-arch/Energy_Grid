// "On the map" cards of the risk layers: US outages (EAGLE-I) and water risk (WRI Aqueduct).
// Every number is the file's own or a sum of it, said on the card.

import { Card } from "./CountryCards";
import { useFile } from "../app/data";
import { WATER_COLOR, WATER_INDICATORS, hoursText, type UsOutagesFile, type WaterFile } from "../lib/risk";
import { rgbCss } from "../lib/theme";
import { useApp } from "../app/store";

const muted = "text-[#8d94a1]";

export function UsOutagesCard() {
  const f = useFile<UsOutagesFile>("usOutages");
  if (!f) return <Card title="US power outages">Loading EAGLE-I…</Card>;
  const top = Math.max(...f.national);
  const m = f.month;
  const mTop = m ? Math.max(1, ...m.values) : 1;
  return (
    <Card title="US power outages" note="EAGLE-I · ORNL">
      <div className={`mb-1 text-[10px] ${muted}`}>Customer-hours without power, whole country (sum over counties, computed)</div>
      {f.years.map((y, i) => (
        <div key={y} className="flex items-center gap-2 text-[11px]">
          <span className="w-9 tabular-nums text-slate-400">{y}</span>
          <span className="h-1.5 rounded-sm bg-[rgb(230,120,80)]" style={{ width: `${(70 * f.national[i]) / top}%` }} />
          <span className="tabular-nums text-slate-200">{hoursText(f.national[i])}</span>
          {f.partial[String(y)] && <span className={`text-[9.5px] ${muted}`}>{f.partial[String(y)]}</span>}
        </div>
      ))}
      <div className={`mt-3 mb-1 text-[9px] uppercase tracking-[0.14em] ${muted}`}>Largest events</div>
      {f.events.slice(0, 8).map(([state, start, end, peak]) => (
        <div key={`${state}${start}`} className="flex justify-between gap-2 text-[11px]">
          <span className="text-slate-300">
            {state} <span className={muted}>{start.slice(0, 10)} → {end.slice(0, 10)}</span>
          </span>
          <span className="tabular-nums text-slate-100">{peak.toLocaleString("en-US")}</span>
        </div>
      ))}
      <div className={`mt-1 text-[10px] leading-snug ${muted}`}>
        Peak customers out at one moment in the state (sum over its counties). An event: {f.event_rule.min_customers.toLocaleString("en-US")} or more customers out in one state, gaps up to{" "}
        {f.event_rule.gap_min} min (computed).
      </div>
      {m && (
        <>
          <div className={`mt-3 mb-1 text-[9px] uppercase tracking-[0.14em] ${muted}`}>{m.month}, every {m.step_min} min</div>
          <svg viewBox={`0 0 ${m.values.length - 1 || 1} 10`} preserveAspectRatio="none" className="block h-[28px] w-full">
            <polyline
              fill="none"
              stroke="rgb(230,120,80)"
              strokeWidth={1}
              vectorEffect="non-scaling-stroke"
              points={m.values.map((v, i) => `${i},${10 - (10 * v) / mTop}`).join(" ")}
            />
          </svg>
          <div className={`text-[10px] ${muted}`}>Customers out in the whole country (sum over counties); peak {mTop.toLocaleString("en-US")}.</div>
        </>
      )}
      <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
        Customers are utility meters, not people. Counts as utilities report them to EAGLE-I; coverage grew over the years (lake: coverage, dqi).
      </div>
    </Card>
  );
}

export function WaterCard({ iso3 }: { iso3?: string }) {
  const f = useFile<WaterFile>("water");
  const ind = useApp((s) => s.waterIndicator);
  if (!f) return <Card title="Water risk">Loading WRI Aqueduct…</Card>;
  const col = f.order.indexOf(ind);
  const counts = new Map<number | null, number>();
  for (const b of f.basins) counts.set(b.c[col], (counts.get(b.c[col]) ?? 0) + 1);
  const labels = f.indicators[ind].labels;
  return (
    <Card title={`Water risk · ${WATER_INDICATORS.find((w) => w.id === ind)?.short ?? ind}`} note={`WRI Aqueduct ${f.version}`}>
      <div className={`mb-1 text-[10px] ${muted}`}>River basins in each category, worldwide (count, computed)</div>
      {Object.entries(labels)
        .filter(([c]) => Number(c) >= -1)
        .map(([c, label]) => (
          <div key={c} className="flex items-center justify-between gap-2 text-[11px]">
            <span className="flex items-center gap-1.5 text-slate-300">
              <span className="h-2 w-2 rounded-sm" style={{ background: rgbCss(WATER_COLOR[c] ?? [90, 90, 90]) }} />
              {label}
            </span>
            <span className="tabular-nums text-slate-100">{(counts.get(Number(c)) ?? 0).toLocaleString("en-US")}</span>
          </div>
        ))}
      <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
        {iso3 ? "Basins cross borders, so the counts are worldwide. " : ""}Baseline conditions; Aqueduct's projections (2030–2080) and monthly values are in the data lake. Water stress = withdrawals ÷ available
        renewable water.
      </div>
    </Card>
  );
}
