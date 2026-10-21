// US gas pipelines (EIA, scripts/fetch_us_gas.py): thin calm lines, interstate a little brighter.

import type { Layer } from "@deck.gl/core";
import { PathLayer } from "@deck.gl/layers";

import { US_PIPE_COLOR, type UsGasPipesFile } from "../lib/usGas";
import type { Frame } from "./build";
import { memo } from "./memo";

/** [path, line index] */
type Seg = [[number, number][], number];

export function usGasLayers(fr: Frame): Layer[] {
  const f = fr.layers.gasPipesUS ? (fr.files.usGasPipes as UsGasPipesFile | undefined) : undefined;
  if (!f) return [];
  const data = memo("usGasSegs", [f], () => f.lines.flatMap((l, k) => l[0].map((p): Seg => [p, k])));
  return [
    new PathLayer<Seg>({
      id: "us-gas-pipes",
      data,
      getPath: (s) => s[0],
      getColor: (s) => [...US_PIPE_COLOR, /interstate/i.test(f.lines[s[1]][1] ?? "") ? 170 : 90],
      getWidth: (s) => (/interstate/i.test(f.lines[s[1]][1] ?? "") ? 1.4 : 0.8),
      widthUnits: "pixels",
      pickable: true,
      autoHighlight: true,
      highlightColor: [255, 255, 255, 140],
    }),
  ];
}
