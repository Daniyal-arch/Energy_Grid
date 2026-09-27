// GPU-animated flow rendering for network lines (power grid, cross-border links).
//
// FlowPathLayer draws each path as ONE soft glowing line with round dots gliding
// along it. Line core, halo and dots are all computed in the fragment shader from
// a single `phase` uniform, so animating is one uniform update per frame: no
// per-frame particle arrays and no attribute re-uploads (the old CPU "capsule"
// particles were both the visual noise and the per-frame cost).
//
// Distances along paths are in Web Mercator units (EPSG:3857 metres), so dot
// spacing is uniform on screen across Germany's latitude range. Spacing is
// quantised per integer zoom: between levels, extra dots fade in halfway between
// the existing ones, so density stays constant while zooming and no dot ever
// jumps.

import type { Accessor, AccessorFunction, DefaultProps } from "@deck.gl/core";
import { PathLayer, ScatterplotLayer, type PathLayerProps, type ScatterplotLayerProps } from "@deck.gl/layers";

const EARTH_CIRCUMFERENCE = 40_075_016.686;
const MERCATOR_R = 6_378_137;

/** Web Mercator units per screen pixel (512 px tiles, as MapLibre/deck.gl use). */
export function unitsPerPixel(zoom: number): number {
  return EARTH_CIRCUMFERENCE / (512 * 2 ** zoom);
}

function mercator([lon, lat]: [number, number]): [number, number] {
  const phi = (Math.max(-85, Math.min(85, lat)) * Math.PI) / 180;
  return [(MERCATOR_R * lon * Math.PI) / 180, MERCATOR_R * Math.log(Math.tan(Math.PI / 4 + phi / 2))];
}

/**
 * Cumulative Mercator distance per vertex, oriented for the flow shader: dots
 * travel toward increasing values, so `reverse` negates the distances to make
 * them travel from the last vertex to the first. `offset` desynchronises paths.
 */
export function flowDistances(path: [number, number][], reverse = false, offset = 0): number[] {
  const out = new Array<number>(path.length);
  let prev = mercator(path[0]);
  let d = offset;
  out[0] = reverse ? -d : d;
  for (let i = 1; i < path.length; i++) {
    const p = mercator(path[i]);
    d += Math.hypot(p[0] - prev[0], p[1] - prev[1]);
    out[i] = reverse ? -d : d;
    prev = p;
  }
  return out;
}

/** Quadratic Bézier from a to b, bowed sideways by `bend` × chord length. */
export function curvedPath(a: [number, number], b: [number, number], bend = 0.18, samples = 32): [number, number][] {
  const mx = (a[0] + b[0]) / 2;
  const my = (a[1] + b[1]) / 2;
  // bow in screen-ish space: scale longitude by cos(lat) so the curve is symmetric
  const k = Math.cos((my * Math.PI) / 180);
  const dx = (b[0] - a[0]) * k;
  const dy = b[1] - a[1];
  const c: [number, number] = [mx - (dy * bend) / k, my + dx * bend];
  const out: [number, number][] = [];
  for (let i = 0; i <= samples; i++) {
    const t = i / samples;
    const u = 1 - t;
    out.push([u * u * a[0] + 2 * u * t * c[0] + t * t * b[0], u * u * a[1] + 2 * u * t * c[1] + t * t * b[1]]);
  }
  return out;
}

const smoothstep = (e0: number, e1: number, x: number) => {
  const t = Math.max(0, Math.min(1, (x - e0) / (e1 - e0)));
  return t * t * (3 - 2 * t);
};

/**
 * Shared animation clock. `tick` advances the flow at a constant on-screen speed
 * (px/s) regardless of zoom; `uniforms` hands a layer its phase/spacing for the
 * current zoom. The accumulator stays in float64 here and only `phase mod
 * spacing` (a small number) reaches the float32 shader.
 */
export class FlowClock {
  private acc = 0;
  private last = -1;

