// What consumers pay (scripts/fetch_retail_prices.py): Eurostat's half-yearly prices per
// consumption band and EIA's monthly average price per US state. Values are the sources';
// the tax split is the difference of Eurostat's three tax levels (computed, said on the card).

import { Card } from "./CountryCards";
import { RETAIL_STOPS, SERIES_LABEL, FLAG_TEXT, euroCents, newestMonth, newestOf, usCents, type RetailFile, type RetailSeries } from "../lib/retail";
import { rgbCss } from "../lib/theme";
import { stopColor } from "../app/colors";

const muted = "text-[#8d94a1]";
const PART_COLOR = ["rgb(120,170,210)", "rgb(214,170,96)", "rgb(150,150,164)"];
const PARTS = ["energy and network", "taxes and levies", "VAT"];
const SERIES: RetailSeries[] = ["elec_household", "elec_business", "gas_household", "gas_business"];

/** A country's four retail prices, newest half-year, with the tax split and the household line. */
export function RetailCountryCard({ f, iso, wholesale }: { f: RetailFile; iso: string; wholesale?: { eur_mwh: number; period: string } }) {
  const rows = SERIES.map((s) => ({ s, row: f.eu.series[s][iso] })).filter((r) => r.row);
  if (!rows.length) return null;
  const hh = f.eu.series.elec_household[iso];
  const line = hh?.I_TAX ?? [];
  const top = Math.max(...line.map((v) => v ?? 0), 0.01);
  const gb = iso === "GB" ? f.eu.gb : undefined;
  return (
    <Card title="What consumers pay" note={gb ? "DESNZ · half-yearly" : "Eurostat · half-yearly"}>
      <div className="space-y-2.5">
        {rows.map(({ s, row }) => {
          const n = newestOf(f, row);
          if (!n) return null;
          // the three tax levels as parts of the price (differences, computed)
          const base = row.X_TAX[n.k];
          const levies = row.X_VAT[n.k] != null && base != null ? row.X_VAT[n.k]! - base : null;
          const vat = row.X_VAT[n.k] != null ? n.v - row.X_VAT[n.k]! : null;
          const parts = [base, levies, vat];
          const split = parts.every((p) => p != null && p >= 0);
          return (
            <div key={s} className="text-[11px]">
              <div className="flex justify-between gap-2">
                <span className="text-slate-200">{SERIES_LABEL[s].title}</span>
                <span className="tabular-nums text-slate-50">
                  {euroCents(n.v)}/kWh <span className={muted}>{n.period}{n.flag ? `, ${FLAG_TEXT[n.flag] ?? n.flag}` : ""}</span>
                </span>
              </div>
              {split && (
                <div className="mt-0.5 flex h-[6px] overflow-hidden rounded-sm bg-white/[0.05]">
                  {parts.map((p, i) => (
                    <div key={i} title={`${PARTS[i]} ${euroCents(p)}`} style={{ width: `${(100 * (p as number)) / n.v}%`, background: PART_COLOR[i] }} />
                  ))}
                </div>
              )}
              <div className={`text-[10px] ${muted}`}>{SERIES_LABEL[s].band}</div>
            </div>
          );
        })}
      </div>
      <div className={`mt-2 flex flex-wrap gap-x-3 text-[10px] ${muted}`}>
        {PARTS.map((p, i) => (
          <span key={p} className="inline-flex items-center gap-1">
            <span className="h-1.5 w-2.5 rounded-sm" style={{ background: PART_COLOR[i] }} />
            {p}
          </span>
        ))}
      </div>
      {line.some((v) => v != null) && (
        <>
          <div className={`mt-3 mb-1 text-[9px] uppercase tracking-[0.14em] ${muted}`}>Households, electricity, last {line.length} half-years</div>
          <div className="flex h-12 items-end gap-[3px]">
            {line.map((v, i) => (
              <div key={f.eu.periods[i]} className="flex-1" title={`${f.eu.periods[i]}: ${euroCents(v)}`}>
                <div className="rounded-t-sm" style={{ height: `${v == null ? 0 : (100 * v) / top}%`, background: rgbCss(stopColor(RETAIL_STOPS, v == null ? null : v * 100) ?? [60, 60, 70]) }} />
              </div>
            ))}
          </div>
          <div className={`flex justify-between text-[9.5px] ${muted}`}>
            <span>{f.eu.periods[0]}</span>
            <span>{f.eu.periods[f.eu.periods.length - 1]}</span>
          </div>
        </>
      )}
      <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
        All taxes and levies included; the bar splits each price by Eurostat's three tax levels (without taxes; without VAT and recoverable taxes; all taxes), differences
        computed. Business prices are usually paid without VAT.
        {gb ? ` UK figures: ${gb.source}, in pence per kWh; shown in euros (${gb.conversion}). Businesses' electricity: ${gb.not_published.elec_business ?? "not published"}.` : ""}
        {wholesale ? ` Wholesale for comparison: day-ahead average ${wholesale.eur_mwh.toFixed(2)} €/MWh = ${(wholesale.eur_mwh / 10).toFixed(2)} c€/kWh over ${wholesale.period} (ENTSO-E, divided by 10).` : ""}
      </div>
    </Card>
  );
}

