// Layers: what colours the countries, and the map's layers in a few plain groups. Each layer
// says in one line what it shows; its key appears only while it is on. Layers that need
// another time mode are not listed (a line under the group says where they are).

import { useState, type ReactNode } from "react";

import { FUEL_COLOR, FUEL_LABEL } from "../lib/energy";
import { IRENA_METRICS, IRENA_STOPS, IRENA_TICKS } from "../lib/irena";
import { PRICE_METRICS, stopGradient } from "../lib/prices";
import { SUN_MAX_WM2 } from "../lib/sunLayer";
import { rgbCss, type RGB } from "../lib/theme";
import { METRICS, metricGradient } from "../lib/transition";
import { ACCESS_STOPS, ACCESS_TICKS, BR_COLOR, DC_COLOR, ON_COLOR, TW_COLOR, US_COLOR } from "../lib/world";
import { HV_STEPS, PLANT_TYPE_COLOR, PLANT_TYPE_LABEL, STATUS_LABEL } from "../lib/worldPlants";
import { CABLE_STYLE, FLOW, GAS, HVDC, MULTI_ZONE, OFFLINE_STOPS, PRICE_STOPS, SHARE_STOPS, SUBSTATION, VOLTAGE_BANDS, gradientCss } from "../app/colors";
import { BEAM_MIN_MW } from "../app/geo";
import { useDataStore } from "../app/data";
import type { StatsFile } from "../app/types";
import { priceRange, rampCss } from "../map/priceTerrain";
import { currentDay } from "../map/tooltip";
import {
  COLOURS,
  LAYERS,
  LAYER_GROUPS,
  actions,
  useApp,
  type ColourId,
  type LayerGroup,
  type LayerId,
  type LayerInfo,
  type PlantStatus,
  type TimeMode,
} from "../app/store";

const muted = "text-[#8d94a1]";
const MODE_LABEL: Record<TimeMode, string> = { live: "Live", day: "24 h", years: "Years" };

function Scale({ gradient, ticks, note }: { gradient: string; ticks: string[]; note?: ReactNode }) {
  return (
    <div>
      <div className="h-2 rounded-sm" style={{ background: gradient }} />
      <div className={`mt-0.5 flex justify-between text-[9px] ${muted}`}>
        {ticks.map((t) => (
          <span key={t}>{t}</span>
        ))}
      </div>
      {note && <div className={`mt-1 text-[9.5px] leading-snug ${muted}`}>{note}</div>}
    </div>
  );
}

const Swatch = ({ color, label, kind = "dot" }: { color: string; label: string; kind?: "dot" | "line" | "dash" | "ring" | "half" }) => (
  <span className="inline-flex items-center gap-1.5 text-[10px] text-slate-300">
    {kind === "dot" && <span className="h-2 w-2 rounded-full" style={{ background: color }} />}
    {kind === "ring" && <span className="h-2 w-2 rounded-full border" style={{ borderColor: color }} />}
    {kind === "half" && <span className="h-2 w-2 rounded-full border" style={{ borderColor: color, background: `color-mix(in srgb, ${color} 35%, transparent)` }} />}
    {kind === "line" && <span className="h-[2px] w-4 rounded" style={{ background: color }} />}
    {kind === "dash" && <span className="w-4 border-t border-dashed" style={{ borderColor: color }} />}
    {label}
  </span>
);
const Swatches = ({ children }: { children: ReactNode }) => <div className="flex flex-wrap gap-x-3 gap-y-1">{children}</div>;
const fuelSwatches = (groups: string[], color: Record<string, RGB>, label: Record<string, string>) => (
  <Swatches>
    {groups.map((g) => (
      <Swatch key={g} color={rgbCss(color[g] ?? [150, 150, 150])} label={label[g] ?? g} />
    ))}
  </Swatches>
);
const Note = ({ children }: { children: ReactNode }) => <div className={`mt-1 text-[9.5px] leading-snug ${muted}`}>{children}</div>;

