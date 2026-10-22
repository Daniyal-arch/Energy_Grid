// Dashboards: ready-made views (Europe, the US, countries, the world) and the user's own, saved in
// this browser. A dashboard is a set of datasets, an area (countries, or wherever the camera looks),
// a time mode and the countries' colour; the right panel's Dashboard tab gives its figures.

import { useEffect, useMemo, useState } from "react";

import { useFile } from "../app/data";
import { CATEGORIES, DATASETS, DATASET_BY_ID, EU27, colourOfDatasets, covers, coverageLabel, datasetModes, datasetsOn, iso3Of, layersOfDatasets, setCountryNames } from "../app/datasets";
import { DASHBOARDS, DASHBOARD_GROUPS, actions, findDashboard, layersOf, useApp, type DashboardGroup } from "../app/store";
import type { WorldFile } from "../app/types";
import { EUROPE_ISO3 } from "../lib/transition";

const muted = "text-[#8d94a1]";

/** Country names (ISO alpha-3) from the world outlines. */
export function useCountryNames(): (iso3: string) => string {
  const world = useFile<WorldFile>("world");
  return useMemo(() => {
    const m = new Map((world?.features ?? []).map((f) => [f.properties.iso3, f.properties.name]));
    m.set("MLT", "Malta");
    return (c: string) => m.get(c) ?? c;
  }, [world]);
}

const EU_ISO3 = EU27.map(iso3Of);
const same = (a: string[], b: string[]) => a.length === b.length && a.every((x) => b.includes(x));
/** "EU-27", "Europe", "Germany, France", "12 countries". */
export function areaText(area: string[] | null, name: (c: string) => string): string {
  if (!area) return "Wherever the map looks";
  if (same(area, EU_ISO3)) return "EU-27";
  if (same(area, [...EUROPE_ISO3])) return "Europe";
  if (area.length <= 3) return area.map(name).join(", ");
  return `${area.length} countries`;
}

/** The dashboard on screen: its name, and whether layers changed since it opened. */
export function useDashboardName(): { name: string; edited: boolean; mineId?: string } {
  const id = useApp((s) => s.dashboard);
  const edited = useApp((s) => s.edited);
  const title = useApp((s) => s.title);
  useApp((s) => s.mine);
  const names = useCountryNames();
  const d = findDashboard(id);
  // a country's own dashboard is named once the outlines have loaded
  const label = id?.startsWith("country:") ? `${names(id.slice(8))} in detail` : d?.label;
  return { name: title ?? label ?? "My view", edited: edited && !!d, mineId: d?.group === "Mine" ? d.id : undefined };
}

