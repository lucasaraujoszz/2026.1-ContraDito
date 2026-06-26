import { formatScore, scoreHex } from "@/lib/utils";

interface ScoreGaugeProps {
  score: number | null;
  size?: number;
}

export function ScoreGauge({ score, size = 100 }: ScoreGaugeProps) {
  const stroke = Math.max(4, size * 0.05);
  const r = (size - stroke * 2) / 2;
  const cx = size / 2;
  const circ = 2 * Math.PI * r;
  const offset = score !== null ? circ * (1 - score / 100) : circ;
  const color = scoreHex(score);

  return (
    <div
      className="relative flex items-center justify-center"
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} className="absolute -rotate-90" aria-hidden>
        <circle
          cx={cx} cy={cx} r={r}
          fill="none"
          stroke="rgba(255,255,255,0.05)"
          strokeWidth={stroke}
        />
        <circle
          cx={cx} cy={cx} r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeDasharray={circ}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 1.2s cubic-bezier(0.4,0,0.2,1)" }}
        />
      </svg>
      <span
        className="relative font-data font-bold leading-none tabular-nums"
        style={{ fontSize: size * 0.27, color }}
      >
        {formatScore(score)}
      </span>
    </div>
  );
}

export function ScoreBar({ score, width = 80 }: { score: number | null; width?: number }) {
  const color = scoreHex(score);
  const pct = score !== null ? score : 0;

  return (
    <div className="flex items-center gap-3">
      <div
        className="relative h-[3px] rounded-full overflow-hidden"
        style={{ width, background: "rgba(255,255,255,0.06)" }}
      >
        <div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{ width: `${pct}%`, backgroundColor: color, transition: "width 0.8s ease" }}
        />
      </div>
      <span
        className="font-data text-sm font-semibold tabular-nums"
        style={{ color, minWidth: "3.5rem", textAlign: "right" }}
      >
        {score !== null ? `${formatScore(score)}%` : "N/D"}
      </span>
    </div>
  );
}
