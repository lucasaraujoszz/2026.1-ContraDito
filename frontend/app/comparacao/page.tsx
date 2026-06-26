"use client";

import { useState, useEffect, useRef } from "react";
import { Search, X, Swords, AlertTriangle } from "lucide-react";
import { getParlamentares, getTimeline } from "@/lib/api";
import { TendenciaRecente } from "@/components/TendenciaRecente";
import { Avatar } from "@/components/ui/Avatar";
import { ScoreGauge } from "@/components/ui/ScoreBadge";
import { ComparisonChart } from "@/components/CoherenceChart";
import { scoreHex } from "@/lib/utils";
import type { Parlamentar, TimelinePoint } from "@/lib/types";

const ESTADOS = [
  "AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MG","MS","MT",
  "PA","PB","PE","PI","PR","RJ","RN","RO","RR","RS","SC","SE","SP","TO",
];

const PARTIDOS = [
  "AVANTE","DC","DEM","MDB","NOVO","PCdoB","PDT","PL","PMB","PMN",
  "PP","PRD","PRTB","PSB","PSD","PSDB","PSol","PSC","PT","PTB","PTC",
  "Podemos","REDE","Republicanos","SOLIDARIEDADE","UP","Agir",
].sort();

function ParlamentarSelector({
  selected,
  onSelect,
  excludeId,
  accent,
  label,
  partido: partidoInicial = "",
  estado: estadoInicial = "",
}: {
  selected: Parlamentar | null;
  onSelect: (p: Parlamentar | null) => void;
  excludeId?: number;
  accent: string;
  label: string;
  partido?: string;
  estado?: string;
}) {
  const [query, setQuery] = useState("");
  const [partido, setPartido] = useState(partidoInicial);
  const [estado, setEstado] = useState(estadoInicial);
  const [results, setResults] = useState<Parlamentar[]>([]);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (query.length < 2) { setResults([]); return; }
    const t = setTimeout(async () => {
      try {
        const d = await getParlamentares({ busca: query, partido: partido || undefined, estado: estado || undefined, tamanho: 8 });
        setResults(d.itens.filter((p) => p.id !== excludeId));
      } catch { /* silent */ }
    }, 280);
    return () => clearTimeout(t);
  }, [query, excludeId, partido, estado]);

  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  if (selected) {
    const color = scoreHex(selected.score_coerencia);
    return (
      <div className="glass rounded-xl p-6 flex flex-col items-center gap-4 text-center" style={{ borderColor: `${accent}28` }}>
        <p className="text-[10px] uppercase tracking-widest" style={{ color: accent }}>{label}</p>
        <Avatar name={selected.nome_urna} url={selected.url_foto} size={72} ringColor={`${accent}55`} />
        <div>
          <p className="font-display text-xl font-bold text-bright">{selected.nome_urna}</p>
          <p className="text-xs text-dim mt-1">{selected.partido} · {selected.cargo} · {selected.estado}</p>
        </div>
        {selected.dados_insuficientes ? (
          <div className="flex flex-col items-center gap-1.5 py-1">
            <AlertTriangle size={18} className="text-pending" />
            <p className="font-data text-[11px] text-pending text-center leading-snug">
              Dados insuficientes
            </p>
            <p className="text-[10px] text-dim">mín. 3 votos válidos (RF15)</p>
          </div>
        ) : (
          <ScoreGauge score={selected.score_coerencia} size={80} />
        )}
        <button
          onClick={() => onSelect(null)}
          className="text-xs text-dim hover:text-incoherent flex items-center gap-1 transition-colors"
        >
          <X size={11} /> Remover
        </button>
      </div>
    );
  }

  return (
    <div ref={ref} className="relative">
      <div className="glass rounded-xl p-6 flex flex-col items-center gap-4">
        <p className="text-[10px] uppercase tracking-widest" style={{ color: accent }}>{label}</p>
        <div
          className="w-16 h-16 rounded-full border-2 border-dashed flex items-center justify-center"
          style={{ borderColor: `${accent}35` }}
        >
          <Search size={18} style={{ color: accent }} />
        </div>
        <p className="text-sm text-dim">Selecionar parlamentar</p>
        <input
          type="text"
          placeholder="Buscar por nome..."
          value={query}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          className="w-full h-9 px-3 bg-card-alt rounded-lg border border-rim/30 text-sm text-bright placeholder:text-dim focus:outline-none focus:border-pulse/40 transition-colors"
        />

        <div className="flex gap-2 w-full">
          <select
            value={partido}
            onChange={(e) => setPartido(e.target.value)}
            className="flex-1 h-9 px-2 bg-card-alt border border-rim/30 rounded-lg text-sm text-mid focus:outline-none focus:border-pulse/40 transition-colors cursor-pointer"
          >
            <option value="">Partido</option>
            {PARTIDOS.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
          <select
            value={estado}
            onChange={(e) => setEstado(e.target.value)}
            className="w-24 h-9 px-2 bg-card-alt border border-rim/30 rounded-lg text-sm text-mid focus:outline-none focus:border-pulse/40 transition-colors cursor-pointer"
          >
            <option value="">UF</option>
            {ESTADOS.map((e) => <option key={e} value={e}>{e}</option>)}
          </select>
        </div>
      </div>

      {open && results.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-1 glass-elevated rounded-xl overflow-hidden z-20 shadow-2xl">
          {results.map((p) => (
            <button
              key={p.id}
              onClick={() => { onSelect(p); setQuery(""); setOpen(false); }}
              className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-card-alt transition-colors text-left"
            >
              <Avatar name={p.nome_urna} url={p.url_foto} size={32} />
              <div className="flex-1 min-w-0">
                <p className="text-sm text-bright truncate">{p.nome_urna}</p>
                <p className="text-xs text-dim">{p.partido} · {p.estado}</p>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ComparacaoPage() {
  const [polA, setPolA] = useState<Parlamentar | null>(null);
  const [polB, setPolB] = useState<Parlamentar | null>(null);
  const [tlA, setTlA] = useState<TimelinePoint[]>([]);
  const [tlB, setTlB] = useState<TimelinePoint[]>([]);

  useEffect(() => {
    if (polA) getTimeline(polA.id).then(setTlA).catch(() => setTlA([]));
    else setTlA([]);
  }, [polA]);

  useEffect(() => {
    if (polB) getTimeline(polB.id).then(setTlB).catch(() => setTlB([]));
    else setTlB([]);
  }, [polB]);

  const bothSelected = polA && polB;

  return (
    <div className="pt-14 min-h-screen max-w-5xl mx-auto px-4 sm:px-6 pb-24">
      {/* Header */}
      <div className="pt-12 pb-10 text-center">
        <div className="inline-flex items-center gap-2 text-dim mb-3">
          <Swords size={14} />
          <span className="text-[10px] uppercase tracking-[0.25em]">Comparação</span>
        </div>
        <h1 className="font-display text-5xl sm:text-6xl font-bold text-bright">
          Face a Face
        </h1>
        <p className="text-sm text-dim mt-2.5">
          Compare a trajetória de coerência entre dois parlamentares
        </p>
      </div>

      {/* Selectors */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
        <ParlamentarSelector selected={polA} onSelect={setPolA} excludeId={polB?.id} accent="#10b981" label="Parlamentar A" />
        <ParlamentarSelector selected={polB} onSelect={setPolB} excludeId={polA?.id} accent="#5e88ff" label="Parlamentar B" />
      </div>

      {/* Results */}
      {bothSelected ? (
        <div className="mt-10 space-y-6">
          {/* Overlapping chart */}
          <div className="glass rounded-xl p-6">
            <p className="text-[10px] uppercase tracking-[0.2em] text-dim mb-5">
              Evolução Comparada da Coerência
            </p>
            <div className="flex gap-6 mb-4">
              {[
                { name: polA.nome_urna, color: "#10b981" },
                { name: polB.nome_urna, color: "#5e88ff" },
              ].map(({ name, color }) => (
                <div key={name} className="flex items-center gap-2">
                  <div className="w-8 h-[2px] rounded-full" style={{ backgroundColor: color }} />
                  <span className="text-xs text-mid">{name}</span>
                </div>
              ))}
            </div>
            <ComparisonChart dataA={tlA} dataB={tlB} nameA={polA.nome_urna} nameB={polB.nome_urna} />
          </div>

          {/* Score cards */}
          <div className="grid grid-cols-2 gap-4">
            {[
              { pol: polA, accent: "#10b981", label: "Parlamentar A", tl: tlA },
              { pol: polB, accent: "#5e88ff", label: "Parlamentar B", tl: tlB },
            ].map(({ pol, accent, label, tl }) => (
              <div
                key={pol.id}
                className="glass rounded-xl p-6 flex flex-col items-center gap-3 text-center"
                style={{ borderColor: `${accent}22` }}
              >
                <p className="text-[10px] uppercase tracking-widest" style={{ color: accent }}>{label}</p>
                <Avatar name={pol.nome_urna} url={pol.url_foto} size={52} ringColor={`${accent}45`} />
                <div>
                  <p className="font-display text-lg font-bold text-bright">{pol.nome_urna}</p>
                  <p className="text-xs text-dim mt-0.5">{pol.partido} · {pol.estado}</p>
                </div>
                {pol.dados_insuficientes ? (
                  <div className="flex flex-col items-center gap-1.5 py-1">
                    <AlertTriangle size={18} className="text-pending" />
                    <p className="font-data text-[11px] text-pending text-center leading-snug">
                      Dados insuficientes
                    </p>
                    <p className="text-[10px] text-dim">mín. 3 votos válidos (RF15)</p>
                  </div>
                ) : (
                  <ScoreGauge score={pol.score_coerencia} size={72} />
                )}
                {tl.length > 0 && <TendenciaRecente points={tl} />}
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="mt-10 text-center">
          <p className="text-dim text-sm">Selecione dois parlamentares para iniciar a comparação</p>
        </div>
      )}
    </div>
  );
}
