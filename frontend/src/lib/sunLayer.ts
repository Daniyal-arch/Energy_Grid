// Sun layer: Open-Meteo's hourly shortwave radiation (W/m2, average of the preceding hour)
// on the wind file's 2-degree grid, as a soft glow. One pixel per grid point; the GPU
// smooths between pixels (drawing only, the legend names the source).

import type { WindFile } from "./windParticles";

export const SUN_MAX_WM2 = 900;

/** Bounds of the image: half a grid step beyond the outer grid points. */
export function sunBounds(g: WindFile["grid"]): [number, number, number, number] {
  const h = g.step / 2;
  return [g.lon0 - h, g.lat0 - h, g.lon0 + (g.nx - 1) * g.step + h, g.lat0 + (g.ny - 1) * g.step + h];
}

/** The radiation of one hour as an image (north at the top). */
export function sunImage(file: WindFile, hour: number): HTMLCanvasElement | null {
  const rows = file.ghi?.[hour];
  if (!rows) return null;
  const { nx, ny } = file.grid;
  const canvas = document.createElement("canvas");
  canvas.width = nx;
  canvas.height = ny;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  const img = ctx.createImageData(nx, ny);
  for (let j = 0; j < ny; j++)
    for (let i = 0; i < nx; i++) {
      const v = rows[j * nx + i];
      const at = ((ny - 1 - j) * nx + i) * 4;
      const t = v == null ? 0 : Math.min(1, v / SUN_MAX_WM2);
      // dim gold at low sun, warm white near full sun
      img.data[at] = 255;
      img.data[at + 1] = Math.round(176 + 70 * t);
      img.data[at + 2] = Math.round(60 + 120 * t);
      img.data[at + 3] = Math.round(150 * Math.sqrt(t));
    }
  ctx.putImageData(img, 0, 0);
  return canvas;
}
