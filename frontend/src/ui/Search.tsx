// Search: countries (Europe and the world), price zones, live-grid regions and power plants.
// The 183,000 GEM plant names load only when asked for.

import { useEffect, useMemo, useRef, useState } from "react";

import { ZONE_POINT, type PricesFile } from "../lib/prices";
import { BR_POINT, NEM_NAME, NEM_POINT, ON_POINT, TW_POINT, US_POINT, type BrazilFile, type UsFile } from "../lib/world";
import { STATUS_LABEL, type WorldPlantsFile } from "../lib/worldPlants";
import { ensure, useFile } from "../app/data";
import { ISO3 } from "../lib/transition";
import { actions, useApp, type PlantStatus, type Selection } from "../app/store";
import type { CountriesFile, PlantsFile, WorldFile } from "../app/types";

interface Hit {
  key: string;
  label: string;
  kind: string;
  go: () => void;
}

const norm = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const fly = (center: [number, number], zoom: number) => useApp.setState({ flyTo: { center, zoom } });

export default function Search({ onDone, autoFocus = false }: { onDone?: () => void; autoFocus?: boolean }) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [gem, setGem] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const countries = useFile<CountriesFile>("countries");
  const world = useFile<WorldFile>(open ? "world" : null);
  const prices = useFile<PricesFile>(open ? "prices" : null);
  const plants = useFile<PlantsFile>(open ? "plants" : null);
  const us = useFile<UsFile>(open ? "us" : null);
  const br = useFile<BrazilFile>(open ? "brazil" : null);
  const wp = useFile<WorldPlantsFile>(gem ? "worldPlants" : null);
  const names = useFile<{ names: string[] }>(gem ? "plantNames" : null);
  useEffect(() => {
    if (autoFocus) input.current?.focus();
  }, [autoFocus]);

  const hits = useMemo<Hit[]>(() => {
    const t = norm(q.trim());
    if (t.length < 2) return [];
    const out: Hit[] = [];
    const match = (s: string | null | undefined) => !!s && norm(s).includes(t);
    const done = (sel: Selection | null, then?: () => void) => () => {
      if (sel) actions.select(sel);
      then?.();
      setQ("");
      setOpen(false);
      onDone?.();
    };
    const europe = new Set(countries?.countries.map((c) => c.iso) ?? []);
    for (const c of countries?.countries ?? [])
      if (match(c.name) || t === c.iso.toLowerCase())
        out.push({ key: `c:${c.iso}`, label: c.name, kind: "Country · Europe", go: done({ kind: "country", iso2: c.iso, iso3: ISO3[c.iso] }) });
    const iso2Of = Object.fromEntries(Object.entries(ISO3).map(([a, b]) => [b, a]));
    for (const f of world?.features ?? []) {
      const code = f.properties.iso3;
      if (iso2Of[code] && europe.has(iso2Of[code])) continue;
      if (match(f.properties.name) || t === code.toLowerCase())
        out.push({ key: `w:${code}`, label: f.properties.name, kind: "Country", go: done({ kind: "country", iso3: code }) });
    }
    for (const zone of Object.keys(prices?.zones ?? {}))
      if (match(zone))
        out.push({
          key: `z:${zone}`,
          label: zone,
          kind: "Price zone",
          go: done({ kind: "zone", id: zone }, () => {
            const s = useApp.getState();
            if (!s.colour.startsWith("pr_")) actions.setColour("pr_mean");
            useApp.setState({ tab: "prices" });
            if (ZONE_POINT[zone]) fly(ZONE_POINT[zone].at, 4.6);
          }),
        });
    const region = (grid: "us" | "br" | "au" | "tw" | "on", id: string, name: string, at: [number, number] | undefined, kind: string) => {
      if (!at || !(match(name) || match(id))) return;
      out.push({
        key: `r:${grid}:${id}`,
        label: name,
        kind,
        go: done({ kind: "region", grid, id }, () => {
          if (!useApp.getState().layers.liveGrids) actions.toggleLayer("liveGrids");
          fly(at, 3.6);
        }),
      });
    };
    for (const [id, r] of Object.entries(us?.regions ?? {})) region("us", id, r.name, US_POINT[id], "Grid region · US");
    for (const [id, s] of Object.entries(br?.subsystems ?? {})) region("br", id, s.name, BR_POINT[id], "Subsystem · Brazil");
    for (const id of Object.keys(NEM_POINT)) region("au", id, NEM_NAME[id] ?? id, NEM_POINT[id], "Region · Australia");
    region("tw", "TW", "Taiwan", TW_POINT, "Live grid · Taipower");
    region("on", "ON", "Ontario", ON_POINT.ON, "Live grid · IESO");
    if (t.length >= 3) {
      let n = 0;
      for (const p of plants?.plants ?? []) {
        if (n >= 6) break;
        if (!match(p[5])) continue;
        n++;
        out.push({
          key: `p:${p[5]}:${p[2]}`,
          label: p[5],
          kind: `Plant · ${p[4]} · ${Math.round(p[1]).toLocaleString("en-US")} MW`,
          go: done(null, () => {
            if (!useApp.getState().layers.plantsEU) actions.toggleLayer("plantsEU");
            fly([p[2], p[3]], 7.5);
          }),
        });
      }
      if (wp && names) {
        let m = 0;
        for (let k = 0; k < names.names.length && m < 8; k++) {
          if (!match(names.names[k])) continue;
          m++;
          const pt = wp.points[k];
          const status = wp.statuses[pt[3]] as PlantStatus;
          out.push({
            key: `g:${k}`,
            label: names.names[k],
            kind: `Plant · ${STATUS_LABEL[status] ?? status} · ${pt[4].toLocaleString("en-US")} MW`,
            go: done(null, () => {
              actions.setPlantStatus(status);
              fly([pt[0], pt[1]], 7.5);
            }),
          });
        }
      }
    }
    return out.slice(0, 24);
  }, [q, countries, world, prices, plants, us, br, wp, names, onDone]);

  const showGem = q.trim().length >= 3 && !gem;
  return (
    <div className="relative w-full">
      <input
        ref={input}
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setActive(0);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") setActive((a) => Math.min(hits.length - 1, a + 1));
          else if (e.key === "ArrowUp") setActive((a) => Math.max(0, a - 1));
          else if (e.key === "Enter") hits[active]?.go();
          else if (e.key === "Escape") {
            setQ("");
            input.current?.blur();
          }
        }}
        placeholder="Search a country, zone, region or plant"
        className="w-full rounded-lg border border-white/10 bg-[#0b0f16]/90 px-3 py-1.5 text-[12.5px] text-slate-100 placeholder:text-slate-500 outline-none backdrop-blur focus:border-sky-400/50"
        aria-label="Search"
      />
      {open && (hits.length > 0 || showGem) && (
        <div className="absolute left-0 right-0 top-full z-50 mt-1 max-h-[60vh] overflow-y-auto rounded-lg border border-white/10 bg-[#0b0f16]/95 py-1 shadow-2xl backdrop-blur">
          {hits.map((h, i) => (
            <button
              key={h.key}
              onMouseDown={(e) => e.preventDefault()}
              onClick={h.go}
              onMouseEnter={() => setActive(i)}
              className={`flex w-full items-baseline justify-between gap-3 px-3 py-1.5 text-left ${i === active ? "bg-white/[0.08]" : ""}`}
            >
              <span className="truncate text-[12.5px] text-slate-100">{h.label}</span>
              <span className="shrink-0 text-[10px] text-[#8d94a1]">{h.kind}</span>
            </button>
          ))}
          {showGem && (
            <button
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => {
                setGem(true);
                ensure("worldPlants");
                ensure("plantNames");
              }}
              className="w-full px-3 py-1.5 text-left text-[11px] text-sky-300 hover:bg-white/[0.06]"
            >
              Also search 183,000 plants worldwide (Global Energy Monitor, ~10 MB)
            </button>
          )}
          {gem && !names && <div className="px-3 py-1.5 text-[11px] text-[#8d94a1]">Loading plant names…</div>}
        </div>
      )}
    </div>
  );
}
