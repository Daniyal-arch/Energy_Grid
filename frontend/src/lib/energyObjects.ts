// Per-technology 3D objects for the "energy map": at site zoom each site becomes
// a recognizable object scaled by capacity. Canonical meshes are built roughly in
// x,y ∈ [-0.5, 0.5] with z up from the ground (z = 0), then scaled per instance.
// Wind reuses the dedicated turbine meshes (tower + spinning rotor).

import type { Technology } from "./theme";
import type { Mesh } from "./turbineMesh";

// ── tiny mesh builder ──────────────────────────────────────────────────────────
class MeshBuilder {
  v: number[] = [];
  n: number[] = [];
  i: number[] = [];

  private vert(x: number, y: number, z: number, nx: number, ny: number, nz: number): number {
    this.v.push(x, y, z);
    this.n.push(nx, ny, nz);
    return this.v.length / 3 - 1;
  }

  quad(
    p0: [number, number, number],
    p1: [number, number, number],
    p2: [number, number, number],
    p3: [number, number, number],
    nrm: [number, number, number],
  ): void {
    const a = this.vert(...p0, ...nrm);
    const b = this.vert(...p1, ...nrm);
    const c = this.vert(...p2, ...nrm);
    const d = this.vert(...p3, ...nrm);
    this.i.push(a, b, c, a, c, d);
  }

  // box from z0..z1, centred at (cx,cy), half-extents hx,hy (4 sides + top)
  box(cx: number, cy: number, z0: number, z1: number, hx: number, hy: number): void {
    const x0 = cx - hx;
    const x1 = cx + hx;
    const y0 = cy - hy;
    const y1 = cy + hy;
    this.quad([x1, y0, z0], [x1, y1, z0], [x1, y1, z1], [x1, y0, z1], [1, 0, 0]);
    this.quad([x0, y1, z0], [x0, y0, z0], [x0, y0, z1], [x0, y1, z1], [-1, 0, 0]);
    this.quad([x1, y1, z0], [x0, y1, z0], [x0, y1, z1], [x1, y1, z1], [0, 1, 0]);
    this.quad([x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1], [0, -1, 0]);
    this.quad([x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1], [0, 0, 1]);
  }

  // (possibly tapered) cylinder z0..z1, with a top cap
  cyl(cx: number, cy: number, z0: number, z1: number, r0: number, r1: number, seg = 16): void {
    const top = this.vert(cx, cy, z1, 0, 0, 1);
    for (let k = 0; k < seg; k++) {
      const a = (2 * Math.PI * k) / seg;
      const a2 = (2 * Math.PI * (k + 1)) / seg;
      const c = Math.cos(a);
      const s = Math.sin(a);
      const c2 = Math.cos(a2);
      const s2 = Math.sin(a2);
      this.quad(
        [cx + r0 * c, cy + r0 * s, z0],
        [cx + r0 * c2, cy + r0 * s2, z0],
        [cx + r1 * c2, cy + r1 * s2, z1],
        [cx + r1 * c, cy + r1 * s, z1],
        [c, s, 0.2],
      );
      const t1 = this.vert(cx + r1 * c, cy + r1 * s, z1, 0, 0, 1);
      const t2 = this.vert(cx + r1 * c2, cy + r1 * s2, z1, 0, 0, 1);
      this.i.push(top, t1, t2);
    }
  }

  mesh(): Mesh {
    const count = this.v.length / 3;
    return {
      attributes: {
        positions: { value: new Float32Array(this.v), size: 3 },
        normals: { value: new Float32Array(this.n), size: 3 },
        texCoords: { value: new Float32Array(count * 2), size: 2 },
      },
      indices: { value: new Uint16Array(this.i), size: 1 },
    };
  }
}

// ── per-technology canonical meshes ─────────────────────────────────────────────
// Built within x,y ∈ [-0.5, 0.5] with modest heights, so a single uniform scale
// (objectSize) preserves each object's built-in proportions.
function solar(): Mesh {
  // parallel raised panel rows reading as a ground-mounted array
  const m = new MeshBuilder();
  for (let r = 0; r < 7; r++) {
    const y = -0.42 + r * 0.14;
    m.box(0, y, 0.01, 0.1, 0.47, 0.04);
  }
  return m.mesh();
}

