import { useState } from "react";

import { PHASE_COLOR, voltColor, type Phase } from "../lib/grid";
import { rgbCss } from "../lib/theme";

export interface GridLayers {
  backbone: boolean;
  planned: boolean;
  constructionOnly: boolean;
}

const PHASE_LABEL: Record<Phase, string> = {
  construction: "Under construction",
  operational: "Operational",
  approval: "In approval",
  planned: "Planned",
};

const Swatch = ({ color, label }: { color: string; label: string }) => (
  <div className="flex items-center gap-2">
    <span className="h-0.5 w-4 rounded" style={{ background: color }} />
    <span className="text-[11px] text-slate-300">{label}</span>
  </div>
);

function Toggle({ on, label, onClick }: { on: boolean; label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex w-full items-center justify-between gap-2 rounded px-1 py-1 text-xs text-slate-300 hover:bg-ink-800"
    >
      <span>{label}</span>
      <span className={`flex h-3.5 w-6 items-center rounded-full px-0.5 transition ${on ? "bg-accent/70" : "bg-ink-700"}`}>
        <span className={`h-2.5 w-2.5 rounded-full bg-white transition ${on ? "translate-x-2.5" : ""}`} />
      </span>
    </button>
  );
}

export default function GridControl({ layers, setLayers }: { layers: GridLayers; setLayers: (l: GridLayers) => void }) {
  const [open, setOpen] = useState(false);
  const on = layers.backbone || layers.planned;
  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs transition ${
          on ? "border-accent/40 bg-accent/15 text-accent-300" : "border-line text-dim hover:text-slate-200"
        }`}
      >
        <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.4">
          <path d="M2 6h12M2 10h12M6 2v12M10 2v12" />
        </svg>
        Grid
        <svg viewBox="0 0 12 12" className="h-2.5 w-2.5" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="m3 4.5 3 3 3-3" />
        </svg>
      </button>
      {open && (
        <div className="absolute right-0 top-full z-40 mt-1 w-60 space-y-2.5 rounded-md border border-line bg-ink-900/97 p-3 shadow-xl backdrop-blur">
          <div>
            <div className="eyebrow mb-1.5">Layers</div>
            <Toggle on={layers.backbone} label="Transmission backbone" onClick={() => setLayers({ ...layers, backbone: !layers.backbone })} />
            <Toggle on={layers.planned} label="Planned corridors" onClick={() => setLayers({ ...layers, planned: !layers.planned })} />
            <Toggle
              on={layers.constructionOnly}
              label="Under construction only"
              onClick={() => setLayers({ ...layers, constructionOnly: !layers.constructionOnly })}
            />
          </div>
          <div className="border-t border-line pt-2">
            <div className="eyebrow mb-1.5">Backbone</div>
            <div className="space-y-1">
              <Swatch color={rgbCss(voltColor(380000))} label="380 kV" />
              <Swatch color={rgbCss(voltColor(220000))} label="220 kV" />
            </div>
          </div>
          <div className="border-t border-line pt-2">
            <div className="eyebrow mb-1.5">Planned phase</div>
            <div className="space-y-1">
              {(["construction", "operational", "approval", "planned"] as Phase[]).map((p) => (
                <Swatch key={p} color={rgbCss(PHASE_COLOR[p])} label={PHASE_LABEL[p]} />
              ))}
            </div>
          </div>
          <div className="border-t border-line pt-2 text-[10px] leading-snug text-faint">
            Plant arc = nearest substation (estimated connection).
          </div>
        </div>
      )}
    </div>
  );
}
