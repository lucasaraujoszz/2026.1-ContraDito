import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { getParlamentar } from "@/lib/api";
import { Avatar } from "@/components/ui/Avatar";
import { scoreHex, formatDate, formatScore } from "@/lib/utils";
import { DossieClient } from "./DossieClient";

interface PageProps {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { id } = await params;
  try {
    const p = await getParlamentar(Number(id));
    const scoreStr = p.score_coerencia !== null ? `${formatScore(p.score_coerencia)}%` : "Dados insuficientes";
    return {
      title: p.nome_urna,
      description: `Score de Coerência de ${p.nome_urna} (${p.partido}/${p.estado}): ${scoreStr}`,
      openGraph: {
        title: `${p.nome_urna} — ContraDito`,
        description: `Score de Coerência: ${scoreStr} · ${p.partido} · ${p.cargo}`,
        images: p.url_foto ? [{ url: p.url_foto }] : [],
      },
    };
  } catch {
    return { title: "Parlamentar" };
  }
}

export default async function DossiePage({ params }: PageProps) {
  const { id } = await params;

  let parlamentar;
  try {
    parlamentar = await getParlamentar(Number(id));
  } catch {
    notFound();
  }

  const p = parlamentar;
  const color = scoreHex(p.score_coerencia);

  return (
    <div className="pt-14 min-h-screen">
      {/* Hero header */}
      <div
        className="relative"
        style={{ background: `linear-gradient(to bottom, ${color}0a 0%, transparent 100%)` }}
      >
        <div
          className="absolute inset-x-0 top-0 h-px"
          style={{ background: `linear-gradient(to right, transparent, ${color}30, transparent)` }}
        />
        <div className="max-w-5xl mx-auto px-4 sm:px-6 pt-10 pb-8">
          <div className="flex flex-col sm:flex-row items-center sm:items-start gap-6">
            <Avatar name={p.nome_urna} url={p.url_foto} size={96} ringColor={`${color}55`} />

            <div className="text-center sm:text-left">
              <h1 className="font-display text-4xl sm:text-5xl font-bold text-bright leading-tight">
                {p.nome_urna}
              </h1>
              <div className="flex flex-wrap justify-center sm:justify-start gap-2 mt-3">
                {[p.cargo, p.partido, p.estado].map((tag) => (
                  <span
                    key={tag}
                    className="text-xs px-2.5 py-1 rounded-full border border-white/10 text-mid"
                  >
                    {tag}
                  </span>
                ))}
                <span
                  className="text-xs px-2.5 py-1 rounded-full text-mid"
                  style={{ border: `1px solid ${color}25`, background: `${color}0c`, color }}
                >
                  {p.status_mandato}
                </span>
              </div>
              <p className="mt-2 text-xs text-dim">
                Atualizado em {formatDate(p.data_ultima_atualizacao)}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Client-side tabs */}
      <DossieClient parlamentar={p} />
    </div>
  );
}
