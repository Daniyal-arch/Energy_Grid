import { useEffect, useMemo, useState } from "react";

import AtlasHud from "./components/AtlasHud";
import CaptureOverlay from "./components/CaptureOverlay";
import { DEFAULT_GRID_LAYERS, type GridLayers } from "./components/GridControl";
import GridInfoPanel from "./components/GridInfoPanel";
import MapControls from "./components/MapControls";
import MapView, { type ColorMode } from "./components/MapView";
import PowerLegend from "./components/PowerLegend";
import SiteDrawer from "./components/SiteDrawer";
import {
  api,
  type Footprint,
  type GridExchangeRow,
  type GridHistoryPoint,
  type GridSnapshotLatest,
  type RailTimetableBoard,
  type Site,
  type Turbine,
} from "./lib/api";
import { readCapture } from "./lib/capture";
import { loadEnergySites } from "./lib/energySites";
import type { MapFeaturePick } from "./lib/infrastructure";
import { applyFilter, emptyFilter, type Filter } from "./lib/query";

export default function App() {
  const [sites, setSites] = useState<Site[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [filter] = useState<Filter>(emptyFilter());
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [flyTo, setFlyTo] = useState<{ lon: number; lat: number } | null>(null);
  const [footprint, setFootprint] = useState<Footprint | null>(null);
  const [turbines, setTurbines] = useState<Turbine[]>([]);
  const [basemap, setBasemap] = useState<"dark" | "satellite">("dark");
  const [gridMenuOpen, setGridMenuOpen] = useState(false);
  const [gridSel, setGridSel] = useState<MapFeaturePick | null>(null);
  const [grid, setGrid] = useState<GridLayers>(DEFAULT_GRID_LAYERS);
  const [exchange, setExchange] = useState<GridExchangeRow[]>([]);
  const [gridLatest, setGridLatest] = useState<GridSnapshotLatest>({});
  const [railSceneRequest, setRailSceneRequest] = useState(0);
  const [powerSceneRequest, setPowerSceneRequest] = useState(0);
  const [activeScene, setActiveScene] = useState<"atlas" | "rail" | "power">("atlas");
  const [railBoard, setRailBoard] = useState<RailTimetableBoard | null>(null);

  const colorMode: ColorMode = "technology";

  // video capture mode (?capture=4x5 | 9x16), see lib/capture.ts
  const capture = useMemo(() => readCapture(), []);
  const [windHistory, setWindHistory] = useState<GridHistoryPoint[]>([]);
  const [solarHistory, setSolarHistory] = useState<GridHistoryPoint[]>([]);

  useEffect(() => {
    loadEnergySites()
      .then(setSites)
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (!grid.backbone && !grid.exchangeFlows) {
      setGridLatest({});
      return;
    }
    // keep the last good snapshot: the API can answer with a partial/empty
    // fallback while its DB is unreachable, which would blank the readouts
    const load = () =>
      api
        .gridLatest()
        .then((d) => {
          if (d.gen_wind) setGridLatest(d);
        })
        .catch(() => {});
    load();
    const t = setInterval(load, 5 * 60 * 1000);
    return () => clearInterval(t);
  }, [grid.backbone, grid.exchangeFlows]);

  useEffect(() => {
    if (!grid.exchangeFlows) {
      setExchange([]);
      return;
    }
    const load = () => {
      api.gridExchange().then(setExchange).catch(() => {});
    };
    load();
    const t = setInterval(load, 5 * 60 * 1000);
    return () => clearInterval(t);
  }, [grid.exchangeFlows]);

  useEffect(() => {
    if (!error) return;
    const t = setTimeout(() => setError(null), 5000);
    return () => clearTimeout(t);
  }, [error]);

  useEffect(() => {
    if (railSceneRequest <= 0) return;
    const load = () => api.railTimetable("8000105").then(setRailBoard).catch(() => {});
    load();
    const t = setInterval(load, 20 * 1000);
    return () => clearInterval(t);
  }, [railSceneRequest]);

  const sitesById = useMemo(() => new Map(sites.map((s) => [s.id, s])), [sites]);

  // capture: open the power view once, and fetch the 48 h chart series
  useEffect(() => {
    if (!capture) return;
    openPowerScene();
    // the chart is part of the layout, so retry a transient empty/failed answer
    let live = true;
    (async () => {
      for (let attempt = 0; attempt < 20 && live; attempt++) {
        try {
          const [wind, solar] = await Promise.all([api.gridHistory("gen_wind"), api.gridHistory("gen_solar")]);
          if (wind.length > 1 && solar.length > 1) {
            setWindHistory(wind);
            setSolarHistory(solar);
            break;
          }
        } catch {
          // retried below
        }
        await new Promise((r) => setTimeout(r, 4000));
      }
    })();
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [capture]);

  // the recorder waits for this before its first frame (data + chart series in)
  const captureReady =
    // strict: no chart series = no ready signal, so the recorder fails loudly
    // instead of rendering a video without it
    !!capture && sites.length > 0 && !!gridLatest.gen_wind && exchange.length > 0 && windHistory.length > 1;
  useEffect(() => {
    if (captureReady) window.__captureReady = true;
  }, [captureReady]);

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

  const filteredSites = useMemo(() => applyFilter(sites, filter), [sites, filter]);
  const mapSites = grid.energyAssets ? filteredSites : [];

  const selectSite = (id: string) => {
    setGridSel(null);
    setSelectedId(id);
    const s = sitesById.get(id);
    if (s) setFlyTo({ lon: s.lon, lat: s.lat });
  };

  const openRailScene = () => {
    setSelectedId(null);
    setGridSel(null);
    setActiveScene("rail");
    setBasemap("satellite");
    setGrid({
      ...grid,
      stateBoundaries: true,
      energyAssets: false,
      backbone: false,
      planned: false,
      exchangeFlows: false,
      constructionOnly: false,
      rail: true,
      railStations: true,
      railStructures: true,
      gas: false,
      gasNodes: false,
      gasFacilities: false,
      ports: false,
      airports: false,
      industry: false,
    });
    setRailSceneRequest((n) => n + 1);
  };

  const openPowerScene = () => {
    setSelectedId(null);
    setGridSel(null);
    setActiveScene("power");
    setBasemap("dark");
    setGrid({
      ...grid,
      stateBoundaries: true,
      energyAssets: true,
      backbone: true,
      planned: false,
      exchangeFlows: true,
      constructionOnly: false,
      rail: false,
      railStations: false,
      railStructures: false,
      gas: false,
      gasNodes: false,
      gasFacilities: false,
      ports: false,
      airports: false,
      industry: false,
      voltages: { v380: true, v220: true, v110: false },
    });
    setPowerSceneRequest((n) => n + 1);
  };

  const mapView = (
    <MapView
      sites={mapSites}
      colorMode={colorMode}
      selectedId={selectedId}
      onSelect={selectSite}
      flyTo={flyTo}
      footprint={footprint}
      turbines={turbines}
      basemap={basemap}
      gridBackbone={grid.backbone}
      gridPlanned={grid.planned}
      gridExchangeFlows={grid.exchangeFlows}
      gridConstructionOnly={grid.constructionOnly}
      gridVoltages={grid.voltages}
      infraStateBoundaries={grid.stateBoundaries}
      infraRail={grid.rail}
      infraRailStations={grid.railStations}
      infraRailStructures={grid.railStructures}
      infraGas={grid.gas}
      infraPorts={grid.ports}
      infraAirports={grid.airports}
      infraGasNodes={grid.gasNodes}
      infraGasFacilities={grid.gasFacilities}
      infraIndustry={grid.industry}
      railSceneRequest={railSceneRequest}
      powerSceneRequest={powerSceneRequest}
      sceneMode={activeScene}
      gridLatest={gridLatest}
      exchange={exchange}
      capture={capture}
      onGridSelect={(p) => {
        setSelectedId(null);
        setGridSel(p);
      }}
    />
  );

  if (capture) {
    return (
      <div className="flex h-screen w-screen items-center justify-center overflow-hidden bg-[#020305] text-slate-100">
        <div
          className="capture-stage relative overflow-hidden bg-[#07090e]"
          style={{ width: capture.width, height: capture.height }}
        >
          {mapView}
          <CaptureOverlay
            capture={capture}
            latest={gridLatest}
            windHistory={windHistory}
            solarHistory={solarHistory}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-ink-950 text-slate-100">
      {mapView}
      {!selectedId && !gridSel && (
        <>
          <div className="absolute left-4 top-4 z-30">
            <AtlasHud
              layers={grid}
              setLayers={setGrid}
              sites={sites}
              onRailScene={openRailScene}
              onPowerScene={openPowerScene}
              onAtlasScene={() => setActiveScene("atlas")}
            />
          </div>
          <div className="absolute right-4 top-4 z-30">
            <MapControls
              basemap={basemap}
              setBasemap={setBasemap}
              grid={grid}
              setGrid={setGrid}
              onGridMenuOpenChange={setGridMenuOpen}
            />
          </div>
          {!gridMenuOpen && activeScene === "power" && grid.backbone && (
            <div className="absolute bottom-4 right-4 z-20">
              <PowerLegend latest={gridLatest} />
            </div>
          )}
          {!gridMenuOpen && activeScene !== "power" && (
            <div className="pointer-events-none absolute bottom-4 left-1/2 z-20 flex -translate-x-1/2 items-center gap-3 rounded-md border border-line bg-ink-950/75 px-4 py-2 text-[11px] text-slate-300 backdrop-blur">
              <span className="font-mono uppercase tracking-[0.18em] text-accent-300">Animated infrastructure map</span>
              <span className="h-1 w-1 rounded-full bg-slate-600" />
              <span>
                {activeScene === "rail"
                  ? railBoard
                    ? `DB Timetables ${railBoard.station}: ${railBoard.planned.length} planned, ${railBoard.recent_changes.length} recent changes`
                    : "rail scene: waiting for DB Timetables"
                  : "rail, gas, electricity, ports, airports, industry"}
              </span>
            </div>
          )}
        </>
      )}

      {selectedId && <SiteDrawer id={selectedId} site={sitesById.get(selectedId) ?? null} onClose={() => setSelectedId(null)} />}
      {gridSel && <GridInfoPanel pick={gridSel} onClose={() => setGridSel(null)} />}

      {error && (
        <div className="absolute bottom-4 left-1/2 z-30 -translate-x-1/2 rounded-lg border border-red-500/30 bg-red-950/80 px-4 py-2 text-xs text-red-200">
          API unavailable ({error}). Start it with{" "}
          <code className="text-red-100">uv run uvicorn app.main:app --app-dir backend</code>
        </div>
      )}
    </div>
  );
}
