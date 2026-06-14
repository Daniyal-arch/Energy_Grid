// Procedural wind-turbine geometry for deck.gl SimpleMeshLayer. Two canonical
// meshes are scaled per-instance so each turbine matches its real hub height and
// rotor diameter:
//   tower — unit cylinder along +Z (z 0→1), scaled [r, r, hubHeight]
//   rotor — nacelle + 3 blades in the X–Z plane, scaled by rotorDiameter/2 and
//           lifted to hub height via the instance position's z.

export interface Mesh {
  positions: Float32Array;
  normals: Float32Array;
  texCoords: Float32Array;
  indices: Uint16Array;
}

function build(verts: number[], norms: number[], idx: number[]): Mesh {
  return {
    positions: new Float32Array(verts),
    normals: new Float32Array(norms),
    texCoords: new Float32Array((verts.length / 3) * 2),
    indices: new Uint16Array(idx),
  };
}

function makeTower(segments = 14): Mesh {
  const verts: number[] = [];
  const norms: number[] = [];
  const idx: number[] = [];
  for (let i = 0; i < segments; i++) {
    const a = (2 * Math.PI * i) / segments;
    const x = Math.cos(a);
    const y = Math.sin(a);
    // taper slightly toward the top so it reads as a tower, not a pipe
    verts.push(x, y, 0, x * 0.7, y * 0.7, 1);
    norms.push(x, y, 0, x, y, 0);
  }
  for (let i = 0; i < segments; i++) {
    const b0 = i * 2;
    const t0 = i * 2 + 1;
    const b1 = ((i + 1) % segments) * 2;
    const t1 = ((i + 1) % segments) * 2 + 1;
    idx.push(b0, b1, t0, t0, b1, t1);
  }
  return build(verts, norms, idx);
}

function makeRotor(): Mesh {
  const verts: number[] = [];
  const norms: number[] = [];
  const idx: number[] = [];

  const quad = (
    ax: number, ay: number, az: number,
    bx: number, by: number, bz: number,
    cx: number, cy: number, cz: number,
    dx: number, dy: number, dz: number,
    nx: number, ny: number, nz: number,
  ) => {
    const base = verts.length / 3;
    verts.push(ax, ay, az, bx, by, bz, cx, cy, cz, dx, dy, dz);
    for (let k = 0; k < 4; k++) norms.push(nx, ny, nz);
    // front + back so blades are lit from either side
    idx.push(base, base + 1, base + 2, base, base + 2, base + 3);
    idx.push(base, base + 2, base + 1, base, base + 3, base + 2);
  };

  // nacelle: a small box at the hub, along the rotor (Y) axis
  const nx = 0.07;
  const ny0 = -0.22;
  const ny1 = 0.1;
  const nz = 0.07;
  quad(-nx, ny0, nz, nx, ny0, nz, nx, ny1, nz, -nx, ny1, nz, 0, 0, 1);
  quad(-nx, ny0, -nz, nx, ny0, -nz, nx, ny1, -nz, -nx, ny1, -nz, 0, 0, -1);
  quad(nx, ny0, -nz, nx, ny0, nz, nx, ny1, nz, nx, ny1, -nz, 1, 0, 0);
  quad(-nx, ny0, -nz, -nx, ny0, nz, -nx, ny1, nz, -nx, ny1, -nz, -1, 0, 0);

  // three blades in the X–Z plane, slightly forward of the nacelle (+Y)
  const y = 0.11;
  const r0 = 0.05;
  const r1 = 1.0;
  const hw0 = 0.055; // root half-width
  const hw1 = 0.015; // tip half-width
  for (let b = 0; b < 3; b++) {
    const a = Math.PI / 2 + (b * 2 * Math.PI) / 3; // one blade points up
    const ux = Math.cos(a);
    const uz = Math.sin(a);
    const wx = -Math.sin(a); // in-plane perpendicular
    const wz = Math.cos(a);
    quad(
      ux * r0 + wx * hw0, y, uz * r0 + wz * hw0,
      ux * r0 - wx * hw0, y, uz * r0 - wz * hw0,
      ux * r1 - wx * hw1, y, uz * r1 - wz * hw1,
      ux * r1 + wx * hw1, y, uz * r1 + wz * hw1,
      0, 1, 0,
    );
  }
  return build(verts, norms, idx);
}

export const TOWER_MESH = makeTower();
export const ROTOR_MESH = makeRotor();
