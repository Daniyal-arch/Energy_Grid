// Build-time GeoJSON -> MVT tile pyramid for the transmission backbone.
//
// The backbone (~10k LineString features) used to render as a single live
// deck.gl PathLayer with depthCompare:"always" (needed so lines aren't
// depth-culled by 3D meshes), which forces full per-fragment shading of every
// segment on every frame forever — a steady GPU cost that stalled the app.
// Tiling it lets deck.gl's MVTLayer fetch/rasterize only the tiles in view,
// so per-frame cost scales with visible tiles instead of the whole network.
//
// Run manually after grid_transmission.geojson changes (analogous to
// scripts/simplify_grid.py): `npm run tile:grid` from frontend/.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import geojsonvt from "geojson-vt";
import vtpbf from "vt-pbf";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.join(__dirname, "../public/grid_transmission.geojson");
const OUT_DIR = path.join(__dirname, "../public/tiles/grid-backbone");
const SUBS_OUT = path.join(__dirname, "../public/grid_substations.geojson");
const MAX_Z = 9;

const fc = JSON.parse(fs.readFileSync(SRC, "utf-8"));
const lines = {
  type: "FeatureCollection",
  features: fc.features.filter((f) => f.properties?.kind === "line"),
};

// substations are loaded client-side directly (lib/grid.ts's loadGrid), not
// tiled — split them into their own small file so the client never has to
// fetch the full (16+ MB, after the 110 kV tier) line network just for points.
const subs = {
  type: "FeatureCollection",
  features: fc.features.filter((f) => f.properties?.kind === "substation"),
};
fs.writeFileSync(SUBS_OUT, JSON.stringify(subs));
console.log(`wrote ${subs.features.length} substations, ${(fs.statSync(SUBS_OUT).size / 1024).toFixed(0)} KB → ${SUBS_OUT}`);

const tileIndex = geojsonvt(lines, {
  maxZoom: MAX_Z,
  indexMaxZoom: MAX_Z, // eager full-depth build so tileCoords is complete
  indexMaxPoints: 0, // never stop early on point-count — always split to maxZoom
  buffer: 64,
  extent: 4096,
});

if (fs.existsSync(OUT_DIR)) fs.rmSync(OUT_DIR, { recursive: true, force: true });

let tileCount = 0;
let totalBytes = 0;
for (const { z, x, y } of tileIndex.tileCoords) {
  const tile = tileIndex.getTile(z, x, y);
  if (!tile || tile.features.length === 0) continue;
  const buf = vtpbf.fromGeojsonVt({ "grid-backbone": tile });
  const outPath = path.join(OUT_DIR, String(z), String(x), `${y}.pbf`);
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, buf);
  tileCount++;
  totalBytes += buf.length;
}

console.log(`wrote ${tileCount} tiles, ${(totalBytes / 1024).toFixed(0)} KB total → ${OUT_DIR}`);
