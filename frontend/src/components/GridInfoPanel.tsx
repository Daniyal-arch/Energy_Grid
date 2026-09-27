import { PHASE_COLOR, type Phase } from "../lib/grid";
import type { InfraItem, InfraValue, MapFeaturePick } from "../lib/infrastructure";
import { rgbCss } from "../lib/theme";

const PHASE_LABEL: Record<Phase, string> = {
  construction: "Under construction",
  operational: "Operational",
  approval: "In approval",
  planned: "Planned",
};

const INFRA_LABEL: Record<InfraItem["kind"], string> = {
  rail: "Rail infrastructure",
  rail_station: "Rail operating point",
  rail_crossing: "Rail crossing",
  rail_bridge: "Rail bridge",
  rail_tunnel: "Rail tunnel",
  gas_pipeline: "Gas infrastructure",
  gas_compressor: "Gas compressor",
  gas_consumer: "Gas demand node",
  gas_production: "Gas production node",
  gas_powerplant: "Gas power plant",
  port: "Port & logistics",
  airport: "Airport & air logistics",
  gas_storage: "Gas storage",
  lng_terminal: "LNG infrastructure",
  gas_border: "Cross-border dependency",
  industry: "Strategic industry",
};

const kv = (v: number) => (v ? `${Math.round(v / 1000)} kV` : "-");

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-line bg-ink-850 px-2.5 py-1.5">
      <div className="eyebrow">{label}</div>
      <div className="break-words text-slate-200">{value}</div>
    </div>
  );
}

