import { useEffect, useMemo, useState } from "react";

import AssetTable from "./components/AssetTable";
import AssistantPanel from "./components/AssistantPanel";
import FilterPanel from "./components/FilterPanel";
import GridInfoPanel from "./components/GridInfoPanel";
import MapView, { type ColorMode } from "./components/MapView";
import NavRail, { type View } from "./components/NavRail";
import SiteDrawer from "./components/SiteDrawer";
import TopBar from "./components/TopBar";
import { api, type Footprint, type Meta, type RecentDetection, type Site, type Turbine } from "./lib/api";
import { num } from "./lib/format";
import { type GridPick } from "./lib/grid";
import { type GridLayers } from "./components/GridControl";
import { applyFilter, emptyFilter, type Filter } from "./lib/query";

type Bounds = [[number, number], [number, number]] | null;
const TODAY = new Date().toISOString().slice(0, 10);
const BUILDING = new Set(["clearing", "earthworks", "construction"]);

function boundsOf(sites: Site[]): Bounds {
  if (!sites.length) return null;
  let a = 180,
    b = 90,
    c = -180,
    d = -90;
  for (const s of sites) {
    a = Math.min(a, s.lon);
    c = Math.max(c, s.lon);
    b = Math.min(b, s.lat);
    d = Math.max(d, s.lat);
  }
  return [
    [a - 0.15, b - 0.15],
    [c + 0.15, d + 0.15],
  ];
}

