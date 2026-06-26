import type { TimelinePoint, TimelinePointComputed } from "./types";

export function scoreHex(score: number | null): string {
  if (score === null) return "#475569";
  return score >= 70 ? "#10b981" : "#f43f5e";
}

export function scoreColorClass(score: number | null): string {
  if (score === null) return "text-pending";
  return score >= 70 ? "text-coherent" : "text-incoherent";
}

export function formatScore(score: number | null): string {
  if (score === null) return "N/D";
  return score.toFixed(1);
}

export function votoHex(voto: string): string {
  const v = voto.toLowerCase();
  if (v === "sim") return "#10b981";
  if (v === "não" || v === "nao") return "#f43f5e";
  return "#64748b";
}

export function formatDate(iso: string): string {
  return new Date(iso + (iso.includes("T") ? "" : "T12:00:00")).toLocaleDateString(
    "pt-BR",
    { day: "2-digit", month: "short", year: "numeric" }
  );
}

export function getInitials(name: string): string {
  return name
    .split(" ")
    .filter((w) => w.length > 2)
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();
}

export function computeTimeline(points: TimelinePoint[]): TimelinePointComputed[] {
  let coerentes = 0;
  return points.map((p, i) => {
    if (p.eh_coerente) coerentes++;
    const total = i + 1;
    return { ...p, index: total, score: Math.round((coerentes / total) * 1000) / 10 };
  });
}

export type MergedPoint = { date: string; scoreA: number | null; scoreB: number | null };

export function mergeTimelines(
  a: TimelinePointComputed[],
  b: TimelinePointComputed[]
): MergedPoint[] {
  const map = new Map<string, MergedPoint>();
  a.forEach((p) => map.set(p.data_votacao, { date: p.data_votacao, scoreA: p.score, scoreB: null }));
  b.forEach((p) => {
    const ex = map.get(p.data_votacao);
    if (ex) ex.scoreB = p.score;
    else map.set(p.data_votacao, { date: p.data_votacao, scoreA: null, scoreB: p.score });
  });
  return [...map.values()].sort((x, y) => x.date.localeCompare(y.date));
}
