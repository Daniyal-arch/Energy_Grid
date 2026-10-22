/** Solar and wind resource atlases (scripts/build_atlas.py; .github/workflows/atlas.yml):
 *  raster tiles on the public bucket and a 0.1 degree lookup grid read by HTTP range. */

export type AtlasId = "pvout" | "wind";

export interface AtlasInfo {
  title: string;
  unit: string;
  source: string;
  /** stored value = source value x scale (int16) */
  scale: number;
  /** [from, to, rgb]: the classes as drawn (from null = below the first break, to null = above) */
  classes: [number | null, number | null, [number, number, number]][];
  tiles: string;
  max_zoom: number;
  lookup: { url: string; cell_deg: number; width: number; height: number; origin: [number, number]; nodata: number; computed: string };
}

export type AtlasFile = Record<AtlasId, AtlasInfo>;

const cache = new Map<string, Promise<number | null>>();

/** The lookup grid's value at a place (source units), null where the atlas has none. */
export function atlasValue(a: AtlasInfo, lon: number, lat: number): Promise<number | null> {
  const { cell_deg, width, height, origin, nodata, url } = a.lookup;
  const col = Math.min(width - 1, Math.max(0, Math.floor((lon - origin[0]) / cell_deg)));
  const row = Math.min(height - 1, Math.max(0, Math.floor((origin[1] - lat) / cell_deg)));
  const at = (row * width + col) * 2;
  const key = `${url}#${at}`;
  if (!cache.has(key))
    cache.set(
      key,
      fetch(url, { headers: { Range: `bytes=${at}-${at + 1}` }, cache: "no-store" })
        .then((r) => (r.ok ? r.arrayBuffer() : Promise.reject(new Error(`HTTP ${r.status}`))))
        .then((b) => {
          const v = new DataView(b).getInt16(0, true);
          return v === nodata ? null : v / a.scale;
        }),
    );
  return cache.get(key) as Promise<number | null>;
}

/** The cell's south-west corner and size, for the label. */
export function atlasCell(a: AtlasInfo, lon: number, lat: number): string {
  const d = a.lookup.cell_deg;
  const w = Math.floor(lon / d) * d;
  const s = Math.floor(lat / d) * d;
  return `${d}° cell ${s.toFixed(1)}–${(s + d).toFixed(1)}° N, ${w.toFixed(1)}–${(w + d).toFixed(1)}° E`;
}

export const ATLAS_LAYERS: Record<AtlasId, string> = { pvout: "atlas-pvout", wind: "atlas-wind" };
