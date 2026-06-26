import type {
  PaginaParlamentares,
  Parlamentar,
  PaginaVotos,
  TimelinePoint,
  ParlamentarSimilar,
} from "./types";
import type { ParlamentaresParams } from "./api";

const FOTO = (id: number) =>
  `https://www.camara.leg.br/internet/deputado/bandep/${id}.jpg`;

export const MOCK_POLITICOS: Parlamentar[] = [
  {
    id: 204468,
    nome_civil: "Nikolas Ferreira da Costa",
    nome_urna: "Nikolas Ferreira",
    cargo: "Deputado Federal",
    partido: "PL",
    estado: "MG",
    url_foto: FOTO(204468),
    status_mandato: "Em Exercício",
    dados_insuficientes: false,
    score_coerencia: 75.0,
    data_ultima_atualizacao: "2025-05-01T10:00:00Z",
  },
  {
    id: 204529,
    nome_civil: "Tábata Almeida Amaral",
    nome_urna: "Tabata Amaral",
    cargo: "Deputada Federal",
    partido: "PSB",
    estado: "SP",
    url_foto: FOTO(204529),
    status_mandato: "Em Exercício",
    dados_insuficientes: false,
    score_coerencia: 83.3,
    data_ultima_atualizacao: "2025-05-01T10:00:00Z",
  },
  {
    id: 73433,
    nome_civil: "Gleisi Helena Hoffmann",
    nome_urna: "Gleisi Hoffmann",
    cargo: "Deputada Federal",
    partido: "PT",
    estado: "PR",
    url_foto: FOTO(73433),
    status_mandato: "Em Exercício",
    dados_insuficientes: false,
    score_coerencia: 91.7,
    data_ultima_atualizacao: "2025-05-01T10:00:00Z",
  },
  {
    id: 204554,
    nome_civil: "Eduardo Bolsonaro",
    nome_urna: "Eduardo Bolsonaro",
    cargo: "Deputado Federal",
    partido: "PL",
    estado: "SP",
    url_foto: FOTO(204554),
    status_mandato: "Em Exercício",
    dados_insuficientes: false,
    score_coerencia: 41.7,
    data_ultima_atualizacao: "2025-05-01T10:00:00Z",
  },
  {
    id: 178966,
    nome_civil: "Arthur César Pereira de Lira",
    nome_urna: "Arthur Lira",
    cargo: "Deputado Federal",
    partido: "PP",
    estado: "AL",
    url_foto: FOTO(178966),
    status_mandato: "Em Exercício",
    dados_insuficientes: false,
    score_coerencia: 50.0,
    data_ultima_atualizacao: "2025-05-01T10:00:00Z",
  },
  {
    id: 141428,
    nome_civil: "Marcel Rogério Van Hattem",
    nome_urna: "Marcel Van Hattem",
    cargo: "Deputado Federal",
    partido: "NOVO",
    estado: "RS",
    url_foto: FOTO(141428),
    status_mandato: "Em Exercício",
    dados_insuficientes: false,
    score_coerencia: 66.7,
    data_ultima_atualizacao: "2025-05-01T10:00:00Z",
  },
  {
    id: 178959,
    nome_civil: "Kim Paim Kataguiri",
    nome_urna: "Kim Kataguiri",
    cargo: "Deputado Federal",
    partido: "Podemos",
    estado: "SP",
    url_foto: FOTO(178959),
    status_mandato: "Em Exercício",
    dados_insuficientes: false,
    score_coerencia: 58.3,
    data_ultima_atualizacao: "2025-05-01T10:00:00Z",
  },
  {
    id: 220553,
    nome_civil: "Sâmia Bomfim Costa Bonfim",
    nome_urna: "Sâmia Bomfim",
    cargo: "Deputada Federal",
    partido: "PSol",
    estado: "SP",
    url_foto: FOTO(220553),
    status_mandato: "Em Exercício",
    dados_insuficientes: false,
    score_coerencia: 100.0,
    data_ultima_atualizacao: "2025-05-01T10:00:00Z",
  },
  {
    id: 205571,
    nome_civil: "General Walter Souza Braga Netto",
    nome_urna: "General Braga Netto",
    cargo: "Deputado Federal",
    partido: "PL",
    estado: "RJ",
    url_foto: null,
    status_mandato: "Em Exercício",
    dados_insuficientes: false,
    score_coerencia: 33.3,
    data_ultima_atualizacao: "2025-05-01T10:00:00Z",
  },
  {
    id: 160508,
    nome_civil: "Felipe Rigoni Martins",
    nome_urna: "Felipe Rigoni",
    cargo: "Deputado Federal",
    partido: "PSB",
    estado: "ES",
    url_foto: FOTO(160508),
    status_mandato: "Em Exercício",
    dados_insuficientes: true,
    score_coerencia: null,
    data_ultima_atualizacao: "2025-05-01T10:00:00Z",
  },
];

// ─── Proposições mock ────────────────────────────────────────────────────────

