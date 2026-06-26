"use client";

import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import type { TimelinePoint } from "@/lib/types";

const MIN_TOTAL = 12; // requer ao menos 2 pontos "históricos" fora da janela recente
const RECENT_N = 10;

function computeTendencia(points: TimelinePoint[]) {
  if (points.length < MIN_TOTAL) return null;

  const totalCoerentes = points.filter((p) => p.eh_coerente).length;
  const historicalScore = (totalCoerentes / points.length) * 100;

  const recent = points.slice(-RECENT_N);
  const recentCoerentes = recent.filter((p) => p.eh_coerente).length;
  const recentScore = (recentCoerentes / RECENT_N) * 100;

  return { delta: recentScore - historicalScore, total: points.length };
}

export function TendenciaRecente({ points }: { points: TimelinePoint[] }) {
  const t = computeTendencia(points);
  if (!t) return null;

  const flat = Math.abs(t.delta) <= 1;
  const up = t.delta > 1;
  const color = flat ? "#64748b" : up ? "#10b981" : "#f43f5e";
  const Icon = flat ? Minus : up ? TrendingUp : TrendingDown;
  const sign = t.delta > 0 ? "+" : "";

  return (
    <span
      title={`Score médio das últimas ${RECENT_N} votações analisadas comparado ao histórico total (${t.total} votações)`}
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px] font-medium tabular-nums cursor-default"
      style={{ borderColor: `${color}28`, backgroundColor: `${color}0d`, color }}
    >
      <Icon size={11} strokeWidth={2.5} />
      {sign}{t.delta.toFixed(1)} pts nas últimas {RECENT_N} votações
    </span>
  );
}