  tick(now: number, zoom: number, speedPx: number): void {
    const dt = this.last < 0 ? 0 : Math.min(0.1, Math.max(0, (now - this.last) / 1000));
    this.last = now;
    this.acc += dt * speedPx * unitsPerPixel(zoom);
  }

  uniforms(zoom: number, spacingPx: number): { phase: number; spacing: number; secondaryAlpha: number } {
    const level = Math.floor(zoom);
    const spacing = spacingPx * unitsPerPixel(level);
    return {
      phase: ((this.acc % spacing) + spacing) % spacing,
      spacing,
      secondaryAlpha: smoothstep(0.2, 0.95, zoom - level),
    };
  }
}

const flowUniformBlock = /* glsl */ `\
layout(std140) uniform flowUniforms {
  float phase;
  float spacing;
  float secondaryAlpha;
  float lineGlow;
  float dotGlow;
  float dotWhite;
} flow;
`;

type FlowUniformProps = {
  phase: number;
  spacing: number;
  secondaryAlpha: number;
  lineGlow: number;
  dotGlow: number;
  dotWhite: number;
};

const flowUniforms = {
  name: "flow",
  vs: flowUniformBlock,
  fs: flowUniformBlock,
  uniformTypes: {
    phase: "f32",
    spacing: "f32",
    secondaryAlpha: "f32",
    lineGlow: "f32",
    dotGlow: "f32",
    dotWhite: "f32",
  },
} as const;

// PathLayer's fragment shader with the flow shading added. Colour output is
// premultiplied emission, meant for additive blending (FLOW_BLEND) so crossing
// lines and dots bloom into each other like light instead of stacking opaquely.
const flowFs = /* glsl */ `\
#version 300 es
#define SHADER_NAME flow-path-layer-fragment-shader

precision highp float;

in vec4 vColor;
in vec2 vCornerOffset;
in float vMiterLength;
in vec2 vPathPosition;
in float vPathLength;
in float vJointType;
in float vFlowDist;
in float vPxPerUnit;
in float vHalfWidthPx;
in vec3 vFlowStyle;

out vec4 fragColor;

void main(void) {
  geometry.uv = vPathPosition;

  bool beyond = vPathPosition.y < 0.0 || vPathPosition.y > vPathLength;
  if (beyond) {
    if (vJointType > 0.5 && length(vCornerOffset) > 1.0) {
      discard;
    }
    if (vJointType < 0.5 && vMiterLength > path.miterLimit + 1.0) {
      discard;
    }
  }

  // distance to the centre line in px; in round joints/caps it's the distance to the vertex
  float across = (beyond ? length(vCornerOffset) : abs(vPathPosition.x)) * vHalfWidthPx;

  // line: anti-aliased core plus a gaussian halo
  float coreHalf = max(vFlowStyle.x * 0.5, 0.3);
  float core = (1.0 - smoothstep(coreHalf - 0.55, coreHalf + 0.55, across)) * min(1.0, vFlowStyle.x);
  float sigma = coreHalf * 2.2 + 1.1;
  float halo = exp(-across * across / (2.0 * sigma * sigma)) * flow.lineGlow;
  float lineA = max(core, halo);

  // dots: nearest slot on a half-spacing lattice; odd slots are the next zoom
  // level's dots, faded in by secondaryAlpha
  float dotA = 0.0;
  if (vFlowStyle.z > 0.0 && flow.spacing > 0.0) {
    float halfSpacing = flow.spacing * 0.5;
    float rel = vFlowDist - flow.phase;
    float slot = floor(rel / halfSpacing + 0.5);
    float along = (rel - slot * halfSpacing) * vPxPerUnit;
    float r = length(vec2(along, across));
    float radius = vFlowStyle.y;
    float dotCore = 1.0 - smoothstep(radius - 0.6, radius + 0.6, r);
    float dotSigma = radius * 1.6;
    float dotHalo = exp(-r * r / (2.0 * dotSigma * dotSigma)) * flow.dotGlow;
    float lod = mix(1.0, flow.secondaryAlpha, mod(slot, 2.0));
    dotA = max(dotCore, dotHalo) * vFlowStyle.z * lod;
  }

  vec3 dotColor = mix(vColor.rgb, vec3(1.0), flow.dotWhite);
  vec3 emission = (vColor.rgb * lineA + dotColor * dotA) * vColor.a;
  float alpha = clamp(lineA + dotA, 0.0, 1.0) * vColor.a;
  if (alpha < 0.003) {
    discard;
  }
  fragColor = vec4(emission, alpha);

  DECKGL_FILTER_COLOR(fragColor, geometry);
}
`;

