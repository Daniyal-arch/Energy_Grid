// Geometry and timing helpers for animated flow lines (FlowArrowLayer).
//
// Distances along paths are in Web Mercator units (EPSG:3857 metres), so arrow
// spacing is uniform on screen across Europe's latitude range. Spacing is
// quantised per integer zoom, so density stays constant while zooming.

const EARTH_CIRCUMFERENCE = 40_075_016.686;
const MERCATOR_R = 6_378_137;

/** Web Mercator units per screen pixel (512 px tiles, as MapLibre/deck.gl use). */
export function unitsPerPixel(zoom: number): number {
  return EARTH_CIRCUMFERENCE / (512 * 2 ** zoom);
}

function mercator([lon, lat]: [number, number]): [number, number] {
  const phi = (Math.max(-85, Math.min(85, lat)) * Math.PI) / 180;
  return [(MERCATOR_R * lon * Math.PI) / 180, MERCATOR_R * Math.log(Math.tan(Math.PI / 4 + phi / 2))];
}

/**
 * Cumulative Mercator distance per vertex, oriented for the flow shader: dots
 * travel toward increasing values, so `reverse` negates the distances to make
 * them travel from the last vertex to the first. `offset` desynchronises paths.
 */
export function flowDistances(path: [number, number][], reverse = false, offset = 0): number[] {
  const out = new Array<number>(path.length);
  let prev = mercator(path[0]);
  let d = offset;
  out[0] = reverse ? -d : d;
  for (let i = 1; i < path.length; i++) {
    const p = mercator(path[i]);
    d += Math.hypot(p[0] - prev[0], p[1] - prev[1]);
    out[i] = reverse ? -d : d;
    prev = p;
  }
  return out;
}

/** Quadratic Bézier from a to b, bowed sideways by `bend` × chord length. */
export function curvedPath(a: [number, number], b: [number, number], bend = 0.18, samples = 32): [number, number][] {
  const mx = (a[0] + b[0]) / 2;
  const my = (a[1] + b[1]) / 2;
  // bow in screen-ish space: scale longitude by cos(lat) so the curve is symmetric
  const k = Math.cos((my * Math.PI) / 180);
  const dx = (b[0] - a[0]) * k;
  const dy = b[1] - a[1];
  const c: [number, number] = [mx - (dy * bend) / k, my + dx * bend];
  const out: [number, number][] = [];
  for (let i = 0; i <= samples; i++) {
    const t = i / samples;
    const u = 1 - t;
    out.push([u * u * a[0] + 2 * u * t * c[0] + t * t * b[0], u * u * a[1] + 2 * u * t * c[1] + t * t * b[1]]);
  }
  return out;
}

const smoothstep = (e0: number, e1: number, x: number) => {
  const t = Math.max(0, Math.min(1, (x - e0) / (e1 - e0)));
  return t * t * (3 - 2 * t);
};

/**
 * Shared animation clock. `tick` advances the flow at a constant on-screen speed
 * (px/s) regardless of zoom; `uniforms` hands a layer its phase/spacing for the
 * current zoom. The accumulator stays in float64 here and only `phase mod
 * spacing` (a small number) reaches the float32 shader.
 */
export class FlowClock {
  private acc = 0;
  private last = -1;

  tick(now: number, zoom: number, speedPx: number): void {
    const dt = this.last < 0 ? 0 : Math.min(0.1, Math.max(0, (now - this.last) / 1000));
    this.last = now;
    this.acc += dt * speedPx * unitsPerPixel(zoom);
  }

  uniforms(zoom: number, spacingPx: number): { phase: number; spacing: number; secondaryAlpha: number } {
    const level = Math.floor(zoom);
    const spacing = spacingPx * unitsPerPixel(level);
    return {
      phase: ((this.acc % spacing) + spacing) % spacing,
      spacing,
      secondaryAlpha: smoothstep(0.2, 0.95, zoom - level),
    };
  }
}
