// "Check a site": the site analysis panel (ui/Panel.tsx). Every card reads the map's own files
// and names its source; distances, point-in-outline tests and sums within the area the user
// picks (a radius around the point) are computed here and in lib/site.ts. What the cards find in
// the area goes to the map (lib/site.ts publishSite, map/siteLayers.ts). A card with nothing for
// the place stays away.

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { create } from "zustand";

import { useFile } from "../app/data";
import type { CountriesFile, GridFile, PlantsFile, WorldFile } from "../app/types";
import { atlasValue, type AtlasFile } from "../lib/atlas";
import { POP_CELL, peopleWithin } from "../lib/population";
import { gbSiteTotals, type ConnectFile } from "../lib/connect";
import { CONNECT_EU, connectEuKey, valueText, type ConnectEuFile } from "../lib/connectEu";
import { frNumber, ieRoom, itTotals, type FrFile, type IeFile, type ItFile } from "../lib/connectMore";
import { FUEL_COLOR, FUEL_LABEL, power } from "../lib/energy";
import type { PricesFile } from "../lib/prices";
import { euroCents, newestMonth, newestOf, usCents, type RetailFile } from "../lib/retail";
import { hoursText, newestYear, type UsCountiesFile, type UsOutagesFile, type WaterFile } from "../lib/risk";
import { SITE_RADII, SITE_RADIUS_KM, areaKey, inFlatPolygons, inGeoJsonPolygons, inPairPolygons, km, kmText, publishSite, searchSiteLines, searchSiteSubstations, siteKey, useSiteLines, useSiteSubstations, type LineSearch, type LonLat, type NearLine, type SitePlant } from "../lib/site";
import type { MastrMuniFile } from "../lib/mastr";
import { CONSTRAINT_RADIUS_KM, SHARE_STEP_KM, floodClassAt, floodLabel, protectedAround, roadsAround, type ConstraintsFile, type ProtectedFile, type ProtectedSearch } from "../lib/constraints";
import { actions } from "../app/store";
import type { RGB } from "../lib/theme";
import { ISO3, type TransitionFile } from "../lib/transition";
import { US_TYPE_COLOR, US_TYPE_LABEL, gwText, type UsPlantsFile, type UsQueueFile, type UsQueuesLiveFile, type UsState, type UsStatesFile } from "../lib/us";
import type { DataCentresFile } from "../lib/world";
import { PLANT_TYPE_COLOR, PLANT_TYPE_LABEL, type WorldPlantsFile } from "../lib/worldPlants";
import { Card } from "./CountryCards";

const muted = "text-[#8d94a1]";
const GREY: RGB = [150, 154, 166];

export interface Place {
  site: LonLat;
  /** Europe's countries (countries.json) carry ISO alpha-2; the world's outlines alpha-3 */
  iso2: string | null;
  iso3: string | null;
  name: string | null;
  europe: boolean;
  state: UsState | null;
  /** the outlines have arrived (a place at sea has no country) */
  ready: boolean;
  /** the area: a circle of this radius around the point, km */
  radius: number;
}

/** Which country (and US state) holds the site: point in the map's own outlines. */
export function usePlace(site: LonLat, radius: number = SITE_RADIUS_KM): Place {
  const countries = useFile<CountriesFile>("countries");
  const world = useFile<WorldFile>("world");
  const [lon, lat] = site;
  const eu = useMemo(() => countries?.countries.find((c) => inFlatPolygons([lon, lat], c.polygons)) ?? null, [countries, lon, lat]);
  const w = useMemo(() => (eu || !world ? null : (world.features.find((f) => inGeoJsonPolygons([lon, lat], f.geometry.coordinates)) ?? null)), [eu, world, lon, lat]);
  const iso3 = eu ? (ISO3[eu.iso] ?? null) : (w?.properties.iso3 ?? null);
  // loaded at once with the other outlines (small), not after the country is known
  const states = useFile<UsStatesFile>("usStates");
  const state = useMemo(() => states?.states.find((s) => inFlatPolygons([lon, lat], s.polygons)) ?? null, [states, lon, lat]);
  return {
    site,
    iso2: eu?.iso ?? null,
    iso3,
    name: state ? `${state.name}, United States` : (eu?.name ?? w?.properties.name ?? null),
    europe: !!eu,
    state,
    ready: !!countries && (!!eu || !!world) && (iso3 !== "USA" || !!states),
    radius,
  };
}

function Row({ k, v, sub }: { k: ReactNode; v: ReactNode; sub?: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-[3px] text-[11.5px]">
      <span className="min-w-0 text-slate-300">{k}</span>
      <span className="shrink-0 text-right tabular-nums text-slate-100">
        {v}
        {sub && <span className={`ml-1 text-[10px] ${muted}`}>{sub}</span>}
      </span>
    </div>
  );
}
const Note = ({ children }: { children: ReactNode }) => <p className={`mt-2 text-[10px] leading-snug ${muted}`}>{children}</p>;
const Loading = ({ what }: { what: string }) => <p className={`text-[11px] ${muted}`}>Reading {what}…</p>;
const sum = (v: number[]) => v.reduce((a, b) => a + b, 0);
const round = (v: number, d: number) => Number(v.toFixed(d));

// ---------------------------------------------------------------- the report behind the cards (CSV download)

/** [item, value, unit, note, source]: one figure as a card shows it, unformatted. */
export type ReportRow = [string, string | number | null, string, string, string];
const SECTIONS = ["Grid", "Room to connect", "Constraints", "Power plants", "Prices", "Risk", "Around it"] as const;
type Section = (typeof SECTIONS)[number];
const useSiteReport = create<{ key: string; sections: Partial<Record<Section, ReportRow[]>> }>(() => ({ key: "", sections: {} }));

/** A card hands its figures to the report (kept per site). */
function useReport(place: Place, section: Section, rows: (ReportRow | null | false | undefined)[]) {
  const key = areaKey(place.site, place.radius);
  const json = JSON.stringify(rows.filter(Boolean));
  useEffect(() => {
    const clean = JSON.parse(json) as ReportRow[];
    useSiteReport.setState((s) => ({ key, sections: { ...(s.key === key ? s.sections : {}), [section]: clean } }));
  }, [key, section, json]);
}

