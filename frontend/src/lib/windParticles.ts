// Wind layer: particles drifting with Open-Meteo's hourly wind at 100 m (wind.json, built
// by scripts/fetch_wind.py). The field is read as published on its 2-degree grid; between
// grid points and between hours it is interpolated for drawing only.

export interface WindFile {
  fetched: string;
  grid: { lon0: number; lat0: number; step: number; nx: number; ny: number };
  /** first hour (UTC) */
  start: string;
  step_s: number;
  /** per hour, per grid point (row by row from the south-west): 0.1 m/s */
  speed: (number | null)[][];
  /** per hour, per grid point: degrees, where the wind blows from */
  dir: (number | null)[][];
}

export class WindField {
  readonly grid: WindFile["grid"];
  readonly start: number;
  readonly hours: number;
  private u: Float32Array[];
  private v: Float32Array[];

  constructor(file: WindFile) {
    this.grid = file.grid;
    this.start = Date.parse(file.start);
    this.hours = file.speed.length;
    const n = file.grid.nx * file.grid.ny;
    this.u = [];
    this.v = [];
    for (let h = 0; h < this.hours; h++) {
      const u = new Float32Array(n);
      const v = new Float32Array(n);
      for (let k = 0; k < n; k++) {
        const s = file.speed[h][k];
        const d = file.dir[h][k];
        if (s == null || d == null) {
          u[k] = NaN;
          v[k] = NaN;
          continue;
        }
        // meteorological direction (from where it blows) -> eastward / northward m/s
        const rad = (d * Math.PI) / 180;
        u[k] = (-s / 10) * Math.sin(rad);
        v[k] = (-s / 10) * Math.cos(rad);
      }
      this.u.push(u);
      this.v.push(v);
    }
  }

  /** Hour position (fractional) of a moment, clamped to the file. */
  hourAt(ms: number): number {
    return Math.max(0, Math.min(this.hours - 1, (ms - this.start) / 3_600_000));
  }

  /** [u, v] in m/s at a point, or null outside the grid or where values are missing. */
  sample(lon: number, lat: number, hour: number, out: Float32Array): boolean {
    const g = this.grid;
    const x = (lon - g.lon0) / g.step;
    const y = (lat - g.lat0) / g.step;
    if (x < 0 || y < 0 || x > g.nx - 1 || y > g.ny - 1) return false;
    const x0 = Math.min(g.nx - 2, Math.floor(x));
    const y0 = Math.min(g.ny - 2, Math.floor(y));
    const fx = x - x0;
    const fy = y - y0;
    const h0 = Math.min(this.hours - 1, Math.floor(hour));
    const h1 = Math.min(this.hours - 1, h0 + 1);
    const fh = hour - h0;
    const k = y0 * g.nx + x0;
    const at = (f: Float32Array) =>
      (f[k] * (1 - fx) + f[k + 1] * fx) * (1 - fy) + (f[k + g.nx] * (1 - fx) + f[k + g.nx + 1] * fx) * fy;
    const u = at(this.u[h0]) * (1 - fh) + at(this.u[h1]) * fh;
    const v = at(this.v[h0]) * (1 - fh) + at(this.v[h1]) * fh;
    if (Number.isNaN(u) || Number.isNaN(v)) return false;
    out[0] = u;
    out[1] = v;
    return true;
  }
}

/** Colour of a trail by wind speed: calm is faint, a turbine's rated speed is bright. */
function speedRGBA(s: number, out: Uint8Array, at: number, fade: number): void {
  const t = Math.min(1, s / 15);
  out[at] = 150 + 100 * t;
  out[at + 1] = 190 + 60 * t;
  out[at + 2] = 220 + 35 * t;
  out[at + 3] = Math.round((30 + 190 * t) * fade);
}

export interface WindSegments {
  length: number;
  attributes: {
    getSourcePosition: { value: Float32Array; size: 2 };
    getTargetPosition: { value: Float32Array; size: 2 };
    getColor: { value: Uint8Array; size: 4; normalized: true };
  };
}

