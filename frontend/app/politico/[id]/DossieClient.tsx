"use client";

import { useState, useEffect } from "react";
import { getTimeline, getVotos, getSimilares } from "@/lib/api";
import { TendenciaRecente } from "@/components/TendenciaRecente";
import { ScoreGauge } from "@/components/ui/ScoreBadge";
import { CoherenceChart } from "@/components/CoherenceChart";
import { VotosTable } from "@/components/VotosTable";
import { SimilaresGrid } from "@/components/SimilaresGrid";
import { Skeleton } from "@/components/ui/Skeleton";
import type { Parlamentar, TimelinePoint, PaginaVotos, ParlamentarSimilar } from "@/lib/types";

type Tab = "perfil" | "votacoes" | "similares";

const TABS: { key: Tab; label: string }[] = [
  { key: "perfil", label: "Perfil" },
  { key: "votacoes", label: "Votações" },
  { key: "similares", label: "Similares" },
];

export function DossieClient({ parlamentar: p }: { parlamentar: Parlamentar }) {
  const [tab, setTab] = useState<Tab>("perfil");

  const [timeline, setTimeline] = useState<TimelinePoint[] | null>(null);
  const [votos, setVotos] = useState<PaginaVotos | null>(null);
  const [votosPagina, setVotosPagina] = useState(1);
  const [similares, setSimilares] = useState<ParlamentarSimilar[] | null>(null);

  const [loadingTL, setLoadingTL] = useState(false);
  const [loadingV, setLoadingV] = useState(false);
  const [loadingS, setLoadingS] = useState(false);

  useEffect(() => {
    if (tab === "perfil" && timeline === null) {
      setLoadingTL(true);
      getTimeline(p.id).then(setTimeline).catch(() => setTimeline([])).finally(() => setLoadingTL(false));
    }
  }, [tab, p.id, timeline]);

  useEffect(() => {
    if (tab === "votacoes") {
      setLoadingV(true);
      getVotos(p.id, { pagina: votosPagina, tamanho: 20 })
        .then(setVotos)
        .catch(() => setVotos(null))
        .finally(() => setLoadingV(false));
    }
  }, [tab, p.id, votosPagina]);

  useEffect(() => {
    if (tab === "similares" && similares === null) {
      setLoadingS(true);
      getSimilares(p.id).then(setSimilares).catch(() => setSimilares([])).finally(() => setLoadingS(false));
    }
  }, [tab, p.id, similares]);

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 pb-24">
      {/* Tabs */}
      <div className="flex border-b border-white/[0.08] mt-10">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`relative px-5 py-3 text-sm font-medium transition-colors ${
              tab === t.key ? "text-bright" : "text-dim hover:text-mid"
            }`}
          >
            {t.label}
            {tab === t.key && (
              <span className="absolute bottom-0 inset-x-3 h-[2px] bg-coherent rounded-full" />
            )}
          </button>
        ))}
      </div>

      <div className="mt-8">
        {/* PERFIL */}
        {tab === "perfil" && (
          <div className="space-y-10">
            <div className="flex flex-col items-center gap-5 py-4">
              {p.dados_insuficientes ? (
                <div className="text-center space-y-1.5">
                  <p className="text-mid text-sm">Score indisponível</p>
                  <p className="text-xs text-dim">
                    {loadingTL || timeline === null
                      ? "Mínimo de 3 votações analisadas pela IA necessário."
                      : timeline.length === 0
                      ? "Nenhuma votação deste parlamentar foi analisada pela IA ainda."
                      : `${timeline.length} votação${timeline.length > 1 ? "ões analisadas" : " analisada"} — mínimo de 3 necessário.`}
                  </p>
                </div>
              ) : (
                <>
                  <ScoreGauge score={p.score_coerencia} size={148} />
                  <div className="text-center">
                    <p className="text-[11px] uppercase tracking-[0.2em] text-dim">Score de Coerência</p>
                    <p className="text-xs text-mid mt-1 max-w-xs">
                      {p.score_coerencia !== null
                        ? p.score_coerencia >= 70
                          ? "Votações majoritariamente em linha com os discursos"
                          : "Divergências identificadas entre discursos e votações"
                        : "Dados insuficientes para cálculo"}
                    </p>
                  </div>
                </>
              )}
            </div>

            <div>
              <div className="flex items-center gap-3 mb-4">
                <p className="text-[11px] uppercase tracking-[0.2em] text-dim">
                  Evolução da Coerência
                </p>
                {timeline && timeline.length > 0 && (
                  <TendenciaRecente points={timeline} />
                )}
              </div>
              {loadingTL ? (
                <Skeleton className="h-[220px] w-full rounded-xl" />
              ) : timeline !== null ? (
                <>
                  <CoherenceChart data={timeline} />
                  {timeline.length > 0 && (
                    <p className="mt-2 text-[11px] text-dim">
                      Cada ponto representa uma votação analisada pela IA. O score acumula progressivamente — quanto mais à direita, mais recente.
                      {timeline.length >= 12 && " A tendência compara o score médio das últimas 10 votações com o histórico total."}
                    </p>
                  )}
                </>
              ) : null}
            </div>
          </div>
        )}

        {/* VOTAÇÕES */}
        {tab === "votacoes" && (
          <>
            {loadingV ? (
              <div className="rounded-xl border border-white/[0.07] overflow-hidden">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div key={i} className="flex gap-4 px-4 py-3.5 border-b border-white/[0.05] bg-card">
                    <Skeleton className="h-4 w-40" />
                    <Skeleton className="h-4 w-16 ml-auto" />
                  </div>
                ))}
              </div>
            ) : votos ? (
              <VotosTable pagina={votos} onPageChange={(pg) => setVotosPagina(pg)} />
            ) : (
              <p className="py-12 text-center text-mid text-sm">
                Não foi possível carregar as votações.
              </p>
            )}
          </>
        )}

        {/* SIMILARES */}
        {tab === "similares" && (
          <>
            <p className="text-xs text-dim mb-5">
              Parlamentares que votaram de forma idêntica (Sim/Não) nas mesmas
              proposições — mínimo de 5 em comum.
            </p>
            {loadingS ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {Array.from({ length: 6 }).map((_, i) => (
                  <Skeleton key={i} className="h-20 rounded-xl" />
                ))}
              </div>
            ) : similares !== null ? (
              <SimilaresGrid similares={similares} />
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}
