import { useEffect, useMemo, useState } from "react";

import type { Site } from "../lib/api";
import type { GridLayers } from "./GridControl";
import { INFRA_COLOR, loadInfrastructure, type InfrastructureManifest } from "../lib/infrastructure";
import { num } from "../lib/format";
import { rgbCss, TECH_COLOR } from "../lib/theme";

function atlasClock(tick: number): string {
  const minutes = Math.floor(((tick % 90_000) / 90_000) * 24 * 60);
  const hh = Math.floor(minutes / 60).toString().padStart(2, "0");
  const mm = (minutes % 60).toString().padStart(2, "0");
  return `${hh}:${mm}`;
}

function activeCount(base: number, max: number, tick: number, phaseShift = 0): number {
  const phase = (((tick + phaseShift) % 90_000) / 90_000) * Math.PI;
  return Math.round(base + Math.sin(phase) * Math.max(0, max - base));
}

function Metric({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="border-t border-line px-3 py-2">
      <div className="flex items-center gap-2">
        <span className="h-1.5 w-1.5 rounded-full" style={{ background: color }} />
        <span className="eyebrow">{label}</span>
      </div>
      <div className="mt-0.5 font-mono text-lg font-semibold tabular-nums text-slate-100">{value}</div>
    </div>
  );
}

function LayerRow({
  color,
  label,
  count,
  on,
  onToggle,
}: {
  color: string;
  label: string;
  count: number | string;
  on: boolean;
  onToggle: () => void;
}) {
  const countLabel = typeof count === "number" ? num(count) : count;
  return (
    <button
      onClick={onToggle}
      className={`flex w-full items-center justify-between gap-3 rounded px-1.5 py-1 text-left text-xs transition ${
        on ? "bg-white/[0.04] text-slate-200" : "text-slate-600 hover:bg-white/[0.03] hover:text-slate-400"
      }`}
    >
      <span className="flex min-w-0 items-center gap-2">
        <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: color, opacity: on ? 1 : 0.35 }} />
        <span className="truncate">{label}</span>
      </span>
      <span className="flex items-center gap-2">
        <span className="font-mono tabular-nums">{countLabel}</span>
        <span className={`h-3 w-5 rounded-full ${on ? "bg-accent/70" : "bg-ink-700"}`}>
          <span className={`block h-3 w-3 rounded-full bg-white transition ${on ? "translate-x-2" : ""}`} />
        </span>
      </span>
    </button>
  );
}

