"use client";

import { useState, useCallback } from "react";
import { Search, X } from "lucide-react";

export type Filters = {
  busca: string;
  partido: string;
  estado: string;
  cargo: string;
  ordem: string;
  incluirSemDados: boolean;
};

const ESTADOS = [
  "AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MG","MS","MT",
  "PA","PB","PE","PI","PR","RJ","RN","RO","RR","RS","SC","SE","SP","TO",
];

const PARTIDOS = [
  "AVANTE","DC","DEM","MDB","NOVO","PCdoB","PDT","PL","PMB","PMN",
  "PP","PRD","PRTB","PSB","PSD","PSDB","PSol","PSC","PT","PTB","PTC",
  "Podemos","REDE","Republicanos","SOLIDARIEDADE","UP","Agir",
].sort();

const SELECT_CLASS =
  "h-10 px-3 bg-card border border-rim/30 rounded-lg text-sm text-mid focus:outline-none focus:border-pulse/40 transition-colors cursor-pointer";

interface FilterBarProps {
  onChange: (f: Filters) => void;
}

export function FilterBar({ onChange }: FilterBarProps) {
  const [f, setF] = useState<Filters>({
    busca: "", partido: "", estado: "", cargo: "", ordem: "mais_coerentes", incluirSemDados: false,
  });

  const update = useCallback(
    (key: keyof Filters, value: string | boolean) => {
      const next = { ...f, [key]: value };
      setF(next);
      onChange(next);
    },
    [f, onChange]
  );

  return (
    <div className="flex flex-col sm:flex-row gap-2.5">
      <div className="relative flex-1">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-dim pointer-events-none" />
        <input
          type="text"
          placeholder="Buscar parlamentar..."
          value={f.busca}
          onChange={(e) => update("busca", e.target.value)}
          className="w-full h-10 pl-9 pr-9 bg-card border border-rim/30 rounded-lg text-sm text-bright placeholder:text-dim focus:outline-none focus:border-pulse/40 transition-colors"
        />
        {f.busca && (
          <button
            onClick={() => update("busca", "")}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-dim hover:text-mid"
          >
            <X size={13} />
          </button>
        )}
      </div>

      <select value={f.partido} onChange={(e) => update("partido", e.target.value)} className={SELECT_CLASS}>
        <option value="">Partido</option>
        {PARTIDOS.map((p) => <option key={p} value={p}>{p}</option>)}
      </select>

      <select value={f.estado} onChange={(e) => update("estado", e.target.value)} className={SELECT_CLASS}>
        <option value="">UF</option>
        {ESTADOS.map((e) => <option key={e} value={e}>{e}</option>)}
      </select>

      <select value={f.ordem} onChange={(e) => update("ordem", e.target.value)} className={SELECT_CLASS}>
        <option value="">Ordenar</option>
        <option value="mais_coerentes">Maior Score</option>
        <option value="menos_coerentes">Menor Score</option>
      </select>

      <button
        type="button"
        onClick={() => update("incluirSemDados", !f.incluirSemDados)}
        title="Parlamentares com menos de 3 votações analisadas ficam ocultos por padrão"
        className={`h-10 px-3 rounded-lg border text-xs font-medium flex-shrink-0 transition-colors ${
          f.incluirSemDados
            ? "border-pulse/40 bg-pulse/10 text-pulse"
            : "border-rim/30 bg-card text-dim hover:text-mid"
        }`}
      >
        Sem dados
      </button>
    </div>
  );
}