/** Europe: countries ranked by what households pay for electricity, newest half-year. */
export function RetailRankingCard({ f, onPick }: { f: RetailFile; onPick: (iso: string) => void }) {
  const rows = Object.entries(f.eu.series.elec_household)
    .map(([iso, row]) => ({ iso, n: newestOf(f, row) }))
    .filter((r): r is { iso: string; n: NonNullable<ReturnType<typeof newestOf>> } => r.n != null && r.iso !== "EU")
    .sort((a, b) => b.n.v - a.n.v);
  const eu = newestOf(f, f.eu.series.elec_household.EU);
  const top = rows[0]?.n.v || 1;
  return (
    <Card title="What households pay" note={`Eurostat · ${f.eu.periods[f.eu.periods.length - 1]}`}>
      {eu && (
        <div className="text-[22px] font-light text-slate-50">
          {euroCents(eu.v)}/kWh <span className={`text-[11px] ${muted}`}>EU average, {eu.period} (Eurostat's EU27 figure)</span>
        </div>
      )}
      <div className="mt-2 space-y-[3px]">
        {rows.map((r) => (
          <button key={r.iso} onClick={() => onPick(r.iso)} className="flex w-full items-center gap-2 text-[11px] tabular-nums hover:opacity-80">
            <span className="w-6 text-left text-slate-300">{r.iso}</span>
            <span className="relative h-[6px] flex-1 overflow-hidden rounded-sm bg-white/[0.05]">
              <span className="absolute inset-y-0 left-0 rounded-sm" style={{ width: `${(100 * r.n.v) / top}%`, background: rgbCss(stopColor(RETAIL_STOPS, r.n.v * 100) ?? [60, 60, 70]) }} />
            </span>
            <span className="w-[86px] text-right text-slate-100">
              {euroCents(r.n.v)}
              {r.n.period !== f.eu.periods[f.eu.periods.length - 1] ? <span className={muted}> ·{r.n.period.slice(2)}</span> : null}
            </span>
          </button>
        ))}
      </div>
      <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
        Electricity, households, band DC (2,500–4,999 kWh a year), all taxes and levies included; each country's newest half-year (an older one is marked). Click a country for
        its four prices.{f.eu.gb ? " GB: DESNZ's figure in the same band, converted at the ECB's half-year average rate." : ""}
      </div>
    </Card>
  );
}

/** US: states ranked by the average residential price, newest month, with the US figure. */
export function UsRetailCard({ f, onPick }: { f: RetailFile; onPick?: (code: string) => void }) {
  const us = f.us;
  if (!us) return null;
  const rows = Object.entries(us.price)
    .filter(([code]) => code !== "US")
    .map(([code, p]) => ({ code, n: newestMonth(us.months, p.RES), p }))
    .filter((r): r is typeof r & { n: NonNullable<typeof r.n> } => r.n != null)
    .sort((a, b) => b.n.v - a.n.v);
  const nat = newestMonth(us.months, us.price.US?.RES);
  const top = rows[0]?.n.v || 1;
  return (
    <Card title="What households pay" note={`EIA · ${nat?.month ?? us.months[us.months.length - 1]}`}>
      {nat && (
        <div className="text-[22px] font-light text-slate-50">
          {usCents(nat.v)}/kWh <span className={`text-[11px] ${muted}`}>US average, residential (EIA)</span>
        </div>
      )}
      <div className="mt-2 space-y-[3px]">
        {rows.map((r) => (
          <button key={r.code} onClick={() => onPick?.(r.code)} className="flex w-full items-center gap-2 text-[11px] tabular-nums hover:opacity-80">
            <span className="w-6 text-left text-slate-300">{r.code}</span>
            <span className="relative h-[6px] flex-1 overflow-hidden rounded-sm bg-white/[0.05]">
              <span className="absolute inset-y-0 left-0 rounded-sm" style={{ width: `${(100 * r.n.v) / top}%`, background: rgbCss(stopColor(RETAIL_STOPS, r.n.v) ?? [60, 60, 70]) }} />
            </span>
            <span className="w-[56px] text-right text-slate-100">{usCents(r.n.v)}</span>
          </button>
        ))}
      </div>
      <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
        Average residential price, US cents per kWh: revenue ÷ sales as EIA publishes it per state and month (Forms EIA-861, EIA-861M). Colour the map by "Household electricity price" to
        see the states.
      </div>
    </Card>
  );
}
