// Flat chevrons (›››) marching along paths: a solid guide line with arrowheads that
// move toward the flow direction, drawn entirely in the fragment shader from one
// `phase` uniform (same approach as FlowPathLayer in flowLayers.ts, different mark).
// Used for the Europe view's cross-border flow arcs. Per-vertex distances come from
// `flowDistances`, so arrows move toward increasing values at a constant on-screen
// speed (FlowClock).

import type { Accessor, AccessorFunction, DefaultProps } from "@deck.gl/core";
import { PathLayer, type PathLayerProps } from "@deck.gl/layers";

const arrowUniformBlock = /* glsl */ `\
layout(std140) uniform arrowUniforms {
  float phase;
  float spacing;
  float strokePx;
  float lineAlpha;
} arrow;
`;

const arrowUniforms = {
  name: "arrow",
  vs: arrowUniformBlock,
  fs: arrowUniformBlock,
  uniformTypes: { phase: "f32", spacing: "f32", strokePx: "f32", lineAlpha: "f32" },
} as const;

const arrowFs = /* glsl */ `\
#version 300 es
#define SHADER_NAME flow-arrow-layer-fragment-shader

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
in vec3 vArrowStyle;

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

  // guide line under the arrows
  float coreHalf = max(vArrowStyle.x * 0.5, 0.3);
  float lineA = (1.0 - smoothstep(coreHalf - 0.5, coreHalf + 0.5, across)) * arrow.lineAlpha;

  // chevrons: apex ahead, arms trailing back at 45 degrees; arm is the half span
  float arrowA = 0.0;
  if (arrow.spacing > 0.0) {
    float cellPx = arrow.spacing * vPxPerUnit;
    float pos = fract((vFlowDist - arrow.phase) / arrow.spacing) * cellPx;
    float arm = vArrowStyle.y;
    float apex = cellPx * 0.5 + arm * 0.5;
    float d = pos - (apex - across);
    float stroke = arrow.strokePx * 0.5;
    float inArm = 1.0 - smoothstep(arm - 0.5, arm + 0.5, across);
    arrowA = (1.0 - smoothstep(stroke - 0.6, stroke + 0.6, abs(d))) * inArm;
  }

  float markA = arrowA * vArrowStyle.z;
  vec3 color = mix(vColor.rgb, vec3(1.0), 0.55 * arrowA);
  float lineOnly = lineA * (1.0 - markA);
  float alpha = clamp(max(lineOnly, markA), 0.0, 1.0) * vColor.a;
  if (alpha < 0.003) {
    discard;
  }
  fragColor = vec4(color * alpha, alpha);

  DECKGL_FILTER_COLOR(fragColor, geometry);
}
`;

type _FlowArrowLayerProps<DataT> = {
  /** Per-vertex distances from `flowDistances` (arrows move toward larger values). */
  getTimestamps?: AccessorFunction<DataT, number[]>;
  /** [guide line px, arrow half span px, arrow opacity 0..1]; total footprint comes from getWidth. */
  getArrowStyle?: Accessor<DataT, [number, number, number]>;
  phase?: number;
  spacing?: number;
  /** chevron stroke width, px */
  strokePx?: number;
  lineAlpha?: number;
};

export type FlowArrowLayerProps<DataT = unknown> = _FlowArrowLayerProps<DataT> & PathLayerProps<DataT>;

const defaultProps: DefaultProps<FlowArrowLayerProps> = {
  getTimestamps: { type: "accessor", value: (d: any) => d.timestamps },
  getArrowStyle: { type: "accessor", value: [0.8, 2, 1] },
  phase: { type: "number", value: 0 },
  spacing: { type: "number", value: 0 },
  strokePx: { type: "number", value: 2 },
  lineAlpha: { type: "number", value: 0.2 },
};

export class FlowArrowLayer<DataT = any, ExtraProps extends {} = {}> extends PathLayer<
  DataT,
  Required<_FlowArrowLayerProps<DataT>> & ExtraProps
> {
  static layerName = "FlowArrowLayer";
  static defaultProps = defaultProps;

  getShaders() {
    const shaders = super.getShaders();
    return {
      ...shaders,
      fs: arrowFs,
      modules: [...shaders.modules, arrowUniforms],
      inject: {
        "vs:#decl": /* glsl */ `\
in float instanceTimestamps;
in float instanceNextTimestamps;
in vec3 instanceArrowStyles;
out float vFlowDist;
out float vPxPerUnit;
out float vHalfWidthPx;
out vec3 vArrowStyle;
`,
        "vs:#main-end": /* glsl */ `\
float flowSegment = instanceNextTimestamps - instanceTimestamps;
vFlowDist = instanceTimestamps + flowSegment * vPathPosition.y / max(vPathLength, 1e-6);
vHalfWidthPx = widthPixels.x;
vPxPerUnit = vPathLength * widthPixels.x / max(abs(flowSegment), 1e-6);
vArrowStyle = instanceArrowStyles;
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
      instanceArrowStyles: {
        size: 3,
        accessor: "getArrowStyle",
        defaultValue: [0.8, 2, 1],
      },
    });
  }

  draw(params: any) {
    const { phase, spacing, strokePx, lineAlpha } = this.props;
    this.state.model!.shaderInputs.setProps({ arrow: { phase, spacing, strokePx, lineAlpha } });
    super.draw(params);
  }
}
