import { TripsLayer } from "@deck.gl/geo-layers";
import { GeoJsonLayer, PathLayer } from "@deck.gl/layers";
import { MapboxOverlay } from "@deck.gl/mapbox";
import maplibregl from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";

import { POWER_LAND, outlineFromStates, setPowerBasemap } from "../lib/powerScene";
import { BASEMAP_STYLE, rgbCss, type RGB } from "../lib/theme";

// One service day of German rail, 00:00 -> 24:00 as a time-lapse (?railday=YYYYMMDD).
// Data: frontend/public/data/rail_day/<date>.json from scripts/build_rail_day.py.
// Times are published real-time values where the recorder caught them, timetable
// otherwise; the coverage shown in the credits comes from the build.

type RawTrip = [number, string, number[], number[], number[]];
interface RailDayFile {
  date: string;
  coverage: { train_runs: number; events_observed: number; events_total: number };
  classes: string[];
  segments: number[][];
  /** hops without track geometry (drawn straight), left out of the track layer */
  straight_segments?: number[];
  trips: RawTrip[];
}
interface Run {
  cls: number;
  path: [number, number][];
  ts: number[];
}

const CLASS_COLOR: RGB[] = [
  [255, 200, 70], // long-distance
  [90, 175, 255], // regional
  [240, 110, 200], // S-Bahn
];
const CLASS_LABEL = ["Long-distance", "Regional", "S-Bahn"];
const DAY_SECONDS = 24 * 3600;
const LOOP_SECONDS = 60; // real seconds for one full day
const TRAIL = 300; // trail length, seconds of day time
const GERMANY: [[number, number], [number, number]] = [
  [5.6, 47.2],
  [15.2, 55.1],
];

function buildRuns(day: RailDayFile): Run[] {
  const runs: Run[] = [];
  for (const [cls, , segs, times] of day.trips) {
    const path: [number, number][] = [];
    const ts: number[] = [];
    segs.forEach((segId, i) => {
      if (segId < 0) return;
      const flat = day.segments[segId];
      const dep = times[2 * i + 1];
      const arr = times[2 * (i + 1)];
      const pts: [number, number][] = [];
      for (let k = 0; k < flat.length; k += 2) pts.push([flat[k], flat[k + 1]]);
      const cum = [0];
      for (let k = 1; k < pts.length; k++) {
        const kx = Math.cos((pts[k][1] * Math.PI) / 180);
        cum.push(cum[k - 1] + Math.hypot((pts[k][0] - pts[k - 1][0]) * kx, pts[k][1] - pts[k - 1][1]));
      }
      const total = cum[cum.length - 1] || 1;
      pts.forEach((p, k) => {
        path.push(p);
        ts.push(dep + ((arr - dep) * cum[k]) / total);
      });
    });
    if (path.length >= 2) runs.push({ cls, path, ts });
  }
  return runs;
}

const HOUR = 3600;
const LAND_FILL: [number, number, number, number] = [...POWER_LAND, 255];

/**
 * Cut every run into hourly pieces so each frame draws one bucket only. A piece
 * for hour h holds the points timed [h - TRAIL, h + 1 h], plus one point either
 * side, so the head and the fading trail stay complete while now is inside h.
 */
function hourSlices(runs: Run[]): { hour: number; runs: Run[] }[] {
  const byHour = new Map<number, Run[]>();
  for (const r of runs) {
    const first = Math.floor(r.ts[0] / HOUR);
    const last = Math.floor(r.ts[r.ts.length - 1] / HOUR);
    for (let h = first; h <= last; h++) {
      const from = h * HOUR - TRAIL;
      const to = (h + 1) * HOUR;
      let a = 0;
      while (a < r.ts.length - 1 && r.ts[a + 1] < from) a++;
      let b = r.ts.length - 1;
      while (b > 0 && r.ts[b - 1] > to) b--;
      if (b <= a) continue;
      const piece = { cls: r.cls, path: r.path.slice(a, b + 1), ts: r.ts.slice(a, b + 1) };
      const list = byHour.get(h);
      if (list) list.push(piece);
      else byHour.set(h, [piece]);
    }
  }
  return [...byHour.entries()].map(([hour, list]) => ({ hour, runs: list }));
}

