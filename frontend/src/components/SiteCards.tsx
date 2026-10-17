// "Check a site": the cards of the site panel (ui/Panel.tsx). Every card reads the map's own
// files and names its source; distances, point-in-outline tests and sums within
// SITE_RADIUS_KM are computed in lib/site.ts. A card with nothing for the place stays away.

import { useEffect, useMemo, type ReactNode } from "react";

import { useFile } from "../app/data";
import type { CountriesFile, GridFile, PlantsFile, WorldFile } from "../app/types";
import { gbSiteTotals, type ConnectFile } from "../lib/connect";
import { FUEL_LABEL, power } from "../lib/energy";
import type { PricesFile } from "../lib/prices";
import { euroCents, newestMonth, newestOf, usCents, type RetailFile } from "../lib/retail";
import { hoursText, newestYear, type UsCountiesFile, type UsOutagesFile, type WaterFile } from "../lib/risk";
import { SITE_RADIUS_KM, inFlatPolygons, inGeoJsonPolygons, inPairPolygons, km, kmText, searchSiteLines, siteKey, useSiteLines, type LineSearch, type LonLat } from "../lib/site";
import { ISO3, type TransitionFile } from "../lib/transition";
import { US_TYPE_LABEL, gwText, type UsPlantsFile, type UsQueueFile, type UsQueuesLiveFile, type UsState, type UsStatesFile } from "../lib/us";
import type { DataCentresFile } from "../lib/world";
import { PLANT_TYPE_LABEL, type WorldPlantsFile } from "../lib/worldPlants";
import { Card } from "./CountryCards";

const muted = "text-[#8d94a1]";
const R = SITE_RADIUS_KM;

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
}

