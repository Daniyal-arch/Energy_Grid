import { useEffect, useState } from "react";

import { DEFAULT_VOLTAGES, PHASE_COLOR, voltColor, type Phase, type VoltageTiers } from "../lib/grid";
import { INFRA_COLOR } from "../lib/infrastructure";
import { TECH_COLOR, rgbCss } from "../lib/theme";

export interface GridLayers {
  stateBoundaries: boolean;
  energyAssets: boolean;
  backbone: boolean;
  planned: boolean;
  exchangeFlows: boolean;
  constructionOnly: boolean;
  rail: boolean;
  railStations: boolean;
  railStructures: boolean;
  gas: boolean;
  gasNodes: boolean;
  gasFacilities: boolean;
  ports: boolean;
  airports: boolean;
  industry: boolean;
  voltages: VoltageTiers;
}

export const DEFAULT_GRID_LAYERS: GridLayers = {
  stateBoundaries: true,
  energyAssets: true,
  backbone: true,
  planned: false,
  exchangeFlows: false,
  constructionOnly: false,
  rail: true,
  railStations: false,
  railStructures: true,
  gas: true,
  gasNodes: true,
  gasFacilities: false,
  ports: true,
  airports: true,
  industry: false,
  voltages: DEFAULT_VOLTAGES,
};

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

function VoltageToggle({
  color,
  label,
  on,
  onClick,
}: {
  color: string;
  label: string;
  on: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="flex w-full items-center justify-between gap-2 rounded px-1 py-1 hover:bg-ink-800"
    >
      <span className="flex items-center gap-2">
        <span className="h-0.5 w-4 rounded" style={{ background: color, opacity: on ? 1 : 0.35 }} />
        <span className={`text-[11px] ${on ? "text-slate-300" : "text-faint"}`}>{label}</span>
      </span>
      <span className={`flex h-3.5 w-6 items-center rounded-full px-0.5 transition ${on ? "bg-accent/70" : "bg-ink-700"}`}>
        <span className={`h-2.5 w-2.5 rounded-full bg-white transition ${on ? "translate-x-2.5" : ""}`} />
      </span>
    </button>
  );
}

function Toggle({
  on,
  label,
  color,
  onClick,
}: {
  on: boolean;
  label: string;
  color?: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="flex w-full items-center justify-between gap-2 rounded px-1 py-1 text-xs text-slate-300 hover:bg-ink-800"
    >
      <span className="flex items-center gap-2">
        {color && <span className="h-2 w-2 rounded-full" style={{ background: color, opacity: on ? 1 : 0.35 }} />}
        {label}
      </span>
      <span className={`flex h-3.5 w-6 items-center rounded-full px-0.5 transition ${on ? "bg-accent/70" : "bg-ink-700"}`}>
        <span className={`h-2.5 w-2.5 rounded-full bg-white transition ${on ? "translate-x-2.5" : ""}`} />
      </span>
    </button>
  );
}