const PROPOSICOES = [
  { id: "PL-1088-2023", tipo: "PL", numero: 1088, ano: 2023, ementa: "Reforma tributária — unificação do IBS e CBS sobre consumo" },
  { id: "PEC-006-2023", tipo: "PEC", numero: 6, ano: 2023, ementa: "Emenda constitucional de reforma tributária" },
  { id: "PL-2630-2023", tipo: "PL", numero: 2630, ano: 2023, ementa: "Regulamentação das plataformas digitais (PL das Fake News)" },
  { id: "PL-4173-2023", tipo: "PL", numero: 4173, ano: 2023, ementa: "Regulamenta o mercado de apostas esportivas (Lei das Bets)" },
  { id: "PL-1026-2024", tipo: "PL", numero: 1026, ano: 2024, ementa: "Imposto seletivo sobre produtos nocivos à saúde" },
  { id: "PEC-003-2024", tipo: "PEC", numero: 3, ano: 2024, ementa: "Voto impresso auditável em eleições" },
  { id: "PL-0872-2024", tipo: "PL", numero: 872, ano: 2024, ementa: "Marco legal dos agrotóxicos — novo modelo de licenciamento" },
  { id: "PL-3399-2024", tipo: "PL", numero: 3399, ano: 2024, ementa: "Criminalização do aborto até o 9º mês equiparado ao homicídio" },
  { id: "PL-0001-2025", tipo: "PL", numero: 1, ano: 2025, ementa: "Alteração da taxa de juros do crédito rotativo do cartão" },
  { id: "PL-0555-2025", tipo: "PL", numero: 555, ano: 2025, ementa: "Regulamentação da inteligência artificial no setor público" },
  { id: "PL-0777-2025", tipo: "PL", numero: 777, ano: 2025, ementa: "Pacote fiscal de contenção de gastos — corte de benefícios" },
  { id: "PEC-015-2025", tipo: "PEC", numero: 15, ano: 2025, ementa: "Emenda constitucional sobre licença-maternidade e paternidade" },
];

// ─── Votos mock por político ─────────────────────────────────────────────────

type MockVoto = {
  proposicao_id: string;
  voto_oficial: string;
  inferencia_ia: string;
  justificativa: string;
  eh_coerente: boolean | null;
  partido_na_epoca: string;
};