/** Which country (and US state) holds the site: point in the map's own outlines. */
export function usePlace(site: LonLat): Place {
  const countries = useFile<CountriesFile>("countries");
  const world = useFile<WorldFile>("world");
  const [lon, lat] = site;
  const eu = useMemo(() => countries?.countries.find((c) => inFlatPolygons([lon, lat], c.polygons)) ?? null, [countries, lon, lat]);
  const w = useMemo(() => (eu || !world ? null : (world.features.find((f) => inGeoJsonPolygons([lon, lat], f.geometry.coordinates)) ?? null)), [eu, world, lon, lat]);
  const iso3 = eu ? (ISO3[eu.iso] ?? null) : (w?.properties.iso3 ?? null);
  const states = useFile<UsStatesFile>(iso3 === "USA" ? "usStates" : null);
  const state = useMemo(() => states?.states.find((s) => inFlatPolygons([lon, lat], s.polygons)) ?? null, [states, lon, lat]);
  return {
    site,
    iso2: eu?.iso ?? null,
    iso3,
    name: state ? `${state.name}, United States` : (eu?.name ?? w?.properties.name ?? null),
    europe: !!eu,
    state,
    ready: !!countries && (!!eu || !!world) && (iso3 !== "USA" || !!states),
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

/** Records within the radius, nearest first. */
function within<T>(rows: T[] | undefined, at: (r: T) => LonLat, site: LonLat): { row: T; d: number }[] {
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
  const key = siteKey(site);
  const inUs = !!place.state;
  useEffect(() => {
    searchSiteLines("world", site);
    if (inUs) searchSiteLines("us", site);
  }, [site, inUs]);
  const world = useSiteLines((s) => (s.world.key === key ? s.world : null));
  const us = useSiteLines((s) => (s.us.key === key ? s.us : null));
  const grid = useFile<GridFile>(place.europe ? "grid" : null);
  const subs = useMemo(() => within(grid?.substations, (s) => [s[1], s[2]], site), [grid, site]);
  return (
    <Card title="Grid" note={`straight-line distance`} accent={[236, 178, 120]}>
      {inUs && lineRow("Nearest line, 100 kV or more", us?.result ?? null, !!us?.failed, (s) => s.nearest)}
      {lineRow("Nearest line, 220 kV or more", world?.result ?? null, !!world?.failed, (s) => s.nearest)}
      {lineRow("Nearest line, 345 kV or more", world?.result ?? null, !!world?.failed, (s) => s.ehv)}
      {place.europe &&
        (grid ? (
          <>
            <Row k="Nearest substation, 220 kV or more" v={subs[0] ? kmText(subs[0].d) : `none within ${R} km`} sub={subs[0] ? `${subs[0].row[0]} kV` : undefined} />
            <Row k={`Substations within ${R} km`} v={subs.length.toLocaleString("en-US")} />
          </>
        ) : (
          <Loading what="substations" />
        ))}
      <Note>
        Distance in a straight line to the line's mapped course. Lines: OpenStreetMap (ODbL) via Overture Maps, the map's own tiles ({inUs ? "US lines from 100 kV, " : ""}
        lines from 220 kV worldwide; simplified by about 0.1 km), voltage as tagged.{place.europe ? " Substations: PyPSA-Eur's network from OpenStreetMap." : ""} Projects connect at
        substations, where the operator has room: a line nearby is not a connection offer.
      </Note>
    </Card>
  );
}

// ---------------------------------------------------------------- room to connect

export function SiteCapacityCard({ place }: { place: Place }) {
  const { site } = place;
  const connect = useFile<ConnectFile>(place.iso2 === "GB" || place.iso2 === "NL" ? "connect" : null);
  const queue = useFile<UsQueueFile>(place.state ? "usQueue" : null);
  const live = useFile<UsQueuesLiveFile>(place.state ? "usQueuesLive" : null);
  const nl = useMemo(() => (place.iso2 === "NL" && connect ? (connect.nl.areas.find((a) => inPairPolygons(site, a.polygons)) ?? null) : null), [connect, place.iso2, site]);
  const gb = useMemo(
    () => (place.iso2 === "GB" && connect ? within(gbSiteTotals(connect.gb), (t) => [t.site[1] as number, t.site[2] as number], site) : []),
    [connect, place.iso2, site],
  );
  const code = place.state?.code;
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
        <Note>
          Transmission Entry Capacity contracted and not yet connected, summed per site (computed); sites placed by NESO's GSP lookup, those without a position left out.
          Contracts, not spare capacity.
        </Note>
      </Card>
    );
  }
  if (code && queue) {
    const st = queue.states[code];
    // a hybrid counts under each of its types with its full capacity: types, not a total
    const mine = Object.entries(live?.markets ?? {})
      .map(([m, v]) => ({ m, types: Object.entries(v.by_state?.[code] ?? {}).sort((a, b) => b[1] - a[1]) }))
      .filter((x) => x.types.length > 0)
      .sort((a, b) => b.types[0][1] - a.types[0][1]);
    const types = st ? queue.types.map((t, i) => ({ t, mw: st.active[i] })).filter((x) => x.mw > 0).sort((a, b) => b.mw - a.mw) : [];
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

// ---------------------------------------------------------------- plants nearby

interface NearPlant {
  name: string | null;
  type: string;
  mw: number;
  d: number;
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
  const us = !!place.state;
  const eu = useFile<PlantsFile>(place.europe ? "plants" : null);
  const usp = useFile<UsPlantsFile>(us ? "usPlants" : null);
  const gem = useFile<WorldPlantsFile>(place.ready && !us ? "worldPlants" : null);
  const data = useMemo(() => {
    if (us) {
      if (!usp) return null;
      const near = within(usp.points, (p) => [p[0], p[1]], site);
      const of = (status: string) =>
        near
          .filter((n) => usp.statuses[n.row[3]] === status)
          .map((n) => ({ name: usp.plants[n.row[6]]?.[0] ?? null, type: US_TYPE_LABEL[usp.types[n.row[2]]] ?? usp.types[n.row[2]], mw: n.row[4], d: n.d }));
      return { operating: of("operating"), construction: of("construction"), planned: of("planned"), source: `EIA-860M (${usp.release}), units of 1 MW and more, net summer capacity` };
    }
    if (!gem || (place.europe && !eu)) return null;
    const near = within(gem.points, (p) => [p[0], p[1]], site);
    const of = (status: string) =>
      near.filter((n) => gem.statuses[n.row[3]] === status).map((n) => ({ name: null, type: PLANT_TYPE_LABEL[gem.types[n.row[2]]] ?? gem.types[n.row[2]], mw: n.row[4], d: n.d }));
    if (place.europe && eu) {
      const op = within(eu.plants, (p) => [p[2], p[3]], site).map((n) => ({ name: n.row[5], type: FUEL_LABEL[eu.groups[n.row[0]]] ?? eu.groups[n.row[0]], mw: n.row[1], d: n.d }));
      return {
        operating: op,
        construction: of("construction"),
        planned: of("planned"),
        source: "operating: powerplantmatching (units of 20 MW and more); building and planned: Global Energy Monitor's Integrated Power Tracker",
      };
    }
    return { operating: of("operating"), construction: of("construction"), planned: of("planned"), source: "Global Energy Monitor's Integrated Power Tracker (its own size thresholds per type)" };
  }, [us, usp, gem, eu, place.europe, site]);
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
  if (!place.europe && !place.state) return null;
  const iso2 = place.iso2;
  const zones = iso2 && prices ? Object.entries(prices.zones).filter(([, z]) => z.country === iso2) : [];
  const business = iso2 && retail ? newestOf(retail, retail.eu.series.elec_business[iso2]) : null;
  const household = iso2 && retail ? newestOf(retail, retail.eu.series.elec_household[iso2]) : null;
  const usRow = place.state && retail?.us ? retail.us.price[place.state.code] : undefined;
  const months = retail?.us?.months ?? [];
  const us = usRow ? { ind: newestMonth(months, usRow.IND), com: newestMonth(months, usRow.COM), res: newestMonth(months, usRow.RES) } : null;
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

// ---------------------------------------------------------------- the country's power, data centres

export function SiteCountryCard({ place }: { place: Place }) {
  const t = useFile<TransitionFile>(place.iso3 ? "transition" : null);
  const dc = useFile<DataCentresFile>(place.ready ? "datacentres" : null);
  const near = useMemo(() => within(dc?.points, (p) => [p[0], p[1]], place.site), [dc, place.site]);
  const e = place.iso3 ? t?.entities[place.iso3] : undefined;
  const k = e && t ? [...t.years.keys()].reverse().find((i) => e.renewables[i] != null) : undefined;
  return (
    <Card title="Around it" accent={[150, 160, 180]}>
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
      <Note>Country figures: Ember's yearly data (newest year with a value). Data centres: mapped in OpenStreetMap, a subset that follows mapping effort.</Note>
    </Card>
  );
}

export function SiteCards({ place }: { place: Place }) {
  if (!place.ready) return <Loading what="the outlines" />;
  return (
    <>
      <SiteGridCard place={place} />
      <SiteCapacityCard place={place} />
      <SitePlantsCard place={place} />
      <SitePricesCard place={place} />
      <SiteRiskCard place={place} />
      <SiteCountryCard place={place} />
      <p className={`px-1 text-[10px] leading-snug ${muted}`}>
        A first screen from public data, not a connection study. Right-click another place (or use Check a site) to compare; the link in the address bar opens this site.
      </p>
    </>
  );
}
