// Comets gliding along paths: a bright head with a tapering, fading tail, drawn
// entirely in the fragment shader from one `phase` uniform (same approach as
// FlowPathLayer in flowLayers.ts, different mark). Used for the Europe view's
// cross-border flow arcs. Per-vertex distances come from `flowDistances`, so heads
// move toward increasing values at a constant on-screen speed (FlowClock).

import type { Accessor, AccessorFunction, DefaultProps } from "@deck.gl/core";
import { PathLayer, type PathLayerProps } from "@deck.gl/layers";

const cometUniformBlock = /* glsl */ `\
layout(std140) uniform cometUniforms {
  float phase;
  float spacing;
  float tailPx;
  float lineAlpha;
} comet;
`;

const cometUniforms = {
  name: "comet",
  vs: cometUniformBlock,
  fs: cometUniformBlock,
  uniformTypes: { phase: "f32", spacing: "f32", tailPx: "f32", lineAlpha: "f32" },
} as const;

const cometFs = /* glsl */ `\
#version 300 es
#define SHADER_NAME comet-path-layer-fragment-shader

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
in vec3 vCometStyle;

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
  float across = (beyond ? length(vCornerOffset) : abs(vPathPosition.x)) * vHalfWidthPx;

  // faint guide line under the comets
  float coreHalf = max(vCometStyle.x * 0.5, 0.3);
  float lineA = (1.0 - smoothstep(coreHalf - 0.5, coreHalf + 0.5, across)) * comet.lineAlpha;

  float headA = 0.0;
  float tailA = 0.0;
  if (comet.spacing > 0.0) {
    float rel = (vFlowDist - comet.phase) / comet.spacing;
    // px behind the next head ahead, and px past the previous head
    float behind = (ceil(rel) - rel) * comet.spacing * vPxPerUnit;
    float ahead = (rel - floor(rel)) * comet.spacing * vPxPerUnit;
    float radius = vCometStyle.y;
    float r = length(vec2(min(behind, ahead), across));
    headA = 1.0 - smoothstep(radius - 0.6, radius + 0.6, r);
    float k = clamp(behind / comet.tailPx, 0.0, 1.0);
    float width = radius * (1.0 - 0.75 * k);
    tailA = exp(-1.6 * k) * (1.0 - k) * exp(-across * across / (2.0 * width * width));
  }

  float cometA = max(headA, tailA * 0.85) * vCometStyle.z;
  vec3 color = mix(vColor.rgb, vec3(1.0), 0.75 * headA);
  float alpha = clamp(max(lineA, cometA), 0.0, 1.0) * vColor.a;
  if (alpha < 0.003) {
    discard;
  }
  fragColor = vec4(color * alpha, alpha);

  DECKGL_FILTER_COLOR(fragColor, geometry);
}
`;

type _CometPathLayerProps<DataT> = {
  /** Per-vertex distances from `flowDistances` (heads move toward larger values). */
  getTimestamps?: AccessorFunction<DataT, number[]>;
  /** [guide line px, head radius px, comet opacity 0..1]; total footprint comes from getWidth. */
  getCometStyle?: Accessor<DataT, [number, number, number]>;
  phase?: number;
  spacing?: number;
  tailPx?: number;
  lineAlpha?: number;
};

export type CometPathLayerProps<DataT = unknown> = _CometPathLayerProps<DataT> & PathLayerProps<DataT>;

const defaultProps: DefaultProps<CometPathLayerProps> = {
  getTimestamps: { type: "accessor", value: (d: any) => d.timestamps },
  getCometStyle: { type: "accessor", value: [0.8, 2, 1] },
  phase: { type: "number", value: 0 },
  spacing: { type: "number", value: 0 },
  tailPx: { type: "number", value: 60 },
  lineAlpha: { type: "number", value: 0.2 },
};

export class CometPathLayer<DataT = any, ExtraProps extends {} = {}> extends PathLayer<
  DataT,
  Required<_CometPathLayerProps<DataT>> & ExtraProps
> {
  static layerName = "CometPathLayer";
  static defaultProps = defaultProps;

  getShaders() {
    const shaders = super.getShaders();
    return {
      ...shaders,
      fs: cometFs,
      modules: [...shaders.modules, cometUniforms],
      inject: {
        "vs:#decl": /* glsl */ `\
in float instanceTimestamps;
in float instanceNextTimestamps;
in vec3 instanceCometStyles;
out float vFlowDist;
out float vPxPerUnit;
out float vHalfWidthPx;
out vec3 vCometStyle;
`,
        "vs:#main-end": /* glsl */ `\
float flowSegment = instanceNextTimestamps - instanceTimestamps;
vFlowDist = instanceTimestamps + flowSegment * vPathPosition.y / max(vPathLength, 1e-6);
vHalfWidthPx = widthPixels.x;
vPxPerUnit = vPathLength * widthPixels.x / max(abs(flowSegment), 1e-6);
vCometStyle = instanceCometStyles;
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
      instanceCometStyles: {
        size: 3,
        accessor: "getCometStyle",
        defaultValue: [0.8, 2, 1],
      },
    });
  }

  draw(params: any) {
    const { phase, spacing, tailPx, lineAlpha } = this.props;
    this.state.model!.shaderInputs.setProps({ comet: { phase, spacing, tailPx, lineAlpha } });
    super.draw(params);
  }
}