const VOTOS_POR_POLITICO: Record<number, MockVoto[]> = {
  // Rigoni (160508) — 10 ausências, 2 votos efetivos → score null (RF15)
  160508: [
    { proposicao_id: "PL-1088-2023", voto_oficial: "Ausente", inferencia_ia: "A Favor", justificativa: null as unknown as string, eh_coerente: null, partido_na_epoca: "PSB" },
    { proposicao_id: "PEC-006-2023", voto_oficial: "Ausente", inferencia_ia: "A Favor", justificativa: null as unknown as string, eh_coerente: null, partido_na_epoca: "PSB" },
    { proposicao_id: "PL-2630-2023", voto_oficial: "Ausente", inferencia_ia: "A Favor", justificativa: null as unknown as string, eh_coerente: null, partido_na_epoca: "PSB" },
    { proposicao_id: "PL-4173-2023", voto_oficial: "Ausente", inferencia_ia: "Contra",  justificativa: null as unknown as string, eh_coerente: null, partido_na_epoca: "PSB" },
    { proposicao_id: "PL-1026-2024", voto_oficial: "Ausente", inferencia_ia: "A Favor", justificativa: null as unknown as string, eh_coerente: null, partido_na_epoca: "PSB" },
    { proposicao_id: "PEC-003-2024", voto_oficial: "Ausente", inferencia_ia: "Contra",  justificativa: null as unknown as string, eh_coerente: null, partido_na_epoca: "PSB" },
    { proposicao_id: "PL-0872-2024", voto_oficial: "Ausente", inferencia_ia: "Contra",  justificativa: null as unknown as string, eh_coerente: null, partido_na_epoca: "PSB" },
    { proposicao_id: "PL-3399-2024", voto_oficial: "Ausente", inferencia_ia: "Contra",  justificativa: null as unknown as string, eh_coerente: null, partido_na_epoca: "PSB" },
    { proposicao_id: "PL-0001-2025", voto_oficial: "Ausente", inferencia_ia: "A Favor", justificativa: null as unknown as string, eh_coerente: null, partido_na_epoca: "PSB" },
    { proposicao_id: "PL-0555-2025", voto_oficial: "Ausente", inferencia_ia: "A Favor", justificativa: null as unknown as string, eh_coerente: null, partido_na_epoca: "PSB" },
    { proposicao_id: "PL-0777-2025", voto_oficial: "Sim",     inferencia_ia: "A Favor", justificativa: "Apoiou o pacote fiscal em única participação registrada no semestre.", eh_coerente: true,  partido_na_epoca: "PSB" },
    { proposicao_id: "PEC-015-2025", voto_oficial: "Não",     inferencia_ia: "A Favor", justificativa: "Apesar de declarações favoráveis à licença-parental, votou contra o texto.", eh_coerente: false, partido_na_epoca: "PSB" },
  ],
  // Sâmia Bomfim (220553) — 12/12 coerentes = 100.0%
  220553: [
    { proposicao_id: "PL-1088-2023", voto_oficial: "Sim", inferencia_ia: "A Favor", justificativa: "Defendeu a reforma como medida de justiça fiscal e redistribuição de renda.", eh_coerente: true,  partido_na_epoca: "PSol" },
    { proposicao_id: "PEC-006-2023", voto_oficial: "Sim", inferencia_ia: "A Favor", justificativa: "Votação consistente com apoio irrestrito à reforma tributária constitucional.", eh_coerente: true,  partido_na_epoca: "PSol" },
    { proposicao_id: "PL-2630-2023", voto_oficial: "Sim", inferencia_ia: "A Favor", justificativa: "Liderou campanha pelo projeto, classificando-o como essencial ao combate à desinformação.", eh_coerente: true,  partido_na_epoca: "PSol" },
    { proposicao_id: "PL-4173-2023", voto_oficial: "Não", inferencia_ia: "Contra",  justificativa: "Posicionou-se contra a regulamentação das bets por impacto nas famílias pobres.", eh_coerente: true,  partido_na_epoca: "PSol" },
    { proposicao_id: "PL-1026-2024", voto_oficial: "Sim", inferencia_ia: "A Favor", justificativa: "Defendeu o imposto seletivo como instrumento de saúde pública.", eh_coerente: true,  partido_na_epoca: "PSol" },
    { proposicao_id: "PEC-003-2024", voto_oficial: "Não", inferencia_ia: "Contra",  justificativa: "Classificou o voto impresso como desnecessário e oneroso ao erário.", eh_coerente: true,  partido_na_epoca: "PSol" },
    { proposicao_id: "PL-0872-2024", voto_oficial: "Não", inferencia_ia: "Contra",  justificativa: "Integrante da frente parlamentar anti-veneno, votou coerentemente contra o projeto.", eh_coerente: true,  partido_na_epoca: "PSol" },
    { proposicao_id: "PL-3399-2024", voto_oficial: "Não", inferencia_ia: "Contra",  justificativa: "Uma das mais vocais opositoras, comparando o projeto a retrocesso medieval.", eh_coerente: true,  partido_na_epoca: "PSol" },
    { proposicao_id: "PL-0001-2025", voto_oficial: "Sim", inferencia_ia: "A Favor", justificativa: "Defendeu o limite dos juros rotativos como proteção ao consumidor endividado.", eh_coerente: true,  partido_na_epoca: "PSol" },
    { proposicao_id: "PL-0555-2025", voto_oficial: "Sim", inferencia_ia: "A Favor", justificativa: "Apoiou a regulamentação da IA com ênfase em direitos trabalhistas e privacidade.", eh_coerente: true,  partido_na_epoca: "PSol" },
    { proposicao_id: "PL-0777-2025", voto_oficial: "Não", inferencia_ia: "Contra",  justificativa: "Criticou o pacote fiscal como ataque aos direitos sociais conquistados.", eh_coerente: true,  partido_na_epoca: "PSol" },
    { proposicao_id: "PEC-015-2025", voto_oficial: "Sim", inferencia_ia: "A Favor", justificativa: "Autora de emenda ampliando a licença; votação plenamente alinhada com sua atuação.", eh_coerente: true,  partido_na_epoca: "PSol" },
  ],
  // Gleisi Hoffmann (73433) — 11/12 coerentes = 91.7%
  73433: [
    { proposicao_id: "PL-1088-2023", voto_oficial: "Sim", inferencia_ia: "A Favor", justificativa: "Defendeu a reforma como pauta central do governo Lula.", eh_coerente: true,  partido_na_epoca: "PT" },
    { proposicao_id: "PEC-006-2023", voto_oficial: "Sim", inferencia_ia: "A Favor", justificativa: "Votação alinhada com a posição oficial do PT e do governo federal.", eh_coerente: true,  partido_na_epoca: "PT" },
    { proposicao_id: "PL-2630-2023", voto_oficial: "Sim", inferencia_ia: "A Favor", justificativa: "Apoiou o projeto como medida necessária contra o ecossistema de desinformação.", eh_coerente: true,  partido_na_epoca: "PT" },
    { proposicao_id: "PL-4173-2023", voto_oficial: "Não", inferencia_ia: "Contra",  justificativa: "Contrária à regulamentação das bets por impacto na população vulnerável.", eh_coerente: true,  partido_na_epoca: "PT" },
    { proposicao_id: "PL-1026-2024", voto_oficial: "Sim", inferencia_ia: "A Favor", justificativa: "Apoiou o imposto seletivo como política de saúde pública e tributação justa.", eh_coerente: true,  partido_na_epoca: "PT" },
    { proposicao_id: "PEC-003-2024", voto_oficial: "Não", inferencia_ia: "Contra",  justificativa: "Classificou a PEC como instrumento de desestabilização eleitoral.", eh_coerente: true,  partido_na_epoca: "PT" },
    { proposicao_id: "PL-0872-2024", voto_oficial: "Não", inferencia_ia: "Contra",  justificativa: "Votação coerente com o discurso de proteção ao meio ambiente e à saúde pública.", eh_coerente: true,  partido_na_epoca: "PT" },
    { proposicao_id: "PL-3399-2024", voto_oficial: "Não", inferencia_ia: "Contra",  justificativa: "Líder da bancada contrária, votou em linha com sua posição histórica.", eh_coerente: true,  partido_na_epoca: "PT" },
    { proposicao_id: "PL-0001-2025", voto_oficial: "Sim", inferencia_ia: "A Favor", justificativa: "Defendeu o teto de juros como vitória do governo para o consumidor.", eh_coerente: true,  partido_na_epoca: "PT" },
    { proposicao_id: "PL-0555-2025", voto_oficial: "Sim", inferencia_ia: "A Favor", justificativa: "Apoiou a regulamentação com ênfase na soberania digital nacional.", eh_coerente: true,  partido_na_epoca: "PT" },
    { proposicao_id: "PL-0777-2025", voto_oficial: "Não", inferencia_ia: "Contra",  justificativa: "Liderou a oposição ao pacote, classificando-o como corte de direitos sociais.", eh_coerente: true,  partido_na_epoca: "PT" },
    { proposicao_id: "PEC-015-2025", voto_oficial: "Não", inferencia_ia: "A Favor", justificativa: "Apoiou publicamente a proposta mas votou contra por discordância de texto substitutivo.", eh_coerente: false, partido_na_epoca: "PT" },
  ],
  // Tabata Amaral (204529) — 10/12 coerentes = 83.3%
  204529: [
    { proposicao_id: "PL-1088-2023", voto_oficial: "Sim", inferencia_ia: "A Favor", justificativa: "Defendeu a reforma tributária como pauta de justiça fiscal.", eh_coerente: true,  partido_na_epoca: "PSB" },
    { proposicao_id: "PEC-006-2023", voto_oficial: "Sim", inferencia_ia: "A Favor", justificativa: "Votação alinhada com discursos de apoio à emenda constitucional.", eh_coerente: true,  partido_na_epoca: "PSB" },
    { proposicao_id: "PL-2630-2023", voto_oficial: "Sim", inferencia_ia: "A Favor", justificativa: "Apoiou o projeto afirmando ser necessário para combater desinformação.", eh_coerente: true,  partido_na_epoca: "PSB" },
    { proposicao_id: "PL-4173-2023", voto_oficial: "Sim", inferencia_ia: "Contra",  justificativa: "Apesar de declarações contrárias às apostas, votou a favor da regulamentação após negociação.", eh_coerente: false, partido_na_epoca: "PSB" },
    { proposicao_id: "PL-1026-2024", voto_oficial: "Sim", inferencia_ia: "A Favor", justificativa: "Apoiou a tributação de produtos nocivos à saúde.", eh_coerente: true,  partido_na_epoca: "PSB" },
    { proposicao_id: "PEC-003-2024", voto_oficial: "Não", inferencia_ia: "Contra",  justificativa: "Criticou a proposta como desnecessária e onerosa para o processo eleitoral.", eh_coerente: true,  partido_na_epoca: "PSB" },
    { proposicao_id: "PL-0872-2024", voto_oficial: "Não", inferencia_ia: "Contra",  justificativa: "Manifestou-se contra o afrouxamento das regras de agrotóxicos.", eh_coerente: true,  partido_na_epoca: "PSB" },
    { proposicao_id: "PL-3399-2024", voto_oficial: "Não", inferencia_ia: "Contra",  justificativa: "Uma das líderes da oposição à proposta, declarando-a inconstitucional.", eh_coerente: true,  partido_na_epoca: "PSB" },
    { proposicao_id: "PL-0001-2025", voto_oficial: "Sim", inferencia_ia: "A Favor", justificativa: "Defendeu o limite dos juros rotativos como proteção ao consumidor.", eh_coerente: true,  partido_na_epoca: "PSB" },
    { proposicao_id: "PL-0555-2025", voto_oficial: "Sim", inferencia_ia: "A Favor", justificativa: "Propôs emendas ao texto e votou a favor da regulamentação.", eh_coerente: true,  partido_na_epoca: "PSB" },
    { proposicao_id: "PL-0777-2025", voto_oficial: "Não", inferencia_ia: "Contra",  justificativa: "Criticou o pacote fiscal como prejudicial à classe trabalhadora.", eh_coerente: true,  partido_na_epoca: "PSB" },
    { proposicao_id: "PEC-015-2025", voto_oficial: "Sim", inferencia_ia: "Contra",  justificativa: "Considerou o texto insuficiente em discursos, mas votou sim após pressão da bancada.", eh_coerente: false, partido_na_epoca: "PSB" },
  ],
  // Nikolas Ferreira (204468) — 9/12 coerentes = 75.0%
  204468: [
    { proposicao_id: "PL-1088-2023", voto_oficial: "Sim", inferencia_ia: "A Favor",  justificativa: "Defendeu simplificação tributária em discurso de março/2023.", eh_coerente: true,  partido_na_epoca: "PL" },
    { proposicao_id: "PEC-006-2023", voto_oficial: "Sim", inferencia_ia: "A Favor",  justificativa: "Apoiou publicamente a reforma tributária em entrevistas ao longo de 2023.", eh_coerente: true,  partido_na_epoca: "PL" },
    { proposicao_id: "PL-2630-2023", voto_oficial: "Não", inferencia_ia: "Contra",   justificativa: "Criticou o projeto em plenário, chamando-o de censura à liberdade de expressão.", eh_coerente: true,  partido_na_epoca: "PL" },
    { proposicao_id: "PL-4173-2023", voto_oficial: "Sim", inferencia_ia: "Contra",   justificativa: "Apesar de discurso contrário às apostas, votou a favor da regulamentação.", eh_coerente: false, partido_na_epoca: "PL" },
    { proposicao_id: "PL-1026-2024", voto_oficial: "Não", inferencia_ia: "Contra",   justificativa: "Posicionou-se contra novos tributos em diversas falas no primeiro semestre de 2024.", eh_coerente: true,  partido_na_epoca: "PL" },
    { proposicao_id: "PEC-003-2024", voto_oficial: "Sim", inferencia_ia: "A Favor",  justificativa: "Defendeu o voto impresso como garantia democrática em pelo menos três pronunciamentos.", eh_coerente: true,  partido_na_epoca: "PL" },
    { proposicao_id: "PL-0872-2024", voto_oficial: "Sim", inferencia_ia: "A Favor",  justificativa: "Apoiou a modernização do licenciamento de defensivos agrícolas.", eh_coerente: true,  partido_na_epoca: "PL" },
    { proposicao_id: "PL-3399-2024", voto_oficial: "Sim", inferencia_ia: "A Favor",  justificativa: "Declarou-se veementemente a favor da proposta em pronunciamento de agosto/2024.", eh_coerente: true,  partido_na_epoca: "PL" },
    { proposicao_id: "PL-0001-2025", voto_oficial: "Não", inferencia_ia: "A Favor",  justificativa: "Apesar de defender redução do custo do crédito, votou contra o mecanismo proposto.", eh_coerente: false, partido_na_epoca: "PL" },
    { proposicao_id: "PL-0555-2025", voto_oficial: "Não", inferencia_ia: "A Favor",  justificativa: "Expressou apoio à regulamentação da IA mas votou contra o texto final.", eh_coerente: false, partido_na_epoca: "PL" },
    { proposicao_id: "PL-0777-2025", voto_oficial: "Sim", inferencia_ia: "A Favor",  justificativa: "Apoiou corte de gastos como forma de equilíbrio fiscal.", eh_coerente: true,  partido_na_epoca: "PL" },
    { proposicao_id: "PEC-015-2025", voto_oficial: "Sim", inferencia_ia: "A Favor",  justificativa: "Manifestou apoio à ampliação da licença-parental em pronunciamento.", eh_coerente: true,  partido_na_epoca: "PL" },
  ],
  // Marcel Van Hattem (141428) — 8/12 coerentes = 66.7%
  141428: [
    { proposicao_id: "PL-1088-2023", voto_oficial: "Não", inferencia_ia: "Contra",  justificativa: "Criticou a reforma como aumento disfarçado da carga tributária.", eh_coerente: true,  partido_na_epoca: "NOVO" },
    { proposicao_id: "PEC-006-2023", voto_oficial: "Não", inferencia_ia: "Contra",  justificativa: "Votação consistente com postura contrária à intervenção constitucional no sistema tributário.", eh_coerente: true,  partido_na_epoca: "NOVO" },
    { proposicao_id: "PL-2630-2023", voto_oficial: "Não", inferencia_ia: "Contra",  justificativa: "Classificou o projeto como censura estatal e ameaça à liberdade de expressão.", eh_coerente: true,  partido_na_epoca: "NOVO" },
    { proposicao_id: "PL-4173-2023", voto_oficial: "Sim", inferencia_ia: "A Favor", justificativa: "Defensor da liberdade de mercado, apoiou a regulamentação sem proibição.", eh_coerente: true,  partido_na_epoca: "NOVO" },
    { proposicao_id: "PL-1026-2024", voto_oficial: "Não", inferencia_ia: "Contra",  justificativa: "Contrário à criação de novos impostos, votou consistentemente contra.", eh_coerente: true,  partido_na_epoca: "NOVO" },
    { proposicao_id: "PEC-003-2024", voto_oficial: "Sim", inferencia_ia: "A Favor", justificativa: "Defensor da transparência eleitoral, apoiou o voto impresso.", eh_coerente: true,  partido_na_epoca: "NOVO" },
    { proposicao_id: "PL-0872-2024", voto_oficial: "Sim", inferencia_ia: "Contra",  justificativa: "Declarou-se contra o projeto mas cedeu a pressões do setor agrícola no voto final.", eh_coerente: false, partido_na_epoca: "NOVO" },
    { proposicao_id: "PL-3399-2024", voto_oficial: "Não", inferencia_ia: "A Favor", justificativa: "Expressou apoio ao texto em discurso mas votou contra após críticas ao artigo 3º.", eh_coerente: false, partido_na_epoca: "NOVO" },
    { proposicao_id: "PL-0001-2025", voto_oficial: "Não", inferencia_ia: "Contra",  justificativa: "Contrário à interferência do Estado no mercado de crédito; voto consistente.", eh_coerente: true,  partido_na_epoca: "NOVO" },
    { proposicao_id: "PL-0555-2025", voto_oficial: "Não", inferencia_ia: "Contra",  justificativa: "Opôs-se à regulamentação estatal da IA como limitação à inovação privada.", eh_coerente: true,  partido_na_epoca: "NOVO" },
    { proposicao_id: "PL-0777-2025", voto_oficial: "Sim", inferencia_ia: "Contra",  justificativa: "Discursou contra o modelo do pacote mas votou a favor para não bloquear os cortes.", eh_coerente: false, partido_na_epoca: "NOVO" },
    { proposicao_id: "PEC-015-2025", voto_oficial: "Não", inferencia_ia: "A Favor", justificativa: "Declarou apoio à licença-parental ampliada mas rejeitou o texto por questões de custeio.", eh_coerente: false, partido_na_epoca: "NOVO" },
  ],
  // Kim Kataguiri (178959) — 7/12 coerentes = 58.3%
  178959: [
    { proposicao_id: "PL-1088-2023", voto_oficial: "Sim", inferencia_ia: "A Favor", justificativa: "Apoiou a reforma como medida de modernização do sistema fiscal.", eh_coerente: true,  partido_na_epoca: "Podemos" },
    { proposicao_id: "PEC-006-2023", voto_oficial: "Sim", inferencia_ia: "A Favor", justificativa: "Votação alinhada com posicionamento favorável à emenda constitucional.", eh_coerente: true,  partido_na_epoca: "Podemos" },
    { proposicao_id: "PL-2630-2023", voto_oficial: "Sim", inferencia_ia: "Contra",  justificativa: "Criticou o projeto em discursos mas votou a favor sob pressão da bancada.", eh_coerente: false, partido_na_epoca: "Podemos" },
    { proposicao_id: "PL-4173-2023", voto_oficial: "Não", inferencia_ia: "Contra",  justificativa: "Posicionou-se contra a regulamentação das apostas por risco de dependência.", eh_coerente: true,  partido_na_epoca: "Podemos" },
    { proposicao_id: "PL-1026-2024", voto_oficial: "Sim", inferencia_ia: "Contra",  justificativa: "Disse ser contra novos tributos mas votou a favor do imposto seletivo.", eh_coerente: false, partido_na_epoca: "Podemos" },
    { proposicao_id: "PEC-003-2024", voto_oficial: "Não", inferencia_ia: "Contra",  justificativa: "Classificou o voto impresso como medida desnecessária e custosa.", eh_coerente: true,  partido_na_epoca: "Podemos" },
    { proposicao_id: "PL-0872-2024", voto_oficial: "Não", inferencia_ia: "A Favor", justificativa: "Declarou-se favorável à modernização do licenciamento mas votou contra o texto.", eh_coerente: false, partido_na_epoca: "Podemos" },
    { proposicao_id: "PL-3399-2024", voto_oficial: "Não", inferencia_ia: "Contra",  justificativa: "Contrário à criminalização do aborto; votou coerentemente contra.", eh_coerente: true,  partido_na_epoca: "Podemos" },
    { proposicao_id: "PL-0001-2025", voto_oficial: "Sim", inferencia_ia: "A Favor", justificativa: "Defendeu o limite de juros como medida de proteção ao consumidor.", eh_coerente: true,  partido_na_epoca: "Podemos" },
    { proposicao_id: "PL-0555-2025", voto_oficial: "Sim", inferencia_ia: "A Favor", justificativa: "Apoiou a regulamentação da IA com ênfase em segurança dos dados.", eh_coerente: true,  partido_na_epoca: "Podemos" },
    { proposicao_id: "PL-0777-2025", voto_oficial: "Não", inferencia_ia: "A Favor", justificativa: "Declarou apoio ao ajuste fiscal mas votou contra o pacote por discordar dos cortes.", eh_coerente: false, partido_na_epoca: "Podemos" },
    { proposicao_id: "PEC-015-2025", voto_oficial: "Sim", inferencia_ia: "Contra",  justificativa: "Disse ser contra a PEC por custo fiscal mas cedeu à votação partidária.", eh_coerente: false, partido_na_epoca: "Podemos" },
  ],
  // Arthur Lira (178966) — 6/12 coerentes = 50.0%
  178966: [
    { proposicao_id: "PL-1088-2023", voto_oficial: "Sim", inferencia_ia: "A Favor", justificativa: "Apoiou a reforma como parceiro do governo na Câmara.", eh_coerente: true,  partido_na_epoca: "PP" },
    { proposicao_id: "PEC-006-2023", voto_oficial: "Sim", inferencia_ia: "A Favor", justificativa: "Votação alinhada com o acordo político firmado com o governo federal.", eh_coerente: true,  partido_na_epoca: "PP" },
    { proposicao_id: "PL-2630-2023", voto_oficial: "Não", inferencia_ia: "A Favor", justificativa: "Declarou-se favorável ao projeto mas votou contra após pressão da bancada conservadora.", eh_coerente: false, partido_na_epoca: "PP" },
    { proposicao_id: "PL-4173-2023", voto_oficial: "Sim", inferencia_ia: "Contra",  justificativa: "Disse ser contrário à regulamentação das apostas mas votou a favor em acordo parlamentar.", eh_coerente: false, partido_na_epoca: "PP" },
    { proposicao_id: "PL-1026-2024", voto_oficial: "Não", inferencia_ia: "A Favor", justificativa: "Expressou apoio ao imposto seletivo em público mas votou contra no plenário.", eh_coerente: false, partido_na_epoca: "PP" },
    { proposicao_id: "PEC-003-2024", voto_oficial: "Sim", inferencia_ia: "Contra",  justificativa: "Posicionou-se contra o voto impresso mas votou a favor para manter aliança.", eh_coerente: false, partido_na_epoca: "PP" },
    { proposicao_id: "PL-0872-2024", voto_oficial: "Sim", inferencia_ia: "A Favor", justificativa: "Aliado histórico do agronegócio, votou em linha com sua bancada.", eh_coerente: true,  partido_na_epoca: "PP" },
    { proposicao_id: "PL-3399-2024", voto_oficial: "Não", inferencia_ia: "A Favor", justificativa: "Declarou apoio à proposta mas votou contra para evitar desgaste político.", eh_coerente: false, partido_na_epoca: "PP" },
    { proposicao_id: "PL-0001-2025", voto_oficial: "Sim", inferencia_ia: "A Favor", justificativa: "Apoiou o limite de juros em acordo com o governo.", eh_coerente: true,  partido_na_epoca: "PP" },
    { proposicao_id: "PL-0555-2025", voto_oficial: "Sim", inferencia_ia: "A Favor", justificativa: "Votação consistente com apoio declarado à regulamentação responsável da IA.", eh_coerente: true,  partido_na_epoca: "PP" },
    { proposicao_id: "PL-0777-2025", voto_oficial: "Sim", inferencia_ia: "A Favor", justificativa: "Apoiou o pacote fiscal como gesto de responsabilidade orçamentária.", eh_coerente: true,  partido_na_epoca: "PP" },
    { proposicao_id: "PEC-015-2025", voto_oficial: "Sim", inferencia_ia: "Contra",  justificativa: "Disse ser contrário ao custo fiscal mas votou a favor em troca de apoio político.", eh_coerente: false, partido_na_epoca: "PP" },
  ],
  // Eduardo Bolsonaro (204554) — 5/12 coerentes = 41.7%
  204554: [
    { proposicao_id: "PL-1088-2023", voto_oficial: "Não", inferencia_ia: "A Favor",  justificativa: "Declarou apoio à simplificação fiscal mas votou contra a proposta governista.", eh_coerente: false, partido_na_epoca: "PL" },
    { proposicao_id: "PEC-006-2023", voto_oficial: "Não", inferencia_ia: "A Favor",  justificativa: "Disse defender reforma tributária mas rejeitou o texto constitucional.", eh_coerente: false, partido_na_epoca: "PL" },
    { proposicao_id: "PL-2630-2023", voto_oficial: "Não", inferencia_ia: "Contra",   justificativa: "Chamou o projeto de 'censura governamental' em múltiplos pronunciamentos.", eh_coerente: true,  partido_na_epoca: "PL" },
    { proposicao_id: "PL-4173-2023", voto_oficial: "Sim", inferencia_ia: "Contra",   justificativa: "Discursou contra as apostas mas votou a favor da regulamentação.", eh_coerente: false, partido_na_epoca: "PL" },
    { proposicao_id: "PL-1026-2024", voto_oficial: "Não", inferencia_ia: "A Favor",  justificativa: "Disse apoiar tributação de produtos nocivos mas votou contra o texto.", eh_coerente: false, partido_na_epoca: "PL" },
    { proposicao_id: "PEC-003-2024", voto_oficial: "Sim", inferencia_ia: "A Favor",  justificativa: "Defensor histórico do voto impresso, votou coerentemente.", eh_coerente: true,  partido_na_epoca: "PL" },
    { proposicao_id: "PL-0872-2024", voto_oficial: "Não", inferencia_ia: "A Favor",  justificativa: "Declarou apoio ao agronegócio mas votou contra o marco dos agrotóxicos.", eh_coerente: false, partido_na_epoca: "PL" },
    { proposicao_id: "PL-3399-2024", voto_oficial: "Sim", inferencia_ia: "A Favor",  justificativa: "Expressou apoio público à proposta; votação consistente.", eh_coerente: true,  partido_na_epoca: "PL" },
    { proposicao_id: "PL-0001-2025", voto_oficial: "Sim", inferencia_ia: "Contra",   justificativa: "Disse ser contra intervenção no mercado de crédito mas votou a favor.", eh_coerente: false, partido_na_epoca: "PL" },
    { proposicao_id: "PL-0555-2025", voto_oficial: "Não", inferencia_ia: "Contra",   justificativa: "Posicionou-se contra regulamentação governamental da IA; voto consistente.", eh_coerente: true,  partido_na_epoca: "PL" },
    { proposicao_id: "PL-0777-2025", voto_oficial: "Sim", inferencia_ia: "A Favor",  justificativa: "Apoiou o corte de gastos como medida fiscal responsável.", eh_coerente: true,  partido_na_epoca: "PL" },
    { proposicao_id: "PEC-015-2025", voto_oficial: "Não", inferencia_ia: "A Favor",  justificativa: "Declarou apoio à família mas votou contra a ampliação da licença-parental.", eh_coerente: false, partido_na_epoca: "PL" },
  ],
  // General Braga Netto (205571) — 4/12 coerentes = 33.3%
  205571: [
    { proposicao_id: "PL-1088-2023", voto_oficial: "Não", inferencia_ia: "A Favor",  justificativa: "Disse apoiar a simplificação tributária mas votou contra a proposta.", eh_coerente: false, partido_na_epoca: "PL" },
    { proposicao_id: "PEC-006-2023", voto_oficial: "Não", inferencia_ia: "A Favor",  justificativa: "Declarou apoio à reforma mas rejeitou o texto constitucional.", eh_coerente: false, partido_na_epoca: "PL" },
    { proposicao_id: "PL-2630-2023", voto_oficial: "Não", inferencia_ia: "Contra",   justificativa: "Contrário à regulação estatal da internet; voto alinhado com posição.", eh_coerente: true,  partido_na_epoca: "PL" },
    { proposicao_id: "PL-4173-2023", voto_oficial: "Sim", inferencia_ia: "Contra",   justificativa: "Discursou contra as apostas mas votou pela regulamentação.", eh_coerente: false, partido_na_epoca: "PL" },
    { proposicao_id: "PL-1026-2024", voto_oficial: "Não", inferencia_ia: "A Favor",  justificativa: "Expressou apoio ao imposto seletivo mas votou contra no plenário.", eh_coerente: false, partido_na_epoca: "PL" },
    { proposicao_id: "PEC-003-2024", voto_oficial: "Sim", inferencia_ia: "A Favor",  justificativa: "Defensor histórico do voto impresso; votação coerente.", eh_coerente: true,  partido_na_epoca: "PL" },
    { proposicao_id: "PL-0872-2024", voto_oficial: "Sim", inferencia_ia: "Contra",   justificativa: "Declarou-se contra o afrouxamento mas votou a favor sob pressão da bancada ruralista.", eh_coerente: false, partido_na_epoca: "PL" },
    { proposicao_id: "PL-3399-2024", voto_oficial: "Não", inferencia_ia: "A Favor",  justificativa: "Disse apoiar a proposta mas votou contra após repercussão negativa.", eh_coerente: false, partido_na_epoca: "PL" },
    { proposicao_id: "PL-0001-2025", voto_oficial: "Sim", inferencia_ia: "Contra",   justificativa: "Declarou-se contra intervenção no mercado de crédito mas votou a favor.", eh_coerente: false, partido_na_epoca: "PL" },
    { proposicao_id: "PL-0555-2025", voto_oficial: "Não", inferencia_ia: "Contra",   justificativa: "Contrário à regulamentação governamental da IA; voto consistente.", eh_coerente: true,  partido_na_epoca: "PL" },
    { proposicao_id: "PL-0777-2025", voto_oficial: "Sim", inferencia_ia: "A Favor",  justificativa: "Apoiou o pacote fiscal como medida de equilíbrio orçamentário.", eh_coerente: true,  partido_na_epoca: "PL" },
    { proposicao_id: "PEC-015-2025", voto_oficial: "Não", inferencia_ia: "A Favor",  justificativa: "Disse apoiar ampliação da licença-parental mas votou contra o custeio.", eh_coerente: false, partido_na_epoca: "PL" },
  ],
};

