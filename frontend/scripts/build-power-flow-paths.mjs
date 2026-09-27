import fs from "node:fs";

const IN = new URL("../public/grid_transmission.geojson", import.meta.url);
const OUT = new URL("../public/data/power_flow_paths.json", import.meta.url);
const M_LAT = 111_320;
// short substation-to-substation links are kept so the network reads as connected
const MIN_CORRIDOR_M = 2_500;

function mLon(lat) {
  return M_LAT * Math.cos((lat * Math.PI) / 180);
}

function hash(value) {
  let h = 2166136261;
  for (let i = 0; i < value.length; i++) {
    h ^= value.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function roundCoord(v) {
  return Math.round(v * 1_000_000) / 1_000_000;
}

function key([lon, lat]) {
  return `${Math.round(lon * 10_000) / 10_000},${Math.round(lat * 10_000) / 10_000}`;
}

function toLineStrings(feature) {
  const g = feature.geometry;
  if (!g) return [];
  if (g.type === "LineString") return [g.coordinates];
  if (g.type === "MultiLineString") return g.coordinates;
  return [];
}

function lengthMeters(path) {
  let distance = 0;
  for (let i = 1; i < path.length; i++) {
    const a = path[i - 1];
    const b = path[i];
    const lat = (a[1] + b[1]) / 2;
    distance += Math.hypot((b[0] - a[0]) * mLon(lat), (b[1] - a[1]) * M_LAT);
  }
  return distance;
}


function perpendicularDistance(p, a, b) {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  if (dx === 0 && dy === 0) return Math.hypot(p[0] - a[0], p[1] - a[1]);
  const t = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)));
  return Math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy));
}

function simplify(path, tolerance = 0.0012) {
  if (path.length <= 3) return path;
  let maxDistance = 0;
  let index = 0;
  for (let i = 1; i < path.length - 1; i++) {
    const d = perpendicularDistance(path[i], path[0], path[path.length - 1]);
    if (d > maxDistance) {
      index = i;
      maxDistance = d;
    }
  }
  if (maxDistance <= tolerance) return [path[0], path[path.length - 1]];
  const left = simplify(path.slice(0, index + 1), tolerance);
  const right = simplify(path.slice(index), tolerance);
  return left.slice(0, -1).concat(right);
}

// Evenly spaced points along the path (metres), so smoothing works per distance
// rather than per OSM vertex (vertex density varies wildly along a line).
function resample(path, step) {
  const out = [path[0]];
  let carry = 0;
  for (let i = 1; i < path.length; i++) {
    const a = path[i - 1];
    const b = path[i];
    const lat = (a[1] + b[1]) / 2;
    const seg = Math.hypot((b[0] - a[0]) * mLon(lat), (b[1] - a[1]) * M_LAT);
    let t = step - carry;
    while (t < seg) {
      const r = t / seg;
      out.push([a[0] + (b[0] - a[0]) * r, a[1] + (b[1] - a[1]) * r]);
      t += step;
    }
    carry = seg - (t - step);
  }
  out.push(path[path.length - 1]);
  return out;
}

// Triangular-kernel moving average: removes the short jogs OSM lines make
// around towers and substations (they render as ticks under a glow shader) and
// rounds corners into the smooth curves of a network map. The window tapers to
// zero at both ends, so corridors still meet exactly at their substations
// without a kink in the last segment.
function smooth(points, radius) {
  const n = points.length;
  if (n < 3) return points;
  const out = [points[0]];
  for (let i = 1; i < n - 1; i++) {
    const r = Math.min(radius, i, n - 1 - i);
    let sx = 0;
    let sy = 0;
    let sw = 0;
    for (let j = -r; j <= r; j++) {
      const p = points[i + j];
      const w = r + 1 - Math.abs(j);
      sx += p[0] * w;
      sy += p[1] * w;
      sw += w;
    }
    out.push([sx / sw, sy / sw]);
  }
  out.push(points[n - 1]);
  return out;
}

function appendPath(base, next) {
  if (!base.length) {
    base.push(...next);
    return;
  }
  base.push(...next.slice(1));
}

