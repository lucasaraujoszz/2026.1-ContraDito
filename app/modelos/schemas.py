from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date as date_type


class PoliticoDB(BaseModel):
    id: int
    nome_civil: str
    nome_urna: str
    partido: str
    cargo: str
    estado: str
    status_mandato: str
    url_foto: Optional[str] = None
    score_coerencia: Optional[float] = None
    data_ultima_atualizacao: Optional[datetime] = None


class PaginaPoliticosDB(BaseModel):
    total_registros: int
    pagina_atual: int
    tamanho_pagina: int
    total_paginas: int
    itens: List[PoliticoDB]


class PoliticoResumoVotosSchema(BaseModel):
    politico_id: int
    casa: str
    total_votos: int
    qtd_sim: int
    qtd_nao: int
    qtd_ausencia: int
    qtd_abstencao: int
    qtd_obstrucao: int
    qtd_outros: int


class PoliticoDetalhadoDB(BaseModel):
    politico: PoliticoDB
    resumo_votos: Optional[PoliticoResumoVotosSchema] = None


class DiscursoDB(BaseModel):
    id: str  # UUID
    politico_id: Optional[int] = None
    data_discurso: Optional[str] = None
    texto_bruto: str
    url_video: Optional[str] = None
    sumario: Optional[str] = None
    fase_evento: Optional[str] = None


class PaginaDiscursosDB(BaseModel):
    total_registros: int
    pagina_atual: int
    tamanho_pagina: int
    total_paginas: int
    itens: List[DiscursoDB]


class DiscursoChunkDB(BaseModel):
    id: str  # UUID
    discurso_id: str  # UUID
    texto_chunk: str


class ProposicaoDB(BaseModel):
    id: str  # UUID
    proposicao_id: str
    id_camara: Optional[int] = None
    id_senado: Optional[int] = None
    id_votacao_camara: Optional[str] = None
    id_votacao_senado: Optional[int] = None
    tipo: str
    numero: int
    ano: int
    ementa: str
    data_votacao: Optional[date_type] = None
    url_texto_inteiro: Optional[str] = None
    resumo_executivo: Optional[str] = None
    erro_resumo: Optional[str] = None


class PaginaProposicoesDB(BaseModel):
    total_registros: int
    pagina_atual: int
    tamanho_pagina: int
    total_paginas: int
    itens: List[ProposicaoDB]


class VotoDB(BaseModel):
    id: str  # UUID
    proposicao_id: str
    politico_id: int
    partido_na_epoca: Optional[str] = None
    voto_oficial: str
    chunks_proximos: Optional[List[dict]] = None


class PaginaVotosDB(BaseModel):
    total_registros: int
    pagina_atual: int
    tamanho_pagina: int
    total_paginas: int
    itens: List[VotoDB]


class VotoTimelineSchema(BaseModel):
    data_votacao: Optional[date_type] = None
    proposicao_id: str
    tipo: str
    numero: int
    ano: int
    ementa: str
    voto_oficial: str


class DivergenciaVotoSchema(BaseModel):
    proposicao_id: str
    ementa: str
    voto_politico_1: str
    voto_politico_2: str


class ComparacaoResponse(BaseModel):
    concordancia_percentual: float
    proposicoes_em_comum: int
    divergencias: List[DivergenciaVotoSchema]


class AfinidadeSchema(BaseModel):
    politico: PoliticoDB
    concordancia: float
    votos_comuns: int


class AfinidadesResponse(BaseModel):
    gemeo: Optional[AfinidadeSchema] = None
    antipoda: Optional[AfinidadeSchema] = None


class FidelidadeResponse(BaseModel):
    taxa_fidelidade: float
    votos_alinhados: int
    votos_rebeldes: int
    total_votos_com_orientacao: int


class PolarizacaoResponse(BaseModel):
    proposicao_id: str
    qtd_sim: int
    qtd_nao: int
    pct_sim: float
    pct_nao: float
    polarizacao: float
    classificacao: str


class CoesaoPartidoSchema(BaseModel):
    partido: str
    indice_coesao: float


class CoesaoGeralResponse(BaseModel):
    itens: List[CoesaoPartidoSchema]