// Gera votos genéricos para os demais políticos
function gerarVotosGenericos(politicoId: number, partido: string, score: number): MockVoto[] {
  const seed = politicoId % 7;
  return PROPOSICOES.map((p, i) => {
    const isCoerente = (i + seed) % 10 < Math.round(score / 10);
    const votoFavor = (i + seed) % 3 !== 0;
    return {
      proposicao_id: p.id,
      voto_oficial: votoFavor ? "Sim" : "Não",
      inferencia_ia: isCoerente ? (votoFavor ? "A Favor" : "Contra") : (votoFavor ? "Contra" : "A Favor"),
      justificativa: isCoerente
        ? "Votação alinhada com as declarações públicas do parlamentar sobre este tema."
        : "A postura expressa em discursos anteriores contrasta com o voto registrado em plenário.",
      eh_coerente: isCoerente,
      partido_na_epoca: partido,
    };
  });
}

// ─── Datas para o timeline ───────────────────────────────────────────────────

const DATAS_VOTACAO: Record<string, string> = {
  "PL-1088-2023": "2023-07-12",
  "PEC-006-2023": "2023-11-09",
  "PL-2630-2023": "2023-09-28",
  "PL-4173-2023": "2023-12-21",
  "PL-1026-2024": "2024-03-14",
  "PEC-003-2024": "2024-05-23",
  "PL-0872-2024": "2024-06-17",
  "PL-3399-2024": "2024-09-11",
  "PL-0001-2025": "2025-01-08",
  "PL-0555-2025": "2025-03-19",
  "PL-0777-2025": "2025-04-02",
  "PEC-015-2025": "2025-04-28",
};