function buildEdges(fc) {
  const edges = [];
  for (const feature of fc.features) {
    const p = feature.properties || {};
    if (p.kind !== "line") continue;
    const voltage = Number(p.voltage || 0);
    if (voltage !== 220_000 && voltage !== 380_000) continue;
    const cables = Number.parseInt(String(p.cables || "3"), 10) || 3;
    for (const rawPath of toLineStrings(feature)) {
      if (!rawPath || rawPath.length < 2) continue;
      const path = rawPath.map(([lon, lat]) => [roundCoord(lon), roundCoord(lat)]);
      if (lengthMeters(path) < 250) continue;
      const startKey = key(path[0]);
      const endKey = key(path[path.length - 1]);
      if (startKey === endKey) continue;
      edges.push({
        id: edges.length,
        voltage,
        cables,
        path,
        startKey,
        endKey,
        used: false,
      });
    }
  }
  return edges;
}

function mergeVoltage(edges, voltage) {
  const voltageEdges = edges.filter((edge) => edge.voltage === voltage);
  const graph = new Map();
  for (const edge of voltageEdges) {
    for (const k of [edge.startKey, edge.endKey]) {
      const row = graph.get(k);
      if (row) row.push(edge);
      else graph.set(k, [edge]);
    }
  }

  function unusedAt(k) {
    return (graph.get(k) || []).filter((edge) => !edge.used);
  }

  function trace(startKey, firstEdge) {
    const path = [];
    let cablesTotal = 0;
    let segments = 0;
    let currentKey = startKey;
    let edge = firstEdge;
    while (edge && !edge.used) {
      edge.used = true;
      segments += 1;
      cablesTotal += edge.cables;
      const forward = edge.startKey === currentKey;
      appendPath(path, forward ? edge.path : [...edge.path].reverse());
      currentKey = forward ? edge.endKey : edge.startKey;
      const choices = unusedAt(currentKey);
      if (choices.length !== 1) break;
      edge = choices[0];
    }
    return { path, cables: Math.max(1, Math.round(cablesTotal / Math.max(1, segments))), segments };
  }

  const corridors = [];
  const starts = [...graph.entries()]
    .filter(([, row]) => row.length !== 2)
    .flatMap(([k, row]) => row.map((edge) => [k, edge]));

  for (const [startKey, edge] of starts) {
    if (!edge.used) corridors.push(trace(startKey, edge));
  }

  for (const edge of voltageEdges) {
    if (!edge.used) corridors.push(trace(edge.startKey, edge));
  }

  return corridors
    .filter((row) => row.path.length >= 2 && lengthMeters(row.path) >= MIN_CORRIDOR_M)
    .map((row) => ({
      ...row,
      // ~200 m samples, ±600 m kernel, then drop points a 25 m tolerance can't see
      path: simplify(smooth(resample(row.path, 200), 3), 0.0003).map(([lon, lat]) => [roundCoord(lon), roundCoord(lat)]),
    }));
}

const fc = JSON.parse(fs.readFileSync(IN, "utf8"));
const edges = buildEdges(fc);
const rows = [];

for (const voltage of [380_000, 220_000]) {
  for (const row of mergeVoltage(edges, voltage)) {
    const id = `${voltage}-${rows.length}`;
    const seed = hash(`${id}-${row.path[0][0]}-${row.path[0][1]}-${row.path[row.path.length - 1][0]}-${row.path[row.path.length - 1][1]}`);
    rows.push({
      id,
      voltage,
      cables: row.cables,
      seed,
      source_segments: row.segments,
      length_m: Math.round(lengthMeters(row.path)),
      path: row.path,
    });
  }
}

rows.sort((a, b) => b.voltage - a.voltage || b.length_m - a.length_m);

fs.mkdirSync(new URL("../public/data/", import.meta.url), { recursive: true });
fs.writeFileSync(
  OUT,
  JSON.stringify({
    generated_at: new Date().toISOString().slice(0, 10),
    source: "Merged from original OpenStreetMap 220/380 kV German transmission-line geometry bundled with the atlas.",
    caveat: "Line glow and particles encode live system context; exact internal per-line MW is not public telemetry.",
    lines: rows,
  }),
);

console.log(`merged ${edges.length.toLocaleString("en-US")} raw segments into ${rows.length.toLocaleString("en-US")} flow corridors`);
