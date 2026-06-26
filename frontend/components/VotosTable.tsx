"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { formatDate, votoHex } from "@/lib/utils";
import type { Voto, PaginaVotos } from "@/lib/types";

function VotoRow({ v }: { v: Voto }) {
  const [open, setOpen] = useState(false);
  const hasDetails = !!(v.justificativa || v.inferencia_ia);
  const vColor = votoHex(v.voto_oficial);

  return (
    <>
      <div
        onClick={() => hasDetails && setOpen((o) => !o)}
        className={`grid grid-cols-[1fr_auto_auto_auto] md:grid-cols-[2fr_auto_auto_auto_auto] gap-x-4 items-center px-4 py-3.5 border-b border-white/[0.05] transition-colors ${hasDetails ? "cursor-pointer" : ""} ${open ? "bg-card-alt" : "hover:bg-card-alt/60"}`}
      >
        <div className="min-w-0">
          <p className="text-sm font-medium text-bright truncate">
            {v.tipo} {v.numero}/{v.ano}
          </p>
          {v.ementa && (
            <p className="text-[11px] text-dim mt-0.5 line-clamp-1">{v.ementa}</p>
          )}
        </div>

        <span className="hidden md:block text-xs text-dim tabular-nums flex-shrink-0">
          {formatDate(v.data_votacao)}
        </span>

        <span className="text-xs font-data font-semibold flex-shrink-0 tabular-nums" style={{ color: vColor }}>
          {v.voto_oficial}
        </span>

        <span
          className={`hidden md:inline-flex text-[11px] px-2 py-0.5 rounded-full font-medium flex-shrink-0 ${
            v.eh_coerente === null
              ? "bg-white/5 text-dim"
              : v.eh_coerente
              ? "bg-coherent/10 text-coherent"
              : "bg-incoherent/10 text-incoherent"
          }`}
        >
          {v.eh_coerente === null ? "—" : v.eh_coerente ? "Coerente" : "Incoerente"}
        </span>

        <div className="w-4 flex justify-center">
          {hasDetails && (
            <span className="text-dim">
              {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
            </span>
          )}
        </div>
      </div>

      {open && (
        <div className="bg-card-alt/50 border-b border-white/[0.05] px-6 py-4 space-y-3">
          {v.inferencia_ia && (
            <div>
              <p className="text-[10px] uppercase tracking-widest text-dim mb-1">Postura inferida</p>
              <p className="text-sm text-mid">{v.inferencia_ia}</p>
            </div>
          )}
          {v.justificativa && (
            <div>
              <p className="text-[10px] uppercase tracking-widest text-dim mb-1">Justificativa da IA</p>
              <p className="text-sm text-mid leading-relaxed">{v.justificativa}</p>
            </div>
          )}
          {v.partido_na_epoca && (
            <p className="text-xs text-dim">Partido na época: <span className="text-mid">{v.partido_na_epoca}</span></p>
          )}
        </div>
      )}
    </>
  );
}

export function VotosTable({ pagina, onPageChange }: { pagina: PaginaVotos; onPageChange: (p: number) => void }) {
  return (
    <div className="rounded-xl border border-white/[0.07] overflow-hidden">
      <div className="grid grid-cols-[1fr_auto_auto_auto_auto] md:grid-cols-[2fr_auto_auto_auto_auto] gap-x-4 px-4 py-2.5 bg-card-alt border-b border-white/[0.07]">
        {["Proposição", "Data", "Voto", "Coerência", ""].map((h, i) => (
          <span
            key={i}
            className={`text-[10px] uppercase tracking-widest text-dim font-medium ${i === 1 || i === 3 ? "hidden md:block" : ""}`}
          >
            {h}
          </span>
        ))}
      </div>

      {pagina.itens.length === 0 ? (
        <div className="py-14 text-center text-mid text-sm bg-card">Nenhuma votação encontrada.</div>
      ) : (
        pagina.itens.map((v) => <VotoRow key={v.id} v={v} />)
      )}

      {pagina.total_paginas > 1 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-white/[0.05] text-xs text-dim bg-card">
          <span>{pagina.total_registros} votações · pág. {pagina.pagina_atual}/{pagina.total_paginas}</span>
          <div className="flex gap-2">
            {[
              { label: "←", page: pagina.pagina_atual - 1, disabled: pagina.pagina_atual === 1 },
              { label: "→", page: pagina.pagina_atual + 1, disabled: pagina.pagina_atual === pagina.total_paginas },
            ].map(({ label, page, disabled }) => (
              <button
                key={label}
                onClick={() => onPageChange(page)}
                disabled={disabled}
                className="px-3 py-1 border border-white/10 rounded-md hover:bg-card-alt disabled:opacity-30 transition-colors"
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