export default function AtlasHud({
  layers,
  setLayers,
  sites,
  onRailScene,
  onPowerScene,
  onAtlasScene,
}: {
  layers: GridLayers;
  setLayers: (layers: GridLayers) => void;
  sites: Site[];
  onRailScene: () => void;
  onPowerScene: () => void;
  /** back to the plain atlas (leaves the rail/power scene styling) */
  onAtlasScene: () => void;
}) {
  const [manifest, setManifest] = useState<InfrastructureManifest | null>(null);
  const [tick, setTick] = useState(() => Date.now());

  useEffect(() => {
    loadInfrastructure().then((data) => setManifest(data.manifest)).catch(() => {});
  }, []);

  useEffect(() => {
    const id = setInterval(() => setTick(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const counts = manifest?.counts ?? {};
  const energyCount = sites.length || counts.energy_sites || 0;
  const activeRail = activeCount(7, Math.min(520, Math.max(80, (counts.rail_routes ?? 0) / 3)), tick);
  const activeGas = activeCount(12, Math.min(360, Math.max(70, (counts.gas_pipeline_segments ?? 0) / 5)), tick, 18_000);
  const activePorts = activeCount(3, Math.min(45, counts.ports ?? 0), tick, 36_000);
  const showCore = () => {
    onAtlasScene();
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
  };
  const hideAll = () => {
    onAtlasScene();
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
  };

  const visibleRows = useMemo(
    () => [
      {
        color: rgbCss(INFRA_COLOR.state_boundary),
        label: "Federal states",
        count: counts.state_boundaries ?? 0,
        on: layers.stateBoundaries,
        onToggle: () => setLayers({ ...layers, stateBoundaries: !layers.stateBoundaries }),
      },
      {
        color: rgbCss(TECH_COLOR.solar),
        label: "Energy sites",
        count: energyCount,
        on: layers.energyAssets,
        onToggle: () => setLayers({ ...layers, energyAssets: !layers.energyAssets }),
      },
      {
        color: rgbCss(INFRA_COLOR.port),
        label: "Electricity grid",
        count: "grid",
        on: layers.backbone,
        onToggle: () => setLayers({ ...layers, backbone: !layers.backbone }),
      },
      {
        color: rgbCss(INFRA_COLOR.rail_bridge),
        label: "Power corridors",
        count: "plan",
        on: layers.planned,
        onToggle: () => setLayers({ ...layers, planned: !layers.planned }),
      },
      {
        color: rgbCss(INFRA_COLOR.rail),
        label: "Power exchange",
        count: "flow",
        on: layers.exchangeFlows,
        onToggle: () => setLayers({ ...layers, exchangeFlows: !layers.exchangeFlows }),
      },
      {
        color: rgbCss(INFRA_COLOR.rail),
        label: "Rail routes",
        count: counts.rail_routes ?? 0,
        on: layers.rail,
        onToggle: () => setLayers({ ...layers, rail: !layers.rail }),
      },
      {
        color: rgbCss(INFRA_COLOR.rail_station),
        label: "Rail nodes",
        count: counts.rail_nodes ?? 0,
        on: layers.railStations,
        onToggle: () => setLayers({ ...layers, railStations: !layers.railStations }),
      },
      {
        color: rgbCss(INFRA_COLOR.rail_bridge),
        label: "Rail structures",
        count: counts.rail_structures ?? 0,
        on: layers.railStructures,
        onToggle: () => setLayers({ ...layers, railStructures: !layers.railStructures }),
      },
      {
        color: rgbCss(INFRA_COLOR.gas_pipeline),
        label: "Gas corridors",
        count: counts.gas_pipeline_segments ?? 0,
        on: layers.gas,
        onToggle: () => setLayers({ ...layers, gas: !layers.gas }),
      },
      {
        color: rgbCss(INFRA_COLOR.gas_storage),
        label: "Gas storage/borders",
        count: counts.gas_nodes ?? 0,
        on: layers.gasNodes,
        onToggle: () => setLayers({ ...layers, gasNodes: !layers.gasNodes }),
      },
      {
        color: rgbCss(INFRA_COLOR.gas_compressor),
        label: "Gas facilities",
        count: counts.gas_nodes ?? 0,
        on: layers.gasFacilities,
        onToggle: () => setLayers({ ...layers, gasFacilities: !layers.gasFacilities }),
      },
      {
        color: rgbCss(INFRA_COLOR.port),
        label: "Ports",
        count: counts.ports ?? 0,
        on: layers.ports,
        onToggle: () => setLayers({ ...layers, ports: !layers.ports }),
      },
      {
        color: rgbCss(INFRA_COLOR.airport),
        label: "Airports",
        count: counts.airports ?? 0,
        on: layers.airports,
        onToggle: () => setLayers({ ...layers, airports: !layers.airports }),
      },
      {
        color: rgbCss(INFRA_COLOR.industry),
        label: "Strategic industry",
        count: counts.industrial_sites ?? 0,
        on: layers.industry,
        onToggle: () => setLayers({ ...layers, industry: !layers.industry }),
      },
    ],
    [counts, energyCount, layers, setLayers],
  );

  return (
    <aside className="w-[320px] overflow-hidden rounded-md border border-line bg-ink-950/78 shadow-2xl backdrop-blur-xl">
      <div className="border-b border-line px-4 py-3">
        <div className="eyebrow text-accent-300">Germany infrastructure atlas</div>
        <div className="mt-1 flex items-end justify-between gap-4">
          <div className="font-serif text-[26px] uppercase tracking-[0.18em] text-slate-100">Germany</div>
          <div className="font-mono text-3xl font-light tabular-nums text-slate-100">{atlasClock(tick)}</div>
        </div>
      </div>

      <div className="grid grid-cols-3 divide-x divide-line">
        <Metric label="Rail motion" value={num(activeRail)} color={rgbCss(INFRA_COLOR.rail)} />
        <Metric label="Gas motion" value={num(activeGas)} color={rgbCss(INFRA_COLOR.gas_pipeline)} />
        <Metric label="Port nodes" value={num(activePorts)} color={rgbCss(INFRA_COLOR.port)} />
      </div>

      <div className="space-y-2 px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="eyebrow">Source-backed layers</div>
          <div className="text-[10px] text-faint">{manifest ? manifest.generated_at : "loading"}</div>
        </div>
        <div className="grid grid-cols-4 gap-1">
          <button onClick={onPowerScene} className="rounded border border-sky-400/35 bg-sky-400/10 px-2 py-1 text-xs text-sky-200 hover:bg-sky-400/20">
            Power
          </button>
          <button onClick={onRailScene} className="rounded border border-accent/35 bg-accent/10 px-2 py-1 text-xs text-accent-200 hover:bg-accent/20">
            Rail
          </button>
          <button onClick={showCore} className="rounded border border-line px-2 py-1 text-xs text-slate-300 hover:bg-ink-800">
            Core
          </button>
          <button onClick={hideAll} className="rounded border border-line px-2 py-1 text-xs text-slate-300 hover:bg-ink-800">
            Hide all
          </button>
        </div>
        <div className="space-y-1.5">
          {visibleRows.map((row) => (
            <LayerRow key={row.label} {...row} />
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 divide-x divide-line border-t border-line">
        <div className="px-4 py-2">
          <div className="eyebrow">Hydrogen core</div>
          <div className="font-mono text-sm font-semibold tabular-nums text-slate-100">
            {manifest?.hydrogen_context.approved_length_km.toLocaleString("en-DE") ?? "-"} km
          </div>
          <div className="text-[10px] text-faint">approved network</div>
        </div>
        <div className="px-4 py-2">
          <div className="eyebrow">Energy sites</div>
          <div className="font-mono text-sm font-semibold tabular-nums text-slate-100">
            {num(energyCount)}
          </div>
          <div className="text-[10px] text-faint">MaStR point layer</div>
        </div>
      </div>
    </aside>
  );
}
