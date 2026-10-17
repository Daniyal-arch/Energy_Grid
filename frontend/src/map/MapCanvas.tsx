// The map: MapLibre (globe, world land, world grid tiles) with deck.gl drawn inside it.
// One render loop outside React advances the clocks and hands deck.gl its layers; React
// only mounts this once. When nothing moves and nothing changed, a frame costs nothing.

import { AmbientLight, DirectionalLight, LightingEffect, MapView, _GlobeView as GlobeView, _SunLight as SunLight, type PickingInfo } from "@deck.gl/core";
import { MapboxOverlay } from "@deck.gl/mapbox";
import maplibregl from "maplibre-gl";
import { useEffect, useRef } from "react";

import { FlowClock } from "../lib/flowLayers";
import { GEM_PIPES, GEM_POINTS } from "../lib/gem";
import { IRENA_STOPS, irenaK, irenaMetricById, irenaScale, irenaValue, type IrenaFile, type IrenaMetricId } from "../lib/irena";
import { sunBounds, sunImage } from "../lib/sunLayer";
import { rgbCss } from "../lib/theme";
import { EUROPE_ISO3, ISO3, metricById, metricColor, type MetricId, type TransitionFile } from "../lib/transition";
import { WindField, WindParticles, type WindFile } from "../lib/windParticles";
import { ACCESS_STOPS, latest, type WorldStatsFile } from "../lib/world";
import { US_CENTRE } from "../lib/us";
import { TR_NO_DATA, stopColor } from "../app/colors";
import { ensure, fileOf, useDataStore } from "../app/data";
import { centralSun, dayFileKey, dayIndexKey, nightImage, sunAltAt, DAY_SECONDS, unitIndexKey, unitOutKey } from "../app/day";
import { EUROPE_CENTRE, angularDistance, bbox, isNarrow, MOBILE_QUERY } from "../app/geo";
import { actions, clearYearFromUrl, motion, useApp, writeUrl, yearFromUrl, type LayerId, type Selection } from "../app/store";
import type { CountriesFile, DayFile, Shape, WorldFile } from "../app/types";
import { buildLayers, labelsOf, selectedIso2, type Frame, type LabelCollection } from "./build";
import { memo } from "./memo";
import { GRID_LAYERS, LAND, OCEAN, PREDICTED_LAYERS, STYLE, US_GRID_LAYERS, addGridLayers, dayFrame, dayPadding, europeCamera, europeView, setProjection, usFrame, worldCamera } from "./style";
import { TIP_STYLE, countryHtml, tooltip } from "./tooltip";

const SEC_PER_YEAR = 0.9;
/** From this zoom the map is flat (mercator) everywhere. */
const FLAT_ZOOM = 7;
const ISO2_OF = Object.fromEntries(Object.entries(ISO3).map(([a, b]) => [b, a]));

/** Where new wind particles appear on the globe: the side facing the camera, narrower
 *  as the camera comes closer. */
function globeBox(c: maplibregl.LngLat, zoom: number): [number, number, number, number] {
  const half = Math.min(170, 110 / Math.pow(2, Math.max(0, zoom - 1.5)));
  return [c.lng - half, Math.max(-80, c.lat - half * 0.6), c.lng + half, Math.min(80, c.lat + half * 0.6)];
}

