import GridControl, { type GridLayers } from "./GridControl";

interface Props {
  basemap: "dark" | "satellite";
  setBasemap: (b: "dark" | "satellite") => void;
  grid: GridLayers;
  setGrid: (g: GridLayers) => void;
  onGridMenuOpenChange?: (open: boolean) => void;
}

// Floating equivalent of the old persistent top bar — just the two map-level
// controls (basemap, grid layers), as a small pill cluster over the map.
export default function MapControls({ basemap, setBasemap, grid, setGrid, onGridMenuOpenChange }: Props) {
  return (
    <div className="flex items-center gap-2 rounded-md border border-line bg-ink-950/80 p-1 shadow-xl backdrop-blur">
      <div className="flex items-center divide-x divide-line overflow-hidden rounded text-xs">
        {(["dark", "satellite"] as const).map((b) => (
          <button
            key={b}
            onClick={() => setBasemap(b)}
            className={`px-2 py-1 capitalize transition ${
              basemap === b ? "bg-accent/15 text-accent-300" : "text-dim hover:text-slate-200"
            }`}
          >
            {b}
          </button>
        ))}
      </div>
      <GridControl layers={grid} setLayers={setGrid} onOpenChange={onGridMenuOpenChange} />
    </div>
  );
}