export function DashboardList({ onDone }: { onDone?: () => void }) {
  const current = useApp((s) => s.dashboard);
  const mine = useApp((s) => s.mine);
  const groupOf = (DASHBOARDS.find((d) => d.id === current)?.group ?? (mine.some((d) => d.id === current) ? "Mine" : "Europe")) as DashboardGroup;
  const [open, setOpen] = useState<DashboardGroup | null>(groupOf);
  const [copied, setCopied] = useState(false);
  const groups = DASHBOARD_GROUPS.filter((g) => g !== "Mine" || mine.length > 0);
  return (
    <div className="space-y-1">
      {groups.map((g) => {
        const list = g === "Mine" ? mine : DASHBOARDS.filter((d) => d.group === g);
        const isOpen = open === g;
        return (
          <div key={g} className={`rounded-lg ${isOpen ? "bg-white/[0.03]" : ""}`}>
            <button onClick={() => setOpen(isOpen ? null : g)} className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left hover:bg-white/[0.06]" aria-expanded={isOpen}>
              <span className="text-[11px] uppercase tracking-[0.18em] text-slate-200">{g === "Mine" ? "My dashboards" : g}</span>
              <span className={`flex items-center gap-2 text-[10px] ${muted}`}>
                {list.length}
                <span className="text-[9px]">{isOpen ? "▲" : "▼"}</span>
              </span>
            </button>
            {isOpen && (
              <div className="space-y-0.5 pb-1">
                {g === "Countries" && <AnyCountry onDone={onDone} />}
                {list.map((d) => (
                  <div key={d.id} className={`group flex items-start rounded-lg hover:bg-white/[0.07] ${current === d.id ? "bg-white/[0.1]" : ""}`}>
                    <button
                      onClick={() => {
                        actions.applyDashboard(d.id);
                        onDone?.();
                      }}
                      className="min-w-0 flex-1 px-3 py-1.5 pl-5 text-left"
                    >
                      <div className="text-[12.5px] text-slate-100">{d.label}</div>
                      <div className={`text-[10.5px] ${muted}`}>{d.blurb}</div>
                    </button>
                    {g === "Mine" && (
                      <span className="flex shrink-0 gap-1 px-2 py-1.5 opacity-60 group-hover:opacity-100">
                        <button
                          onClick={() => {
                            actions.applyDashboard(d.id);
                            actions.openBuilder({ kind: "save", id: d.id });
                            onDone?.();
                          }}
                          className="rounded px-1 text-[10.5px] text-slate-300 hover:bg-white/10"
                          title="Edit this dashboard"
                        >
                          Edit
                        </button>
                        <button onClick={() => actions.deleteDashboard(d.id)} className="rounded px-1 text-[10.5px] text-slate-400 hover:bg-white/10 hover:text-slate-100" title="Delete this dashboard">
                          ✕
                        </button>
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
      <div className="grid grid-cols-2 gap-1 pt-1">
        <button
          onClick={() => {
            actions.openBuilder({ kind: "new" });
            onDone?.();
          }}
          className="rounded-lg border border-sky-400/40 bg-sky-400/10 px-3 py-1.5 text-[11px] text-sky-100 hover:bg-sky-400/20"
        >
          + New dashboard
        </button>
        <button
          onClick={() => {
            const d = findDashboard(useApp.getState().dashboard);
            actions.openBuilder({ kind: "save", id: d?.group === "Mine" ? d.id : undefined });
            onDone?.();
          }}
          className="rounded-lg border border-white/10 px-3 py-1.5 text-[11px] text-slate-200 hover:bg-white/[0.07]"
        >
          Save this view
        </button>
      </div>
      <button
        onClick={() => {
          navigator.clipboard?.writeText(window.location.href).then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
          });
        }}
        className="w-full rounded-lg border border-white/10 px-3 py-1.5 text-[11px] text-slate-300 hover:bg-white/[0.07]"
      >
        {copied ? "Link copied" : "Copy a link to this view"}
      </button>
    </div>
  );
}

/** Any country's dashboard, found by name (the featured ones are listed under it). */
function AnyCountry({ onDone }: { onDone?: () => void }) {
  const world = useFile<WorldFile>("world");
  const [q, setQ] = useState("");
  const all = useMemo(() => (world?.features ?? []).map((f) => [f.properties.iso3, f.properties.name] as [string, string]).sort((a, b) => a[1].localeCompare(b[1])), [world]);
  useEffect(() => setCountryNames(all), [all]);
  const t = norm(q.trim());
  const hits = t ? all.filter(([, n]) => norm(n).includes(t)).slice(0, 6) : [];
  return (
    <div className="px-3 pb-1">
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Any country: type its name…"
        className="w-full rounded-md border border-white/10 bg-[#0d1119] px-2 py-1.5 text-[12px] text-slate-100 outline-none placeholder:text-slate-500 focus:border-sky-400/50"
      />
      {hits.map(([c, n]) => (
        <button
          key={c}
          onClick={() => {
            actions.applyDashboard(`country:${c}`);
            onDone?.();
          }}
          className="mt-0.5 block w-full rounded-md px-2 py-1 text-left text-[12px] text-slate-200 hover:bg-white/[0.08]"
        >
          {n} <span className={`text-[10.5px] ${muted}`}>· its dashboard</span>
        </button>
      ))}
    </div>
  );
}

export function DashboardsMenu() {
  const [open, setOpen] = useState(false);
  const { name, edited } = useDashboardName();
  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-[#0b0f16]/90 px-3 py-1.5 text-[12px] text-slate-200 backdrop-blur hover:bg-white/[0.08]"
        aria-expanded={open}
        title="Dashboards: ready-made views and your own"
      >
        <span className={`text-[9.5px] uppercase tracking-[0.16em] ${muted}`}>Dashboard</span>
        <span className="max-w-[220px] truncate">{name}</span>
        {edited && <span className="text-[10px] text-amber-200/80">edited</span>}
        <span className="text-[9px] text-slate-400">▼</span>
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute left-0 top-full z-50 mt-1 max-h-[75vh] w-80 overflow-y-auto rounded-xl border border-white/10 bg-[#0b0f16]/95 p-1.5 shadow-2xl backdrop-blur">
            <DashboardList onDone={() => setOpen(false)} />
          </div>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- the builder

const norm = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

function AreaPicker({ area, setArea }: { area: string[] | null; setArea: (a: string[] | null) => void }) {
  const world = useFile<WorldFile>("world");
  const name = useCountryNames();
  const [q, setQ] = useState("");
  const all = useMemo(() => (world?.features ?? []).map((f) => [f.properties.iso3, f.properties.name] as const).sort((a, b) => a[1].localeCompare(b[1])), [world]);
  const hits = q.trim().length >= 1 ? all.filter(([c, n]) => norm(n).includes(norm(q.trim())) && !area?.includes(c)).slice(0, 8) : [];
  const quick: [string, string[] | null][] = [
    ["Anywhere", null],
    ["EU-27", EU_ISO3],
    ["Europe", [...EUROPE_ISO3]],
    ["United States", ["USA"]],
  ];
  return (
    <div>
      <div className="flex flex-wrap gap-1">
        {quick.map(([label, a]) => {
          const on = a ? !!area && same(area, a) : !area;
          return (
            <button
              key={label}
              onClick={() => setArea(a)}
              className={`rounded-full border px-2.5 py-0.5 text-[11px] ${on ? "border-sky-400/50 bg-sky-400/15 text-sky-100" : "border-white/10 text-slate-300 hover:bg-white/[0.07]"}`}
            >
              {label}
            </button>
          );
        })}
      </div>
      {area && area.length > 0 && !quick.some(([, a]) => a && same(area, a)) && (
        <div className="mt-2 flex flex-wrap gap-1">
          {area.map((c) => (
            <button key={c} onClick={() => setArea(area.filter((x) => x !== c))} className="inline-flex items-center gap-1 rounded-full border border-white/15 bg-white/[0.05] px-2 py-0.5 text-[11px] text-slate-200 hover:border-white/30">
              {name(c)} <span className="text-slate-500">✕</span>
            </button>
          ))}
        </div>
      )}
      <div className="relative mt-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Add a country…"
          className="w-full rounded-md border border-white/10 bg-[#0d1119] px-2 py-1.5 text-[12px] text-slate-100 outline-none placeholder:text-slate-500 focus:border-sky-400/50"
        />
        {hits.length > 0 && (
          <div className="absolute inset-x-0 top-full z-10 mt-1 rounded-md border border-white/10 bg-[#0b0f16] p-1 shadow-xl">
            {hits.map(([c, n]) => (
              <button
                key={c}
                onClick={() => {
                  setArea([...(area ?? []), c]);
                  setQ("");
                }}
                className="block w-full rounded px-2 py-1 text-left text-[12px] text-slate-200 hover:bg-white/[0.08]"
              >
                {n}
              </button>
            ))}
          </div>
        )}
      </div>
      <div className={`mt-1 text-[10px] ${muted}`}>
        {area ? "The map frames these countries and the figures are for them." : "No area: the figures follow the region the map looks at, or the country you click."}
      </div>
    </div>
  );
}

export function DashboardBuilder() {
  const builder = useApp((s) => s.builder);
  if (!builder) return null;
  return <Builder key={`${builder.kind}:${builder.id ?? ""}`} kind={builder.kind} id={builder.id} />;
}

function Builder({ kind, id }: { kind: "new" | "save"; id?: string }) {
  const s = useApp.getState();
  const editing = id ? findDashboard(id) : undefined;
  const name = useCountryNames();
  const [label, setLabel] = useState(kind === "save" ? (editing?.label ?? "") : "");
  const [area, setArea] = useState<string[] | null>(kind === "save" ? s.area : null);
  const [chosen, setChosen] = useState<string[]>(kind === "save" ? datasetsOn(s.layers, s.colour).map((d) => d.id) : []);
  const [q, setQ] = useState("");
  const close = () => actions.openBuilder(null);
  // one colouring at a time: choosing one drops another
  const toggle = (d: string) =>
    setChosen((c) => (c.includes(d) ? c.filter((x) => x !== d) : [...c.filter((x) => !(DATASET_BY_ID.get(d)?.colour && DATASET_BY_ID.get(x)?.colour)), d]));
  const t = norm(q.trim());
  const shown = DATASETS.filter((d) => !t || norm(`${d.name} ${d.description} ${d.parts.map((p) => `${p.source} ${p.where.join(" ")}`).join(" ")}`).includes(t));
  const create = () => {
    const blurb = `${areaText(area, name)} · ${chosen.length} dataset${chosen.length === 1 ? "" : "s"}`;
    useApp.setState({ layers: layersOf(layersOfDatasets(chosen)), colour: colourOfDatasets(chosen), selection: null });
    actions.setArea(area);
    if (!area) useApp.setState({ flyTo: s.region === "us" ? "us" : s.region === "world" ? "world" : "europe" });
    actions.saveDashboard(label || (area ? areaText(area, name) : "My dashboard"), blurb, editing?.group === "Mine" ? editing.id : undefined);
    close();
  };
  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center overflow-y-auto bg-black/50 p-4 pt-16 backdrop-blur-[2px]" onClick={close}>
      <div className="w-full max-w-2xl rounded-2xl border border-white/10 bg-[#0b0f16]/98 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between border-b border-white/[0.07] px-5 py-3">
          <div>
            <h2 className="text-[16px] font-light tracking-wide text-slate-100">{editing?.group === "Mine" ? "Edit dashboard" : kind === "save" ? "Save this view as a dashboard" : "New dashboard"}</h2>
            <div className={`mt-0.5 text-[11px] ${muted}`}>Pick an area and the datasets; the map shows them and the right panel gives their figures. Saved in this browser; share it with a link.</div>
          </div>
          <button onClick={close} className="rounded-md border border-white/10 px-2 py-1 text-[11px] text-slate-300 hover:bg-white/10" aria-label="Close">
            ✕
          </button>
        </div>
        <div className="grid gap-5 px-5 py-4 md:grid-cols-[230px_1fr]">
          <div className="space-y-4">
            <label className="block">
              <span className={`text-[10px] uppercase tracking-[0.18em] ${muted}`}>Name</span>
              <input
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder={area ? areaText(area, name) : "My dashboard"}
                className="mt-1.5 w-full rounded-md border border-white/10 bg-[#0d1119] px-2 py-1.5 text-[12.5px] text-slate-100 outline-none placeholder:text-slate-500 focus:border-sky-400/50"
              />
            </label>
            <div>
              <div className={`mb-1.5 text-[10px] uppercase tracking-[0.18em] ${muted}`}>Area</div>
              <AreaPicker area={area} setArea={setArea} />
            </div>
          </div>
          <div className="min-w-0">
            <div className="mb-1.5 flex items-center justify-between">
              <span className={`text-[10px] uppercase tracking-[0.18em] ${muted}`}>Datasets · {chosen.length} chosen</span>
              {chosen.length > 0 && (
                <button onClick={() => setChosen([])} className="text-[10.5px] text-slate-400 hover:text-slate-100">
                  Clear
                </button>
              )}
            </div>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Find a dataset, a source or a country code…"
              className="mb-2 w-full rounded-md border border-white/10 bg-[#0d1119] px-2 py-1.5 text-[12px] text-slate-100 outline-none placeholder:text-slate-500 focus:border-sky-400/50"
            />
            <div className="max-h-[48vh] space-y-2 overflow-y-auto pr-1">
              {CATEGORIES.map((c) => {
                const list = shown.filter((d) => d.category === c);
                if (!list.length) return null;
                return (
                  <div key={c}>
                    <div className="px-1 pb-0.5 text-[11px] font-medium text-slate-300">{c}</div>
                    {list.map((d) => {
                      const here = covers(d, area);
                      const on = chosen.includes(d.id);
                      const modes = datasetModes(d);
                      return (
                        <label key={d.id} className={`flex cursor-pointer items-start gap-2 rounded-md px-1.5 py-1 hover:bg-white/[0.05] ${here ? "" : "opacity-45"}`}>
                          <input type="checkbox" checked={on} onChange={() => toggle(d.id)} className="mt-[3px] accent-sky-400" />
                          <span className="mt-[5px] h-2 w-2 shrink-0 rounded-full" style={{ background: d.color }} />
                          <span className="min-w-0 flex-1">
                            <span className="flex flex-wrap items-baseline gap-x-1.5 text-[12px] text-slate-100">
                              {d.name}
                              <span className="text-[9.5px] uppercase tracking-wider text-slate-500">{coverageLabel(d)}</span>
                              {!modes.includes("live") && <span className="text-[9.5px] text-amber-200/70">{modes.includes("day") ? "24 h view" : "years view"}</span>}
                            </span>
                            <span className={`block text-[10.5px] ${muted}`}>{here ? d.description : "No data in this area"}</span>
                          </span>
                        </label>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
        <div className="flex items-center justify-end gap-2 border-t border-white/[0.07] px-5 py-3">
          <button onClick={close} className="rounded-lg border border-white/10 px-3 py-1.5 text-[12px] text-slate-300 hover:bg-white/[0.07]">
            Cancel
          </button>
          <button
            onClick={create}
            disabled={!chosen.length}
            className="rounded-lg border border-sky-400/50 bg-sky-400/20 px-3 py-1.5 text-[12px] text-sky-50 hover:bg-sky-400/30 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {editing?.group === "Mine" ? "Save changes" : "Create dashboard"}
          </button>
        </div>
      </div>
    </div>
  );
}