/** Files the map needs for what is switched on (panels load their own). */
function wantedKeys(): string[] {
  const s = useApp.getState();
  const L = s.layers;
  const keys = ["countries"];
  if (L.gridEU || L.hvdc || L.substations) keys.push("grid");
  if (L.plantsEU) keys.push("plants");
  if (L.gas) keys.push("gas");
  if (L.lngSendOut) keys.push("lngTerminals");
  if (L.ets) keys.push("ets");
  if (L.ctrace) keys.push("ctrace");
  if (L.connect) keys.push("connect");
  if (L.usOutages) keys.push("usOutages", "usCounties");
  if (L.water) keys.push("water");
  if (L.mastrDE) keys.push("mastrMuni", "mastrUnits");
  if (L.cables) keys.push("cables");
  if (L.plantsWorld) keys.push("worldPlants");
  // EIA wins over GEM in the US: GEM's points inside the states are left out
  if (L.plantsUS) keys.push("usPlants");
  if (L.turbinesUS) keys.push("usTurbines");
  // the queue is shaded against the plants each state runs today
  if (L.usQueue) keys.push("usQueue", "usPlants");
  if (L.plantsUS || L.turbinesUS || L.gridUS || L.usQueue) keys.push("usStates");
  if (L.dataCentres) keys.push("datacentres");
  if (L.liveGrids) keys.push("us", "brazil", "aemo", "taiwan", "ontario");
  if (L.financeCoal || L.financeGas) keys.push("gemFinance");
  for (const [id, style] of [...Object.entries(GEM_PIPES), ...Object.entries(GEM_POINTS)]) if (L[id as LayerId]) keys.push(style.file);
  if (s.mode === "live") {
    keys.push("stats");
    if (L.flows) keys.push("flows", "capacity");
    if (L.gasFlows) keys.push("gasFlows");
    if (L.wind || L.sun) keys.push("windWorld");
  }
  if (s.colour === "offline") keys.push("outages");
  if (s.colour.startsWith("pr_")) keys.push("prices");
  if (s.colour === "access") keys.push("worldStats");
  if (s.colour === "rt_household") keys.push("retail", "usStates");
  if (s.colour.startsWith("ir_")) keys.push("irena");
  if (s.mode === "years" || s.colour.startsWith("tr_")) keys.push("transition");
  if (s.mode === "day") {
    keys.push(dayIndexKey(s.dayRegion));
    const date = dayDate();
    // the US replay has no weather layers
    if (date) keys.push(dayFileKey(s.dayRegion, date), ...(s.dayRegion === "eu" ? [`dayWind:${date}`] : []));
    if (L.plantOutput) keys.push(unitIndexKey(s.dayRegion), ...(date ? [unitOutKey(s.dayRegion, date)] : []));
    if (L.usNodePrices && s.dayRegion === "us" && date) keys.push(`usNodes:${date}`);
  }
  const iso = selectedIso2(s.selection);
  if (iso && L.plantsEU && s.mode === "live") keys.push("plants", `units:${iso}`);
  return keys;
}

/** The replayed day: the one asked for, else the newest in the archive. */
function dayDate(): string | null {
  const s = useApp.getState();
  const index = fileOf<{ all: string[] }>(dayIndexKey(s.dayRegion));
  if (!index) return s.day;
  return s.day && index.all.includes(s.day) ? s.day : (index.all[index.all.length - 1] ?? null);
}