/**
 * "Lighten" (per-channel max) blending for the emissive flow layers. Real grid
 * geometry has many sub-pixel segments with jittery directions; each segment
 * shades its own slice of the glow, and with additive blending those overlapping
 * slices summed into hairy rays. With max, overlaps resolve to the nearest
 * segment, i.e. a clean distance field of the whole polyline.
 */
export const FLOW_BLEND = {
  depthCompare: "always",
  depthWriteEnabled: false,
  blend: true,
  blendColorOperation: "max",
  blendColorSrcFactor: "one",
  blendColorDstFactor: "one",
  blendAlphaOperation: "max",
  blendAlphaSrcFactor: "one",
  blendAlphaDstFactor: "one",
} as const;

type _FlowPathLayerProps<DataT> = {
  /** Per-vertex distances from `flowDistances` (dots move toward larger values). */
  getTimestamps?: AccessorFunction<DataT, number[]>;
  /** [line core width px, dot radius px, dot opacity 0..1]. Total footprint comes from getWidth. */
  getFlowStyle?: Accessor<DataT, [number, number, number]>;
  phase?: number;
  spacing?: number;
  secondaryAlpha?: number;
  lineGlow?: number;
  dotGlow?: number;
  dotWhite?: number;
};

export type FlowPathLayerProps<DataT = unknown> = _FlowPathLayerProps<DataT> & PathLayerProps<DataT>;

const defaultProps: DefaultProps<FlowPathLayerProps> = {
  getTimestamps: { type: "accessor", value: (d: any) => d.timestamps },
  getFlowStyle: { type: "accessor", value: [1.2, 1.8, 1] },
  phase: { type: "number", value: 0 },
  spacing: { type: "number", value: 0 },
  secondaryAlpha: { type: "number", value: 0 },
  lineGlow: { type: "number", value: 0.3 },
  dotGlow: { type: "number", value: 0.5 },
  dotWhite: { type: "number", value: 0.7 },
};

export class FlowPathLayer<DataT = any, ExtraProps extends {} = {}> extends PathLayer<
  DataT,
  Required<_FlowPathLayerProps<DataT>> & ExtraProps
> {
  static layerName = "FlowPathLayer";
  static defaultProps = defaultProps;

  getShaders() {
    const shaders = super.getShaders();
    return {
      ...shaders,
      fs: flowFs,
      modules: [...shaders.modules, flowUniforms],
      inject: {
        "vs:#decl": /* glsl */ `\
in float instanceTimestamps;
in float instanceNextTimestamps;
in vec3 instanceFlowStyles;
out float vFlowDist;
out float vPxPerUnit;
out float vHalfWidthPx;
out vec3 vFlowStyle;
`,
        // vPathPosition.y / vPathLength run along the segment in half-width units,
        // so they convert both the distance and the px scale of the segment
        "vs:#main-end": /* glsl */ `\
float flowSegment = instanceNextTimestamps - instanceTimestamps;
vFlowDist = instanceTimestamps + flowSegment * vPathPosition.y / max(vPathLength, 1e-6);
vHalfWidthPx = widthPixels.x;
vPxPerUnit = vPathLength * widthPixels.x / max(abs(flowSegment), 1e-6);
vFlowStyle = instanceFlowStyles;
`,
      },
    };
  }

  initializeState() {
    super.initializeState();
    this.getAttributeManager()!.addInstanced({
      timestamps: {
        size: 1,
        accessor: "getTimestamps",
        shaderAttributes: {
          instanceTimestamps: { vertexOffset: 0 },
          instanceNextTimestamps: { vertexOffset: 1 },
        },
      },
      instanceFlowStyles: {
        size: 3,
        accessor: "getFlowStyle",
        defaultValue: [1.2, 1.8, 1],
      },
    });
  }

  draw(params: any) {
    const { phase, spacing, secondaryAlpha, lineGlow, dotGlow, dotWhite } = this.props;
    const flow: FlowUniformProps = { phase, spacing, secondaryAlpha, lineGlow, dotGlow, dotWhite };
    this.state.model!.shaderInputs.setProps({ flow });
    super.draw(params);
  }
}

