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
function solar(): Mesh {
  // parallel raised panel rows reading as a ground-mounted array
  const m = new MeshBuilder();
  for (let r = 0; r < 5; r++) {
    const y = -0.4 + r * 0.2;
    m.box(0, y, 0.02, 0.12, 0.46, 0.05);
  }
  return m.mesh();
}

function storage(): Mesh {
  // grid of battery containers
  const m = new MeshBuilder();
  for (let gx = 0; gx < 3; gx++)
    for (let gy = 0; gy < 2; gy++) {
      m.box(-0.3 + gx * 0.3, -0.22 + gy * 0.44, 0, 0.16, 0.12, 0.16);
    }
  return m.mesh();
}

function biomass(): Mesh {
  // hall + two silos
  const m = new MeshBuilder();
  m.box(-0.18, 0, 0, 0.28, 0.26, 0.34);
  m.cyl(0.28, -0.15, 0, 0.62, 0.13, 0.13);
  m.cyl(0.28, 0.18, 0, 0.52, 0.11, 0.11);
  return m.mesh();
}

function combustion(): Mesh {
  // turbine hall + tall chimney
  const m = new MeshBuilder();
  m.box(-0.1, 0, 0, 0.34, 0.34, 0.34);
  m.cyl(0.32, 0, 0, 1.0, 0.06, 0.045);
  return m.mesh();
}

function geothermal(): Mesh {
  // plant block + hyperbolic-ish cooling tower
  const m = new MeshBuilder();
  m.box(-0.22, 0, 0, 0.26, 0.26, 0.3);
  m.cyl(0.22, 0, 0, 0.62, 0.24, 0.18);
  return m.mesh();
}

function hydro(): Mesh {
  // wide low powerhouse
  const m = new MeshBuilder();
  m.box(0, 0, 0, 0.26, 0.46, 0.22);
  m.box(0, -0.34, 0, 0.34, 0.46, 0.06); // forebay lip
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

// per-instance scale [x, y, z] = base × these factors; base derives from capacity
export const OBJECT_SCALE: Record<Technology, [number, number, number]> = {
  solar: [1.0, 1.0, 0.22],
  wind: [0.06, 0.06, 1.0], // tower; rotor handled separately
  biomass: [0.5, 0.5, 0.7],
  hydro: [1.0, 0.7, 0.4],
  geothermal: [0.55, 0.55, 0.8],
  combustion: [0.5, 0.5, 1.0],
  storage: [0.8, 0.8, 0.35],
};

// object base size in metres — compressed capacity range so it reads at site zoom
export function objectSize(capacityMw: number): number {
  return Math.min(30, Math.max(2.2, Math.sqrt(Math.max(capacityMw, 1)))) * 70;
}
