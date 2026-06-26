import Link from "next/link";
import { Avatar } from "@/components/ui/Avatar";
import { scoreHex } from "@/lib/utils";
import type { ParlamentarSimilar } from "@/lib/types";

export function SimilaresGrid({ similares }: { similares: ParlamentarSimilar[] }) {
  if (similares.length === 0) {
    return (
      <div className="py-14 text-center rounded-xl border border-white/[0.07] text-mid text-sm space-y-1">
        <p>Nenhum parlamentar com votação similar encontrado.</p>
        <p className="text-dim text-xs">Mínimo de 5 proposições em comum (Sim/Não).</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
      {similares.map((s) => {
        const scoreColor = scoreHex(s.score_coerencia);
        const concColor = s.percentual_concordancia >= 70 ? "#10b981" : "#f59e0b";

        return (
          <Link
            key={s.id}
            href={`/politico/${s.id}`}
            className="group glass rounded-xl p-4 flex items-center gap-3.5 hover:border-white/[0.14] transition-colors"
          >
            <Avatar name={s.nome_urna} url={s.url_foto} size={46} ringColor={`${scoreColor}45`} />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-bright truncate group-hover:text-coherent transition-colors">
                {s.nome_urna}
              </p>
              <p className="text-[11px] text-dim mt-0.5">{s.partido} · {s.estado}</p>
              <div className="flex items-baseline gap-1.5 mt-1.5">
                <span className="font-data text-xs font-bold" style={{ color: concColor }}>
                  {s.percentual_concordancia.toFixed(0)}%
                </span>
                <span className="text-[10px] text-dim">concordância</span>
                <span className="text-[10px] text-dim">· {s.votos_em_comum} votos</span>
              </div>
            </div>
          </Link>
        );
      })}
    </div>
  );
}
