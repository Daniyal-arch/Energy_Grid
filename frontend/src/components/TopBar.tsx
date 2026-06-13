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
    <header className="flex items-center justify-between border-b border-white/10 bg-[#0a0e15] px-4 py-2">
      <div className="flex items-center gap-3">
        <div>
          <div className="text-sm font-semibold leading-none text-slate-100">gridwatch</div>
          <div className="text-[10px] text-slate-500">German energy construction monitoring</div>
        </div>
        <span className="ml-2 rounded-md border border-white/10 px-2 py-0.5 text-[11px] capitalize text-slate-400">
          {title}
        </span>
      </div>

      <div className="flex items-center gap-5">
        <Kpi label="Sites" value={num(sites.length)} sub={mw(totalMw)} />
        <Kpi label="Under construction" value={num(building.length)} accent="#38bdf8" />
        <Kpi label="Behind deadline" value={num(overdueCount)} accent="#f87171" />
        <Kpi label="Recent changes" value={num(recent.length)} accent="#f4b740" />
        <div className="border-l border-white/10 pl-4 text-right">
          <div className="text-[10px] uppercase tracking-wider text-slate-500">Data as of</div>
          <div className="flex items-center gap-1.5 text-xs text-slate-300">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            {meta?.latest_observation ? fmtDate(meta.latest_observation) : "—"}
          </div>
        </div>
      </div>
    </header>
  );
}

const Kpi = ({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent?: string }) => (
  <div className="text-right">
    <div className="text-[10px] uppercase tracking-wider text-slate-500">{label}</div>
    <div className="text-base font-semibold leading-tight tabular-nums" style={{ color: accent ?? "#e8edf4" }}>
      {value}
    </div>
    {sub && <div className="text-[10px] text-slate-500">{sub}</div>}
  </div>
);