export default function GridControl({
  layers,
  setLayers,
  onOpenChange,
}: {
  layers: GridLayers;
  setLayers: (l: GridLayers) => void;
  onOpenChange?: (open: boolean) => void;
}) {
  const [open, setOpen] = useState(false);
  useEffect(() => onOpenChange?.(open), [open, onOpenChange]);
  const on =
    layers.stateBoundaries ||
    layers.energyAssets ||
    layers.backbone ||
    layers.planned ||
    layers.exchangeFlows ||
    layers.rail ||
    layers.railStations ||
    layers.railStructures ||
    layers.gas ||
    layers.gasNodes ||
    layers.gasFacilities ||
    layers.ports ||
    layers.airports ||
    layers.industry;
  const showCore = () =>
    setLayers({
      ...layers,
      stateBoundaries: true,
      energyAssets: true,
      backbone: true,
      planned: false,
      exchangeFlows: false,
      constructionOnly: false,
      rail: true,
      railStations: false,
      railStructures: true,
      gas: true,
      gasNodes: true,
      gasFacilities: false,
      ports: true,
      airports: true,
      industry: false,
    });
  const hideAll = () =>
    setLayers({
      ...layers,
      stateBoundaries: false,
      energyAssets: false,
      backbone: false,
      planned: false,
      exchangeFlows: false,
      constructionOnly: false,
      rail: false,
      railStations: false,
      railStructures: false,
      gas: false,
      gasNodes: false,
      gasFacilities: false,
      ports: false,
      airports: false,
      industry: false,
    });

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
        Atlas layers
        <svg viewBox="0 0 12 12" className="h-2.5 w-2.5" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="m3 4.5 3 3 3-3" />
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 top-full z-40 mt-1 max-h-[calc(100vh-7rem)] w-80 space-y-2.5 overflow-y-auto rounded-md border border-line bg-ink-900/97 p-3 shadow-xl backdrop-blur">
          <div className="grid grid-cols-2 gap-1 border-b border-line pb-2">
            <button onClick={showCore} className="rounded border border-line px-2 py-1 text-xs text-slate-300 hover:bg-ink-800">
              Core
            </button>
            <button onClick={hideAll} className="rounded border border-line px-2 py-1 text-xs text-slate-300 hover:bg-ink-800">
              Hide all
            </button>
          </div>

          <div>
            <div className="eyebrow mb-1.5">Reference</div>
            <Toggle
              on={layers.stateBoundaries}
              label="Federal states"
              color={rgbCss(INFRA_COLOR.state_boundary)}
              onClick={() => setLayers({ ...layers, stateBoundaries: !layers.stateBoundaries })}
            />
          </div>

          <div className="border-t border-line pt-2">
            <div className="eyebrow mb-1.5">Energy system</div>
            <Toggle
              on={layers.energyAssets}
              label="Energy generation sites"
              color={rgbCss(TECH_COLOR.solar)}
              onClick={() => setLayers({ ...layers, energyAssets: !layers.energyAssets })}
            />
            <Toggle
              on={layers.backbone}
              label="Electricity transmission"
              color={rgbCss(voltColor(380000))}
              onClick={() => setLayers({ ...layers, backbone: !layers.backbone })}
            />
            <Toggle
              on={layers.planned}
              label="Power expansion corridors"
              color={rgbCss(PHASE_COLOR.construction)}
              onClick={() => setLayers({ ...layers, planned: !layers.planned })}
            />
            <Toggle
              on={layers.exchangeFlows}
              label="Cross-border power exchange"
              color={rgbCss([150, 230, 255])}
              onClick={() => setLayers({ ...layers, exchangeFlows: !layers.exchangeFlows })}
            />
            <Toggle
              on={layers.gas}
              label="Gas pipelines"
              color={rgbCss(INFRA_COLOR.gas_pipeline)}
              onClick={() => setLayers({ ...layers, gas: !layers.gas })}
            />
            <Toggle
              on={layers.gasNodes}
              label="Storage, LNG, border points"
              color={rgbCss(INFRA_COLOR.gas_storage)}
              onClick={() => setLayers({ ...layers, gasNodes: !layers.gasNodes })}
            />
            <Toggle
              on={layers.gasFacilities}
              label="Gas compressors and demand"
              color={rgbCss(INFRA_COLOR.gas_compressor)}
              onClick={() => setLayers({ ...layers, gasFacilities: !layers.gasFacilities })}
            />
          </div>

          <div className="border-t border-line pt-2">
            <div className="eyebrow mb-1.5">Mobility and logistics</div>
            <Toggle
              on={layers.rail}
              label="DB rail network"
              color={rgbCss(INFRA_COLOR.rail)}
              onClick={() => setLayers({ ...layers, rail: !layers.rail })}
            />
            <Toggle
              on={layers.railStations}
              label="Rail operating points"
              color={rgbCss(INFRA_COLOR.rail_station)}
              onClick={() => setLayers({ ...layers, railStations: !layers.railStations })}
            />
            <Toggle
              on={layers.railStructures}
              label="Rail bridges and tunnels"
              color={rgbCss(INFRA_COLOR.rail_bridge)}
              onClick={() => setLayers({ ...layers, railStructures: !layers.railStructures })}
            />
            <Toggle
              on={layers.ports}
              label="Ports"
              color={rgbCss(INFRA_COLOR.port)}
              onClick={() => setLayers({ ...layers, ports: !layers.ports })}
            />
            <Toggle
              on={layers.airports}
              label="Airports"
              color={rgbCss(INFRA_COLOR.airport)}
              onClick={() => setLayers({ ...layers, airports: !layers.airports })}
            />
          </div>

          <div className="border-t border-line pt-2">
            <div className="eyebrow mb-1.5">Industrial geography</div>
            <Toggle
              on={layers.industry}
              label="Strategic industry"
              color={rgbCss(INFRA_COLOR.industry)}
              onClick={() => setLayers({ ...layers, industry: !layers.industry })}
            />
          </div>

          <div className="border-t border-line pt-2">
            <div className="eyebrow mb-1.5">Transmission voltage</div>
            <div className="space-y-0.5">
              <VoltageToggle
                color={rgbCss(voltColor(380000))}
                label="380 kV"
                on={layers.voltages.v380}
                onClick={() => setLayers({ ...layers, voltages: { ...layers.voltages, v380: !layers.voltages.v380 } })}
              />
              <VoltageToggle
                color={rgbCss(voltColor(220000))}
                label="220 kV"
                on={layers.voltages.v220}
                onClick={() => setLayers({ ...layers, voltages: { ...layers.voltages, v220: !layers.voltages.v220 } })}
              />
              <VoltageToggle
                color={rgbCss(voltColor(110000))}
                label="110 kV"
                on={layers.voltages.v110}
                onClick={() => setLayers({ ...layers, voltages: { ...layers.voltages, v110: !layers.voltages.v110 } })}
              />
            </div>
          </div>

          {layers.planned && (
            <div className="border-t border-line pt-2">
              <div className="eyebrow mb-1.5">Power corridor phase</div>
              <Toggle
                on={layers.constructionOnly}
                label="Show build phase only"
                onClick={() => setLayers({ ...layers, constructionOnly: !layers.constructionOnly })}
              />
              <div className="mt-1 space-y-1">
                {(["construction", "operational", "approval", "planned"] as Phase[]).map((p) => (
                  <Swatch key={p} color={rgbCss(PHASE_COLOR[p])} label={PHASE_LABEL[p]} />
                ))}
              </div>
            </div>
          )}

          <div className="border-t border-line pt-2 text-[10px] leading-snug text-faint">
            Moving lights are atlas animations for direction, density, and attention. Click any feature for source,
            date, and caveat.
          </div>
        </div>
      )}
    </div>
  );
}