/** The status key shared by GEM's point layers. */
const pointStatus = (color: string) => (
  <Swatches>
    <Swatch color={color} label="operating" />
    <Swatch color={color} kind="half" label="building" />
    <Swatch color={color} kind="ring" label="planned" />
    <Swatch color="rgb(130,134,146)" label="idle" />
  </Swatches>
);
const pipeStatus = (color: string) => (
  <Swatches>
    <Swatch color={color} kind="line" label="operating" />
    <Swatch color={color} kind="dash" label="building or planned" />
  </Swatches>
);

export function ColourLegend({ colour }: { colour: ColourId }) {
  if (colour === "renewable") return <Scale gradient={gradientCss(SHARE_STOPS)} ticks={["0 %", "50 %", "100 % renewable"]} note="share of generation, newest 15-min interval (ENTSO-E)" />;
  if (colour === "price")
    return (
      <Scale
        gradient={gradientCss(PRICE_STOPS)}
        ticks={["0", "125", "≥ 250 €/MWh"]}
        note={
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-3 rounded-sm" style={{ background: rgbCss(MULTI_ZONE) }} /> several price zones (see the panel)
          </span>
        }
      />
    );
  if (colour === "offline") return <Scale gradient={gradientCss(OFFLINE_STOPS)} ticks={["0", "15", "≥ 30 GW offline"]} note="generating units unavailable now (ENTSO-E A80)" />;
  if (colour.startsWith("ir_")) {
    const m = IRENA_METRICS.find((x) => x.id === colour.slice(3))!;
    return <Scale gradient={gradientCss(IRENA_STOPS)} ticks={IRENA_TICKS} note={`${m.note}; the years mode shows each year, live the newest`} />;
  }
  if (colour === "access") return <Scale gradient={gradientCss(ACCESS_STOPS)} ticks={ACCESS_TICKS} note="newest year per country (World Bank)" />;
  if (colour.startsWith("pr_")) {
    const m = PRICE_METRICS.find((x) => x.id === colour.slice(3))!;
    return <Scale gradient={stopGradient(m.stops)} ticks={m.ticks} note={`${m.note} · 12 months · zone markers where a country has several zones`} />;
  }
  if (colour.startsWith("tr_")) {
    const m = METRICS.find((x) => x.id === colour.slice(3))!;
    return <Scale gradient={metricGradient(m)} ticks={m.ticks} note={`${m.note} (Ember)`} />;
  }
  return null;
}

/** The Prices layer's key: the colour runs over the replayed day's own range. */
function PriceKey() {
  const mode = useApp((s) => s.mode);
  const files = useDataStore((d) => d.files);
  const range = priceRange(mode === "day" ? currentDay() : null, files.stats as StatsFile | undefined);
  const ticks = range ? [`${Math.round(range[0])}`, `${Math.round((range[0] + range[1]) / 2)}`, `${Math.round(range[1])} €/MWh`] : ["cheapest", "", "dearest"];
  return (
    <Scale
      gradient={rampCss}
      ticks={ticks}
      note={`Slab height: day-ahead price (100 €/MWh stands 50 km; several zones: their median). Colour: cheapest to dearest ${mode === "day" ? "of this day" : "right now"}; below zero lies flat in cyan. Towers on the slabs: generation. ENTSO-E.`}
    />
  );
}