// ─── Funções de consulta mock ─────────────────────────────────────────────────

export function mockGetParlamentares(params: ParlamentaresParams): PaginaParlamentares {
  let itens = [...MOCK_POLITICOS];

  if (params.busca) {
    const q = params.busca.toLowerCase();
    itens = itens.filter(
      (p) =>
        p.nome_urna.toLowerCase().includes(q) ||
        p.nome_civil.toLowerCase().includes(q)
    );
  }
  if (params.partido) itens = itens.filter((p) => p.partido === params.partido);
  if (params.estado)  itens = itens.filter((p) => p.estado === params.estado);

  if (params.ordem === "mais_coerentes") {
    itens.sort((a, b) => (b.score_coerencia ?? -1) - (a.score_coerencia ?? -1));
  } else if (params.ordem === "menos_coerentes") {
    itens.sort((a, b) => (a.score_coerencia ?? 101) - (b.score_coerencia ?? 101));
  }

  const tamanho = params.tamanho ?? 20;
  const pagina  = params.pagina  ?? 1;
  const inicio  = (pagina - 1) * tamanho;

  return {
    total_registros: itens.length,
    pagina_atual: pagina,
    tamanho_pagina: tamanho,
    total_paginas: Math.ceil(itens.length / tamanho),
    itens: itens.slice(inicio, inicio + tamanho),
  };
}