/** trains running per minute, total and per class (for the curve and counters) */
function perMinute(runs: Run[]): { total: Int32Array; byClass: Int32Array[] } {
  const total = new Int32Array(1440);
  const byClass = [new Int32Array(1440), new Int32Array(1440), new Int32Array(1440)];
  for (const r of runs) {
    const a = Math.max(0, Math.floor(r.ts[0] / 60));
    const b = Math.min(1439, Math.floor(r.ts[r.ts.length - 1] / 60));
    for (let m = a; m <= b; m++) {
      total[m]++;
      byClass[r.cls][m]++;
    }
  }
  return { total, byClass };
}

const clock = (sec: number) => {
  const m = Math.floor(sec / 60) % 1440;
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
};

export default function RailDayView({ date }: { date: string }) {
  const container = useRef<HTMLDivElement>(null);
  const overlay = useRef<MapboxOverlay | null>(null);
  const [day, setDay] = useState<RailDayFile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(0);

  useEffect(() => {
    const resolve =
      date === "latest" || date === ""
        ? fetch("/data/rail_day/index.json")
            .then((r) => (r.ok ? r.json() : Promise.reject(new Error("no rail days built yet"))))
            .then((idx: { dates: string[] }) => idx.dates[idx.dates.length - 1])
        : Promise.resolve(date);
    resolve
      .then((d) => fetch(`/data/rail_day/${d}.json`))
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`rail_day/${date}.json -> ${r.status}`))))
      .then(setDay)
      .catch((e) => setError(String(e)));
  }, [date]);

  const runs = useMemo(() => (day ? buildRuns(day) : []), [day]);
  const counts = useMemo(() => perMinute(runs), [runs]);
  const buckets = useMemo(() => hourSlices(runs), [runs]);
  const tracks = useMemo(() => {
    if (!day) return [];
    const straight = new Set(day.straight_segments ?? []);
    return day.segments.filter((s, i) => s.length >= 4 && !straight.has(i));
  }, [day]);
  const [states, setStates] = useState<GeoJSON.FeatureCollection | null>(null);
  useEffect(() => {
    fetch("/data/state_boundaries.geojson")
      .then((r) => r.json())
      .then(setStates)
      .catch(() => {});
  }, []);
  const outline = useMemo(() => (states ? outlineFromStates(states) : []), [states]);

  useEffect(() => {
    if (!container.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      style: BASEMAP_STYLE,
      bounds: GERMANY,
      fitBoundsOptions: { padding: 40 },
      attributionControl: false,
      antialias: true,
    });
    const declutter = () => {
      if (map.getLayer("background")) setPowerBasemap(map, true);
    };
    map.on("styledata", declutter);
    const o = new MapboxOverlay({ interleaved: false, layers: [] });
    map.addControl(o);
    overlay.current = o;
    return () => map.remove();
  }, []);

  // one clock: a whole day in LOOP_SECONDS, then repeat
  useEffect(() => {
    if (!runs.length) return;
    const t0 = performance.now();
    let raf = 0;
    const loop = () => {
      setNow((((performance.now() - t0) / 1000 / LOOP_SECONDS) * DAY_SECONDS) % DAY_SECONDS);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [runs]);

  useEffect(() => {
    overlay.current?.setProps({
      layers: [
        new GeoJsonLayer({
          id: "rail-land",
          data: states ?? { type: "FeatureCollection", features: [] },
          stroked: true,
          filled: true,
          getFillColor: LAND_FILL,
          getLineColor: [58, 72, 94, 140],
          getLineWidth: 0.7,
          lineWidthUnits: "pixels",
          parameters: { depthCompare: "always", depthWriteEnabled: false },
        }),
        new PathLayer<[number, number][]>({
          id: "rail-outline",
          data: outline,
          getPath: (d) => d,
          getColor: [112, 132, 158, 190],
          getWidth: 1,
          widthUnits: "pixels",
          parameters: { depthCompare: "always", depthWriteEnabled: false },
        }),
        new PathLayer<number[]>({
          id: "rail-tracks",
          data: tracks,
          getPath: (s) => {
            const p: [number, number][] = [];
            for (let k = 0; k < s.length; k += 2) p.push([s[k], s[k + 1]]);
            return p;
          },
          getColor: [90, 110, 140, 70],
          getWidth: 0.8,
          widthUnits: "pixels",
          parameters: { depthCompare: "always", depthWriteEnabled: false },
        }),
        // one layer per hour of day; only the current hour is drawn (invisible
        // layers keep their GPU buffers, so switching is free)
        ...buckets.map(
          (b) =>
            new TripsLayer<Run>({
              id: `rail-trains-${b.hour}`,
              data: b.runs,
              visible: b.hour === Math.floor(now / HOUR),
              getPath: (r) => r.path,
              getTimestamps: (r) => r.ts,
              getColor: (r) => CLASS_COLOR[r.cls],
              getWidth: (r) => (r.cls === 0 ? 2.4 : r.cls === 1 ? 1.8 : 1.5),
              widthUnits: "pixels",
              fadeTrail: true,
              trailLength: TRAIL,
              currentTime: now,
              parameters: { depthCompare: "always", depthWriteEnabled: false },
            }),
        ),
      ],
    });
  }, [buckets, tracks, now, states, outline]);

  const minute = Math.min(1439, Math.floor(now / 60));
  const maxCount = Math.max(1, ...counts.total);
  const curve = useMemo(() => {
    const W = 220;
    const H = 44;
    let d = `M0,${H}`;
    for (let m = 0; m < 1440; m += 5) d += `L${((m / 1439) * W).toFixed(1)},${(H - (counts.total[m] / maxCount) * H).toFixed(1)}`;
    return { d: `${d}L${W},${H}Z`, W, H };
  }, [counts, maxCount]);
  const observed = day ? Math.round((100 * day.coverage.events_observed) / Math.max(1, day.coverage.events_total)) : 0;

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-[#07090e] text-slate-100">
      <div ref={container} className="absolute inset-0" />
      <div className="pointer-events-none absolute left-6 top-5 z-10">
        <div className="font-serif text-[34px] uppercase leading-none tracking-[0.2em]">Germany</div>
        <div className="mt-2 text-[10px] uppercase tracking-[0.32em] text-[#aab3c0]">A day on the rails</div>
        <div className="mt-4 text-[44px] font-light leading-none tabular-nums tracking-wide">{clock(now)}</div>
        <div className="mt-2 text-[12px] font-semibold tracking-[0.04em] text-slate-200">
          {counts.total[minute].toLocaleString("en-US")} trains running
        </div>
        <svg width={curve.W} height={curve.H + 2} className="mt-3" aria-hidden>
          <path d={curve.d} fill="rgba(170,179,192,0.35)" />
          <line x1={(minute / 1439) * curve.W} x2={(minute / 1439) * curve.W} y1="0" y2={curve.H} stroke="#e8eef6" strokeWidth="1" />
        </svg>
        <div className="mt-1 text-[9px] uppercase tracking-[0.24em] text-[#8d94a1]">Trains running</div>
      </div>
      <div className="pointer-events-none absolute bottom-6 left-6 z-10 w-[220px] space-y-1.5">
        {CLASS_LABEL.map((label, c) => {
          const n = counts.byClass[c][minute];
          const peak = Math.max(1, ...counts.byClass[c]);
          return (
            <div key={label}>
              <div className="flex items-center justify-between text-[11px] text-slate-200">
                <span className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full" style={{ background: rgbCss(CLASS_COLOR[c]) }} />
                  {label}
                </span>
                <span className="tabular-nums">{n.toLocaleString("en-US")}</span>
              </div>
              <div className="mt-0.5 h-[3px] rounded-full bg-white/[0.07]">
                <div className="h-full rounded-full" style={{ width: `${(n / peak) * 100}%`, background: rgbCss(CLASS_COLOR[c]) }} />
              </div>
            </div>
          );
        })}
      </div>
      <div className="pointer-events-none absolute bottom-4 right-5 z-10 text-right text-[9px] leading-relaxed text-[#6f7888]">
        <div>Timetable: gtfs.de (DELFI) · Real-time: gtfs.de GTFS-Realtime, {observed}% of stop times observed</div>
        <div>Track: © OpenStreetMap contributors · Basemap © CARTO</div>
      </div>
      <a
        href="/"
        className="absolute right-5 top-4 z-10 rounded border border-white/10 bg-black/40 px-3 py-1.5 text-xs text-slate-300 hover:bg-white/10"
      >
        ← Atlas
      </a>
      {(error || !day) && (
        <div className="absolute inset-0 z-20 flex items-center justify-center text-sm text-slate-400">
          {error ?? "loading rail day…"}
        </div>
      )}
    </div>
  );
}
