// "Check a site" on the map: the analysis area and everything the panel found inside it, drawn
// whatever layers are switched on. Outside the area the map is dimmed; inside: high-voltage lines
// by voltage (the map's own tiles), substations, plants by fuel (filled: operating; rings:
// building or planned), data centres, GB capacity sites, the Dutch capacity-map area, the
// nearest line and distance rings. Calm: no motion, the app's colours.

import type { Layer } from "@deck.gl/core";
import { LineLayer, PathLayer, ScatterplotLayer, SolidPolygonLayer, TextLayer } from "@deck.gl/layers";

import { NL_COLOR } from "../lib/connect";
import { power } from "../lib/energy";
import {
  SITE_RADIUS_KM,
  areaKey,
  kmText,
  useSiteFeatures,
  useSiteLines,
  type LonLat,
  type NearLine,
  type SiteFeatures,
  type SiteLine,
  type SitePlant,
} from "../lib/site";
import type { RGB } from "../lib/theme";
import { US_BANDS } from "../lib/us";
import type { Frame } from "./build";
import { memo } from "./memo";

const SITE: RGB = [226, 232, 240];
const LINE: RGB = [236, 178, 120];
const DC: RGB = [196, 150, 255];
const GB: RGB = [206, 138, 72];
const ON_TOP = { depthCompare: "always", depthWriteEnabled: false } as const;

/** The map's voltage colours (Europe's bands plus the US 100–199 kV band). */
const lineColor = (kv: number | null): [number, number, number, number] => {
  if (kv == null) return [150, 154, 166, 170];
  const b = US_BANDS.find((x) => kv >= x.min) ?? US_BANDS[US_BANDS.length - 1];
  return [...b.color, 235];
};
const lineWidth = (kv: number | null) => (kv == null ? 1.2 : kv >= 380 ? 2.6 : kv >= 275 ? 2.1 : kv >= 200 ? 1.7 : 1.3);

/** A circle as a ring of points (local flat projection; fine at these distances). */
function circle(c: LonLat, rKm: number, n = 96): LonLat[] {
  const dLat = rKm / 111.2;
  const dLon = dLat / Math.max(0.05, Math.cos((c[1] * Math.PI) / 180));
  return Array.from({ length: n + 1 }, (_, i) => {
    const a = (2 * Math.PI * i) / n;
    return [c[0] + dLon * Math.sin(a), c[1] + dLat * Math.cos(a)] as LonLat;
  });
}

type NlShape = { polygon: [number, number][][]; nl: NonNullable<SiteFeatures["nl"]> };

const plantRadius = (mw: number) => Math.max(3, Math.min(16, 2.5 + Math.sqrt(Math.max(0, mw)) * 0.45));

