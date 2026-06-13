import type { Meta, RecentDetection, Site } from "../lib/api";
import { fmtDate, mw, num } from "../lib/format";

const BUILDING = new Set(["clearing", "earthworks", "construction"]);

interface Props {
  sites: Site[];
  meta: Meta | null;
  overdueCount: number;
  recent: RecentDetection[];
  title: string;
}

export default function TopBar({ sites, meta, overdueCount, recent, title }: Props) {
  const totalMw = sites.reduce((a, s) => a + s.capacity_mw, 0);
  const analysed = sites.filter((s) => s.status !== "unknown");
  const building = analysed.filter((s) => BUILDING.has(s.status));

  return (
    <header className="flex h-14 shrink-0 items-stretch justify-between border-b border-line bg-ink-900">
      <div className="flex items-center gap-3 pl-4 pr-5">
        <div className="h-7 w-7 rounded-md bg-gradient-to-br from-sky-400 to-emerald-400" />
        <div className="leading-tight">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold tracking-tight text-slate-100">gridwatch</span>
            <span className="rounded border border-line px-1.5 py-px text-[10px] capitalize text-dim">
              {title}
            </span>
          </div>
          <div className="text-[10px] text-faint">German energy construction monitoring</div>
        </div>
      </div>

      <div className="flex items-stretch divide-x divide-line">
        <Stat label="Sites" value={num(sites.length)} sub={mw(totalMw)} />
        <Stat label="Analysed" value={num(analysed.length)} sub={`of ${num(sites.length)}`} />
        <Stat label="Under construction" value={num(building.length)} accent="#38bdf8" />
        <Stat label="Behind deadline" value={num(overdueCount)} accent="#f87171" />
        <Stat label="Recent changes" value={num(recent.length)} accent="#f4b740" />
        <div className="flex flex-col justify-center px-5">
          <span className="eyebrow">Data as of</span>
          <span className="flex items-center gap-1.5 font-mono text-[13px] tabular-nums text-slate-200">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_6px_#34d399]" />
            {meta?.latest_observation ? fmtDate(meta.latest_observation) : "—"}
          </span>
        </div>
      </div>
    </header>
  );
}

const Stat = ({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent?: string }) => (
  <div className="flex min-w-[88px] flex-col justify-center px-4">
    <span className="eyebrow whitespace-nowrap">{label}</span>
    <span
      className="font-mono text-[17px] font-semibold leading-none tabular-nums"
      style={{ color: accent ?? "#e6e9ef" }}
    >
      {value}
    </span>
    {sub && <span className="mt-0.5 text-[10px] text-faint">{sub}</span>}
  </div>
);
