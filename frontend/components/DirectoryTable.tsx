"use client";

import { ParlamentarCard } from "@/components/ParlamentarCard";
import { RowSkeleton } from "@/components/ui/Skeleton";
import type { Filters } from "@/components/FilterBar";
import type { PaginaParlamentares } from "@/lib/types";

interface Props {
  loading: boolean;
  error: string | null;
  data: PaginaParlamentares | null;
  filters: Filters;
  pagina: number;
  onRetry: () => void;
}

export function DirectoryTable({ loading, error, data, filters, onRetry }: Props) {
  return (
    <div className="mt-4 rounded-xl border border-white/[0.07] overflow-hidden">
      <div className="flex items-center gap-4 px-6 py-2.5 bg-card-alt border-b border-white/[0.07]">
        <div className="hidden sm:block w-0.5 flex-shrink-0" />
        <div className="w-11 flex-shrink-0" />
        <span className="flex-1 text-[10px] uppercase tracking-widest text-dim font-medium">
          PARLAMENTAR
        </span>
        <span className="hidden sm:block text-[10px] uppercase tracking-widest text-dim font-medium w-14">
          PARTIDO
        </span>
        <span className="hidden md:block text-[10px] uppercase tracking-widest text-dim font-medium w-36">
          CARGO
        </span>
        <span className="text-[10px] uppercase tracking-widest text-dim font-medium text-right" style={{ minWidth: "7.5rem" }}>
          COERÊNCIA
        </span>
      </div>
      {error ? (
        <div className="py-16 text-center space-y-3 bg-card">
          <p className="text-mid text-sm">{error}</p>
          <button onClick={onRetry} className="text-xs text-pulse hover:underline">
            Tentar novamente
          </button>
        </div>
      ) : loading ? (
        Array.from({ length: 10 }).map((_, i) => <RowSkeleton key={i} />)
      ) : data?.itens.length === 0 ? (
        <div className="py-16 text-center text-mid text-sm bg-card">
          Nenhum parlamentar encontrado para os filtros selecionados.
        </div>
      ) : (
        data?.itens
          .filter((p) => filters.incluirSemDados || p.score_coerencia !== null)
          .map((p) => <ParlamentarCard key={p.id} parlamentar={p} />)
      )}
    </div>
  );
}
