import { useEffect, useMemo, useState } from "react";

import CommandBar from "./components/CommandBar";
import FilterPanel from "./components/FilterPanel";
import MapView, { type ColorMode } from "./components/MapView";
import PulseHeader from "./components/PulseHeader";
import SiteDrawer from "./components/SiteDrawer";
import { api, type RecentDetection, type Site } from "./lib/api";
import { applyFilter, emptyFilter, filterActive, parseQuery, type Filter } from "./lib/query";

type Bounds = [[number, number], [number, number]] | null;

function boundsOf(sites: Site[]): Bounds {
  if (sites.length < 2) return null;
  let minLon = 180,
    minLat = 90,
    maxLon = -180,
    maxLat = -90;
  for (const s of sites) {
    minLon = Math.min(minLon, s.lon);
    maxLon = Math.max(maxLon, s.lon);
    minLat = Math.min(minLat, s.lat);
    maxLat = Math.max(maxLat, s.lat);
  }
  return [
    [minLon, minLat],
    [maxLon, maxLat],
  ];
}

export default function App() {
  const [sites, setSites] = useState<Site[]>([]);
  const [recent, setRecent] = useState<RecentDetection[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>(emptyFilter());
  const [understood, setUnderstood] = useState<string[]>([]);
  const [colorMode, setColorMode] = useState<ColorMode>("state");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [focus, setFocus] = useState<Bounds>(null);

  useEffect(() => {
    api.sites().then(setSites).catch((e) => setError(String(e)));
    api.recent(60).then(setRecent).catch(() => {});
  }, []);

  const filtered = useMemo(() => applyFilter(sites, filter), [sites, filter]);

  const onQuery = (text: string) => {
    if (!text.trim()) return;
    const { filter: f, understood: u } = parseQuery(text);
    setFilter(f);
    setUnderstood(u);
    const b = boundsOf(applyFilter(sites, f));
    if (b) setFocus(b);
  };

  const clearQuery = () => {
    setFilter(emptyFilter());
    setUnderstood([]);
  };

  // keep the understood chips honest when the panel edits the filter directly
  const setFilterManual = (f: Filter) => {
    setFilter(f);
    if (!filterActive(f)) setUnderstood([]);
  };

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-[#070a10] text-slate-100">
      <MapView
        sites={filtered}
        colorMode={colorMode}
        recent={recent}
        selectedId={selectedId}
        onSelect={setSelectedId}
        focusBounds={focus}
      />

      {/* top brand + pulse */}
      <header className="pointer-events-none absolute left-0 right-0 top-0 z-10 flex items-start justify-between p-4">
        <div className="pointer-events-auto flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="h-7 w-7 rounded-lg bg-gradient-to-br from-sky-400 to-emerald-400" />
            <div>
              <div className="text-sm font-semibold leading-none">gridwatch</div>
              <div className="text-[10px] text-slate-500">German energy construction · live</div>
            </div>
          </div>
        </div>
        <div className="pointer-events-auto">
          <PulseHeader sites={sites} recent={recent} />
        </div>
      </header>

      {/* agent-first command bar, centred */}
      <div className="pointer-events-none absolute left-1/2 top-20 z-10 -translate-x-1/2">
        <div className="pointer-events-auto">
          <CommandBar
            understood={understood}
            resultCount={understood.length ? filtered.length : null}
            onSubmit={onQuery}
            onClear={clearQuery}
          />
        </div>
      </div>

      {/* left rail */}
      <div className="absolute bottom-0 left-0 top-0 z-10 pt-[120px]">
        <div className="h-full">
          <FilterPanel
            all={sites}
            filter={filter}
            setFilter={setFilterManual}
            colorMode={colorMode}
            setColorMode={setColorMode}
          />
        </div>
      </div>

      {selectedId && <SiteDrawer id={selectedId} onClose={() => setSelectedId(null)} />}

      {error && (
        <div className="absolute bottom-4 left-1/2 z-30 -translate-x-1/2 rounded-lg border border-red-500/30 bg-red-950/80 px-4 py-2 text-xs text-red-200">
          Couldn’t reach the API ({error}). Start it with{" "}
          <code className="text-red-100">uv run uvicorn app.main:app --app-dir backend</code>
        </div>
      )}
    </div>
  );
}
