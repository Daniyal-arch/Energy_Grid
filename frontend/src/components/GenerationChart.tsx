import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { GenPoint } from "../lib/api";

export default function GenerationChart({ points, color }: { points: GenPoint[]; color: string }) {
  const data = points.map((p) => ({ t: Date.parse(p.date), gwh: p.mwh / 1000 }));
  return (
    <ResponsiveContainer width="100%" height={110}>
      <LineChart data={data} margin={{ top: 4, right: 6, bottom: 0, left: -8 }}>
        <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
        <XAxis
          dataKey="t"
          type="number"
          domain={["dataMin", "dataMax"]}
          scale="time"
          tickFormatter={(t: number) => new Date(t).toLocaleDateString("en-GB", { day: "2-digit", month: "short" })}
          tick={{ fill: "#64748b", fontSize: 10 }}
          stroke="rgba(255,255,255,0.1)"
        />
        <YAxis tick={{ fill: "#64748b", fontSize: 10 }} stroke="rgba(255,255,255,0.1)" width={36} />
        <Tooltip
          contentStyle={{
            background: "rgba(12,16,24,0.95)",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: 8,
            fontSize: 11,
          }}
          labelFormatter={(t) => new Date(t as number).toLocaleDateString("en-GB")}
          formatter={(v: number) => [`${v.toFixed(0)} GWh`, "Germany"]}
        />
        <Line type="monotone" dataKey="gwh" stroke={color} dot={false} strokeWidth={1.5} />
      </LineChart>
    </ResponsiveContainer>
  );
}
