import type { Mesh } from "./turbineMesh";

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

function train(): Mesh {
  const m = new MeshBuilder();
  m.box(0, -0.58, 0.04, 0.24, 0.15, 0.42);
  m.box(0, -0.02, 0.04, 0.27, 0.16, 0.48);
  m.box(0, 0.56, 0.04, 0.27, 0.15, 0.44);
  m.box(0, 0.98, 0.08, 0.23, 0.1, 0.14);
  m.box(0, -0.02, 0.27, 0.33, 0.1, 0.86);
  m.box(-0.12, -0.48, 0.02, 0.08, 0.025, 0.24);
  m.box(0.12, -0.48, 0.02, 0.08, 0.025, 0.24);
  m.box(-0.12, 0.52, 0.02, 0.08, 0.025, 0.24);
  m.box(0.12, 0.52, 0.02, 0.08, 0.025, 0.24);
  return m.mesh();
}

function trainWindows(): Mesh {
  const m = new MeshBuilder();
  m.box(-0.162, -0.58, 0.15, 0.2, 0.012, 0.24);
  m.box(0.162, -0.58, 0.15, 0.2, 0.012, 0.24);
  m.box(-0.172, -0.02, 0.16, 0.22, 0.012, 0.29);
  m.box(0.172, -0.02, 0.16, 0.22, 0.012, 0.29);
  m.box(-0.162, 0.52, 0.15, 0.2, 0.012, 0.24);
  m.box(0.162, 0.52, 0.15, 0.2, 0.012, 0.24);
  m.box(0, 1.11, 0.14, 0.19, 0.072, 0.012);
  return m.mesh();
}

function tunnelPortal(): Mesh {
  const m = new MeshBuilder();
  m.box(0, 0, 0, 0.9, 0.08, 0.42);
  m.box(-0.28, 0, 0, 1.15, 0.12, 0.11);
  m.box(0.28, 0, 0, 1.15, 0.12, 0.11);
  m.box(0, 0, 0.86, 1.15, 0.36, 0.1);
  return m.mesh();
}

function bridgePier(): Mesh {
  const m = new MeshBuilder();
  m.box(0, 0, 0, 1, 0.11, 0.11);
  m.box(0, 0, 0.9, 1.08, 0.24, 0.17);
  return m.mesh();
}

function stationMast(): Mesh {
  const m = new MeshBuilder();
  m.box(0, 0, 0, 0.58, 0.22, 0.18);
  m.box(0, 0, 0.58, 0.72, 0.34, 0.24);
  m.box(0, 0, 0.72, 0.86, 0.2, 0.14);
  return m.mesh();
}

export const TRAIN_MESH = train();
export const TRAIN_WINDOW_MESH = trainWindows();
export const TUNNEL_PORTAL_MESH = tunnelPortal();
export const BRIDGE_PIER_MESH = bridgePier();
export const STATION_MESH = stationMast();
