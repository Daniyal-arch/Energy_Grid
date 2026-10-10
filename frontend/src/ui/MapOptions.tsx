// Switches that change how something on the map draws, shown on the map while it matters:
// bars or beams for a selected country's plants (live mode).

import { BEAM_MIN_MW, HEX_KM } from "../app/geo";
import { actions, useApp } from "../app/store";

const box = "pointer-events-auto rounded-xl border border-white/10 bg-[#0b0f16]/90 px-2.5 py-1.5 backdrop-blur";

export default function MapOptions() {
  const mode = useApp((s) => s.mode);
  const plantsOn = useApp((s) => s.layers.plantsEU);
  const plantStyle = useApp((s) => s.plantStyle);
  const sel = useApp((s) => s.selection);
  const showPlants = mode === "live" && plantsOn && sel?.kind === "country" && !!sel.iso2;
  if (!showPlants) return null;
  return (
    <div className="pointer-events-none absolute left-1/2 top-14 z-20 flex max-w-[92vw] -translate-x-1/2 flex-col items-center gap-1.5 md:top-16">
      {showPlants && (
        <div className={box}>
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase tracking-[0.16em] text-slate-400">Plants as</span>
            {(["bars", "beams"] as const).map((m) => (
              <button
                key={m}
                onClick={() => actions.setPlantStyle(m)}
                className={`rounded-md border px-2.5 py-1 text-[11.5px] ${
                  plantStyle === m ? "border-white/30 bg-white/15 text-slate-100" : "border-white/10 text-slate-300 hover:bg-white/[0.07]"
                }`}
              >
                {m === "bars" ? "Bars" : "Beams & fields"}
              </button>
            ))}
          </div>
          <div className="mt-1 text-center text-[10px] text-[#8d94a1]">
            {plantStyle === "bars"
              ? "Columns: units ≥ 10 MW, height ∝ √ installed capacity (not current output)"
              : `Beams: plants ≥ ${BEAM_MIN_MW} MW. Fields: smaller units summed per ${HEX_KM * 2} km hexagon.`}
          </div>
        </div>
      )}
    </div>
  );
}
