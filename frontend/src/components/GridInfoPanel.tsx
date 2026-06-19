import { PHASE_COLOR, type GridPick, type Phase } from "../lib/grid";
import { rgbCss } from "../lib/theme";

const PHASE_LABEL: Record<Phase, string> = {
  construction: "Under construction",
  operational: "Operational",
  approval: "In approval",
  planned: "Planned",
};

const kv = (v: number) => (v ? `${Math.round(v / 1000)} kV` : "—");

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-line bg-ink-850 px-2.5 py-1.5">
      <div className="eyebrow">{label}</div>
      <div className="text-slate-200">{value}</div>
    </div>
  );
}

export default function GridInfoPanel({ pick, onClose }: { pick: GridPick; onClose: () => void }) {
  return (
    <aside className="absolute right-0 top-0 z-20 flex h-full w-[340px] flex-col gap-4 overflow-y-auto border-l border-line bg-ink-900/95 p-5 backdrop-blur-xl">
      <div className="flex items-start justify-between">
        <div>
          <div className="eyebrow text-accent-400">Grid</div>
          <h2 className="mt-1 text-base font-semibold leading-tight text-slate-100">
            {pick.kind === "corridor"
              ? pick.seg.name || pick.seg.number || "Planned corridor"
              : pick.kind === "substation"
                ? pick.sub.name || "Substation"
                : "Transmission line"}
          </h2>
        </div>
        <button onClick={onClose} className="text-slate-500 hover:text-slate-200">
          ✕
        </button>
      </div>

      {pick.kind === "corridor" && (
        <>
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: rgbCss(PHASE_COLOR[pick.seg.phase]) }} />
            <span className="text-sm font-medium" style={{ color: rgbCss(PHASE_COLOR[pick.seg.phase]) }}>
              {PHASE_LABEL[pick.seg.phase]}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            {pick.seg.number && <Fact label="Project" value={pick.seg.number} />}
            {pick.seg.spannung && <Fact label="Voltage" value={pick.seg.spannung} />}
            {pick.seg.technik && <Fact label="Technology" value={pick.seg.technik} />}
            <Fact label="Type" value="Planned corridor" />
          </div>
          <div className="rounded-md border border-line bg-ink-850 px-3 py-2 text-xs leading-snug text-slate-400">
            {pick.seg.status}
          </div>
          <p className="text-[10px] leading-relaxed text-faint">
            Source: Bundesnetzagentur Netzausbau (BBPlG/EnLAG). Construction phase is the
            official status, updated quarterly.
          </p>
        </>
      )}

      {pick.kind === "substation" && (
        <div className="grid grid-cols-2 gap-2 text-xs">
          <Fact label="Voltage" value={kv(pick.sub.voltage)} />
          <Fact label="Type" value="Substation" />
          <Fact label="Source" value="OpenStreetMap" />
        </div>
      )}

      {pick.kind === "line" && (
        <div className="grid grid-cols-2 gap-2 text-xs">
          <Fact label="Voltage" value={kv(pick.line.voltage)} />
          <Fact label="Type" value="Transmission line" />
          <Fact label="Source" value="OpenStreetMap" />
        </div>
      )}
    </aside>
  );
}
