import type { GridSnapshotLatest } from "../lib/api";
import { EXCHANGE_COLOR, PLANT_COLOR, PLANT_LABEL, POWER_LINE_COLOR, type PlantGroup } from "../lib/powerScene";
import { rgbCss, type RGB } from "../lib/theme";

// Legend + live readout for the power view. Every number is a stored backend
// observation (energy-charts via /grid/latest), shown as-is — nothing is summed
// or derived here.

// the map's dots are the line colour mixed toward white (FlowPathLayer dotWhite)
const whiten = (c: RGB, t: number): RGB => [c[0] + (255 - c[0]) * t, c[1] + (255 - c[1]) * t, c[2] + (255 - c[2]) * t];

function LineSwatch({ color }: { color: RGB }) {
  return (
    <svg width="26" height="10" viewBox="0 0 26 10" aria-hidden className="shrink-0">
      <line x1="1" y1="5" x2="25" y2="5" stroke={rgbCss(color)} strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="16" cy="5" r="2.3" fill={rgbCss(whiten(color, 0.7))} />
    </svg>
  );
}

function PlantSwatch({ color, ring = false }: { color: RGB; ring?: boolean }) {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden className="shrink-0">
      <circle cx="7" cy="7" r="6" fill={rgbCss(color, 0.22)} />
      <circle cx="7" cy="7" r="3.4" fill={ring ? "none" : rgbCss(color)} stroke={rgbCss(color)} strokeWidth={ring ? 1.6 : 0} />
    </svg>
  );
}

const gw = (mw: number | undefined) => (mw == null ? "–" : `${(mw / 1000).toFixed(1)} GW`);

export default function PowerLegend({ latest }: { latest: GridSnapshotLatest }) {
  const value = (metric: string) => {
    const v = latest[metric]?.value;
    return v == null ? undefined : Number(v);
  };
  const ts = latest.renewable_share?.ts ?? latest.gen_wind?.ts;
  const asOf = ts ? new Date(ts).toISOString().slice(11, 16) : null;
  const share = value("renewable_share");
  const carbon = value("carbon_intensity");

  const plants: Array<{ group: PlantGroup; main?: string; detail?: string }> = [
    { group: "wind", main: gw(value("gen_wind")) },
    { group: "solar", main: gw(value("gen_solar")), detail: "parks on map; output incl. rooftop" },
    {
      group: "fossil",
      detail: `lignite ${gw(value("gen_lignite"))} · coal ${gw(value("gen_hard_coal"))} · gas ${gw(value("gen_gas"))}`,
    },
    {
      group: "other",
      detail: `biomass ${gw(value("gen_biomass"))} · hydro ${gw(value("gen_hydro"))} · storage ring`,
    },
  ];

  return (
    <aside className="w-[284px] rounded-md border border-line bg-ink-950/80 px-4 py-3 shadow-2xl backdrop-blur-xl">
      <div className="flex items-center justify-between">
        <div className="eyebrow text-accent-300">Power system</div>
        <div className="flex items-center gap-1.5 text-[10px] text-faint">
          <span className="h-1.5 w-1.5 rounded-full bg-positive" />
          {asOf ? `live · ${asOf} UTC` : "waiting for live data"}
        </div>
      </div>

      <div className="mt-2 grid grid-cols-2 gap-x-4">
        <div>
          <div className="eyebrow">Renewable share</div>
          <div className="font-mono text-[15px] font-semibold tabular-nums text-slate-100">
            {share == null ? "–" : `${share.toFixed(0)} %`}
          </div>
        </div>
        <div>
          <div className="eyebrow">Carbon</div>
          <div className="font-mono text-[15px] font-semibold tabular-nums text-slate-100">
            {carbon == null ? "–" : `${Math.round(carbon)} g/kWh`}
          </div>
        </div>
      </div>

      <div className="mt-2.5 border-t border-line pt-2">
        <div className="eyebrow mb-1.5">Plants · generation now</div>
        <div className="space-y-1.5">
          {plants.map((row) => (
            <div key={row.group} className="flex items-start gap-2.5">
              <div className="pt-0.5">
                <PlantSwatch color={PLANT_COLOR[row.group]} />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-2 text-xs text-slate-200">
                  <span>{PLANT_LABEL[row.group]}</span>
                  {row.main && <span className="font-mono tabular-nums text-slate-100">{row.main}</span>}
                </div>
                {row.detail && <div className="truncate text-[10px] text-faint">{row.detail}</div>}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-2.5 grid grid-cols-2 gap-x-3 gap-y-1.5 border-t border-line pt-2.5 text-xs text-slate-300">
        <div className="flex items-center gap-2">
          <LineSwatch color={POWER_LINE_COLOR.v380} />
          <span>380 kV</span>
        </div>
        <div className="flex items-center gap-2">
          <LineSwatch color={POWER_LINE_COLOR.v220} />
          <span>220 kV</span>
        </div>
        <div className="col-span-2 flex items-center gap-2">
          <LineSwatch color={EXCHANGE_COLOR} />
          <span>Cross-border flow</span>
        </div>
      </div>

      <p className="mt-2 text-[10px] leading-relaxed text-faint">
        Dots travel with the power. Cross-border: energy-charts physical flows. Per-line flows inside Germany are
        not published: dots show the typical north-to-south transfer. Plant links run to the nearest 220/380 kV
        substation (approximate); small units are grouped when zoomed out. Glow and pulse follow live output.
      </p>
    </aside>
  );
}