export function mockGetParlamentar(id: number): Parlamentar {
  const p = MOCK_POLITICOS.find((p) => p.id === id);
  if (!p) throw new Error(`Mock: parlamentar ${id} não encontrado`);
  return p;
}

export function mockGetVotos(id: number, params: { pagina?: number; tamanho?: number }): PaginaVotos {
  const politico = MOCK_POLITICOS.find((p) => p.id === id);
  const partido  = politico?.partido ?? "PL";
  const score    = politico?.score_coerencia ?? 60;

  const raw = VOTOS_POR_POLITICO[id] ?? gerarVotosGenericos(id, partido, score);

  const ordered =
    params.tamanho === undefined || params.pagina === undefined
      ? [...raw].reverse()
      : [...raw].reverse();

  const tamanho = params.tamanho ?? 20;
  const pagina  = params.pagina  ?? 1;
  const inicio  = (pagina - 1) * tamanho;
  const propMap = Object.fromEntries(PROPOSICOES.map((p) => [p.id, p]));

  return {
    total_registros: ordered.length,
    pagina_atual: pagina,
    tamanho_pagina: tamanho,
    total_paginas: Math.ceil(ordered.length / tamanho),
    itens: ordered.slice(inicio, inicio + tamanho).map((v, i) => {
      const prop = propMap[v.proposicao_id];
      return {
        id:           `mock-${id}-${i}`,
        proposicao_id: v.proposicao_id,
        tipo:          prop?.tipo ?? "PL",
        numero:        prop?.numero ?? 0,
        ano:           prop?.ano ?? 2024,
        ementa:        prop?.ementa ?? null,
        data_votacao:  DATAS_VOTACAO[v.proposicao_id] ?? "2024-01-01",
        voto_oficial:  v.voto_oficial,
        inferencia_ia: v.inferencia_ia,
        justificativa: v.justificativa,
        eh_coerente:   v.eh_coerente,
        partido_na_epoca: v.partido_na_epoca,
      };
    }),
  };
}