function LayerLegend({ id }: { id: LayerId }) {
  const status = useApp((s) => s.plantStatus);
  switch (id) {
    case "prices":
      return <PriceKey />;
    case "flows":
      return <Note>Arrows point the way the power goes; labels from 1 GW. ENTSO-E, every 15 minutes.</Note>;
    case "liveGrids":
      return (
        <Swatches>
          <Swatch color={rgbCss(US_COLOR)} label="US" kind="ring" />
          <Swatch color={rgbCss(BR_COLOR)} label="Brazil" kind="ring" />
          <Swatch color="rgb(120,222,255)" label="Australia" kind="ring" />
          <Swatch color={rgbCss(TW_COLOR)} label="Taiwan" kind="ring" />
          <Swatch color={rgbCss(ON_COLOR)} label="Ontario" kind="ring" />
        </Swatches>
      );
    case "towers":
      return <Note>Stacked by source; 1 GW = 14 km tall.</Note>;
    case "gridEU":
      return (
        <Swatches>
          {VOLTAGE_BANDS.map((b) => (
            <Swatch key={b.min} color={rgbCss(b.color)} kind="line" label={b.label} />
          ))}
        </Swatches>
      );
    case "hvdc":
      return <Swatches><Swatch color={rgbCss(HVDC)} kind="dash" label="HVDC link" /></Swatches>;
    case "substations":
      return <Swatches><Swatch color={rgbCss(SUBSTATION)} label="from zoom 5" /></Swatches>;
    case "gridWorld":
      return (
        <Swatches>
          {HV_STEPS.map(([kv, c], i) => (
            <Swatch key={kv} color={c} kind="line" label={i === 0 ? "220 kV" : `${kv} kV`} />
          ))}
        </Swatches>
      );
    case "cables":
      return (
        <Swatches>
          {Object.entries(CABLE_STYLE).map(([k, s]) => (
            <Swatch key={k} color={`rgba(${s.color.join(",")})`} kind="line" label={s.label} />
          ))}
        </Swatches>
      );
    case "predicted":
      return <Note>Predicted from night-time lights and roads, not surveyed.</Note>;
    case "plantsEU":
      return (
        <>
          {fuelSwatches(["nuclear", "coal", "gas", "hydro", "wind", "solar", "bio"], FUEL_COLOR, { ...FUEL_LABEL, gas: "Gas & oil" })}
          <Note>Size grows with capacity. Pick a country to see every unit (beams from {BEAM_MIN_MW} MW).</Note>
        </>
      );
    case "plantsWorld":
      return (
        <>
          <div className="mb-1.5 flex flex-wrap gap-1">
            {(["operating", "construction", "planned", "retired"] as PlantStatus[]).map((st) => (
              <button
                key={st}
                onClick={() => actions.setPlantStatus(st)}
                className={`rounded-full border px-2 py-0.5 text-[10px] ${st === status ? "border-white/30 bg-white/15 text-slate-100" : "border-white/10 text-slate-400 hover:text-slate-200"}`}
              >
                {STATUS_LABEL[st]}
              </button>
            ))}
          </div>
          {fuelSwatches(Object.keys(PLANT_TYPE_COLOR), PLANT_TYPE_COLOR, PLANT_TYPE_LABEL)}
        </>
      );
    case "gasPipes":
      return <>{pipeStatus("rgb(255,196,96)")}<Note>Thicker = more capacity. Global Energy Monitor.</Note></>;
    case "oilPipes":
      return <>{pipeStatus("rgb(222,110,82)")}<Note>Thicker = more capacity. Global Energy Monitor.</Note></>;
    case "lngTerminals":
      return (
        <>
          <Swatches>
            <Swatch color="rgb(255,150,92)" label="export" />
            <Swatch color="rgb(255,215,150)" label="import" />
          </Swatches>
          {pointStatus("rgb(255,150,92)")}
        </>
      );
    case "coalTerminals":
      return pointStatus("rgb(196,182,166)");
    case "oilGasFields":
      return (
        <>
          <Swatches>
            <Swatch color="rgb(214,96,64)" label="oil" />
            <Swatch color="rgb(255,150,92)" label="gas" />
            <Swatch color="rgb(235,120,80)" label="both" />
          </Swatches>
          {pointStatus("rgb(214,96,64)")}
        </>
      );
    case "coalMines":
      return pointStatus("rgb(160,146,132)");
    case "methane":
      return <Note>Each glow is one satellite observation; bigger = more methane per hour.</Note>;
    case "gas":
      return <Swatches><Swatch color={rgbCss(GAS)} kind="ring" label="storage site (SciGRID_gas)" /></Swatches>;
    case "financeCoal":
    case "financeGas":
      return (
        <>
          <Swatches>
            <Swatch color={id === "financeCoal" ? "rgb(232,204,128)" : "rgb(255,170,60)"} kind="line" label="money abroad, thicker = more" />
            <Swatch color={id === "financeCoal" ? "rgb(232,204,128)" : "rgb(255,170,60)"} label="project, by money received" />
          </Swatches>
          <Note>Arrows run from the financiers' home country, for flows of $300 m or more. Smaller flows and lending at home count in the panel's totals. Global Energy Monitor.</Note>
        </>
      );
    case "steel":
      return (
        <>
          <Swatches>
            <Swatch color="rgb(120,200,255)" label="electric arc furnace" />
            <Swatch color="rgb(200,205,215)" label="blast furnace and other" />
          </Swatches>
          {pointStatus("rgb(120,200,255)")}
        </>
      );
    case "cement":
      return pointStatus("rgb(206,192,166)");
    case "chemicals":
      return <Note>Plant locations; the inventory gives no capacity.</Note>;
    case "ironOre":
      return pointStatus("rgb(206,112,88)");
    case "dataCentres":
      return <Note>Zoomed out: count per area. A mapped subset, not every site.</Note>;
    case "wind":
      return <Note>Brighter = stronger. ECMWF forecast (live), Open-Meteo (24 h).</Note>;
    case "sun":
      return <Scale gradient="linear-gradient(90deg, rgba(255,214,72,0), rgba(255,214,72,0.8))" ticks={["0", `${SUN_MAX_WM2} W/m²`]} />;
    case "night":
      return <Note>Darkness at the time on the clock.</Note>;
  }
  return null;
}

