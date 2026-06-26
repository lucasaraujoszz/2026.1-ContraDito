"use client";

import { useState, useEffect, useCallback } from "react";
import { getParlamentares } from "@/lib/api";
import type { Filters } from "@/components/FilterBar";
import { FilterBar } from "@/components/FilterBar";
import type { PaginaParlamentares } from "@/lib/types";
import { Hero } from "@/components/Hero";
import { HowItWorks } from "@/components/HowItWorks";
import { DirectoryTable } from "@/components/DirectoryTable";
import { Pagination } from "@/components/Pagination";

export default function HomePage() {
  const [filters, setFilters] = useState<Filters>({
    busca: "", partido: "", estado: "", cargo: "", ordem: "mais_coerentes", incluirSemDados: false,
  });
  const [pagina, setPagina] = useState(1);
  const [data, setData] = useState<PaginaParlamentares | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (f: Filters, p: number) => {
    setLoading(true);
    setError(null);
    try {
      const result = await getParlamentares({
        busca: f.busca || undefined,
        partido: f.partido || undefined,
        estado: f.estado || undefined,
        cargo: f.cargo || undefined,
        ordem: f.ordem || undefined,
        pagina: p,
        tamanho: 20,
      });
      setData(result);
    } catch {
      setError("Não foi possível carregar os parlamentares. Verifique se a API está disponível.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(filters, pagina); }, [filters, pagina, load]);

  const handleFilters = useCallback((f: Filters) => {
    setFilters(f);
    setPagina(1);
  }, []);

  return (
    <div className="pt-14 min-h-screen">
      <Hero />
      <HowItWorks />
      <section className="max-w-7xl mx-auto px-4 sm:px-6 pb-24">
        <FilterBar onChange={handleFilters} />
        {data && !loading && (() => {
          const semDados = data.itens.filter((p) => p.score_coerencia === null).length;
          const ocultos = !filters.incluirSemDados ? semDados : 0;
          return (
            <p className="mt-3 text-xs text-dim">
              {data.total_registros.toLocaleString("pt-BR")} parlamentares
              {filters.busca ? ` para "${filters.busca}"` : ""}
              {ocultos > 0 && (
                <span className="ml-2 text-dim/60">
                  · {ocultos} sem dados suficientes ocultos
                </span>
              )}
            </p>
          );
        })()}
        <DirectoryTable
          loading={loading}
          error={error}
          data={data}
          filters={filters}
          pagina={pagina}
          onRetry={() => load(filters, pagina)}
        />
        {data && data.total_paginas > 1 && (
          <Pagination
            pagina={pagina}
            totalPaginas={data.total_paginas}
            loading={loading}
            onChange={setPagina}
          />
        )}
      </section>
    </div>
  );
}