function text(value: InfraValue | undefined, fallback = "-"): string {
  if (value === null || value === undefined || value === "") return fallback;
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

function metric(value: InfraValue | undefined, unit: string, digits = 0): string {
  if (typeof value !== "number") return "-";
  return `${value.toLocaleString("en-DE", { maximumFractionDigits: digits })} ${unit}`;
}

function railNodeRole(value: InfraValue | undefined): string {
  const type = text(value).toLowerCase();
  if (type.includes("haltepunkt")) return "Passenger stop on the line, usually without switches.";
  if (type.includes("abzweig")) return "Junction where routes branch or merge.";
  if (type.includes("überleit") || type.includes("Ã¼berleit") || type.includes("ueberleit")) {
    return "Crossover point where trains can move between parallel tracks.";
  }
  if (type.includes("ausweich") || type.includes("anschluss")) {
    return "Passing, siding, or industrial/access connection point.";
  }
  if (type.includes("block")) return "Signalling block point controlling train spacing.";
  if (type.includes("bahnhof")) return "Station or yard operating point with tracks, signals, or switching role.";
  return "Rail operating point used by DB InfraGO for routing, control, or access.";
}

function InfrastructureDetails({ pick }: { pick: Extract<MapFeaturePick, { kind: "infrastructure" }> }) {
  const { item, manifest } = pick;
  const p = item.properties;
  const source = manifest.sources[item.sourceKey];
  return (
    <>
      <div className="grid grid-cols-2 gap-2 text-xs">
        {item.kind === "rail" && (
          <>
            <Fact label="Route" value={text(p.route)} />
            <Fact label="Tracks" value={text(p.tracks)} />
            <Fact label="Electrification" value={text(p.electrification)} />
            <Fact label="State" value={text(p.state)} />
          </>
        )}
        {(item.kind === "rail_bridge" || item.kind === "rail_tunnel") && (
          <>
            <Fact label="Route" value={text(p.route)} />
            <Fact label="Length" value={metric(p.length_m, "m")} />
            <Fact label="State" value={text(p.state)} />
            <Fact label="Crossing" value={text(p.crossing_type)} />
          </>
        )}
        {item.kind === "rail_station" && (
          <>
            <Fact label="Code" value={text(p.code)} />
            <Fact label="Type" value={text(p.type)} />
            <Fact label="Physical role" value={railNodeRole(p.type)} />
            <Fact label="Route" value={text(p.route)} />
            <Fact label="State" value={text(p.state)} />
          </>
        )}
        {item.kind === "rail_crossing" && (
          <>
            <Fact label="Physical role" value="Road or path crossing the railway line." />
            <Fact label="Route" value={text(p.route)} />
            <Fact label="Road type" value={text(p.road_type)} />
            <Fact label="Protection" value={text(p.protection)} />
            <Fact label="State" value={text(p.state)} />
          </>
        )}
        {item.kind === "gas_pipeline" && (
          <>
            <Fact label="Diameter" value={metric(p.diameter_mm, "mm")} />
            <Fact label="Pressure" value={metric(p.pressure_bar, "bar")} />
            <Fact label="Model capacity" value={metric(p.capacity_mcmd, "mcm/day", 1)} />
            <Fact label="Length" value={metric(p.length_km, "km", 1)} />
          </>
        )}
        {(item.kind === "gas_compressor" ||
          item.kind === "gas_consumer" ||
          item.kind === "gas_production" ||
          item.kind === "gas_powerplant") && (
          <>
            <Fact label="Capacity" value={metric(p.capacity_mcmd, "mcm/day", 1)} />
            <Fact label="Power" value={metric(p.gas_power_mw, "MW", 1)} />
            <Fact label="From" value={text(p.from_country)} />
            <Fact label="To" value={text(p.to_country)} />
          </>
        )}
        {item.kind === "port" && (
          <>
            <Fact label="Port code" value={text(p.port_id)} />
            <Fact label="NUTS region" value={text(p.nuts_code)} />
          </>
        )}
        {item.kind === "airport" && (
          <>
            <Fact label="ICAO" value={text(p.icao)} />
            <Fact label="TEN-T" value={text(p.tentec)} />
            <Fact label="Passenger class" value={text(p.passenger_class)} />
          </>
        )}
        {(item.kind === "gas_storage" || item.kind === "lng_terminal") && (
          <>
            <Fact label="Working gas" value={metric(p.working_gas_mcm, "mcm", 1)} />
            <Fact label="Send-out" value={metric(p.sendout_mcmd, "mcm/day", 1)} />
          </>
        )}
        {item.kind === "gas_border" && (
          <>
            <Fact label="From" value={text(p.from_country)} />
            <Fact label="To" value={text(p.to_country)} />
          </>
        )}
        {item.kind === "industry" && (
          <>
            <Fact label="Sector" value={text(p.sector)} />
            <Fact label="Activity" value={text(p.activity)} />
            <Fact label="Reporting year" value={text(p.reporting_year)} />
            <Fact label="Seveso site" value={text(p.seveso)} />
          </>
        )}
      </div>
      <div className="border-t border-line pt-3 text-[11px] leading-relaxed text-slate-400">
        <div className="mb-1 font-medium text-slate-200">{source.name}</div>
        <div>{source.coverage}</div>
        <div className="mt-2 text-faint">
          Published {source.published}. {source.caveat}
        </div>
        <a
          href={source.url}
          target="_blank"
          rel="noreferrer"
          className="mt-2 inline-block text-accent-300 hover:text-accent-200"
        >
          Open source dataset
        </a>
      </div>
      <p className="text-[10px] leading-relaxed text-faint">
        Map heights and moving trails are visual encodings for legibility. Interpret only the labeled values as
        quantitative measures.
      </p>
    </>
  );
}

function titleOf(pick: MapFeaturePick): string {
  if (pick.kind === "infrastructure") return pick.item.name;
  if (pick.kind === "corridor") return pick.seg.name || pick.seg.number || "Planned corridor";
  if (pick.kind === "substation") return pick.sub.name || "Substation";
  return `Cross-border flow - ${pick.flow.neighbor_zone}`;
}

export default function GridInfoPanel({ pick, onClose }: { pick: MapFeaturePick; onClose: () => void }) {
  return (
    <aside className="absolute right-0 top-0 z-20 flex h-full w-[340px] flex-col gap-4 overflow-y-auto border-l border-line bg-ink-900/95 p-5 backdrop-blur-xl">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="eyebrow text-accent-400">
            {pick.kind === "infrastructure" ? INFRA_LABEL[pick.item.kind] : "Electricity grid"}
          </div>
          <h2 className="mt-1 break-words text-base font-semibold leading-tight text-slate-100">{titleOf(pick)}</h2>
        </div>
        <button onClick={onClose} title="Close" className="text-slate-500 hover:text-slate-200">
          x
        </button>
      </div>

      {pick.kind === "infrastructure" && <InfrastructureDetails pick={pick} />}

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
            Source: Bundesnetzagentur Netzausbau (BBPlG/EnLAG). Project phase is the official corridor status.
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

      {pick.kind === "exchange" && (
        <>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <Fact label="Neighbor" value={pick.flow.neighbor_zone} />
            <Fact
              label="Flow"
              value={`${pick.flow.value_mw >= 0 ? "Import" : "Export"} - ${Math.abs(pick.flow.value_mw).toFixed(0)} MW`}
            />
            <Fact label="Source" value="Energy-Charts.info" />
          </div>
          <p className="text-[10px] leading-relaxed text-faint">
            Source: Energy-Charts.info (Fraunhofer ISE). Physical cross-border flow, hourly.
          </p>
        </>
      )}
    </aside>
  );
}