function Toggle({ on }: { on: boolean }) {
  return (
    <span className={`relative h-[16px] w-[28px] shrink-0 rounded-full transition-colors ${on ? "bg-sky-400/80" : "bg-white/15"}`}>
      <span className={`absolute top-[2px] h-[12px] w-[12px] rounded-full bg-white shadow transition-all ${on ? "left-[14px]" : "left-[2px]"}`} />
    </span>
  );
}

function LayerRow({ info }: { info: LayerInfo }) {
  const on = useApp((s) => s.layers[info.id]);
  return (
    <div className={`rounded-lg transition-colors ${on ? "bg-white/[0.05]" : "hover:bg-white/[0.03]"}`}>
      <button onClick={() => actions.toggleLayer(info.id)} className="flex w-full items-center gap-2.5 px-2 py-1.5 text-left" aria-pressed={on}>
        <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: info.color, opacity: on ? 1 : 0.45 }} />
        <span className="min-w-0 flex-1">
          <span className={`flex items-baseline gap-1.5 text-[12.5px] ${on ? "text-slate-50" : "text-slate-300"}`}>
            <span className="truncate">{info.label}</span>
            {info.coverage !== "World" && <span className="shrink-0 text-[9.5px] uppercase tracking-wider text-slate-500">{info.coverage}</span>}
          </span>
          <span className={`block truncate text-[10.5px] ${muted}`}>{info.desc}</span>
        </span>
        <Toggle on={on} />
      </button>
      {on && (
        <div className="px-2 pb-2 pl-[30px]">
          <LayerLegend id={info.id} />
        </div>
      )}
    </div>
  );
}

