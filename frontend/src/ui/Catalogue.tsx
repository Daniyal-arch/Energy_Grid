// The data catalogue: every dataset by category with where it has data, its sources, how often it
// updates and the coverage registry's countries; switch any on from here. Opened from the
// Datasets panel; the same file (app/datasets.json) feeds the agent.

import { useState } from "react";

import { CATEGORIES, DATASETS, coverageLabel, datasetModes, datasetOn, toggleDataset } from "../app/datasets";
import { actions, useApp, type LayerGroup } from "../app/store";
import { DatasetDetails } from "./LayersPanel";

const muted = "text-[#8d94a1]";
const norm = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const MODE: Record<string, string> = { live: "live", day: "24 h", years: "years" };

export function Catalogue() {
  const open = useApp((s) => s.catalogue);
  const layers = useApp((s) => s.layers);
  const [cat, setCat] = useState<LayerGroup | "all">("all");
  const [q, setQ] = useState("");
  if (!open) return null;
  const t = norm(q.trim());
  const list = DATASETS.filter(
    (d) => (cat === "all" || d.category === cat) && (!t || norm(`${d.name} ${d.description} ${d.parts.map((p) => `${p.source} ${p.what} ${p.where.join(" ")}`).join(" ")}`).includes(t)),
  );
  const close = () => useApp.setState({ catalogue: false, coverageOf: null });
  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center overflow-y-auto bg-black/55 p-4 pt-12 backdrop-blur-[2px]" onClick={close}>
      <div className="flex max-h-[86vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#0b0f16]/98 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-3 border-b border-white/[0.07] px-5 py-3">
          <div>
            <h2 className="text-[16px] font-light tracking-wide text-slate-100">Data catalogue</h2>
            <div className={`mt-0.5 text-[11px] ${muted}`}>
              {DATASETS.length} datasets in {CATEGORIES.length} categories. Each names where it has data and its sources; every file and rule is in docs/DATA_SOURCES.md.
            </div>
          </div>
          <button onClick={close} className="rounded-md border border-white/10 px-2 py-1 text-[11px] text-slate-300 hover:bg-white/10" aria-label="Close">
            ✕
          </button>
        </div>
        <div className="grid min-h-0 flex-1 md:grid-cols-[190px_1fr]">
          <nav className="flex gap-1 overflow-x-auto border-b border-white/[0.07] p-2 md:block md:space-y-0.5 md:overflow-y-auto md:border-b-0 md:border-r">
            {(["all", ...CATEGORIES] as const).map((c) => {
              const n = c === "all" ? DATASETS.length : DATASETS.filter((d) => d.category === c).length;
              return (
                <button
                  key={c}
                  onClick={() => setCat(c)}
                  className={`flex shrink-0 items-center justify-between gap-2 rounded-md px-2.5 py-1.5 text-left text-[12px] md:w-full ${cat === c ? "bg-white/[0.1] text-slate-50" : "text-slate-300 hover:bg-white/[0.05]"}`}
                >
                  {c === "all" ? "All datasets" : c}
                  <span className={`text-[10.5px] ${muted}`}>{n}</span>
                </button>
              );
            })}
          </nav>
          <div className="min-h-0 overflow-y-auto p-3">
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Find a dataset, a source or a country code…"
              className="mb-3 w-full rounded-md border border-white/10 bg-[#0d1119] px-2 py-1.5 text-[12px] text-slate-100 outline-none placeholder:text-slate-500 focus:border-sky-400/50"
            />
            {list.length === 0 && <div className={`text-[12px] ${muted}`}>Nothing found.</div>}
            <div className="space-y-2">
              {list.map((d) => {
                const on = datasetOn(d, layers);
                const where = coverageLabel(d) || "World";
                return (
                  <div key={d.id} className="rounded-xl border border-white/[0.07] bg-white/[0.02]">
                    <div className="flex items-start gap-2.5 px-3 pt-2.5">
                      <span className="mt-[5px] h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: d.color }} />
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-baseline gap-x-2 text-[13px] text-slate-100">
                          {d.name}
                          <span className="text-[9.5px] uppercase tracking-wider text-slate-500">{where}</span>
                          <span className={`text-[10px] ${muted}`}>
                            {cat === "all" ? `${d.category} · ` : ""}
                            {datasetModes(d)
                              .map((m) => MODE[m])
                              .join(", ")}
                          </span>
                        </div>
                      </div>
                      <button
                        onClick={() => {
                          toggleDataset(d);
                          actions.showCoverage(null);
                        }}
                        className={`shrink-0 rounded-md border px-2 py-0.5 text-[11px] ${on ? "border-sky-400/50 bg-sky-400/15 text-sky-100" : "border-white/10 text-slate-300 hover:bg-white/[0.08]"}`}
                      >
                        {on ? "On the map ✓" : "Show on map"}
                      </button>
                    </div>
                    <div className="pt-1.5">
                      <DatasetDetails d={d} tinted={false} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
