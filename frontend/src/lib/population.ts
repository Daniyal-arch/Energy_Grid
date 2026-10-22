// People around a place: the GHSL 2025 population on a 0.1 degree grid (scripts/build_population.py),
// int32 people per cell, row-major from 90 N 180 W, 3600 x 1800, on the public bucket; read by HTTP
// range requests, one per grid row the circle touches.

export const POP_URL = "https://pub-73b8a23457984ffc93f888f77e1bebde.r2.dev/grid/population-0.1deg.i32";
export const POP_CELL = 0.1;
const W = 3600;
const H = 1800;
const R = 6371;

const rad = (d: number) => (d * Math.PI) / 180;
function haversine(lon1: number, lat1: number, lon2: number, lat2: number): number {
  const a = Math.sin(rad(lat2 - lat1) / 2) ** 2 + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(rad(lon2 - lon1) / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

/** The people in the cells whose centre lies within `km` of the place (sum, computed); null when not read. */
export async function peopleWithin(lon: number, lat: number, km: number): Promise<{ people: number; cells: number }> {
  const dLat = km / 111.2;
  const dLon = km / (111.2 * Math.max(0.05, Math.cos(rad(lat))));
  const r0 = Math.max(0, Math.floor((90 - (lat + dLat)) / POP_CELL));
  const r1 = Math.min(H - 1, Math.floor((90 - (lat - dLat)) / POP_CELL));
  const c0 = Math.max(0, Math.floor((lon - dLon + 180) / POP_CELL));
  const c1 = Math.min(W - 1, Math.floor((lon + dLon + 180) / POP_CELL));
  let people = 0;
  let cells = 0;
  await Promise.all(
    Array.from({ length: r1 - r0 + 1 }, async (_, i) => {
      const row = r0 + i;
      const a = (row * W + c0) * 4;
      const r = await fetch(POP_URL, { headers: { Range: `bytes=${a}-${a + (c1 - c0 + 1) * 4 - 1}` }, cache: "no-store" });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const v = new DataView(await r.arrayBuffer());
      const clat = 90 - (row + 0.5) * POP_CELL;
      for (let c = c0; c <= c1; c++) {
        const clon = (c + 0.5) * POP_CELL - 180;
        if (haversine(lon, lat, clon, clat) > km) continue;
        people += v.getInt32((c - c0) * 4, true);
        cells++;
      }
    }),
  );
  return { people, cells };
}
