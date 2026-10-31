// The wave-9 sources too large for a map file, or lines and polygons (scripts/wave9.py writes
// w9/<id>.pmtiles with every record): MapLibre vector layers, one per source, switched with the
// source's row in the Layers panel. A click shows the record's fields as published and its source.

import maplibregl from "maplibre-gl";

import WAVE9 from "../app/wave9.json";

interface TileLayer {
  id: string;
  label: string;
  color: string;
  tiles: string;
  kind: string;
  minzoom: number;
  fields: string[];
  source: string;
}

export const W9_TILE_LAYERS = (WAVE9.layers as Partial<TileLayer>[]).filter((d) => d.tiles) as TileLayer[];
const idsOf = (d: TileLayer) => (d.kind === "polygon" ? [`${d.id}-fill`, `${d.id}-line`] : [`${d.id}-${d.kind === "point" ? "dot" : "line"}`]);
const clickReady = new WeakSet<maplibregl.Map>();

function add(map: maplibregl.Map, d: TileLayer): void {
  if (map.getSource(d.id)) return;
  map.addSource(d.id, { type: "vector", url: d.tiles, attribution: d.source });
  const base = { source: d.id, "source-layer": "d", minzoom: d.minzoom };
  const before = map.getLayer("world-pick") ? "world-pick" : undefined;
  if (d.kind === "polygon") {
    map.addLayer({ id: `${d.id}-fill`, type: "fill", ...base, paint: { "fill-color": d.color, "fill-opacity": 0.22 } }, before);
    map.addLayer({ id: `${d.id}-line`, type: "line", ...base, paint: { "line-color": d.color, "line-opacity": 0.7, "line-width": 0.6 } }, before);
  } else if (d.kind === "point") {
    map.addLayer(
      {
        id: `${d.id}-dot`,
        type: "circle",
        ...base,
        paint: {
          "circle-color": d.color,
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 1.2, 8, 2.6, 12, 4],
          "circle-stroke-color": "rgba(12,16,24,0.8)",
          "circle-stroke-width": 0.5,
        },
      },
      before,
    );
  } else {
    map.addLayer({ id: `${d.id}-line`, type: "line", ...base, paint: { "line-color": d.color, "line-width": 1.1, "line-opacity": 0.85 } }, before);
  }
}

function cardOf(d: TileLayer, props: Record<string, unknown>): string {
  const rows = Object.entries(props)
    .filter(([k, v]) => k !== "name" && v != null && v !== "")
    .map(([k, v]) => `<div>${k.replace(/_/g, " ")}: <b>${typeof v === "number" ? v.toLocaleString("en-US") : String(v)}</b></div>`)
    .join("");
  return `<div style="font:12px system-ui;color:#e6e8ec"><b>${props.name ?? d.label}</b><div style="color:#8d94a1">${d.label}</div>${rows}<div style="color:#8d94a1">${d.source}</div></div>`;
}

/** Each frame: add the tile layers switched on (once) and set every one's visibility. */
export function syncWave9Tiles(map: maplibregl.Map, L: Record<string, boolean>): void {
  for (const d of W9_TILE_LAYERS) {
    const on = !!L[d.id];
    if (on) add(map, d);
    for (const id of idsOf(d)) if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
  }
  if (!clickReady.has(map)) {
    clickReady.add(map);
    map.on("click", (e) => {
      const ids = W9_TILE_LAYERS.flatMap(idsOf).filter((id) => map.getLayer(id) && map.getLayoutProperty(id, "visibility") !== "none");
      if (!ids.length) return;
      const hit = map.queryRenderedFeatures(e.point, { layers: ids })[0];
      if (!hit) return;
      const d = W9_TILE_LAYERS.find((x) => hit.layer.id.startsWith(`${x.id}-`));
      if (d) new maplibregl.Popup({ closeButton: true, maxWidth: "280px", className: "w9-popup" }).setLngLat(e.lngLat).setHTML(cardOf(d, hit.properties ?? {})).addTo(map);
    });
  }
}