export function mockGetTimeline(id: number): TimelinePoint[] {
  const politico = MOCK_POLITICOS.find((p) => p.id === id);
  const partido  = politico?.partido ?? "PL";
  const score    = politico?.score_coerencia ?? 60;

  const votos = VOTOS_POR_POLITICO[id] ?? gerarVotosGenericos(id, partido, score);
  const propMap = Object.fromEntries(PROPOSICOES.map((p) => [p.id, p]));

  return votos
    .filter((v) => v.eh_coerente !== null)
    .sort((a, b) => {
      const da = DATAS_VOTACAO[a.proposicao_id] ?? "";
      const db = DATAS_VOTACAO[b.proposicao_id] ?? "";
      return da.localeCompare(db);
    })
    .map((v) => {
      const prop = propMap[v.proposicao_id];
      return {
        data_votacao:  DATAS_VOTACAO[v.proposicao_id] ?? "2024-01-01",
        eh_coerente:   v.eh_coerente as boolean,
        proposicao_id: v.proposicao_id,
        tipo:          prop?.tipo ?? "PL",
        numero:        prop?.numero ?? 0,
        ano:           prop?.ano ?? 2024,
      };
    });
}

export function mockGetSimilares(id: number): ParlamentarSimilar[] {
  const politico  = MOCK_POLITICOS.find((p) => p.id === id);
  if (!politico) return [];

  const isConservador = ["PL", "PP", "PSD", "MDB"].includes(politico.partido);

  return MOCK_POLITICOS.filter((p) => p.id !== id)
    .filter((p) => p.score_coerencia !== null)
    .map((p) => {
      const sameBloc    = ["PL", "PP", "PSD", "MDB"].includes(p.partido) === isConservador;
      const concordancia = sameBloc
        ? 60 + Math.abs((p.id % 30))
        : 30 + Math.abs((p.id % 20));
      const votos_em_comum = 5 + (p.id % 7);
      return {
        id:                     p.id,
        nome_urna:              p.nome_urna,
        partido:                p.partido,
        estado:                 p.estado,
        url_foto:               p.url_foto,
        score_coerencia:        p.score_coerencia,
        percentual_concordancia: Math.min(99, concordancia),
        votos_em_comum,
      };
    })
    .sort((a, b) => b.percentual_concordancia - a.percentual_concordancia)
    .slice(0, 5);
}