/** Normal "over" compositing for layers that output premultiplied colour. */
export const PREMULTIPLIED_BLEND = {
  depthCompare: "always",
  depthWriteEnabled: false,
  blend: true,
  blendColorOperation: "add",
  blendColorSrcFactor: "one",
  blendColorDstFactor: "one-minus-src-alpha",
  blendAlphaOperation: "add",
  blendAlphaSrcFactor: "one",
  blendAlphaDstFactor: "one-minus-src-alpha",
} as const;

type StationDotLayerProps = {
  /** colour of the hole in the middle of the ring (the map's land tone) */
  holeColor?: [number, number, number];
};

/**
 * Transit-map station symbol: a light rim around a dark hole, drawn opaque over
 * the lines (use PREMULTIPLIED_BLEND) so nodes read differently from the glowing
 * flow dots. Rim colour = fill colour; radius = outer rim. Picking unaffected.
 */
export class StationDotLayer<DataT = any, ExtraProps extends {} = {}> extends ScatterplotLayer<
  DataT,
  Required<StationDotLayerProps> & ExtraProps
> {
  static layerName = "StationDotLayer";
  static defaultProps: DefaultProps<StationDotLayerProps & ScatterplotLayerProps> = {
    holeColor: { type: "color", value: [17, 23, 33] },
  };

  getShaders() {
    const shaders = super.getShaders();
    const [r, g, b] = (this.props.holeColor ?? [17, 23, 33]).map((v) => (v / 255).toFixed(4));
    return {
      ...shaders,
      inject: {
        "fs:DECKGL_FILTER_COLOR": /* glsl */ `\
if (picking.isActive < 0.5) {
  float r = length(geometry.uv);
  float w = max(fwidth(r), 1e-4);
  float rim = smoothstep(0.5 - w, 0.5 + w, r);
  vec3 c = mix(vec3(${r}, ${g}, ${b}), mix(color.rgb, vec3(1.0), 0.3), rim);
  color = vec4(c * color.a, color.a);
}
`,
      },
    };
  }
}

/** "Screen" compositing for premultiplied glows: brightens toward white, never blows out. */
export const SCREEN_BLEND = {
  depthCompare: "always",
  depthWriteEnabled: false,
  blend: true,
  blendColorOperation: "add",
  blendColorSrcFactor: "one",
  blendColorDstFactor: "one-minus-src",
  blendAlphaOperation: "add",
  blendAlphaSrcFactor: "one",
  blendAlphaDstFactor: "one-minus-src-alpha",
} as const;

const plantUniformBlock = /* glsl */ `\
layout(std140) uniform plantUniforms {
  float time;
} plant;
`;

const plantUniforms = {
  name: "plant",
  vs: plantUniformBlock,
  fs: plantUniformBlock,
  uniformTypes: { time: "f32" },
} as const;