export function siteLayers(fr: Frame): Layer[] {
  const sel = fr.selection;
  if (sel?.kind !== "site") return [];
  const site: LonLat = [sel.lon, sel.lat];
  const r = sel.r ?? SITE_RADIUS_KM;
  const key = areaKey(site, r);
  const { world, us } = useSiteLines.getState();
  const w = world.key === key ? world.result : null;
  const u = us.key === key ? us.result : null;
  const features = useSiteFeatures.getState();
  const f: SiteFeatures | null = features.key === key ? features : null;
  const near = [u?.nearest, w?.nearest].filter((l): l is NearLine => !!l).sort((a, b) => a.km - b.km)[0];
  const lines: SiteLine[] = memo("siteLines", [w, u], () => [...(u?.lines ?? []), ...(w?.lines ?? [])].sort((a, b) => (a.kv ?? 0) - (b.kv ?? 0)));
  const ring = memo("siteRing", [key], () => circle(site, r));
  const half = memo("siteHalf", [key], () => circle(site, r / 2));
  // dim everything from the area's edge to three radii out
  const mask = memo("siteMask", [key], () => [{ polygon: [circle(site, r * 3.2), circle(site, r).slice().reverse()] }]);
  const plants = f?.plants ?? [];
  const labelled = [...plants]
    .filter((p) => p.status === "operating" && p.name)
    .sort((a, b) => b.mw - a.mw)
    .slice(0, 8);

  const out: Layer[] = [
    new SolidPolygonLayer<{ polygon: LonLat[][] }>({
      id: "site-mask",
      data: mask,
      getPolygon: (d) => d.polygon,
      getFillColor: [5, 7, 11, 150],
      parameters: ON_TOP,
    }),
    new PathLayer<LonLat[]>({
      id: "site-rings",
      data: [ring, half],
      getPath: (d) => d,
      getColor: (d) => (d === ring ? [...SITE, 150] : [...SITE, 55]),
      widthUnits: "pixels",
      getWidth: (d) => (d === ring ? 1.4 : 1),
      parameters: ON_TOP,
    }),
    new TextLayer<{ at: LonLat; text: string }>({
      id: "site-ring-labels",
      data: [
        { at: ring[0], text: `${r} km` },
        { at: half[0], text: `${r / 2} km` },
      ],
      getPosition: (d) => d.at,
      getText: (d) => d.text,
      getSize: 11,
      getColor: [...SITE, 170],
      getPixelOffset: [0, -9],
      fontFamily: "ui-sans-serif, system-ui, sans-serif",
      parameters: ON_TOP,
    }),
  ];

  // ---- the Dutch capacity-map area holding the site
  if (f?.nl) {
    const c: RGB = NL_COLOR[f.nl.offtakeK] ?? [150, 154, 166];
    const nl = f.nl;
    const polys: NlShape[] = nl.polygons.map((poly) => ({ polygon: poly, nl }));
    out.push(
      new SolidPolygonLayer<NlShape>({
        id: "site-nl",
        data: polys,
        getPolygon: (d) => d.polygon,
        getFillColor: [...c, 45],
        pickable: true,
        parameters: ON_TOP,
      }),
      new PathLayer<NlShape>({
        id: "site-nl-outline",
        data: polys,
        getPath: (d) => d.polygon[0],
        getColor: [...c, 200],
        widthUnits: "pixels",
        getWidth: 1.2,
        parameters: ON_TOP,
      }),
    );
  }

  // ---- high-voltage lines inside the area, by voltage
  if (lines.length)
    out.push(
      new PathLayer<SiteLine>({
        id: "site-lines",
        data: lines,
        getPath: (d) => d.path,
        getColor: (d) => lineColor(d.kv),
        widthUnits: "pixels",
        getWidth: (d) => lineWidth(d.kv),
        capRounded: true,
        jointRounded: true,
        pickable: true,
        autoHighlight: true,
        highlightColor: [255, 255, 255, 90],
        parameters: ON_TOP,
      }),
    );

  // ---- the link to the nearest line
  if (near)
    out.push(
      new LineLayer({
        id: "site-link",
        data: [{ from: site, to: near.at }],
        getSourcePosition: (d: { from: LonLat }) => d.from,
        getTargetPosition: (d: { to: LonLat }) => d.to,
        getColor: [...LINE, 220],
        getWidth: 1.5,
        widthUnits: "pixels",
        parameters: ON_TOP,
      }),
    );

  // ---- substations, capacity sites, data centres, plants
  if (f?.subs.length)
    out.push(
      new ScatterplotLayer<SiteFeatures["subs"][number]>({
        id: "site-subs",
        data: f.subs,
        getPosition: (d) => d.at,
        radiusUnits: "pixels",
        getRadius: (d) => (d.kv >= 380 ? 5 : 4),
        getFillColor: [12, 15, 21, 255],
        getLineColor: (d) => lineColor(d.kv),
        stroked: true,
        lineWidthUnits: "pixels",
        getLineWidth: 2,
        pickable: true,
        parameters: ON_TOP,
      }),
    );
  if (f?.gb.length)
    out.push(
      new ScatterplotLayer<SiteFeatures["gb"][number]>({
        id: "site-gb",
        data: f.gb,
        getPosition: (d) => d.at,
        radiusUnits: "pixels",
        getRadius: (d) => Math.max(4, Math.min(18, Math.sqrt(d.mw) * 0.3)),
        filled: false,
        stroked: true,
        getLineColor: [...GB, 220],
        lineWidthUnits: "pixels",
        getLineWidth: 1.5,
        pickable: true,
        parameters: ON_TOP,
      }),
    );
  if (f?.dcs.length)
    out.push(
      new ScatterplotLayer<SiteFeatures["dcs"][number]>({
        id: "site-dcs",
        data: f.dcs,
        getPosition: (d) => d.at,
        radiusUnits: "pixels",
        getRadius: 4,
        getFillColor: [...DC, 230],
        getLineColor: [12, 15, 21, 255],
        stroked: true,
        lineWidthUnits: "pixels",
        getLineWidth: 1,
        pickable: true,
        parameters: ON_TOP,
      }),
    );
  if (plants.length)
    out.push(
      new ScatterplotLayer<SitePlant>({
        id: "site-plants",
        data: plants,
        getPosition: (d) => d.at,
        radiusUnits: "pixels",
        getRadius: (d) => plantRadius(d.mw),
        filled: true,
        stroked: true,
        getFillColor: (d) => (d.status === "operating" ? [...d.color, 215] : [...d.color, 0]),
        getLineColor: (d) => (d.status === "operating" ? [12, 15, 21, 220] : [...d.color, 230]),
        lineWidthUnits: "pixels",
        getLineWidth: (d) => (d.status === "operating" ? 1 : 1.6),
        pickable: true,
        autoHighlight: true,
        highlightColor: [255, 255, 255, 120],
        parameters: ON_TOP,
      }),
      new TextLayer<SitePlant>({
        id: "site-plant-labels",
        data: labelled,
        getPosition: (d) => d.at,
        getText: (d) => `${d.name} · ${power(d.mw)}`,
        getSize: 11,
        getColor: [226, 232, 240, 220],
        getPixelOffset: (d) => [0, -plantRadius(d.mw) - 8],
        fontFamily: "ui-sans-serif, system-ui, sans-serif",
        outlineWidth: 3,
        outlineColor: [5, 7, 11, 230],
        fontSettings: { sdf: true },
        parameters: ON_TOP,
      }),
    );

  // ---- the point itself
  out.push(
    new ScatterplotLayer({
      id: "site-point",
      data: [site],
      getPosition: (d: LonLat) => d,
      getRadius: 6,
      radiusUnits: "pixels",
      filled: true,
      stroked: true,
      getFillColor: [8, 11, 17, 230],
      getLineColor: [...SITE, 255],
      lineWidthUnits: "pixels",
      getLineWidth: 2,
      parameters: ON_TOP,
    }),
  );
  return out;
}

