export type Parlamentar = {
  id: number;
  nome_civil: string;
  nome_urna: string;
  cargo: string;
  partido: string;
  estado: string;
  url_foto: string | null;
  status_mandato: string;
  dados_insuficientes: boolean;
  score_coerencia: number | null;
  data_ultima_atualizacao: string;
};

export type PaginaParlamentares = {
  total_registros: number;
  pagina_atual: number;
  tamanho_pagina: number;
  total_paginas: number;
  itens: Parlamentar[];
};

export type Voto = {
  id: string;
  proposicao_id: string;
  tipo: string;
  numero: number;
  ano: number;
  ementa: string | null;
  data_votacao: string;
  voto_oficial: string;
  inferencia_ia: string | null;
  justificativa: string | null;
  eh_coerente: boolean | null;
  partido_na_epoca: string | null;
};

export type PaginaVotos = {
  total_registros: number;
  pagina_atual: number;
  tamanho_pagina: number;
  total_paginas: number;
  itens: Voto[];
};

export type TimelinePoint = {
  data_votacao: string;
  eh_coerente: boolean;
  proposicao_id: string;
  tipo: string;
  numero: number;
  ano: number;
};

export type TimelinePointComputed = TimelinePoint & {
  score: number;
  index: number;
};

export type ParlamentarSimilar = {
  id: number;
  nome_urna: string;
  partido: string;
  estado: string;
  url_foto: string | null;
  score_coerencia: number | null;
  percentual_concordancia: number;
  votos_em_comum: number;
};