// crisp disc (edge at ~55% of the quad) + a faint tight halo; glow.w = 1 cuts a
// hole (storage ring). Brightness breathes/twinkles at a per-instance phase, so
// neighbours never pulse in sync. Kept small and haze-free so lines stay sharp.
const plantGlowFs = /* glsl */ `\
if (picking.isActive < 0.5) {
  float r = length(geometry.uv);
  float twinkle = 1.0 - vGlow.z + vGlow.z * (0.5 + 0.5 * sin(plant.time * vGlow.y + vSeed * 6.2832));
  float w = max(fwidth(r), 1e-4);
  float disc = 1.0 - smoothstep(0.55 - w, 0.55 + w, r);
  float hole = vGlow.w > 0.5 ? smoothstep(0.27 - w, 0.27 + w, r) : 1.0;
  float core = disc * hole;
  float halo = exp(-r * r * 9.0) * 0.22;
  float a = clamp(max(core, halo) * vGlow.x * twinkle, 0.0, 1.0);
  color = vec4(mix(color.rgb, vec3(1.0), core * 0.18) * a * color.a, a * color.a);
}
`;

// a ring born at the plant's edge that expands to the quad edge and fades out
const plantPingFs = /* glsl */ `\
if (picking.isActive < 0.5) {
  float r = length(geometry.uv);
  float t = fract(plant.time * vGlow.x + vSeed);
  float ring = 1.0 - smoothstep(0.0, 0.07, abs(r - (0.25 + 0.75 * t)));
  float a = ring * (1.0 - t) * (1.0 - t) * vGlow.y;
  color = vec4(color.rgb * a * color.a, a * color.a);
}
`;

type _PlantGlowLayerProps<DataT> = {
  /**
   * glow mode: [brightness 0..1, twinkle speed rad/s, twinkle depth 0..1, ring 0|1]
   * ping mode: [pings per second, strength 0..1, 0, 0]
   */
  getGlow?: Accessor<DataT, [number, number, number, number]>;
  mode?: "glow" | "ping";
  /** seconds; the only per-frame input */
  time?: number;
};

export type PlantGlowLayerProps<DataT = unknown> = _PlantGlowLayerProps<DataT> & ScatterplotLayerProps<DataT>;

/**
 * Animated plant symbols, GPU-only: per-instance style comes from `getGlow`
 * (recomputed only when live data changes), motion from the `time` uniform.
 * Output is premultiplied; pair with SCREEN_BLEND.
 */
export class PlantGlowLayer<DataT = any, ExtraProps extends {} = {}> extends ScatterplotLayer<
  DataT,
  Required<_PlantGlowLayerProps<DataT>> & ExtraProps
> {
  static layerName = "PlantGlowLayer";
  static defaultProps: DefaultProps<PlantGlowLayerProps> = {
    getGlow: { type: "accessor", value: [1, 0, 0, 0] },
    mode: "glow",
    time: { type: "number", value: 0 },
  };

  getShaders() {
    const shaders = super.getShaders();
    return {
      ...shaders,
      modules: [...shaders.modules, plantUniforms],
      inject: {
        "vs:#decl": "in vec4 instanceGlow;\nout vec4 vGlow;\nout float vSeed;\n",
        "vs:#main-end":
          "vGlow = instanceGlow;\nvSeed = fract(sin(dot(instancePositions.xy, vec2(12.9898, 78.233))) * 43758.5453);\n",
        "fs:#decl": "in vec4 vGlow;\nin float vSeed;\n",
        "fs:DECKGL_FILTER_COLOR": this.props.mode === "ping" ? plantPingFs : plantGlowFs,
      },
    };
  }

  initializeState() {
    super.initializeState();
    this.getAttributeManager()!.addInstanced({
      instanceGlow: { size: 4, accessor: "getGlow", defaultValue: [1, 0, 0, 0] },
    });
  }

  draw(params: any) {
    this.state.model!.shaderInputs.setProps({ plant: { time: this.props.time } });
    super.draw(params);
  }
}