function storage(): Mesh {
  // rows of battery containers (long, low boxes)
  const m = new MeshBuilder();
  for (let r = 0; r < 4; r++) {
    m.box(0, -0.33 + r * 0.22, 0, 0.13, 0.46, 0.07);
  }
  return m.mesh();
}

function biomass(): Mesh {
  // hall + two silos of different heights
  const m = new MeshBuilder();
  m.box(-0.2, 0, 0, 0.26, 0.28, 0.34);
  m.cyl(0.26, -0.16, 0, 0.46, 0.14, 0.14);
  m.cyl(0.26, 0.2, 0, 0.36, 0.11, 0.11);
  return m.mesh();
}

function combustion(): Mesh {
  // turbine hall + tall chimney with a cap
  const m = new MeshBuilder();
  m.box(-0.12, 0, 0, 0.3, 0.34, 0.3);
  m.cyl(0.3, 0, 0, 0.58, 0.055, 0.04);
  m.cyl(0.3, 0, 0.58, 0.62, 0.07, 0.07); // cap
  return m.mesh();
}

function geothermal(): Mesh {
  // plant block + tapered (hyperbolic-ish) cooling tower
  const m = new MeshBuilder();
  m.box(-0.24, 0, 0, 0.24, 0.26, 0.28);
  m.cyl(0.22, 0, 0, 0.34, 0.24, 0.13);
  m.cyl(0.22, 0, 0.34, 0.42, 0.13, 0.16); // flared rim
  return m.mesh();
}

function hydro(): Mesh {
  // dam wall across the valley + powerhouse + spillway lip
  const m = new MeshBuilder();
  m.box(0, 0.14, 0, 0.34, 0.5, 0.05); // dam wall (wide, tall, thin)
  m.box(0, -0.06, 0, 0.06, 0.5, 0.05); // spillway face
  m.box(0, -0.28, 0, 0.16, 0.26, 0.13); // powerhouse
  return m.mesh();
}

// non-wind objects (wind is rendered with the turbine meshes)
export const OBJECT_MESH: Record<Exclude<Technology, "wind">, Mesh> = {
  solar: solar(),
  biomass: biomass(),
  hydro: hydro(),
  geothermal: geothermal(),
  combustion: combustion(),
  storage: storage(),
};

// object base size in metres — large enough to read at regional zoom, compressed
// so a 5 MW plant and a 1 GW plant differ but neither dwarfs the map
export function objectSize(capacityMw: number): number {
  return Math.min(18, Math.max(5, Math.sqrt(Math.max(capacityMw, 1)))) * 155;
}

// realistic material colours for the real-scale, fitted-to-footprint object that
// the open site shows (photoreal-leaning; build-state lives on the footprint edge)
export const REAL_COLOR: Record<Technology, [number, number, number]> = {
  solar: [38, 52, 88], // dark blue panels
  wind: [228, 233, 240], // white towers
  biomass: [122, 116, 104], // beige plant
  hydro: [150, 156, 165], // concrete grey
  geothermal: [176, 180, 188], // light grey
  combustion: [126, 130, 138], // industrial grey
  storage: [104, 116, 134], // metallic blue-grey
};

// absolute z-scale (metres per canonical unit) so the fitted object keeps a real
// height regardless of footprint width (panels stay flat, chimneys stay tall)
export const REAL_HZ: Record<Exclude<Technology, "wind">, number> = {
  solar: 42,
  storage: 26,
  biomass: 58,
  combustion: 140,
  geothermal: 145,
  hydro: 46,
};

// height at which each plant emits its plume/spray (metres above ground)
export const STACK_H: Partial<Record<Technology, number>> = {
  combustion: 82,
  biomass: 30,
  geothermal: 58,
  hydro: 9,
};
