"use client";

import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";
import { computeTimeline, formatDate, scoreHex, mergeTimelines } from "@/lib/utils";
import type { TimelinePoint } from "@/lib/types";

interface TooltipPayload {
  value: number;
  payload: { data_votacao: string; tipo: string; numero: number; ano: number; index: number; score: number };
}

function ChartTooltip({ active, payload }: { active?: boolean; payload?: TooltipPayload[] }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  const color = d.score >= 70 ? "#10b981" : "#f43f5e";
  return (
    <div className="glass-elevated rounded-lg px-3 py-2.5 text-xs space-y-1 shadow-xl">
      <p className="text-dim">{formatDate(d.data_votacao)}</p>
      <p className="text-bright font-medium">{d.tipo} {d.numero}/{d.ano}</p>
      <p className="font-data font-bold" style={{ color }}>
        {d.score.toFixed(1)}% — votação #{d.index}
      </p>
    </div>
  );
}

export function CoherenceChart({
  data,
  height = 220,
}: {
  data: TimelinePoint[];
  height?: number;
}) {
  const computed = computeTimeline(data);

  if (computed.length === 0) {
    return (
      <div
        className="flex items-center justify-center rounded-xl bg-card border border-white/[0.06] text-dim text-sm"
        style={{ height }}
      >
        Dados insuficientes para exibir a timeline.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={computed} margin={{ top: 10, right: 4, bottom: 4, left: -16 }}>
        <CartesianGrid strokeDasharray="2 4" stroke="rgba(255,255,255,0.04)" vertical={false} />
        <XAxis
          dataKey="data_votacao"
          tick={{ fill: "#3d4a5c", fontSize: 10, fontFamily: "inherit" }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v: string) =>
            new Date(v + "T12:00:00").toLocaleDateString("pt-BR", { month: "short", year: "2-digit" })
          }
        />
        <YAxis
          domain={[0, 100]}
          ticks={[0, 25, 50, 70, 100]}
          tick={{ fill: "#3d4a5c", fontSize: 10, fontFamily: "inherit" }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v: number) => `${v}%`}
        />
        <ReferenceLine
          y={70}
          stroke="rgba(16,185,129,0.18)"
          strokeDasharray="4 3"
          label={{ value: "70%", position: "insideTopRight", fill: "rgba(16,185,129,0.45)", fontSize: 10 }}
        />
        <Tooltip content={<ChartTooltip />} cursor={{ stroke: "rgba(255,255,255,0.08)", strokeWidth: 1 }} />
        <Line
          type="monotone"
          dataKey="score"
          stroke="#5e88ff"
          strokeWidth={1.5}
          dot={(props: { cx?: number; cy?: number; payload?: { score: number; index: number } }) => {
            if (props.cx == null || props.cy == null || !props.payload) return <g />;
            const color = props.payload.score >= 70 ? "#10b981" : "#f43f5e";
            return <circle key={`d-${props.payload.index}`} cx={props.cx} cy={props.cy} r={3} fill={color} />;
          }}
          activeDot={{ r: 5, strokeWidth: 0 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function ComparisonChart({
  dataA, dataB, nameA, nameB,
}: {
  dataA: TimelinePoint[];
  dataB: TimelinePoint[];
  nameA: string;
  nameB: string;
}) {
  const computedA = computeTimeline(dataA);
  const computedB = computeTimeline(dataB);
  const merged = mergeTimelines(computedA, computedB);

  if (!merged.length) return null;

  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={merged} margin={{ top: 10, right: 4, bottom: 4, left: -16 }}>
        <CartesianGrid strokeDasharray="2 4" stroke="rgba(255,255,255,0.04)" vertical={false} />
        <XAxis
          dataKey="date"
          tick={{ fill: "#3d4a5c", fontSize: 10 }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v: string) =>
            new Date(v + "T12:00:00").toLocaleDateString("pt-BR", { month: "short", year: "2-digit" })
          }
        />
        <YAxis
          domain={[0, 100]}
          ticks={[0, 25, 50, 70, 100]}
          tick={{ fill: "#3d4a5c", fontSize: 10 }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v: number) => `${v}%`}
        />
        <ReferenceLine y={70} stroke="rgba(16,185,129,0.15)" strokeDasharray="4 3" />
        <Tooltip
          contentStyle={{
            background: "rgba(17,25,39,0.92)",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: 8,
            fontSize: 12,
            color: "#8892a4",
          }}
          labelFormatter={(l) => typeof l === "string" ? new Date(l + "T12:00:00").toLocaleDateString("pt-BR") : String(l)}
          formatter={(v) => [typeof v === "number" ? `${v.toFixed(1)}%` : String(v)]}
        />
        <Line type="monotone" dataKey="scoreA" name={nameA} stroke="#10b981" strokeWidth={1.5} dot={false} connectNulls={false} />
        <Line type="monotone" dataKey="scoreB" name={nameB} stroke="#5e88ff" strokeWidth={1.5} dot={false} connectNulls={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