export default function App() {
  const [sites, setSites] = useState<Site[]>([]);
  const [recent, setRecent] = useState<RecentDetection[]>([]);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [deadlines, setDeadlines] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const [view, setView] = useState<View>("map");
  const [colorMode, setColorMode] = useState<ColorMode>("state");
  const [filter, setFilter] = useState<Filter>(emptyFilter());
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [flyTo, setFlyTo] = useState<{ lon: number; lat: number } | null>(null);
  const [footprint, setFootprint] = useState<Footprint | null>(null);
  const [turbines, setTurbines] = useState<Turbine[]>([]);
  const [focus, setFocus] = useState<Bounds>(null);
  const [highlight, setHighlight] = useState<Set<string> | null>(null);
  const [assistantOpen, setAssistantOpen] = useState(true);
  const [statsOpen, setStatsOpen] = useState(true);
  const [basemap, setBasemap] = useState<"dark" | "satellite">("dark");
  const [gridSel, setGridSel] = useState<GridPick | null>(null);
  const [grid, setGrid] = useState<GridLayers>({ backbone: false, planned: false, constructionOnly: false });

  useEffect(() => {
    api.sites().then(setSites).catch((e) => setError(String(e)));
    api.recent(60).then(setRecent).catch(() => {});
    api.meta().then(setMeta).catch(() => {});
    api.legalDeadlines().then(setDeadlines).catch(() => {});
  }, []);

  // the API banner is for a genuine outage; clear it automatically so a transient
  // reload blip doesn't leave it stuck on screen
  useEffect(() => {
    if (!error) return;
    const t = setTimeout(() => setError(null), 5000);
    return () => clearTimeout(t);
  }, [error]);

  const sitesById = useMemo(() => new Map(sites.map((s) => [s.id, s])), [sites]);

  // lazily pull the open site's footprint (terrain-draped extrusion) and, for wind
  // farms, its individual turbines (real 3D models)
  useEffect(() => {
    if (!selectedId) {
      setFootprint(null);
      setTurbines([]);
      return;
    }
    let live = true;
    setFootprint(null);
    setTurbines([]);
    api.footprint(selectedId).then((f) => live && setFootprint(f)).catch(() => {});
    api.turbines(selectedId).then((t) => live && setTurbines(t)).catch(() => {});
    return () => {
      live = false;
    };
  }, [selectedId]);

  const overdueCount = useMemo(
    () =>
      sites.filter(
        (s) =>
          deadlines[s.id] &&
          deadlines[s.id] < TODAY &&
          BUILDING.has(s.status) &&
          s.status !== "unknown",
      ).length,
    [sites, deadlines],
  );

  const building = useMemo(() => sites.filter((s) => BUILDING.has(s.status)).length, [sites]);
  const totalGw = useMemo(() => sites.reduce((a, s) => a + s.capacity_mw, 0) / 1000, [sites]);

  const mapSites = useMemo(() => {
    if (highlight) return sites.filter((s) => highlight.has(s.id));
    return applyFilter(sites, filter);
  }, [sites, filter, highlight]);

  // selecting a site flies the camera in and opens the detail drawer
  const selectSite = (id: string) => {
    setGridSel(null);
    setSelectedId(id);
    const s = sitesById.get(id);
    if (s) setFlyTo({ lon: s.lon, lat: s.lat });
    setView("map");
  };

  const onAgentResult = (ids: string[]) => {
    if (!ids.length) return;
    setHighlight(new Set(ids));
    setFocus(boundsOf(ids.map((id) => sitesById.get(id)!).filter(Boolean)));
  };

  const setFilterManual = (f: Filter) => {
    setFilter(f);
    setHighlight(null);
  };

  return (
    <div className="relative flex h-screen w-screen overflow-hidden bg-ink-950 text-slate-100">
      <NavRail
        view={view}
        setView={setView}
        assistantOpen={assistantOpen}
        toggleAssistant={() => setAssistantOpen((o) => !o)}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          basemap={basemap}
          setBasemap={setBasemap}
          grid={grid}
          setGrid={setGrid}
        />

        <div className="relative min-h-0 flex-1">
          {view === "map" ? (
            <>
              <MapView
                sites={mapSites}
                colorMode={colorMode}
                recent={recent}
                selectedId={selectedId}
                onSelect={selectSite}
                focusBounds={focus}
                flyTo={flyTo}
                footprint={footprint}
                turbines={turbines}
                basemap={basemap}
                gridBackbone={grid.backbone}
                gridPlanned={grid.planned}
                gridConstructionOnly={grid.constructionOnly}
                onGridSelect={(p) => {
                  setSelectedId(null);
                  setGridSel(p);
                }}
              />

              {!selectedId && (
                <div className="absolute bottom-3 right-3 z-10 flex divide-x divide-line overflow-hidden rounded-md border border-line bg-ink-900/85 backdrop-blur">
                  <div className="px-3 py-1.5">
                    <div className="eyebrow">Sites</div>
                    <div className="font-mono text-sm font-semibold tabular-nums text-slate-100">{num(sites.length)}</div>
                    <div className="text-[10px] text-faint">{(totalGw).toFixed(1)} GW</div>
                  </div>
                  <div className="px-3 py-1.5">
                    <div className="eyebrow">Building</div>
                    <div className="font-mono text-sm font-semibold tabular-nums text-accent-400">{num(building)}</div>
                  </div>
                  <div className="px-3 py-1.5">
                    <div className="eyebrow">Behind</div>
                    <div className="font-mono text-sm font-semibold tabular-nums text-alert">{num(overdueCount)}</div>
                  </div>
                </div>
              )}
              {statsOpen ? (
                <div className="absolute bottom-0 left-0 top-0">
                  <FilterPanel
                    all={sites}
                    filter={filter}
                    setFilter={setFilterManual}
                    colorMode={colorMode}
                    setColorMode={setColorMode}
                    meta={meta}
                    onClose={() => setStatsOpen(false)}
                  />
                </div>
              ) : (
                <button
                  onClick={() => setStatsOpen(true)}
                  className="absolute left-3 top-3 z-10 flex items-center gap-1.5 rounded border border-line bg-ink-900/90 px-2.5 py-1.5 text-xs text-slate-300 backdrop-blur hover:border-accent/50 hover:text-accent-300"
                >
                  <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M2 4h12M4 8h8M6 12h4" />
                  </svg>
                  Portfolio & filters
                </button>
              )}
              {highlight && (
                <button
                  onClick={() => setHighlight(null)}
                  className="absolute left-1/2 top-3 z-10 -translate-x-1/2 rounded-full border border-accent/40 bg-ink-900/90 px-3 py-1 text-xs text-accent-300 backdrop-blur"
                >
                  agent result · {mapSites.length} sites — clear
                </button>
              )}
            </>
          ) : (
            <AssetTable sites={sites} deadlines={deadlines} highlight={highlight} onSelect={selectSite} />
          )}

          {selectedId && <SiteDrawer id={selectedId} onClose={() => setSelectedId(null)} />}
          {gridSel && <GridInfoPanel pick={gridSel} onClose={() => setGridSel(null)} />}
        </div>
      </div>

      <AssistantPanel
        open={assistantOpen}
        sitesById={sitesById}
        onResult={onAgentResult}
        onPickSite={selectSite}
        onClose={() => setAssistantOpen(false)}
      />

      {!assistantOpen && (
        <button
          onClick={() => setAssistantOpen(true)}
          title="Open AI Analyst"
          className="absolute right-0 top-1/2 z-30 flex -translate-y-1/2 flex-col items-center gap-2 rounded-l-lg border border-r-0 border-line bg-ink-900/95 px-2 py-3 text-accent-300 backdrop-blur transition hover:bg-ink-800"
        >
          <span className="text-base leading-none">✦</span>
          <span className="text-[10px] font-medium uppercase tracking-wider [writing-mode:vertical-rl]">
            AI Analyst
          </span>
        </button>
      )}

      {error && (
        <div className="absolute bottom-4 left-1/2 z-30 -translate-x-1/2 rounded-lg border border-red-500/30 bg-red-950/80 px-4 py-2 text-xs text-red-200">
          Couldn’t reach the API ({error}). Start it:{" "}
          <code className="text-red-100">uv run uvicorn app.main:app --app-dir backend</code>
        </div>
      )}
    </div>
  );
}

