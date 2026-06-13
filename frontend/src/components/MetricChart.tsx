import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { Detection, Point } from "../lib/api";
import { METRIC_META } from "../lib/format";
import { STATE_COLOR, rgbCss } from "../lib/theme";

interface Props {
  metric: "ndvi" | "bsi" | "vh_db";
  points: Point[];
  detections: Detection[];
}

export default function MetricChart({ metric, points, detections }: Props) {
  const meta = METRIC_META[metric];
  const data = points.map((p) => ({ t: Date.parse(p.date), v: p.value }));
  const year = (t: number) => new Date(t).getFullYear().toString();

  return (
    <div className="mb-4">
      <div className="mb-1 flex items-baseline justify-between">
        <span className="text-xs font-medium text-slate-200">{meta.label}</span>
        <span className="text-[10px] text-slate-500">{meta.help}</span>
      </div>
      <ResponsiveContainer width="100%" height={110}>
        <LineChart data={data} margin={{ top: 4, right: 6, bottom: 0, left: -18 }}>
          <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
          <XAxis
            dataKey="t"
            type="number"
            domain={["dataMin", "dataMax"]}
            scale="time"
            tickFormatter={year}
            tick={{ fill: "#64748b", fontSize: 10 }}
            stroke="rgba(255,255,255,0.1)"
          />
          <YAxis tick={{ fill: "#64748b", fontSize: 10 }} stroke="rgba(255,255,255,0.1)" width={40} />
          <Tooltip
            contentStyle={{
              background: "rgba(12,16,24,0.95)",
              border: "1px solid rgba(255,255,255,0.1)",
              borderRadius: 8,
              fontSize: 11,
            }}
            labelFormatter={(t) => new Date(t as number).toLocaleDateString("en-GB")}
            formatter={(v: number) => [v.toFixed(3), meta.label]}
          />
          {detections.map((d) => (
            <ReferenceLine
              key={d.id}
              x={Date.parse(d.detected_at)}
              stroke={rgbCss(STATE_COLOR[d.to_state], 0.7)}
              strokeDasharray="3 3"
            />
          ))}
          <Line type="monotone" dataKey="v" stroke={meta.color} dot={false} strokeWidth={1.5} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
