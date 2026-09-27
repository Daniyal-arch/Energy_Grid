export const mw = (v: number | null | undefined): string =>
  v == null ? "—" : v >= 1000 ? `${(v / 1000).toFixed(1)} GW` : `${v.toFixed(v < 10 ? 1 : 0)} MW`;

export const num = (v: number): string => v.toLocaleString("en-US");

export const fmtDate = (iso: string | null): string =>
  iso ? new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }) : "—";

// Plain-language labels for remote-sensing metrics.
export const METRIC_META: Record<string, { label: string; help: string; color: string }> = {
  ndvi: {
    label: "Vegetation (NDVI)",
    help: "Greenness. Falls when land is cleared for construction.",
    color: "#34d399",
  },
  bsi: {
    label: "Bare soil (BSI)",
    help: "Exposed earth. Rises during clearing and earthworks.",
    color: "#ef7d3a",
  },
  vh_db: {
    label: "Radar structures (VH dB)",
    help: "Surface roughness. Rises as panels and buildings go up.",
    color: "#38bdf8",
  },
};