export default function MapCanvas() {
  const container = useRef<HTMLDivElement>(null);
  const worldTip = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;
    const narrow = isNarrow();
    const cam0 = europeCamera();
    const map = new maplibregl.Map({
      container: container.current,
      style: STYLE,
      center: cam0.center,
      zoom: cam0.zoom,
      attributionControl: false,
      renderWorldCopies: false,
      pixelRatio: Math.min(window.devicePixelRatio, narrow ? 1.5 : 2),
      // labels change with the clock: swap them at once, without a fade (no blinking)
      fadeDuration: 0,
    });
    map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
    let deckHover = false;
    let deckSynced = false;
    const overlay = new MapboxOverlay({
      // drawn inside the map's own WebGL context: needed for the globe
      interleaved: true,
      layers: [],
      // deck.gl follows the map's moves only once it has loaded; a link's or a story's first
      // camera jump comes earlier, and hover picking would keep the start camera until a pan.
      // One move after its first frame brings it up to date. (onLoad cannot be used: the
      // overlay re-sends its props every frame and would replace deck.gl's own onLoad.)
      onAfterRender: () => {
        if (deckSynced) return;
        deckSynced = true;
        requestAnimationFrame(() => map.fire("move"));
      },
      getTooltip: tooltip,
      onHover: (info: PickingInfo) => {
        deckHover = !!info.object;
        if (deckHover && worldTip.current) worldTip.current.style.display = "none";
      },
    });
    map.addControl(overlay);
    // keep deck.gl's view in step with the map's projection (globe or flat)
    const syncViews = () => {
      const globe = map.getProjection()?.type === "globe";
      const view = globe ? new GlobeView({ id: "mapbox" }) : new MapView({ id: "mapbox" });
      overlay.setProps({ views: view } as unknown as Parameters<typeof overlay.setProps>[0]);
    };
    map.on("style.load", syncViews);
    map.on("styledata", syncViews);
    map.on("projectiontransition", syncViews);
    map.on("deckviewsync", syncViews);
    if (import.meta.env.DEV) Object.assign(window, { __map: map, __overlay: overlay });

    // ------------------------------------------------------------ redraw only when needed
    let dirty = true;
    const touch = () => (dirty = true);
    const unsubApp = useApp.subscribe(touch);
    const unsubData = useDataStore.subscribe(touch);
    map.on("move", touch);
    let mobile = narrow;
    const mq = window.matchMedia(MOBILE_QUERY);
    const onMq = () => {
      mobile = mq.matches;
      dirty = true;
    };
    mq.addEventListener("change", onMq);

    // ------------------------------------------------------------ clicks: deck objects first, then the world's land
    map.on("click", (e) => {
      const s = useApp.getState();
      const info = overlay.pickObject({ x: e.point.x, y: e.point.y, radius: 4 });
      const same = (a: Selection | null, b: Selection) => JSON.stringify(a) === JSON.stringify(b);
      const pick = (sel: Selection, tab = "now") => actions.select(same(s.selection, sel) ? null : sel, tab);
      const id = info?.layer?.id ?? "";
      if (info?.object) {
        if (id === "eu-countries" || id === "price-terrain") {
          const iso = (info.object as Shape).iso;
          return pick({ kind: "country", iso2: iso, iso3: ISO3[iso] }, s.colour.startsWith("pr_") ? "prices" : s.mode === "years" ? "years" : "now");
        }
        if (id === "pr-zones") return pick({ kind: "zone", id: (info.object as { zone: string }).zone }, "prices");
        const region = id.match(/^w-(us|br|au|tw|on)-regions$/);
        if (region) return pick({ kind: "region", grid: region[1] as "us" | "br" | "au" | "tw" | "on", id: (info.object as { id: string }).id });
        return; // plants, cables, sites: hover cards only
      }
      const land = map.queryRenderedFeatures(e.point, { layers: ["world-land"] })[0];
      const code = land?.properties?.iso3 as string | undefined;
      if (code) {
        const iso2 = EUROPE_ISO3.has(code) ? ISO2_OF[code] : undefined;
        return pick({ kind: "country", iso3: code, iso2 }, s.mode === "years" ? "years" : "now");
      }
      actions.select(null);
    });
    // the world's land: a DOM card (deck.gl's cards cover deck objects only)
    map.on("mousemove", "world-land", (e) => {
      const el = worldTip.current;
      const f = e.features?.[0];
      if (!el) return;
      const code = f?.properties?.iso3 as string | undefined;
      const html = !deckHover && code ? countryHtml((f?.properties?.name as string) ?? code, null, code) : null;
      if (!html) {
        el.style.display = "none";
        return;
      }
      el.innerHTML = html;
      el.style.display = "block";
      el.style.left = `${e.point.x + 14}px`;
      el.style.top = `${e.point.y + 14}px`;
    });
    map.on("mouseleave", "world-land", () => {
      if (worldTip.current) worldTip.current.style.display = "none";
    });
    map.on("dragstart", () => useApp.getState().sheet !== "none" && useApp.setState({ sheet: "none" }));
    map.on("moveend", () => {
      const c = map.getCenter();
      writeUrl({ center: [c.lng, c.lat], zoom: map.getZoom(), pitch: map.getPitch(), bearing: map.getBearing() });
      // the overview panel follows the camera: Europe or the US when it faces them, else the world
      const at: [number, number] = [c.lng, c.lat];
      const usZoom = isNarrow() ? 1.3 : 2.6; // closer than the world view: phones frame the US further out
      const region = angularDistance(at, EUROPE_CENTRE) < 35 ? "europe" : angularDistance(at, US_CENTRE) < 24 && map.getZoom() >= usZoom ? "us" : "world";
      if (region !== useApp.getState().region) useApp.setState({ region });
    });

    // ------------------------------------------------------------ camera: stories, search, selection
    let flatNow: boolean | null = null;
    // the price blocks and the US queue stand up: flat, tilted map
    const raisedPrices = () => useApp.getState().layers.prices || useApp.getState().layers.usQueue;
    // zoomed in, the map is flat too: deck.gl's globe drifts from MapLibre's by several pixels
    // from about zoom 9 (10 px at zoom 10, measured), while at zoom 7 globe and mercator agree
    // to a pixel, so the switch does not show (a little hysteresis keeps it from flapping)
    const zoomedIn = () => map.getZoom() >= (flatNow ? FLAT_ZOOM - 0.25 : FLAT_ZOOM);
    const wantFlat = () => {
      const s = useApp.getState();
      return s.mode === "day" || zoomedIn() || (s.mode === "live" && (!!selectedIso2(s.selection) || raisedPrices()));
    };
    const applyProjection = () => {
      const flat = wantFlat();
      if (flat === flatNow) return;
      if (setProjection(map, flat)) flatNow = flat;
    };
    map.on("style.load", applyProjection);
    const fly = (to: NonNullable<ReturnType<typeof useApp.getState>["flyTo"]>) => {
      applyProjection();
      if (to === "day") return dayFrame(map, 1200);
      if (to === "us" || to === "usQueue" || to === "usDay") return usFrame(map, to !== "us" && wantFlat(), 1400);
      const cam = to === "europe" ? europeView(map) : to === "world" ? worldCamera() : to;
      const tilt = typeof to === "object" && wantFlat();
      map.flyTo({ center: cam.center, zoom: cam.zoom, pitch: tilt ? (to.pitch ?? 0) : 0, bearing: tilt ? (to.bearing ?? 0) : 0, duration: 1400 });
    };
    /** Run once a file has arrived (a link can open on a country before its outline loads). */
    const whenFile = (key: string, run: () => void) => {
      if (fileOf(key)) return run();
      ensure(key);
      const off = useDataStore.subscribe((d) => {
        if (!d.files[key]) return;
        off();
        run();
      });
    };
    const focusCountry = (sel: Selection | null, prev: Selection | null) => {
      if (sel?.kind === "country" && !fileOf("countries")) return whenFile("countries", () => focusCountry(sel, prev));
      if (sel?.kind === "country" && !sel.iso2 && !fileOf("world")) return whenFile("world", () => focusCountry(sel, prev));
      applyProjection();
      const countries = fileOf<CountriesFile>("countries");
      const iso2 = selectedIso2(sel);
      const eu = iso2 ? countries?.countries.find((c) => c.iso === iso2) : null;
      if (eu) {
        // tilt into the country so the plant columns stand up (flat map, live mode)
        const pad = isNarrow() ? { left: 12, right: 12, top: 70, bottom: 220 } : { left: 300, right: 420, top: 90, bottom: 80 };
        const cam = map.cameraForBounds(bbox(eu), { padding: pad });
        if (!cam?.center) return;
        const tilt = useApp.getState().mode === "live";
        map.flyTo({ center: cam.center, zoom: Math.min(6.2, (cam.zoom ?? 5) - 0.1), pitch: tilt ? 52 : 0, bearing: tilt ? -12 : 0, duration: 1400 });
        return;
      }
      if (sel?.kind === "country" && sel.iso3) {
        const w = fileOf<WorldFile>("world") ?? null;
        const f = w?.features.find((x) => x.properties.iso3 === sel.iso3);
        if (!f) return;
        // the largest polygon frames the country (overseas islands do not)
        const poly = [...f.geometry.coordinates].sort((a, b) => b[0].length - a[0].length)[0][0];
        const xs = poly.map((p) => p[0]);
        const ys = poly.map((p) => p[1]);
        const cam = map.cameraForBounds(
          [
            [Math.min(...xs), Math.min(...ys)],
            [Math.max(...xs), Math.max(...ys)],
          ],
          { padding: isNarrow() ? { left: 20, right: 20, top: 80, bottom: 240 } : { left: 300, right: 420, top: 90, bottom: 80 } },
        );
        if (cam?.center) map.flyTo({ center: cam.center, zoom: Math.min(5.5, cam.zoom ?? 3), pitch: 0, bearing: 0, duration: 1400 });
        return;
      }
      // back from a European country: the overview again
      if (!sel && selectedIso2(prev)) fly(useApp.getState().mode === "day" ? "day" : "europe");
    };
    const unsubCam = useApp.subscribe((s, prev) => {
      if (s.flyTo && s.flyTo !== prev.flyTo) {
        const to = s.flyTo;
        useApp.setState({ flyTo: null });
        if (map.isStyleLoaded() || map.getLayer("world-land")) fly(to);
        else map.once("style.load", () => fly(to));
      } else if (s.selection !== prev.selection) {
        // a story sets its camera itself
        focusCountry(s.selection, prev.selection);
      } else if (s.mode !== prev.mode) applyProjection();
      else if (s.mode === "live" && !s.selection && s.layers.prices !== prev.layers.prices) {
        const was = flatNow;
        applyProjection();
        if (flatNow && !was) dayFrame(map, 1100);
        if (!flatNow && was) fly("europe");
      } else if (s.mode === "live" && !s.selection && s.layers.usQueue !== prev.layers.usQueue) applyProjection();
    });
    // a link with a selection or a camera, or a story's first camera
    map.once("style.load", () => {
      const s = useApp.getState();
      if (s.flyTo) {
        const to = s.flyTo;
        useApp.setState({ flyTo: null });
        if (typeof to === "object") {
          applyProjection();
          // the 24 h view keeps its padding, so a link opens on the same picture
          const padding = s.mode === "day" ? dayPadding() : undefined;
          map.jumpTo({ center: to.center, zoom: to.zoom, pitch: to.pitch ?? (s.mode === "day" ? 55 : 0), bearing: to.bearing ?? 0, padding });
        } else fly(to);
      } else if (s.selection) focusCountry(s.selection, null);
      else {
        applyProjection();
        map.jumpTo(europeView(map));
      }
    });
    if (useApp.getState().selection) ensure("world");

    // ------------------------------------------------------------ MapLibre's land and grid
    let landKey = "";
    let gridKey = "";
    let skyKey = "";
    const applyMapLibre = (dayFile: DayFile | null, sunAlt: number) => {
      if (!map.getLayer("world-land")) return;
      const s = useApp.getState();
      const t = fileOf<TransitionFile>("transition");
      const ws = fileOf<WorldStatsFile>("worldStats");
      const pick = s.selection?.kind === "country" ? (s.selection.iso3 ?? ISO3[s.selection.iso2 ?? ""] ?? "") : "";
      const irena = fileOf<IrenaFile>("irena");
      const key = `${s.colour}|${s.yearK}|${s.mode}|${t?.fetched}|${ws?.fetched}|${irena?.fetched}|${pick}`;
      if (key !== landKey) {
        landKey = key;
        const pairs: string[] = [];
        if (s.colour.startsWith("tr_") && t) {
          const m = metricById(s.colour.slice(3) as MetricId);
          for (const [code, e] of Object.entries(t.entities)) {
            const c = !e.aggregate ? metricColor(m, e[m.id][s.yearK]) : null;
            if (c) pairs.push(code, rgbCss(c));
          }
        } else if (s.colour.startsWith("ir_") && irena) {
          const m = irenaMetricById(s.colour.slice(3) as IrenaMetricId);
          const k = irenaK(irena, s.mode, t?.years, s.yearK);
          for (const code of Object.keys(irena.capacity_mw)) {
            const c = stopColor(IRENA_STOPS, irenaScale(irenaValue(irena, code, m, k)));
            if (c) pairs.push(code, rgbCss(c));
          }
        } else if (s.colour === "access" && ws) {
          for (const code of Object.keys(ws.access)) {
            const c = stopColor(ACCESS_STOPS, latest(ws.access[code], ws.years)?.value);
            if (c) pairs.push(code, rgbCss(c));
          }
        }
        map.setPaintProperty("world-land", "fill-color-transition", { duration: 450, delay: 0 });
        map.setPaintProperty("world-land", "fill-color", pairs.length ? ["match", ["get", "iso3"], ...pairs, rgbCss(TR_NO_DATA)] : LAND);
        map.setPaintProperty("world-coast", "line-color", pairs.length ? "rgba(6,9,14,0.6)" : "rgba(150,162,182,0.22)");
        // Europe's countries draw their own outline
        map.setFilter("world-pick", ["==", ["get", "iso3"], selectedIso2(s.selection) ? "" : pick]);
      }
      const gk = `${s.layers.gridWorld}|${s.layers.predicted}|${s.layers.gridUS}`;
      if (gk !== gridKey) {
        gridKey = gk;
        if (s.layers.gridWorld) addGridLayers(map, "hv");
        if (s.layers.predicted) addGridLayers(map, "predicted");
        if (s.layers.gridUS) addGridLayers(map, "us");
        for (const id of US_GRID_LAYERS) if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", s.layers.gridUS ? "visible" : "none");
        for (const id of GRID_LAYERS) if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", s.layers.gridWorld ? "visible" : "none");
        for (const id of PREDICTED_LAYERS) if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", s.layers.predicted ? "visible" : "none");
      }
      // 24 h: near-black at night, deep blue by day (sun height over Central Europe)
      const light = dayFile ? Math.max(0, Math.min(1, (sunAlt + 4) / 24)) : -1;
      const sky = light < 0 ? OCEAN : `rgb(${[5 + 9 * light, 7 + 17 * light, 11 + 29 * light].map(Math.round).join(",")})`;
      if (sky !== skyKey) {
        skyKey = sky;
        map.setPaintProperty("background", "background-color", sky);
      }
    };

    // ------------------------------------------------------------ images made on demand
    const nights = new Map<string, ImageBitmap>();
    const nightPending = new Set<string>();
    const nightAt = (d: DayFile, k: number): ImageBitmap | null => {
      const key = `${d.date}:${k}`;
      const hit = nights.get(key);
      if (hit || nightPending.has(key)) return hit ?? null;
      nightPending.add(key);
      createImageBitmap(nightImage(new Date(Date.parse(d.start) + k * d.step_s * 1000))).then((b) => {
        nights.set(key, b);
        dirty = true;
      });
      return null;
    };
    const suns = new WeakMap<WindFile, Map<number, HTMLCanvasElement | null>>();
    const sunAt = (file: WindFile, h: number) => {
      let m = suns.get(file);
      if (!m) suns.set(file, (m = new Map()));
      if (!m.has(h)) m.set(h, sunImage(file, h));
      return m.get(h) ?? null;
    };
    const particles = narrow ? new WindParticles(1200, 6) : new WindParticles(3600, 8);
    const clock = new FlowClock();

    // ------------------------------------------------------------ the loop
    let raf = 0;
    let last = -1;
    let odd = false;
    let wantedKey = "";
    let lastLabels: LabelCollection | null = null;
    const recording = new URLSearchParams(window.location.search).has("record");
    let ready = false;
    const loop = (now: number) => {
      raf = requestAnimationFrame(loop);
      if (import.meta.env.DEV && (window as unknown as { __stop?: boolean }).__stop) return;
      const dt = last < 0 ? 0 : Math.min(100, now - last);
      last = now;
      const s = useApp.getState();
      const files = useDataStore.getState().files;
      if (dirty) applyProjection();

      const wanted = wantedKeys();
      const wk = wanted.join(",");
      if (wk !== wantedKey) {
        wantedKey = wk;
        wanted.forEach((k) => ensure(k));
      }

      // "Plants through a day" opens on the newest day every big producer has reported
      // (Germany and others publish output per unit about five days late)
      if (s.story === "plants-day" && !s.day) {
        const idx = files.unitIndex as { complete: string[] } | undefined;
        const newest = idx?.complete[idx.complete.length - 1];
        if (newest) useApp.setState({ day: newest });
      }
      // the US one opens on the newest day EPA's data are complete for (months back)
      if (s.story === "us-plants-day" && !s.day) {
        const idx = files.usUnitIndex as { days: string[] } | undefined;
        const newest = idx?.days[idx.days.length - 1];
        if (newest) useApp.setState({ day: newest });
      }
      // the clocks
      const date = s.mode === "day" ? dayDate() : null;
      const day = date ? ((files[dayFileKey(s.dayRegion, date)] as DayFile | undefined) ?? null) : null;
      if (day && s.playing) {
        motion.daySlot = Math.min(day.slots - 0.001, motion.daySlot + (dt / 1000) * (day.slots / DAY_SECONDS));
        if (motion.daySlot >= day.slots - 0.001) useApp.setState({ playing: false });
      }
      if (day && Math.floor(motion.daySlot) !== s.slot) useApp.setState({ slot: Math.floor(motion.daySlot) });
      const transition = files.transition as TransitionFile | undefined;
      if (transition && yearFromUrl) {
        const at = transition.years.indexOf(yearFromUrl);
        clearYearFromUrl();
        if (at >= 0) {
          motion.yearPos = at;
          useApp.setState({ playing: false });
        }
      }
      if (s.mode === "years" && transition) {
        const lastYear = transition.years.length - 1;
        if (s.playing) {
          motion.yearPos = Math.min(lastYear, motion.yearPos + dt / 1000 / SEC_PER_YEAR);
          if (motion.yearPos >= lastYear) useApp.setState({ playing: false });
        }
      } else if (s.colour.startsWith("tr_") && transition && s.mode !== "years") {
        motion.yearPos = transition.years.length - 1; // the newest year outside the years mode
      }
      if (transition && Math.floor(motion.yearPos) !== s.yearK) useApp.setState({ yearK: Math.floor(motion.yearPos) });

      const windFile = (s.mode === "day" && date && s.dayRegion === "eu" ? files[`dayWind:${date}`] : s.mode === "live" ? (files.windWorld ?? files.wind) : undefined) as WindFile | undefined;
      const field = windFile ? memo("windField", [windFile], () => new WindField(windFile)) : null;
      const windOn = !!field && s.layers.wind;
      const flowsOn = s.layers.flows && (s.mode === "live" ? !!files.flows : !!day);
      const animating = (day && s.playing) || (s.mode === "years" && s.playing) || windOn || flowsOn || s.layers.liveGrids || s.layers.financeCoal || s.layers.financeGas || s.layers.prices;
      if (!animating && !dirty) return;
      // phones: animations at half rate
      if (mobile && !dirty && (odd = !odd)) return;
      dirty = false;

      const zoom = map.getZoom();
      clock.tick(now, zoom, 40);
      const when = day ? Date.parse(day.start) + motion.daySlot * day.step_s * 1000 : Date.now();
      if (windOn && field) {
        const b = map.getBounds();
        const c0 = map.getCenter();
        const box: [number, number, number, number] =
          map.getProjection()?.type === "globe" ? globeBox(c0, zoom) : [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()];
        // ~1.2 degrees a second at 10 m/s over the whole of Europe; slower when zoomed in
        particles.step(field, field.hourAt(when), (mobile ? 2 : 1) * (dt / 1000), 0.12 * Math.pow(2, 2.5 - zoom), box);
      }
      const dayK = day ? Math.min(day.slots - 1, Math.floor(motion.daySlot)) : 0;
      const slotMs = day ? Date.parse(day.start) + dayK * day.step_s * 1000 : 0;
      // the sun over the replayed region (Central Europe, or the middle of the US)
      const sunAlt = day ? (day.region === "us" ? sunAltAt(-95, 38, new Date(slotMs)) : centralSun(new Date(slotMs))) : 0;
      applyMapLibre(day, sunAlt);

      let sun: Frame["sun"] = null;
      if (s.layers.sun && field && windFile?.ghi) {
        const hour = field.hourAt(when);
        const h0 = Math.floor(hour);
        sun = {
          image: sunAt(windFile, h0),
          next: sunAt(windFile, Math.min(field.hours - 1, h0 + 1)),
          fade: hour - h0,
          bounds: sunBounds(windFile.grid),
        };
      }
      const night = day && s.layers.night ? nightAt(day, dayK) : null;
      if (day && s.layers.night) nightAt(day, Math.min(day.slots - 1, dayK + 1));
      const c = map.getCenter();
      const frame: Frame = {
        mode: s.mode,
        layers: s.layers,
        colour: s.colour,
        plantStatus: s.plantStatus,
        plantStyle: s.plantStyle,
        connectSide: s.connectSide,
        waterIndicator: s.waterIndicator,
        mastrTech: s.mastrTech,
        selection: s.selection,
        files,
        zoom,
        centre: [c.lng, c.lat],
        camKey: `${Math.round(c.lng / 3)},${Math.round(c.lat / 3)}`,
        clock: clock.uniforms(zoom, 72),
        day,
        daySlot: motion.daySlot,
        yearK: Math.floor(motion.yearPos),
        isMobile: mobile,
        wind: windOn && field ? { field, paths: particles.paths() } : null,
        sunAlt,
        dayRegion: s.dayRegion,
        now,
        sun,
        night,
      };
      // light on the towers, columns and price slabs: a fixed key light from the south-west keeps
      // their shape sharp at night; real sunlight (direction from the clock) adds day on top
      const lighting = memo("lighting", [day, dayK], () => {
        if (!day) return null;
        const dayness = Math.max(0, Math.min(1, (sunAlt + 2) / 20));
        return new LightingEffect({
          ambient: new AmbientLight({ color: [255, 255, 255], intensity: 0.75 + 0.15 * dayness }),
          key: new DirectionalLight({ color: [255, 255, 255], intensity: 1.2 - 0.9 * dayness, direction: [1, 2, -5] }),
          sun: new SunLight({ timestamp: slotMs, color: [255, 236, 206], intensity: 1.6 * dayness }),
        });
      });
      const effects = memo("effects", [lighting], () => (lighting ? [lighting] : []));
      overlay.setProps({ layers: buildLayers(frame), effects });
      // recordings (frontend/scripts/record-video.mjs): ready once the day, its weather and the map are in
      if (recording && !ready && map.loaded() && (s.mode !== "day" || (day && (!(s.layers.wind || s.layers.sun) || windFile)))) {
        ready = true;
        Object.assign(window, {
          __captureReady: true,
          __captureGo: () => {
            if (s.mode !== "day") return;
            actions.seekDay(0);
            useApp.setState({ playing: true });
          },
        });
      }
      // labels: MapLibre re-places them only when their content changed
      const labels = labelsOf();
      if (labels !== lastLabels) {
        const src = map.getSource("labels") as maplibregl.GeoJSONSource | undefined;
        if (src) {
          src.setData(labels as unknown as GeoJSON.FeatureCollection);
          lastLabels = labels;
        }
      }
    };
    raf = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(raf);
      unsubApp();
      unsubData();
      unsubCam();
      mq.removeEventListener("change", onMq);
      map.remove();
    };
  }, []);

  return (
    <>
      <div ref={container} className="absolute inset-0" />
      <div ref={worldTip} className="pointer-events-none absolute z-20 hidden" style={{ ...TIP_STYLE, position: "absolute" }} />
    </>
  );
}