const SRC = (s: string) => `<div style="color:#8d94a1">${s}</div>`;

/** Hover cards for the site analysis layers. */
export function siteHtml(id: string, object: unknown): string | null {
  switch (id) {
    case "site-lines": {
      const l = object as SiteLine;
      return `<b>${l.kv != null ? `${l.kv} kV` : "Voltage not tagged"}${l.dc ? ", DC" : ""}</b>${l.name ? `<div>${l.name}</div>` : ""}<div>${kmText(l.km)} from the site at its nearest point</div>${SRC("OpenStreetMap via Overture Maps (the map's line tiles)")}`;
    }
    case "site-subs": {
      const s = object as SiteFeatures["subs"][number];
      return `<b>Substation, ${s.kv} kV</b><div>${kmText(s.km)} from the site</div>${SRC("PyPSA-Eur network from OpenStreetMap")}`;
    }
    case "site-plants": {
      const p = object as SitePlant;
      const st = p.status === "operating" ? "operating" : p.status === "construction" ? "under construction" : "planned";
      return `<b>${p.name ?? p.type}</b><div>${p.name ? `${p.type} · ` : ""}${power(p.mw)} · ${st}</div><div>${kmText(p.km)} from the site</div>${SRC(p.source)}`;
    }
    case "site-dcs": {
      const d = object as SiteFeatures["dcs"][number];
      return `<b>${d.name ?? "Data centre"}</b>${d.operator ? `<div>${d.operator}</div>` : ""}<div>${kmText(d.km)} from the site</div>${SRC("mapped in OpenStreetMap")}`;
    }
    case "site-gb": {
      const g = object as SiteFeatures["gb"][number];
      return `<b>${g.name}</b><div>${g.owner} · ${power(g.mw)} contracted, not yet connected</div><div>${kmText(g.km)} from the site</div>${SRC(`NESO TEC register, ${g.date}`)}`;
    }
    case "site-nl": {
      const a = (object as { nl: NonNullable<SiteFeatures["nl"]> }).nl;
      return `<b>${a.name}</b>${a.operator ? `<div>${a.operator}</div>` : ""}<div>New demand: <b>${a.offtake}</b></div><div>New generation: <b>${a.feedin}</b></div>${SRC("Netbeheer Nederland, capaciteitskaart")}`;
    }
  }
  return null;
}
