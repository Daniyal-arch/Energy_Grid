import { Card } from "./CountryCards";

const muted = "text-[#8d94a1]";

export interface JepxFile {
  fetched: string;
  source: string;
  date: string;
  slots: number;
  /** area -> its 48 half-hour prices (JPY/kWh) and their average, lowest, highest (computed) */
  areas: Record<string, { prices: (number | null)[]; avg: number | null; min: number | null; max: number | null }>;
}

export interface CenaceFile {
  fetched: string;
  source: string;
  date: string;
  /** system -> nodes priced, and per hour [nodes, lowest, median, highest] (MXN/MWh, computed) */
  systems: Record<string, { nodes: number; hours: [number, number, number, number][] }>;
}

const AREA: Record<string, string> = { system: "System price" };
const label = (k: string) => AREA[k] ?? k.charAt(0).toUpperCase() + k.slice(1);

/** Japan: JEPX day-ahead (spot) prices per area for the newest delivery day. */
export function JepxCard({ f }: { f: JepxFile }) {
  const sys = f.areas.system?.prices ?? [];
  const vals = sys.filter((v): v is number => v != null);
  const hi = Math.max(1, ...vals);
  const W = 300;
  const H = 50;
  const d = sys.map((v, i) => (v == null ? "" : `${i && sys[i - 1] != null ? "L" : "M"}${((i / 47) * W).toFixed(1)},${(4 + ((hi - v) / hi) * (H - 8)).toFixed(1)}`)).join("");
  return (
    <Card title="Japan · JEPX spot" note={`delivery ${f.date} · JST`} accent={[255, 160, 160]}>
      <svg viewBox={`0 0 ${W} ${H}`} className="mb-1 w-full">
        <path d={d} fill="none" stroke="rgb(255,160,160)" strokeWidth={1} />
      </svg>
      <div className={`mb-1 text-[9.5px] ${muted}`}>system price, 48 half-hours (0 to {hi} JPY/kWh)</div>
      <div className="space-y-0.5">
        {Object.entries(f.areas).map(([k, a]) => (
          <div key={k} className="flex justify-between text-[11px] tabular-nums">
            <span className="text-slate-300">{label(k)}</span>
            <span className="text-slate-100">
              {a.avg ?? "–"} <span className={muted}>({a.min ?? "–"}–{a.max ?? "–"})</span>
            </span>
          </div>
        ))}
      </div>
      <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
        JPY/kWh as JEPX publishes them; average, lowest and highest of the {f.slots} half-hours computed. JEPX&apos;s terms of use were not found on its site.
      </div>
    </Card>
  );
}

/** Mexico: CENACE day-ahead local marginal prices, the spread across nodes per system. */
export function CenaceCard({ f }: { f: CenaceFile }) {
  return (
    <Card title="Mexico · CENACE day-ahead" note={f.date} accent={[160, 220, 140]}>
      {Object.entries(f.systems).map(([sys, s]) => {
        const med = s.hours.map((h) => h[2]);
        const avg = med.reduce((a, b) => a + b, 0) / Math.max(1, med.length);
        const lo = Math.min(...s.hours.map((h) => h[1]));
        const hi = Math.max(...s.hours.map((h) => h[3]));
        return (
          <div key={sys} className="mb-1.5 text-[11px] tabular-nums">
            <div className="flex justify-between">
              <span className="text-slate-200">{sys}</span>
              <span className="text-slate-100">{Math.round(avg).toLocaleString("en-US")} MXN/MWh</span>
            </div>
            <div className={`text-[9.5px] ${muted}`}>
              {s.nodes.toLocaleString("en-US")} nodes · lowest {Math.round(lo).toLocaleString("en-US")} · highest {Math.round(hi).toLocaleString("en-US")}
            </div>
          </div>
        );
      })}
      <div className={`mt-1 text-[10px] leading-snug ${muted}`}>
        Local marginal prices (PML) of every node CENACE lists, as published; per system the mean of the hourly medians and the lowest and highest node price of the day
        (computed). Nodes are counted, not placed: CENACE publishes no positions.
      </div>
    </Card>
  );
}
