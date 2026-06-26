"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";

interface Props {
  pagina: number;
  totalPaginas: number;
  loading: boolean;
  onChange: (p: number) => void;
}

export function Pagination({ pagina, totalPaginas, loading, onChange }: Props) {
  return (
    <div className="flex items-center justify-center gap-3 mt-6">
      <button
        onClick={() => onChange(Math.max(1, pagina - 1))}
        disabled={pagina === 1 || loading}
        className="flex items-center gap-1.5 px-4 py-2 text-sm text-mid border border-white/10 rounded-lg hover:bg-card-alt disabled:opacity-30 transition-colors"
      >
        <ChevronLeft size={14} /> Anterior
      </button>
      <span className="text-sm text-dim tabular-nums">
        {pagina} / {totalPaginas}
      </span>
      <button
        onClick={() => onChange(Math.min(totalPaginas, pagina + 1))}
        disabled={pagina === totalPaginas || loading}
        className="flex items-center gap-1.5 px-4 py-2 text-sm text-mid border border-white/10 rounded-lg hover:bg-card-alt disabled:opacity-30 transition-colors"
      >
        Próxima <ChevronRight size={14} />
      </button>
    </div>
  );
}