export class WindParticles {
  private readonly n: number;
  private readonly trail: number;
  /** per particle: `trail` positions (lon, lat), newest first */
  private readonly pos: Float32Array;
  private readonly speed: Float32Array;
  private readonly age: Float32Array;
  private readonly life: Float32Array;
  private readonly tmp = new Float32Array(2);
  // two sets of output buffers, swapped every frame so the GPU copy always updates
  private readonly out: { src: Float32Array; dst: Float32Array; col: Uint8Array }[];
  private flip = 0;

  constructor(n: number, trail: number) {
    this.n = n;
    this.trail = trail;
    this.pos = new Float32Array(n * trail * 2);
    this.speed = new Float32Array(n);
    this.age = new Float32Array(n);
    this.life = new Float32Array(n);
    const segs = n * (trail - 1);
    this.out = [0, 1].map(() => ({
      src: new Float32Array(segs * 2),
      dst: new Float32Array(segs * 2),
      col: new Uint8Array(segs * 4),
    }));
    for (let p = 0; p < n; p++) this.life[p] = 0; // all spawn on the first step
  }

  private spawn(p: number, field: WindField, box: [number, number, number, number]): void {
    const g = field.grid;
    const x0 = Math.max(box[0], g.lon0);
    const y0 = Math.max(box[1], g.lat0);
    const x1 = Math.min(box[2], g.lon0 + (g.nx - 1) * g.step);
    const y1 = Math.min(box[3], g.lat0 + (g.ny - 1) * g.step);
    const lon = x0 + Math.random() * Math.max(0, x1 - x0);
    const lat = y0 + Math.random() * Math.max(0, y1 - y0);
    const base = p * this.trail * 2;
    for (let t = 0; t < this.trail; t++) {
      this.pos[base + 2 * t] = lon;
      this.pos[base + 2 * t + 1] = lat;
    }
    this.age[p] = 0;
    this.life[p] = 1.5 + Math.random() * 3.5;
  }

  /**
   * Advance every particle by dt seconds of screen time. `degPerMs` sets how far 1 m/s
   * carries a particle per second on screen (scaled with zoom by the caller).
   */
  step(field: WindField, hour: number, dt: number, degPerMs: number, box: [number, number, number, number]): void {
    const tr = this.trail;
    for (let p = 0; p < this.n; p++) {
      const base = p * tr * 2;
      this.age[p] += dt;
      if (this.age[p] > this.life[p]) {
        this.spawn(p, field, box);
        continue;
      }
      const lon = this.pos[base];
      const lat = this.pos[base + 1];
      if (!field.sample(lon, lat, hour, this.tmp)) {
        this.age[p] = this.life[p] + 1; // left the grid: respawn next frame
        continue;
      }
      const [u, v] = this.tmp;
      this.speed[p] = Math.hypot(u, v);
      // shift the trail back by one point, then move the head
      this.pos.copyWithin(base + 2, base, base + (tr - 1) * 2);
      const k = Math.cos((lat * Math.PI) / 180) || 1e-3;
      this.pos[base] = lon + (u * degPerMs * dt) / k;
      this.pos[base + 1] = lat + v * degPerMs * dt;
    }
  }

  /** Trail segments for a LineLayer (binary attributes), brighter at the head. */
  segments(): WindSegments {
    this.flip ^= 1;
    const { src, dst, col } = this.out[this.flip];
    const tr = this.trail;
    let s = 0;
    for (let p = 0; p < this.n; p++) {
      const base = p * tr * 2;
      // fade in after spawning and out before dying
      const life = Math.min(1, this.age[p] / 0.4, (this.life[p] - this.age[p]) / 0.6);
      for (let t = 0; t < tr - 1; t++, s++) {
        src[2 * s] = this.pos[base + 2 * t];
        src[2 * s + 1] = this.pos[base + 2 * t + 1];
        dst[2 * s] = this.pos[base + 2 * t + 2];
        dst[2 * s + 1] = this.pos[base + 2 * t + 3];
        speedRGBA(this.speed[p], col, 4 * s, Math.max(0, life) * (1 - t / (tr - 1)));
      }
    }
    return {
      length: s,
      attributes: {
        getSourcePosition: { value: src, size: 2 },
        getTargetPosition: { value: dst, size: 2 },
        getColor: { value: col, size: 4, normalized: true },
      },
    };
  }
}
