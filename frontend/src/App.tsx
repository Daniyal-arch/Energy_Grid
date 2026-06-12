// Phase 1 placeholder: map centered on Bavaria/BW. Site markers, detail drawer,
// charts, agent chat, and monitoring feed land as Phase 1/2 progress (see PLAN.md).
import maplibregl from "maplibre-gl";
import { useEffect, useRef } from "react";

const OSM_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};

export default function App() {
  const mapContainer = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!mapContainer.current) return;
    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: OSM_STYLE,
      center: [10.5, 48.6], // Bavaria / Baden-Württemberg
      zoom: 7,
    });
    return () => map.remove();
  }, []);

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center gap-3 border-b border-slate-200 bg-white px-4 py-2">
        <h1 className="text-lg font-semibold text-slate-800">gridwatch</h1>
        <span className="text-sm text-slate-500">
          Solar construction monitoring — Bayern & Baden-Württemberg
        </span>
      </header>
      <main className="flex-1">
        <div ref={mapContainer} className="h-full w-full" />
      </main>
    </div>
  );
}
