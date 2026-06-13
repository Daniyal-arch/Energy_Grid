import type { RecentDetection, Site } from "../lib/api";
import { mw, num } from "../lib/format";

const BUILDING = new Set(["clearing", "earthworks", "construction"]);

export default function PulseHeader({
  sites,
  recent,
}: {
  sites: Site[];
  recent: RecentDetection[];
}) {
  const totalGw = sites.reduce((a, s) => a + s.capacity_mw, 0);
  const analysed = sites.filter((s) => s.status !== "unknown");
  const building = analysed.filter((s) => BUILDING.has(s.status));
  const buildingMw = building.reduce((a, s) => a + s.capacity_mw, 0);
  const complete = analysed.filter((s) => s.status === "complete").length;

  return (
    <div className="flex items-stretch gap-2">
      <Stat label="Sites monitored" value={num(sites.length)} sub={`${mw(totalGw)} total`} />
      <Stat label="Under construction" value={num(building.length)} sub={mw(buildingMw)} accent="#38bdf8" />
      <Stat label="Complete" value={num(complete)} accent="#34d399" />
      <Stat label="Analysed" value={num(analysed.length)} sub={`of ${num(sites.length)}`} />
      <Stat label="Recent changes" value={num(recent.length)} sub="latest detections" accent="#f4b740" />
    </div>
  );
}

const Stat = ({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: string;
}) => (
  <div className="rounded-xl border border-white/5 bg-white/[0.03] px-3.5 py-2 backdrop-blur-md">
    <div className="text-[10px] uppercase tracking-wider text-slate-500">{label}</div>
    <div className="text-lg font-semibold tabular-nums" style={{ color: accent ?? "#e8edf4" }}>
      {value}
    </div>
    {sub && <div className="text-[10px] text-slate-500">{sub}</div>}
  </div>
);