function Group({ group, open, onToggle }: { group: LayerGroup; open: boolean; onToggle: () => void }) {
  const mode = useApp((s) => s.mode);
  const layers = useApp((s) => s.layers);
  const inGroup = LAYERS.filter((l) => l.group === group);
  const shown = inGroup.filter((l) => !l.modes || l.modes.includes(mode));
  const elsewhere = inGroup.filter((l) => l.modes && !l.modes.includes(mode));
  const active = shown.filter((l) => layers[l.id]).length;
  if (!shown.length) return null;
  return (
    <section className="border-t border-white/[0.06] first:border-t-0">
      <button onClick={onToggle} className="flex w-full items-center gap-2 px-3 py-2.5 text-left hover:bg-white/[0.03]" aria-expanded={open}>
        <span className={`text-[10px] text-slate-500 transition-transform ${open ? "rotate-90" : ""}`}>▶</span>
        <span className="flex-1 text-[12px] font-medium text-slate-200">{group}</span>
        <span className={`text-[10.5px] ${active ? "text-sky-300" : "text-slate-500"}`}>{active ? `${active} on` : `${shown.length}`}</span>
      </button>
      {open && (
        <div className="px-1.5 pb-2">
          {shown.map((l) => (
            <LayerRow key={l.id} info={l} />
          ))}
          {elsewhere.length > 0 && (
            <div className={`px-2 pt-1 text-[10px] ${muted}`}>
              Also in {[...new Set(elsewhere.flatMap((l) => l.modes ?? []))].map((m) => MODE_LABEL[m]).join(" and ")}: {elsewhere.map((l) => l.label.toLowerCase()).join(", ")}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

export default function LayersPanel() {
  const colour = useApp((s) => s.colour);
  const mode = useApp((s) => s.mode);
  const layers = useApp((s) => s.layers);
  const [open, setOpen] = useState<Partial<Record<LayerGroup, boolean>>>({});
  const colours = COLOURS.filter((c) => c.modes.includes(mode));
  const colourGroups = [...new Set(colours.map((c) => c.group))];
  const active = LAYERS.filter((l) => layers[l.id] && (!l.modes || l.modes.includes(mode)));
  const groupHasActive = (g: LayerGroup) => active.some((l) => l.group === g);
  return (
    <div>
      <section className="px-3 pb-3 pt-2">
        <label className="text-[10px] uppercase tracking-[0.18em] text-[#8d94a1]" htmlFor="colour-by">
          Colour the countries by
        </label>
        <select
          id="colour-by"
          value={colour}
          onChange={(e) => actions.setColour(e.target.value as ColourId)}
          className="mt-1.5 w-full rounded-md border border-white/10 bg-[#0d1119] px-2 py-1.5 text-[12.5px] text-slate-100 outline-none focus:border-sky-400/50"
        >
          {colourGroups.map((g) =>
            g ? (
              <optgroup key={g} label={g}>
                {colours
                  .filter((c) => c.group === g)
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.label}
                    </option>
                  ))}
              </optgroup>
            ) : (
              colours
                .filter((c) => c.group === g)
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.label === "Plain" ? "Nothing (plain map)" : c.label}
                  </option>
                ))
            ),
          )}
        </select>
        {colour !== "none" && (
          <div className="mt-2">
            <ColourLegend colour={colour} />
          </div>
        )}
      </section>

      <div className="flex items-center justify-between border-t border-white/[0.06] px-3 pb-1.5 pt-2.5">
        <span className="text-[10px] uppercase tracking-[0.18em] text-[#8d94a1]">On the map</span>
        {active.length > 0 && (
          <button onClick={() => active.forEach((l) => actions.toggleLayer(l.id))} className="text-[10.5px] text-slate-400 hover:text-slate-100">
            Clear all
          </button>
        )}
      </div>
      <div className="flex flex-wrap gap-1 px-3 pb-2.5">
        {active.length === 0 && <span className={`text-[11px] ${muted}`}>Nothing yet: switch a layer on below.</span>}
        {active.map((l) => (
          <button
            key={l.id}
            onClick={() => actions.toggleLayer(l.id)}
            className="group inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.04] py-0.5 pl-2 pr-1.5 text-[10.5px] text-slate-200 hover:border-white/25"
            title={`Hide ${l.label.toLowerCase()}`}
          >
            <span className="h-2 w-2 rounded-full" style={{ background: l.color }} />
            {l.label}
            <span className="text-slate-500 group-hover:text-slate-200">✕</span>
          </button>
        ))}
      </div>

      {LAYER_GROUPS.map((g) => (
        <Group key={g} group={g} open={open[g] ?? groupHasActive(g)} onToggle={() => setOpen((o) => ({ ...o, [g]: !(o[g] ?? groupHasActive(g)) }))} />
      ))}
      <div className="h-2" />
    </div>
  );
}