const csvCell = (v: unknown) => {
  const t = v == null ? "" : String(v);
  return /[",\n]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t;
};

function SiteDownload({ place }: { place: Place }) {
  const key = areaKey(place.site, place.radius);
  const report = useSiteReport();
  const rows = report.key === key ? SECTIONS.flatMap((sec) => (report.sections[sec] ?? []).map((r) => [sec, ...r])) : [];
  const download = () => {
    const [lon, lat] = place.site;
    const head = [
      ["section", "item", "value", "unit", "note", "source"],
      ["Site", "Latitude", lat, "degrees", "", ""],
      ["Site", "Longitude", lon, "degrees", "", ""],
      ["Site", "Area radius", place.radius, "km", "figures summed within this distance", ""],
      ["Site", "Place", place.name ?? "", "", "", "the map's outlines"],
      ["Site", "Link", window.location.href, "", "", "InfraAtlas"],
      ["Site", "Downloaded", new Date().toISOString().slice(0, 19) + "Z", "UTC", "", ""],
    ];
    const text = [...head, ...rows].map((r) => r.map(csvCell).join(",")).join("\r\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["\ufeff" + text], { type: "text/csv;charset=utf-8" }));
    a.download = `infraatlas-site-${lat.toFixed(4)}_${lon.toFixed(4)}_${place.radius}km.csv`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };
  return (
    <button
      onClick={download}
      disabled={!rows.length}
      className="w-full rounded-lg border border-white/10 px-3 py-1.5 text-[11px] text-slate-300 hover:bg-white/[0.07] disabled:opacity-40"
    >
      Download these figures (CSV, {rows.length} rows with their sources)
    </button>
  );
}

const OSM_US = "OpenStreetMap via Overture Maps (grid/us-lines.pmtiles)";
const OSM_WORLD = "OpenStreetMap via Overture Maps (grid/world-hv.pmtiles)";
function lineReport(label: string, s: LineSearch | null | undefined, pick: (s: LineSearch) => NearLine | null, source: string): ReportRow | null {
  if (!s) return null;
  const l = pick(s);
  if (!l) return [label, null, "km", `none within ${round(s.radiusKm, 1)} km (the tiles read)`, source];
  return [label, round(l.km, 2), "km", [l.kv != null ? `${l.kv} kV` : "voltage not tagged", l.dc ? "DC" : "", l.name ?? ""].filter(Boolean).join("; "), source];
}

/** Records within the radius, nearest first. */
function within<T>(rows: T[] | undefined, at: (r: T) => LonLat, site: LonLat, R: number): { row: T; d: number }[] {
  if (!rows) return [];
  // a degree of latitude is 111 km: a box test before the distance
  const dLat = R / 111;
  const dLon = R / (111 * Math.max(0.05, Math.cos((site[1] * Math.PI) / 180)));
  const out: { row: T; d: number }[] = [];
  for (const row of rows) {
    const p = at(row);
    if (Math.abs(p[1] - site[1]) > dLat || Math.abs(((p[0] - site[0] + 540) % 360) - 180) > dLon) continue;
    const d = km(site, p);
    if (d <= R) out.push({ row, d });
  }
  return out.sort((a, b) => a.d - b.d);
}

// ---------------------------------------------------------------- the grid

function lineRow(label: string, s: LineSearch | null, failed: boolean, pick: (s: LineSearch) => LineSearch["nearest"]) {
  if (failed) return <Row k={label} v="tiles not reachable" />;
  if (!s) return <Row k={label} v="…" />;
  const l = pick(s);
  if (!l) return <Row k={label} v={`none within ${kmText(s.radiusKm)}`} />;
  return (
    <>
      <Row k={label} v={kmText(l.km)} sub={`${l.kv != null ? `${l.kv} kV` : "voltage not tagged"}${l.dc ? ", DC" : ""}`} />
      {l.name && <div className={`-mt-0.5 truncate pb-0.5 text-right text-[10px] ${muted}`}>{l.name}</div>}
    </>
  );
}

export function SiteGridCard({ place }: { place: Place }) {
  const { site } = place;
  const R = place.radius;
  const key = areaKey(site, R);
  const inUs = !!place.state;
  useEffect(() => {
    searchSiteLines("world", site, R);
    if (inUs) searchSiteLines("us", site, R);
  }, [site, inUs, R]);
  const world = useSiteLines((s) => (s.world.key === key ? s.world : null));
  const us = useSiteLines((s) => (s.us.key === key ? s.us : null));
  const grid = useFile<GridFile>(place.europe ? "grid" : null);
  const subs = useMemo(() => within(grid?.substations, (s) => [s[1], s[2]], site, R), [grid, site, R]);
  useEffect(() => publishSite(key, { subs: subs.map((x) => ({ at: [x.row[1], x.row[2]] as LonLat, kv: x.row[0], km: x.d })) }), [key, subs]);
  const linesIn = (s: LineSearch | null | undefined) => {
    const byKv = new Map<string, number>();
    for (const l of s?.lines ?? []) {
      const k = l.kv != null ? `${l.kv} kV` : "voltage not tagged";
      byKv.set(k, (byKv.get(k) ?? 0) + 1);
    }
    return [...byKv.entries()].sort((a, b) => parseFloat(b[0]) - parseFloat(a[0]));
  };
  const pypsa = "PyPSA-Eur network from OpenStreetMap (grid.json)";
  // outside Europe: every substation mapped in OpenStreetMap (the world tiles)
  const outside = place.ready && !place.europe;
  useEffect(() => {
    if (outside) searchSiteSubstations(site);
  }, [site, outside]);
  const wsub = useSiteSubstations((s) => (s.key === key ? s : null));
  const OSM_SUBS = "OpenStreetMap via Overture Maps (grid/world-substations.pmtiles)";
  // Germany: the grid operator of the municipality (MaStR); US: the utilities serving the county (EIA-861)
  const muni = useFile<MastrMuniFile>(place.iso2 === "DE" ? "mastrMuni" : null);
  const deOps = useFile<{ snapshot: string; municipalities: Record<string, [string, string, number, number, number]> }>(place.iso2 === "DE" ? "deGridOperators" : null);
  const gem = useMemo(() => muni?.gemeinden.find((g) => inFlatPolygons(site, g.polygons)) ?? null, [muni, site]);
  const deOp = gem && deOps ? (deOps.municipalities[gem.ags] ?? null) : null;
  const counties = useFile<UsCountiesFile>(place.state ? "usCounties" : null);
  const utilities = useFile<{ year: string; utilities: Record<string, string>; counties: Record<string, number[]> }>(place.state ? "usUtilities" : null);
  const county = useMemo(() => counties?.counties.find((c) => inFlatPolygons(site, c.polygons)) ?? null, [counties, site]);
  const serving = county && utilities ? (utilities.counties[county.code] ?? []).map((id) => utilities.utilities[String(id)]) : [];
  const mastrSrc = deOps ? `Marktstammdatenregister ${deOps.snapshot} (units' grid connection points)` : "";
  const eiaSrc = utilities ? `EIA-861 service territory ${utilities.year} (PUDL)` : "";
  useReport(place, "Grid", [
    inUs && lineReport("Nearest line, 100 kV or more", us?.result, (s) => s.nearest, OSM_US),
    lineReport("Nearest line, 220 kV or more", world?.result, (s) => s.nearest, OSM_WORLD),
    lineReport("Nearest line, 345 kV or more", world?.result, (s) => s.ehv, OSM_WORLD),
    place.europe && !!grid && ["Nearest substation, 220 kV or more", subs[0] ? round(subs[0].d, 2) : null, "km", subs[0] ? `${subs[0].row[0]} kV` : `none within ${R} km`, pypsa],
    place.europe && !!grid && [`Substations within ${R} km`, subs.length, "count", "220 kV and more", pypsa],
    outside && !!wsub?.result && ["Nearest substation", wsub.result.near[0] ? round(wsub.result.near[0].km, 2) : null, "km", wsub.result.near[0] ? [wsub.result.near[0].kv != null ? `${wsub.result.near[0].kv} kV` : "voltage not tagged", wsub.result.near[0].name ?? ""].filter(Boolean).join("; ") : `none within ${round(wsub.result.radiusKm, 1)} km`, OSM_SUBS],
    outside && !!wsub?.result && [`Substations within ${round(wsub.result.radiusKm, 1)} km`, wsub.result.near.length, "count", "every voltage mapped", OSM_SUBS],
    !!deOp && ["Grid operator of the municipality", deOp[0], "", `${deOp[2]} of ${deOp[4]} units in ${gem?.name ?? gem?.ags}; ${deOp[3]} operators`, mastrSrc],
    ...serving.map((u) => ["Utility serving the county", u, "", county?.name ?? "", eiaSrc] as ReportRow),
  ]);
  return (
    <Card title="Grid" note={`straight-line distance`} accent={[236, 178, 120]}>
      {inUs && lineRow("Nearest line, 100 kV or more", us?.result ?? null, !!us?.failed, (s) => s.nearest)}
      {lineRow("Nearest line, 220 kV or more", world?.result ?? null, !!world?.failed, (s) => s.nearest)}
      {lineRow("Nearest line, 345 kV or more", world?.result ?? null, !!world?.failed, (s) => s.ehv)}
      {world?.result && (
        <Row
          k={`Line sections within ${R} km`}
          v={(world.result.lines.length + (us?.result?.lines.length ?? 0)).toLocaleString("en-US")}
          sub={linesIn(world.result)
            .slice(0, 3)
            .map(([k, n]) => `${k} ${n}`)
            .join(" · ")}
        />
      )}
      {place.europe &&
        (grid ? (
          <>
            <Row k="Nearest substation, 220 kV or more" v={subs[0] ? kmText(subs[0].d) : `none within ${R} km`} sub={subs[0] ? `${subs[0].row[0]} kV` : undefined} />
            <Row k={`Substations within ${R} km`} v={subs.length.toLocaleString("en-US")} />
          </>
        ) : (
          <Loading what="substations" />
        ))}
      {outside &&
        (wsub?.failed ? (
          <Row k="Nearest substation" v="tiles not reachable" />
        ) : !wsub?.result ? (
          <Row k="Nearest substation" v="…" />
        ) : (
          <>
            <Row
              k="Nearest substation"
              v={wsub.result.near[0] ? kmText(wsub.result.near[0].km) : `none within ${kmText(wsub.result.radiusKm)}`}
              sub={wsub.result.near[0] ? (wsub.result.near[0].kv != null ? `${wsub.result.near[0].kv} kV` : "voltage not tagged") : undefined}
            />
            {wsub.result.near[0]?.name && <div className={`-mt-0.5 truncate pb-0.5 text-right text-[10px] ${muted}`}>{wsub.result.near[0].name}</div>}
            <Row k={`Substations within ${kmText(wsub.result.radiusKm)}`} v={wsub.result.near.length.toLocaleString("en-US")} sub="every voltage mapped" />
          </>
        ))}
      {deOp && <Row k="Grid operator of the municipality" v={<span className="truncate">{deOp[0]}</span>} sub={`${deOp[2].toLocaleString("en-US")} of ${deOp[4].toLocaleString("en-US")} units; ${deOp[3]} operators`} />}
      {serving.length > 0 && <Row k={`Utilities serving ${county?.name ?? "the county"}`} v={serving.length} sub={serving.slice(0, 3).join(", ")} />}
      <Note>
        Distance in a straight line to the line's mapped course. Lines: OpenStreetMap (ODbL) via Overture Maps, the map's own tiles ({inUs ? "US lines from 100 kV, " : ""}
        lines from 220 kV worldwide; simplified by about 0.1 km), voltage as tagged.{place.europe ? " Substations: PyPSA-Eur's network from OpenStreetMap." : ""} Projects connect at
        substations, where the operator has room: a line nearby is not a connection offer.{outside ? " Substations outside Europe: every one mapped in OpenStreetMap (points at the centre of mapped outlines), within the tiles read." : ""}
        {deOp ? " Germany: the operator most of the municipality's units are connected to (MaStR, count computed)." : ""}
        {serving.length ? ` United States: the utilities reporting service in the county (EIA-861, ${utilities?.year}).` : ""}
      </Note>
    </Card>
  );
}

// ---------------------------------------------------------------- room to connect

export function SiteCapacityCard({ place }: { place: Place }) {
  const { site } = place;
  const R = place.radius;
  const key = areaKey(site, R);
  const connect = useFile<ConnectFile>(place.iso2 === "GB" || place.iso2 === "NL" ? "connect" : null);
  const queue = useFile<UsQueueFile>(place.state ? "usQueue" : null);
  const live = useFile<UsQueuesLiveFile>(place.state ? "usQueuesLive" : null);
  const nl = useMemo(() => (place.iso2 === "NL" && connect ? (connect.nl.areas.find((a) => inPairPolygons(site, a.polygons)) ?? null) : null), [connect, place.iso2, site]);
  const gb = useMemo(
    () => (place.iso2 === "GB" && connect ? within(gbSiteTotals(connect.gb), (t) => [t.site[1] as number, t.site[2] as number], site, R) : []),
    [connect, place.iso2, site, R],
  );
  useEffect(
    () =>
      publishSite(key, {
        gb: connect
          ? gb.map((g) => ({ at: [g.row.site[1] as number, g.row.site[2] as number] as LonLat, name: g.row.site[0], owner: g.row.site[3], mw: g.row.mw, km: g.d, date: connect.gb.date }))
          : [],
        nl:
          nl && connect
            ? { name: nl.name, operator: nl.operator, offtake: connect.nl.status[nl.offtake], feedin: connect.nl.status[nl.feedin], offtakeK: nl.offtake, polygons: nl.polygons }
            : null,
      }),
    [key, gb, nl, connect],
  );
  const frf = useFile<FrFile>(place.iso2 === "FR" ? "connectFR" : null);
  const ief = useFile<IeFile>(place.iso2 === "IE" ? "connectIE" : null);
  const itf = useFile<ItFile>(place.iso2 === "IT" ? "connectIT" : null);
  const frNear = useMemo(() => (frf ? within(frf.sites, (x) => [x[3], x[4]], site, R) : []), [frf, site, R]);
  const ieNear = useMemo(() => (ief ? within(ief.stations, (x) => [x[3], x[4]], site, R) : []), [ief, site, R]);
  const itReg = useMemo(
    () => (itf ? (Object.entries(itf.nuts2).find(([, ids]) => ids.some((id) => inFlatPolygons(site, itf.shapes[id] ?? []))))?.[0] ?? null : null),
    [itf, site],
  );
  const itTot = itf && itReg ? itTotals(itf)[itReg] : undefined;
  // ten more countries (connect/<cc>.json): the operator's points within the radius, or its area holding the site
  const euCc = place.iso2 ? (CONNECT_EU.find((c) => c === place.iso2 || c === `${place.iso2}-DSO`) ?? null) : null;
  const euf = useFile<ConnectEuFile>(euCc ? connectEuKey(euCc) : null);
  const euNear = useMemo(() => (euf ? within(euf.points, (p) => [p[1], p[2]], site, R) : []), [euf, site, R]);
  const euArea = useMemo(() => euf?.areas.find((a) => inFlatPolygons(site, a[1])) ?? null, [euf, site]);
  const euSrc = euf ? `${euf.source}${euf.updated ? `, ${euf.updated}` : ""}` : "";
  const euCol = euf?.columns[0];
  const capSrc = "Capareseau (RTE and the distribution operators)";
  const esbSrc = ief ? `ESB Networks capacity heatmap (${ief.file})` : "";
  const ternaSrc = "Terna Econnextion (dati.terna.it)";
  const code = place.state?.code;
  const st = code ? queue?.states[code] : undefined;
  // a hybrid counts under each of its types with its full capacity: types, not a total
  const mine = code
    ? Object.entries(live?.markets ?? {})
        .map(([m, v]) => ({ m, types: Object.entries(v.by_state?.[code] ?? {}).sort((a, b) => b[1] - a[1]) }))
        .filter((x) => x.types.length > 0)
        .sort((a, b) => b.types[0][1] - a.types[0][1])
    : [];
  const types = st && queue ? queue.types.map((t, i) => ({ t, mw: st.active[i] })).filter((x) => x.mw > 0).sort((a, b) => b.mw - a.mw) : [];
  const tec = connect ? `NESO TEC register, ${connect.gb.date}` : "";
  const nlSrc = "Netbeheer Nederland capacity map (connect.json)";
  const lbnl = queue ? `LBNL Queued Up, through ${queue.through}` : "";
  useReport(place, "Room to connect", [
    ...(nl && connect
      ? ([
          ["Capacity-map area", nl.name, "", nl.operator ?? "", nlSrc],
          ["New demand", connect.nl.status[nl.offtake], "", "", nlSrc],
          ["New generation", connect.nl.status[nl.feedin], "", "", nlSrc],
          ["Queue, new demand", nl.queue_offtake_mw, "MW", "", nlSrc],
          ["Queue, new generation", nl.queue_feedin_mw, "MW", "", nlSrc],
        ] as ReportRow[])
      : []),
    ...(place.iso2 === "GB" && connect
      ? ([
          [`TEC waiting within ${R} km`, round(sum(gb.map((g) => g.row.mw)), 1), "MW", `${gb.length} sites`, tec],
          ...gb.slice(0, 20).map((g) => [g.row.site[0], round(g.row.mw, 1), "MW", `${round(g.d, 2)} km; ${g.row.site[3]}`, tec]),
        ] as ReportRow[])
      : []),
    ...(st
      ? ([
          [`Active requests in ${place.state?.name}`, round(sum(st.active), 1), "MW", `${st.active_n} projects`, lbnl],
          ...types.map((x) => [`Active requests, ${x.t}`, round(x.mw, 1), "MW", "", lbnl]),
        ] as ReportRow[])
      : []),
    ...(frf
      ? ([
          [`S3REnR capacity left to allocate within ${R} km`, round(sum(frNear.map((x) => frNumber(frf, x.row, "INFO_NA") ?? 0)), 1), "MW", `${frNear.length} substations (sum, computed)`, capSrc],
          ...frNear.slice(0, 20).map((x) => [x.row[1], frNumber(frf, x.row, "INFO_NA"), "MW", `${round(x.d, 2)} km; S3REnR capacity left to allocate`, capSrc]),
        ] as ReportRow[])
      : []),
    ...(ief
      ? ieNear.slice(0, 20).flatMap((x) => [
          [`${x.row[0]}: demand available`, ieRoom(ief, x.row, "offtake"), "MVA", `${round(x.d, 2)} km`, esbSrc],
          [`${x.row[0]}: generation available, firm`, ieRoom(ief, x.row, "feedin"), "MW", `${round(x.d, 2)} km`, esbSrc],
        ] as ReportRow[])
      : []),
    ...(itTot && itReg
      ? ([
          [`Renewables requested in ${itReg}`, round(itTot.fer, 1), "MW", "sum over sources, computed", ternaSrc],
          [`Storage requested in ${itReg}`, round(itTot.storage, 1), "MW", "sum over types, computed", ternaSrc],
        ] as ReportRow[])
      : []),
    ...(euf && euCol
      ? ([
          ...(euArea ? euf.columns.map(([, label, unit], i) => [`${euArea[0]}: ${label}`, euArea[2][i] as number | string | null, unit, "the area holding the site", euSrc]) : []),
          ...euNear.slice(0, 20).map((x) => [x.row[0], x.row[4][0] as number | string | null, euCol[2], `${round(x.d, 2)} km; ${euCol[1]}; ${euf.classes[x.row[5]] ?? ""}`, euSrc]),
        ] as ReportRow[])
      : []),
    ...mine.flatMap((x) =>
      x.types.map(([t, mw]) => [`${x.m}'s own queue, active, ${t}`, round(mw, 1), "MW", "a hybrid counts under each of its types", `${x.m} via gridstatus, ${live?.fetched.slice(0, 10)}`] as ReportRow),
    ),
  ]);
  if (((place.iso2 === "GB" || place.iso2 === "NL") && !connect) || (code && !queue))
    return (
      <Card title="Room to connect" accent={[206, 138, 72]}>
        <Loading what="the queues" />
      </Card>
    );
  if (place.iso2 === "NL" && connect) {
    if (!nl) return null;
    return (
      <Card title="Room to connect" note="Netbeheer Nederland" accent={[206, 138, 72]}>
        <Row k="Capacity-map area" v={nl.name} sub={nl.operator ?? undefined} />
        <Row k="New demand" v={connect.nl.status[nl.offtake]} />
        <Row k="New generation" v={connect.nl.status[nl.feedin]} />
        {(nl.queue_offtake_mw != null || nl.queue_feedin_mw != null) && (
          <Row k="Queue, demand / generation" v={`${nl.queue_offtake_mw != null ? gwText(nl.queue_offtake_mw) : "–"} / ${nl.queue_feedin_mw != null ? gwText(nl.queue_feedin_mw) : "–"}`} />
        )}
        <Note>The grid operators' capacity map (capaciteitskaart): the area holding the site, as published.</Note>
      </Card>
    );
  }
  if (place.iso2 === "GB" && connect) {
    const total = sum(gb.map((g) => g.row.mw));
    return (
      <Card title="Room to connect" note={`NESO TEC register, ${connect.gb.date}`} accent={[206, 138, 72]}>
        <Row k={`Waiting within ${R} km`} v={gwText(total)} sub={`${gb.length} sites`} />
        {gb.slice(0, 5).map((g) => (
          <Row key={g.row.k} k={<span className="truncate">{g.row.site[0]}</span>} v={gwText(g.row.mw)} sub={kmText(g.d)} />
        ))}
        {euf && euNear.length > 0 && (
          <Row
            k={`Distribution register within ${R} km`}
            v={gwText(sum(euNear.map((x) => (typeof x.row[4][0] === "number" ? x.row[4][0] : 0))))}
            sub={`accepted, not connected; ${euNear.length} sites (sum, computed)`}
          />
        )}
        <Note>
          Transmission Entry Capacity contracted and not yet connected, summed per site (computed); sites placed by NESO's GSP lookup, those without a position left out.
          Contracts, not spare capacity.
        </Note>
      </Card>
    );
  }
  if (euf && (euNear.length || euArea)) {
    return (
      <Card title="Room to connect" note={euf.source.split(",")[0]} accent={[206, 138, 72]}>
        {euArea && euf.columns.slice(0, 4).map(([k, label, unit], i) => <Row key={k} k={label} v={valueText(euArea[2][i], unit)} sub={i === 0 ? euArea[0] : undefined} />)}
        {euNear.slice(0, 5).map((x) => (
          <Row key={`${x.row[0]}${x.d}`} k={<span className="truncate">{x.row[0]}</span>} v={valueText(x.row[4][0], euf.columns[0][2])} sub={`${kmText(x.d)} · ${euf.classes[x.row[5]] ?? ""}`} />
        ))}
        <Note>{euf.columns[0][1]}, as published; {euf.note}</Note>
      </Card>
    );
  }
  if (frf && place.iso2 === "FR") {
    const left = sum(frNear.map((x) => frNumber(frf, x.row, "INFO_NA") ?? 0));
    return (
      <Card title="Room to connect" note="Capareseau" accent={[206, 138, 72]}>
        <Row k={`S3REnR capacity left within ${R} km`} v={gwText(left)} sub={`${frNear.length} substations`} />
        {frNear.slice(0, 5).map((x) => (
          <Row key={x.row[0]} k={<span className="truncate">{x.row[1]}</span>} v={gwText(frNumber(frf, x.row, "INFO_NA") ?? 0)} sub={kmText(x.d)} />
        ))}
        <Note>Capacity reserved for renewables by the region's S3REnR and not yet allocated, per substation, as RTE and the distribution operators publish it (sum, computed). For new generation only; indicative.</Note>
      </Card>
    );
  }
  if (ief && place.iso2 === "IE") {
    return (
      <Card title="Room to connect" note="ESB Networks heatmap" accent={[206, 138, 72]}>
        {ieNear.length === 0 && <Row k={`Stations within ${R} km`} v="none" />}
        {ieNear.slice(0, 5).map((x) => (
          <Row key={x.row[0]} k={<span className="truncate">{x.row[0]}</span>} v={`${round(ieRoom(ief, x.row, "offtake") ?? 0, 1)} MVA / ${round(ieRoom(ief, x.row, "feedin") ?? 0, 1)} MW`} sub={kmText(x.d)} />
        ))}
        <Note>Demand available (MVA) / firm generation available (MW) at the nearest 38 kV and 110 kV stations and MV transformers: transformer capacity only, as ESB Networks publishes it.</Note>
      </Card>
    );
  }
  if (itTot && itReg) {
    return (
      <Card title="Waiting to connect" note={`in ${itReg}`} accent={[206, 138, 72]}>
        <Row k="Renewables requested (Terna)" v={gwText(itTot.fer)} />
        <Row k="Storage requested (Terna)" v={gwText(itTot.storage)} />
        <Note>Per region, not per substation: requests to connect to the transmission grid at every stage (Terna Econnextion), most of which will not be built.</Note>
      </Card>
    );
  }
  if (code && queue) {
    return (
      <Card title="Waiting to connect" note={`in ${place.state?.name}`} accent={[206, 138, 72]}>
        {st ? (
          <>
            <Row k="Active requests (LBNL Queued Up)" v={gwText(sum(st.active))} sub={`${st.active_n.toLocaleString("en-US")} projects`} />
            <div className={`pb-1 text-right text-[10px] ${muted}`}>{types.slice(0, 4).map((x) => `${x.t} ${gwText(x.mw)}`).join(" · ")}</div>
          </>
        ) : (
          <Row k="Active requests (LBNL Queued Up)" v="none listed" />
        )}
        {mine.map((x) => (
          <div key={x.m}>
            <Row k={`${x.m}'s own queue, active`} v="" />
            <div className={`-mt-0.5 pb-1 text-right text-[10px] ${muted}`}>{x.types.slice(0, 4).map(([t, mw]) => `${t} ${gwText(mw)}`).join(" · ")}</div>
          </div>
        ))}
        <Note>
          Per state, not per substation: LBNL's yearly compilation (through {queue.through}; each part of a hybrid under its own type) and the markets' own queues read
          weekly ({live?.fetched.slice(0, 10) ?? "…"}; a hybrid under each of its types with its full size, so their types are not added up). Requests, most of which never
          connect.
        </Note>
      </Card>
    );
  }
  return null;
}

// ---------------------------------------------------------------- what stops a build

type Pending<T> = { key: string; v: T | null; failed: boolean };
function useAsync<T>(key: string | null, run: () => Promise<T>): Pending<T> {
  const [st, setSt] = useState<Pending<T>>({ key: "", v: null, failed: false });
  useEffect(() => {
    if (!key) return;
    let live = true;
    setSt({ key, v: null, failed: false });
    run()
      .then((v) => live && setSt({ key, v, failed: false }))
      .catch(() => live && setSt({ key, v: null, failed: true }));
    return () => {
      live = false;
    };
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  return st.key === key ? st : { key: key ?? "", v: null, failed: false };
}

export function SiteConstraintsCard({ place }: { place: Place }) {
  const { site } = place;
  const key = siteKey(site);
  const cf = useFile<ConstraintsFile>("constraints");
  const pf = useFile<ProtectedFile>("protected");
  const covered = place.europe || !!place.state;
  const prot = useAsync<ProtectedSearch>(pf && covered ? `p|${key}` : null, () => protectedAround(pf!.tiles, site));
  const roads = useAsync(cf && covered ? `r|${key}` : null, () => roadsAround(cf!.roads.tiles, site));
  const flood = useAsync(cf ? `f|${key}` : null, async () => {
    const eu = await floodClassAt(cf!.flood.maps.eu.lookup, site[0], site[1]);
    if (eu > 0 || (eu === 0 && place.europe)) return { cls: eu, map: "eu" as const };
    return { cls: Math.max(0, await floodClassAt(cf!.flood.maps.world.lookup, site[0], site[1])), map: "world" as const };
  });
  const R = CONSTRAINT_RADIUS_KM;
  const n2k = pf ? `${pf.natura2000.source}` : "";
  const pad = pf ? `${pf.padus.source}` : "";
  const fl = cf && flood.v ? cf.flood.maps[flood.v.map] : null;
  const flSrc = cf && fl ? `${cf.flood.source}; ${fl.title}; ${fl.lookup.computed}` : "";
  const osm = cf?.roads.source ?? "";
  useReport(place, "Constraints", [
    ...(prot.v
      ? ([
          [`Share of ${R} km around covered by protected areas`, round(100 * prot.v.share, 1), "%", `${prot.v.points} points ${SHARE_STEP_KM} km apart (computed)`, place.europe ? n2k : pad],
          ...prot.v.areas.slice(0, 20).map((a) => [a.name, round(a.km, 2), "km", [a.km === 0 ? "the site is inside" : "to its outline", a.kind, a.gap ? `GAP ${a.gap}` : "", a.id].filter(Boolean).join("; "), a.src === "n2k" ? n2k : pad]),
        ] as ReportRow[])
      : []),
    !!cf && !!flood.v && ["River flood depth, 100-year flood", floodLabel(cf, flood.v.cls), "", flood.v.cls ? `class ${flood.v.cls} of 5` : "", flSrc],
    !!roads.v && ["Nearest major road", roads.v.road ? round(roads.v.road.km, 2) : null, "km", roads.v.road ? [roads.v.road.cls, roads.v.road.name].filter(Boolean).join("; ") : `none within ${round(roads.v.radiusKm, 1)} km`, osm],
    !!roads.v && ["Nearest railway", roads.v.rail ? round(roads.v.rail.km, 2) : null, "km", roads.v.rail ? roads.v.rail.name ?? "standard gauge" : `none within ${round(roads.v.radiusKm, 1)} km`, osm],
  ]);
  if (!cf || (!pf && covered)) return null;
  const wait = (s: { v: unknown; failed: boolean }, k: string) => (s.failed ? <Row k={k} v="tiles not reachable" /> : !s.v ? <Row k={k} v="…" /> : null);
  return (
    <Card title="Constraints" note={`within ${R} km`} accent={[96, 186, 120]}>
      {covered && (wait(prot, "Protected areas") ?? (prot.v && (
        <>
          <Row k={`Protected, share of ${R} km around`} v={`${(100 * prot.v.share).toFixed(1)} %`} sub={`${prot.v.areas.length} areas`} />
          {prot.v.areas.slice(0, 4).map((a) => (
            <Row key={`${a.src}${a.id ?? a.name}`} k={<span className="truncate">{a.name}</span>} v={a.km === 0 ? "inside" : kmText(a.km)} sub={a.kind ?? undefined} />
          ))}
        </>
      )))}
      {wait(flood, "River flood, 100-year") ?? (flood.v && <Row k="River flood depth, 100-year flood" v={floodLabel(cf, flood.v.cls)} sub={flood.v.map === "eu" ? "Europe, 100 m map" : "world, 1 km map"} />)}
      {covered &&
        (wait(roads, "Nearest major road") ??
          (roads.v && (
            <>
              <Row k="Nearest major road" v={roads.v.road ? kmText(roads.v.road.km) : `none within ${kmText(roads.v.radiusKm)}`} sub={roads.v.road?.cls} />
              <Row k="Nearest railway" v={roads.v.rail ? kmText(roads.v.rail.km) : `none within ${kmText(roads.v.radiusKm)}`} sub={roads.v.rail?.name ?? undefined} />
            </>
          )))}
      <Note>
        {covered ? `Protected areas: ${place.europe ? "Natura 2000 (EEA, end 2024)" : "PAD-US 4.1 (USGS)"} from the map's tiles; the share counts points ${SHARE_STEP_KM} km apart inside ${R} km (computed). ` : "Protected areas, roads and rail: Europe and the US only. "}
        Flood: the deepest of JRC's depth classes in the {fl?.lookup.cell_deg ?? "…"}° cell holding the site (computed from the {fl?.title ?? "…"} map), a hazard map, not a flood
        risk assessment.{covered ? " Roads (motorway, trunk, primary) and standard-gauge rail: OpenStreetMap via Overture Maps, straight-line distance." : ""}
      </Note>
    </Card>
  );
}

// ---------------------------------------------------------------- plants nearby

interface NearPlant {
  name: string | null;
  type: string;
  mw: number;
  d: number;
  at: LonLat;
  color: RGB;
}

function PlantRows({ title, rows }: { title: string; rows: NearPlant[] }) {
  if (!rows.length) return <Row k={title} v="none" />;
  const byType = new Map<string, number>();
  for (const r of rows) byType.set(r.type, (byType.get(r.type) ?? 0) + r.mw);
  const types = [...byType.entries()].sort((a, b) => b[1] - a[1]);
  return (
    <>
      <Row k={title} v={power(sum(rows.map((r) => r.mw)))} sub={`${rows.length.toLocaleString("en-US")} map ${rows.length === 1 ? "point" : "points"}`} />
      <div className={`pb-1 text-right text-[10px] ${muted}`}>{types.slice(0, 4).map(([t, mw]) => `${t} ${power(mw)}`).join(" · ")}</div>
    </>
  );
}

export function SitePlantsCard({ place }: { place: Place }) {
  const { site } = place;
  const R = place.radius;
  const key = areaKey(site, R);
  const us = !!place.state;
  const eu = useFile<PlantsFile>(place.europe ? "plants" : null);
  const usp = useFile<UsPlantsFile>(us ? "usPlants" : null);
  const gem = useFile<WorldPlantsFile>(place.ready && !us ? "worldPlants" : null);
  const data = useMemo(() => {
    if (us) {
      if (!usp) return null;
      const near = within(usp.points, (p) => [p[0], p[1]], site, R);
      const of = (status: string) =>
        near
          .filter((n) => usp.statuses[n.row[3]] === status)
          .map((n) => ({
            name: usp.plants[n.row[6]]?.[0] ?? null,
            type: US_TYPE_LABEL[usp.types[n.row[2]]] ?? usp.types[n.row[2]],
            mw: n.row[4],
            d: n.d,
            at: [n.row[0], n.row[1]] as LonLat,
            color: US_TYPE_COLOR[usp.types[n.row[2]]] ?? GREY,
          }));
      return { operating: of("operating"), construction: of("construction"), planned: of("planned"), source: `EIA-860M (${usp.release}), units of 1 MW and more, net summer capacity` };
    }
    if (!gem || (place.europe && !eu)) return null;
    const near = within(gem.points, (p) => [p[0], p[1]], site, R);
    const of = (status: string) =>
      near
        .filter((n) => gem.statuses[n.row[3]] === status)
        .map((n) => ({
          name: null,
          type: PLANT_TYPE_LABEL[gem.types[n.row[2]]] ?? gem.types[n.row[2]],
          mw: n.row[4],
          d: n.d,
          at: [n.row[0], n.row[1]] as LonLat,
          color: PLANT_TYPE_COLOR[gem.types[n.row[2]]] ?? GREY,
        }));
    if (place.europe && eu) {
      const op = within(eu.plants, (p) => [p[2], p[3]], site, R).map((n) => ({
        name: n.row[5],
        type: FUEL_LABEL[eu.groups[n.row[0]]] ?? eu.groups[n.row[0]],
        mw: n.row[1],
        d: n.d,
        at: [n.row[2], n.row[3]] as LonLat,
        color: FUEL_COLOR[eu.groups[n.row[0]]] ?? GREY,
      }));
      return {
        operating: op,
        construction: of("construction"),
        planned: of("planned"),
        source: "operating: powerplantmatching (units of 20 MW and more); building and planned: Global Energy Monitor's Integrated Power Tracker",
      };
    }
    return { operating: of("operating"), construction: of("construction"), planned: of("planned"), source: "Global Energy Monitor's Integrated Power Tracker (its own size thresholds per type)" };
  }, [us, usp, gem, eu, place.europe, site, R]);
  useEffect(() => {
    if (!data) return;
    const pts = (rows: NearPlant[], status: SitePlant["status"]): SitePlant[] =>
      rows.map((r) => ({ at: r.at, mw: r.mw, type: r.type, color: r.color, name: r.name, status, km: r.d, source: data.source }));
    publishSite(key, { plants: [...pts(data.operating, "operating"), ...pts(data.construction, "construction"), ...pts(data.planned, "planned")] });
  }, [key, data]);
  const plantRows = (status: string, rows: NearPlant[]): ReportRow[] => {
    const byType = new Map<string, number>();
    for (const r of rows) byType.set(r.type, (byType.get(r.type) ?? 0) + r.mw);
    return [
      [`${status} within ${R} km`, round(sum(rows.map((r) => r.mw)), 1), "MW", `${rows.length} map points`, data?.source ?? ""],
      ...[...byType.entries()].sort((a, b) => b[1] - a[1]).map(([t, mw]) => [`${status}, ${t}`, round(mw, 1), "MW", "", data?.source ?? ""] as ReportRow),
    ];
  };
  useReport(
    place,
    "Power plants",
    data
      ? [
          ...plantRows("Operating", data.operating),
          ...plantRows("Under construction", data.construction),
          ...plantRows("Planned", data.planned),
          ...[...data.operating]
            .sort((a, b) => b.mw - a.mw || a.d - b.d)
            .slice(0, 15)
            .map((p) => [p.name ?? p.type, round(p.mw, 1), "MW", `${p.type}; ${round(p.d, 2)} km; operating`, data.source] as ReportRow),
        ]
      : [],
  );
  return (
    <Card title="Power plants" note={`within ${R} km`} accent={[255, 128, 72]}>
      {!data ? (
        <Loading what="plants" />
      ) : (
        <>
          <PlantRows title="Operating" rows={data.operating} />
          <PlantRows title="Under construction" rows={data.construction} />
          <PlantRows title="Planned" rows={data.planned} />
          {data.operating.length > 0 && (
            <div className="mt-1.5 border-t border-white/[0.06] pt-1.5">
              <div className={`pb-0.5 text-[9px] uppercase tracking-[0.16em] ${muted}`}>Largest operating</div>
              {[...data.operating].sort((a, b) => b.mw - a.mw || a.d - b.d).slice(0, 4).map((p, i) => (
                <Row key={i} k={<span className="truncate">{p.name ?? p.type}</span>} v={power(p.mw)} sub={`${p.name ? `${p.type}, ` : ""}${kmText(p.d)}`} />
              ))}
            </div>
          )}
          <Note>Capacity summed over the sites within {R} km (computed). Source: {data.source}.</Note>
        </>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------- prices

export function SitePricesCard({ place }: { place: Place }) {
  const prices = useFile<PricesFile>(place.europe ? "prices" : null);
  const retail = useFile<RetailFile>(place.europe || place.state ? "retail" : null);
  const iso2 = place.iso2;
  const zones = iso2 && prices ? Object.entries(prices.zones).filter(([, z]) => z.country === iso2) : [];
  const business = iso2 && retail ? newestOf(retail, retail.eu.series.elec_business[iso2]) : null;
  const household = iso2 && retail ? newestOf(retail, retail.eu.series.elec_household[iso2]) : null;
  const usRow = place.state && retail?.us ? retail.us.price[place.state.code] : undefined;
  const months = retail?.us?.months ?? [];
  const us = usRow ? { ind: newestMonth(months, usRow.IND), com: newestMonth(months, usRow.COM), res: newestMonth(months, usRow.RES) } : null;
  const period = prices ? `${prices.period[0]} to ${prices.period[1]}` : "";
  const flagged = (r: { period: string; flag: string | null }) => r.period + (r.flag ? ` (${r.flag})` : "");
  useReport(place, "Prices", [
    ...zones.flatMap(
      ([id, z]) =>
        [
          [`Day-ahead ${id}, 12-month average`, z.mean, "EUR/MWh", period, "ENTSO-E day-ahead (prices.json)"],
          [`Day-ahead ${id}, hours below zero`, z.negative_hours, "hours", period, "ENTSO-E day-ahead (prices.json)"],
        ] as ReportRow[],
    ),
    business && ["Electricity, businesses (band IC), all taxes", business.v, "EUR/kWh", flagged(business), "Eurostat (retail.json)"],
    household && ["Electricity, households (band DC), all taxes", household.v, "EUR/kWh", flagged(household), "Eurostat (retail.json)"],
    us?.ind && ["Retail price, industrial", us.ind.v, "US cents/kWh", us.ind.month, "EIA (retail.json)"],
    us?.com && ["Retail price, commercial", us.com.v, "US cents/kWh", us.com.month, "EIA (retail.json)"],
    us?.res && ["Retail price, residential", us.res.v, "US cents/kWh", us.res.month, "EIA (retail.json)"],
  ]);
  if (!place.europe && !place.state) return null;
  if (!retail)
    return (
      <Card title="Prices" accent={[255, 196, 90]}>
        <Loading what="prices" />
      </Card>
    );
  return (
    <Card title="Prices" note={place.state ? "EIA" : "ENTSO-E, Eurostat"} accent={[255, 196, 90]}>
      {place.europe &&
        (prices ? (
          zones.length ? (
            <>
              {zones.map(([id, z]) => (
                <Row key={id} k={`Day-ahead ${id}, 12-month average`} v={`€${z.mean.toFixed(2)}/MWh`} sub={`${z.negative_hours.toLocaleString("en-US")} h below zero`} />
              ))}
              <Note>
                ENTSO-E day-ahead prices, {prices.period[0]} to {prices.period[1]} (average and hours below zero computed).
                {zones.length > 1 ? " The country has several bidding zones; the map's files hold no zone outlines, so all are listed." : ""}
              </Note>
            </>
          ) : (
            <Row k="Day-ahead prices" v="no zone in the file" />
          )
        ) : (
          <Loading what="prices" />
        ))}
      {business && <Row k="Electricity, businesses (band IC)" v={`${euroCents(business.v)}/kWh`} sub={business.period} />}
      {household && <Row k="Electricity, households (band DC)" v={`${euroCents(household.v)}/kWh`} sub={household.period} />}
      {(business || household) && <Note>Eurostat, all taxes included, newest half-year.</Note>}
      {us && (
        <>
          {us.ind && <Row k="Industrial" v={`${usCents(us.ind.v)}/kWh`} sub={us.ind.month} />}
          {us.com && <Row k="Commercial" v={`${usCents(us.com.v)}/kWh`} sub={us.com.month} />}
          {us.res && <Row k="Residential" v={`${usCents(us.res.v)}/kWh`} sub={us.res.month} />}
          <Note>EIA's average retail price in {place.state?.name}, newest month.</Note>
        </>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------- risk

export function SiteRiskCard({ place }: { place: Place }) {
  const { site } = place;
  const water = useFile<WaterFile>(place.ready ? "water" : null);
  const counties = useFile<UsCountiesFile>(place.state ? "usCounties" : null);
  const outages = useFile<UsOutagesFile>(place.state ? "usOutages" : null);
  const basin = useMemo(() => water?.basins.find((b) => inFlatPolygons(site, b.polygons)) ?? null, [water, site]);
  const county = useMemo(() => counties?.counties.find((c) => inFlatPolygons(site, c.polygons)) ?? null, [counties, site]);
  const ny = outages ? newestYear(outages) : null;
  const hours = county && outages && ny ? outages.counties[county.code]?.[ny.k] : null;
  useReport(place, "Risk", [
    ...(water && basin
      ? water.order.map(
          (ind, i) =>
            [
              water.indicators[ind]?.name ?? ind,
              water.indicators[ind]?.labels[String(basin.c[i] ?? -9999)] ?? "No Data",
              "WRI category",
              `category ${basin.c[i] ?? "none"}; HydroBASINS ${basin.id}`,
              "WRI Aqueduct 4.0, baseline",
            ] as ReportRow,
        )
      : []),
    !!county && !!ny && [`Customer-hours without power, ${ny.year}`, hours ?? null, "customer-hours", county.name, "ORNL EAGLE-I (sum over the year, computed)"],
    !!county && !!outages && outages.customers[county.code] != null && ["Customers in the county", outages.customers[county.code], "customers", county.name, "ORNL modelled customers"],
  ]);
  return (
    <Card title="Risk" accent={[255, 153, 0]}>
      {!water ? (
        <Loading what="water risk" />
      ) : basin ? (
        <>
          {water.order.map((ind, i) => (
            <Row key={ind} k={water.indicators[ind]?.name ?? ind} v={water.indicators[ind]?.labels[String(basin.c[i] ?? -9999)] ?? "No Data"} />
          ))}
          <Note>WRI Aqueduct 4.0, baseline, the river basin holding the site (HydroBASINS {basin.id}).</Note>
        </>
      ) : (
        <Row k="Water risk" v="no basin outline here" />
      )}
      {place.state &&
        (county && outages && ny ? (
          <>
            <Row k={`Customer-hours without power, ${ny.year}`} v={hours != null ? hoursText(hours) : "–"} sub={county.name} />
            {outages.customers[county.code] != null && <Row k="Customers in the county" v={outages.customers[county.code].toLocaleString("en-US")} sub="ORNL model" />}
            <Note>ORNL EAGLE-I outage records summed over the year (computed), the county holding the site.</Note>
          </>
        ) : (
          <Loading what="outages" />
        ))}
    </Card>
  );
}

// ---------------------------------------------------------------- the resource atlases

/** PVOUT and wind speed at 100 m in the site's 0.1 degree cell (one range request each). */
function useAtlasAt(site: LonLat, on: boolean) {
  const atlas = useFile<AtlasFile>(on ? "atlas" : null);
  const [got, setGot] = useState<{ key: string; pvout: number | null | undefined; wind: number | null | undefined }>({ key: "", pvout: undefined, wind: undefined });
  const key = siteKey(site);
  useEffect(() => {
    if (!atlas) return;
    let live = true;
    const [lon, lat] = site;
    // a lookup that fails (file not published yet) shows nothing rather than a guess
    const read = (k: "pvout" | "wind") => atlasValue(atlas[k], lon, lat).catch(() => undefined);
    Promise.all([read("pvout"), read("wind")]).then(([pvout, wind]) => live && setGot({ key, pvout, wind }));
    return () => {
      live = false;
    };
  }, [atlas, key]); // eslint-disable-line react-hooks/exhaustive-deps
  return { atlas, ...(got.key === key ? got : { pvout: undefined, wind: undefined }) };
}

/** People within the site radius (GHSL 2025 on the 0.1 degree grid); undefined until read or when the grid is missing. */
function usePeopleAt(site: LonLat, on: boolean, R: number) {
  const [got, setGot] = useState<{ key: string; v?: { people: number; cells: number } }>({ key: "" });
  const key = areaKey(site, R);
  useEffect(() => {
    if (!on) return;
    let live = true;
    peopleWithin(site[0], site[1], R)
      .then((v) => live && setGot({ key, v }))
      .catch(() => live && setGot({ key }));
    return () => {
      live = false;
    };
  }, [key, on]); // eslint-disable-line react-hooks/exhaustive-deps
  return got.key === key ? got.v : undefined;
}

// ---------------------------------------------------------------- the country's power, data centres

export function SiteCountryCard({ place }: { place: Place }) {
  const t = useFile<TransitionFile>(place.iso3 ? "transition" : null);
  const dc = useFile<DataCentresFile>(place.ready ? "datacentres" : null);
  const R = place.radius;
  const near = useMemo(() => within(dc?.points, (p) => [p[0], p[1]], place.site, R), [dc, place.site, R]);
  const key = areaKey(place.site, R);
  useEffect(() => publishSite(key, { dcs: near.map((n) => ({ at: [n.row[0], n.row[1]] as LonLat, name: n.row[2], operator: n.row[3], km: n.d })) }), [key, near]);
  const e = place.iso3 ? t?.entities[place.iso3] : undefined;
  const k = e && t ? [...t.years.keys()].reverse().find((i) => e.renewables[i] != null) : undefined;
  const osm = "OpenStreetMap (datacentres.json)";
  const at = useAtlasAt(place.site, place.ready);
  const people = usePeopleAt(place.site, place.ready, R);
  const cell = at.atlas?.pvout.lookup.cell_deg ?? 0.1;
  const atlasNote = `mean over the ${cell}° cell (computed)`;
  useReport(place, "Around it", [
    at.pvout != null && ["PV output potential (PVOUT)", round(at.pvout, 3), "kWh/kWp per day", `${atlasNote}; x365 = ${Math.round(at.pvout * 365)} kWh/kWp a year`, at.atlas?.pvout.source ?? "Global Solar Atlas"],
    !!people && [`People within ${R} km`, people.people, "people", `2025; sum of the ${people.cells} cells of ${POP_CELL}° whose centre is within ${R} km (computed)`, "GHSL GHS-POP R2023A (JRC, CC BY 4.0)"],
    at.wind != null && ["Mean wind speed at 100 m", round(at.wind, 2), "m/s", atlasNote, at.atlas?.wind.source ?? "Global Wind Atlas"],
    !!e && !!t && k != null && [`Renewable share of generation, ${place.iso2 ?? place.iso3}`, e.renewables[k], "%", t.years[k], "Ember yearly electricity data"],
    !!e && !!t && k != null && e.intensity[k] != null && ["Carbon intensity of generation", e.intensity[k], "gCO2/kWh", t.years[k], "Ember yearly electricity data"],
    !!dc && [`Data centres within ${R} km`, near.length, "count", "mapped sites", osm],
    ...(dc ? near.slice(0, 10).map((n) => [n.row[2] ?? n.row[3] ?? "unnamed", round(n.d, 2), "km", n.row[3] ?? "", osm] as ReportRow) : []),
  ]);
  return (
    <Card title="Around it" accent={[150, 160, 180]}>
      {at.pvout != null && (
        <Row
          k="Solar resource (PVOUT)"
          v={`${Math.round(at.pvout * 365).toLocaleString("en-US")} kWh/kWp a year`}
          sub={`${at.pvout.toFixed(2)} a day`}
        />
      )}
      {at.wind != null && <Row k="Mean wind speed at 100 m" v={`${at.wind.toFixed(1)} m/s`} />}
      {people && <Row k={`People within ${R} km`} v={people.people.toLocaleString("en-US")} sub={`GHSL 2025, ${POP_CELL}° cells`} />}
      {e && t && k != null && (
        <>
          <Row k={`Renewable share of generation, ${place.iso2 ?? place.iso3}`} v={`${e.renewables[k]?.toFixed(1)} %`} sub={t.years[k]} />
          {e.intensity[k] != null && <Row k="Carbon intensity of generation" v={`${Math.round(e.intensity[k] as number)} g/kWh`} sub={t.years[k]} />}
        </>
      )}
      {dc && (
        <>
          <Row k={`Data centres within ${R} km`} v={near.length.toLocaleString("en-US")} />
          {near.slice(0, 3).map((n, i) => (
            <Row key={i} k={<span className="truncate">{n.row[2] ?? n.row[3] ?? "unnamed"}</span>} v={kmText(n.d)} sub={n.row[2] && n.row[3] ? n.row[3] : undefined} />
          ))}
        </>
      )}
      <Note>
        {at.pvout != null || at.wind != null
          ? `Solar and wind: Global Solar Atlas (Solargis) and Global Wind Atlas (DTU), ${atlasNote}; a year of PV = the daily total x 365, as the atlas gives it. `
          : ""}
        Country figures: Ember's yearly data (newest year with a value). Data centres: mapped in OpenStreetMap, a subset that follows mapping effort.</Note>
    </Card>
  );
}

/** The area: a radius around the point; everything inside it is summed here and drawn on the map. */
function SiteArea({ place }: { place: Place }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5 px-1">
      <span className={`mr-1 text-[9.5px] uppercase tracking-[0.16em] ${muted}`}>Area</span>
      {SITE_RADII.map((r) => (
        <button
          key={r}
          onClick={() => actions.setSiteRadius(r)}
          className={`rounded-md border px-2 py-0.5 text-[11px] tabular-nums ${
            place.radius === r ? "border-white/30 bg-white/15 text-slate-100" : "border-white/10 text-slate-300 hover:bg-white/[0.07]"
          }`}
        >
          {r} km
        </button>
      ))}
    </div>
  );
}

export function SiteCards({ place }: { place: Place }) {
  if (!place.ready) return <Loading what="the outlines" />;
  return (
    <>
      <SiteArea place={place} />
      <SiteGridCard place={place} />
      <SiteCapacityCard place={place} />
      <SiteConstraintsCard place={place} />
      <SitePlantsCard place={place} />
      <SitePricesCard place={place} />
      <SiteRiskCard place={place} />
      <SiteCountryCard place={place} />
      <SiteDownload place={place} />
      <p className={`px-1 text-[10px] leading-snug ${muted}`}>
        A first screen from public data, not a connection study. The map shows what lies inside the area: high-voltage lines by voltage, substations, plants by fuel (rings:
        building or planned), data centres and capacity sites. Right-click another place to move the area; the link in the address bar opens this analysis.
      </p>
    </>
  );
}
