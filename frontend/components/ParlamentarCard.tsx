import Link from "next/link";
import { Avatar } from "@/components/ui/Avatar";
import { ScoreBar } from "@/components/ui/ScoreBadge";
import { scoreHex } from "@/lib/utils";
import type { Parlamentar } from "@/lib/types";

export function ParlamentarCard({ parlamentar: p }: { parlamentar: Parlamentar }) {
  const color = scoreHex(p.score_coerencia);

  return (
    <Link
      href={`/politico/${p.id}`}
      className="group flex items-center gap-4 px-6 py-4 border-b border-white/[0.05] hover:bg-card-alt transition-colors"
    >
      <div
        className="hidden sm:block w-0.5 h-9 rounded-full flex-shrink-0 opacity-50"
        style={{ backgroundColor: color }}
      />

      <Avatar name={p.nome_urna} url={p.url_foto} size={44} ringColor={`${color}40`} />

      <div className="flex-1 min-w-0">
        <p className="font-medium text-bright text-sm truncate group-hover:text-coherent transition-colors">
          {p.nome_urna}
        </p>
        <p className="text-[11px] text-dim mt-0.5 truncate">{p.nome_civil}</p>
      </div>

      <span className="hidden sm:block text-sm text-mid w-14 flex-shrink-0 font-medium">
        {p.partido}
      </span>

      <span className="hidden md:block text-xs text-dim w-36 flex-shrink-0 truncate">
        {p.cargo}
      </span>

      <div className="flex-shrink-0">
        <ScoreBar score={p.score_coerencia} />
      </div>
    </Link>
  );
}
