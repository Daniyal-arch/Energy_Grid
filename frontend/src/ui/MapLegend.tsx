// The key to what is on the map, under the collapsed Layers button (the open panel shows
// the same keys itself): one compact line per layer drawn in this time mode, with its source.

import type { ReactNode } from "react";

import { FUEL_COLOR, STACK_ORDER } from "../lib/energy";
import { SUN_MAX_WM2 } from "../lib/sunLayer";
import { rgbCss } from "../lib/theme";
import { FLOW, VOLTAGE_BANDS } from "../app/colors";
import { useDataStore } from "../app/data";
import { COLOURS, LAYERS, useApp, type LayerId } from "../app/store";
import type { StatsFile } from "../app/types";
import { priceRange, rampCss } from "../map/priceTerrain";
import { currentDay } from "../map/tooltip";
import { ColourLegend } from "./LayersPanel";

const muted = "text-[#8d94a1]";
const SHORT: Record<string, string> = { nuclear: "Nuclear", coal: "Coal", gas: "Gas", oil: "Oil", hydro: "Hydro", bio: "Bio", wind: "Wind", solar: "Solar" };

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-start gap-1.5">
      <span className="w-[40px] shrink-0 pt-px text-[9.5px] font-medium text-slate-100">{label}</span>
      <div className="min-w-0 flex-1 text-[9px] leading-[13px] text-slate-300">{children}</div>
    </div>
  );
}

const Line = ({ color }: { color: string }) => <span className="mr-1 inline-block h-[2px] w-2.5 rounded align-middle" style={{ background: color }} />;
const Dot = ({ color }: { color: string }) => <span className="mr-0.5 inline-block h-1.5 w-1.5 rounded-sm align-middle" style={{ background: color }} />;

function PriceRow() {
  const mode = useApp((s) => s.mode);
  const files = useDataStore((d) => d.files);
  const range = priceRange(mode === "day" ? currentDay() : null, files.stats as StatsFile | undefined);
  return (
    <Row label="Prices">
      <div className="flex items-center gap-1.5">
        <span className="h-1.5 w-16 shrink-0 rounded-sm" style={{ background: rampCss }} />
        <span className="tabular-nums">{range ? `${Math.round(range[0])}–${Math.round(range[1])} €/MWh` : "cheap to dear"}</span>
      </div>
      <div className={muted}>height &amp; colour = price · ENTSO-E</div>
    </Row>
  );
}

function LayerRow({ id }: { id: LayerId }) {
  switch (id) {
    case "prices":
      return <PriceRow />;
    case "towers":
      return (
        <Row label="Towers">
          <div className="flex flex-wrap gap-x-1.5">
            {STACK_ORDER.filter((g) => SHORT[g]).map((g) => (
              <span key={g} className="whitespace-nowrap">
                <Dot color={rgbCss(FUEL_COLOR[g])} />
                {SHORT[g]}
              </span>
            ))}
          </div>
          <div className={muted}>by source, 1 GW = 14 km · ENTSO-E</div>
        </Row>
      );
    case "flows":
      return (
        <Row label="Flows">
          <Line color={rgbCss(FLOW)} />
          way the power goes · ENTSO-E
        </Row>
      );
    case "gridEU":
      return (
        <Row label="Grid">
          {VOLTAGE_BANDS.map((b, i) => (
            <span key={b.min} className="mr-1 whitespace-nowrap">
              <Line color={rgbCss(b.color)} />
              {i < VOLTAGE_BANDS.length - 1 ? b.label.replace(" kV", "") : b.label}
            </span>
          ))}
        </Row>
      );
    default: {
      const info = LAYERS.find((l) => l.id === id);
      return info ? <Row label={info.label}>{info.desc}</Row> : null;
    }
  }
}

/** Wind, sunshine and night share one line. */
function WeatherRow({ wind, sun, night }: { wind: boolean; sun: boolean; night: boolean }) {
  const mode = useApp((s) => s.mode);
  return (
    <Row label="Weather">
      <div className="whitespace-nowrap">
        {wind && "wind 100 m"}
        {wind && sun && " · "}
        {sun && (
          <>
            <span className="mr-1 inline-block h-1.5 w-5 rounded-sm align-middle" style={{ background: "linear-gradient(90deg, rgba(255,214,72,0.05), rgba(255,214,72,0.9))" }} />
            sun 0–{SUN_MAX_WM2} W/m²
          </>
        )}
      </div>
      <div>
        {night && "night shadow"}
        {night && (wind || sun) && " · "}
        {(wind || sun) && <span className={muted}>{mode === "day" ? "Open-Meteo" : "ECMWF"}, model</span>}
      </div>
    </Row>
  );
}

const WEATHER = new Set<LayerId>(["wind", "sun", "night"]);

export default function MapLegend() {
  const mode = useApp((s) => s.mode);
  const colour = useApp((s) => s.colour);
  const layers = useApp((s) => s.layers);
  const shown = LAYERS.filter((l) => layers[l.id] && (!l.modes || l.modes.includes(mode)));
  const has = (id: LayerId) => shown.some((l) => l.id === id);
  if (colour === "none" && !shown.length) return null;
  return (
    <div className="pointer-events-none mt-1 w-[252px] space-y-1 rounded-xl border border-white/10 bg-[#0b0f16]/95 px-2.5 py-1.5 backdrop-blur">
      {colour !== "none" && (
        <Row label="Colour">
          <div className="mb-0.5">{COLOURS.find((c) => c.id === colour)?.label}</div>
          <ColourLegend colour={colour} />
        </Row>
      )}
      {shown
        .filter((l) => !WEATHER.has(l.id))
        .map((l) => (
          <LayerRow key={l.id} id={l.id} />
        ))}
      {(has("wind") || has("sun") || has("night")) && <WeatherRow wind={has("wind")} sun={has("sun")} night={has("night")} />}
    </div>
  );
}
