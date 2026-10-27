// A dataset's style before one is chosen (map/styleLayers.ts): its own drawing, but the facility
// emissions, summed into hexagons at every scale (the same picture for Europe's and the US files).

import type { Style } from "./maps";

export const DEFAULT_STYLE: Record<string, Style> = { emitters: "hex" };
/** How a dataset is drawn: the chosen style, else its default, else its own drawing (undefined). */
export const styleOf = (styles: Record<string, Style>, dataset: string): Style | undefined => styles[dataset] ?? DEFAULT_STYLE[dataset];
