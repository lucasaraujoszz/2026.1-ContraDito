# ContraDito

Plataforma de transparência política que cruza discursos e votos de parlamentares brasileiros, calculando um Score de Coerência com IA.

## Language

### Parlamentares

**Parlamentar**:
Deputado Federal ou Senador rastreado pelo sistema.
_Avoid_: Político, candidato.

**Dossiê**:
Página de perfil detalhado de um parlamentar (`/politico/[id]`), organizada em três abas — Perfil, Votações e Similares.
_Avoid_: Perfil, página do político.

**Status do Mandato**:
Estado atual do exercício do cargo (ex: "Em Exercício", "Licenciado"). Distinto de cargo ou partido.
_Avoid_: Situação.

### Votos e Coerência

**Votação Analisada**:
Um `Voto` onde a IA encontrou discurso suficiente e produziu um veredito (`eh_coerente IS NOT NULL`). Apenas votações analisadas entram no denominador do Score e na Timeline.
_Avoid_: Votação válida, prova de contradição.

**Score de Coerência**:
Percentual (0–100, uma casa decimal) de votações analisadas onde o parlamentar votou em linha com seus discursos. Nulo quando há menos de 3 votações analisadas.
_Avoid_: Índice de coerência, nota.

**Timeline de Coerência**:
Série cronológica do Score de Coerência acumulado, onde cada ponto representa uma votação analisada. O score de cada ponto é calculado considerando todas as votações analisadas até aquela data.
_Avoid_: Histórico de coerência, gráfico de evolução.

**Concordância**:
Percentual de proposições em que dois parlamentares votaram identicamente (somente votos "Sim" e "Não"). Requer mínimo de 5 proposições em comum para ser calculada.
_Avoid_: Similaridade, alinhamento.

**Dados Suficientes**:
Condição em que um parlamentar possui ao menos 3 votações analisadas, habilitando cálculo de Score e exibição no ranking ordenado. Abaixo desse limiar, métricas são exibidas com denominador explícito (ex: "100% — 1 votação") e o parlamentar é excluído do ranking por padrão (visível via toggle).
_Avoid_: Dados válidos, threshold mínimo.

**Taxa de Presença**:
Percentual de votações registradas (incluindo ausências) em que o parlamentar efetivamente votou (voto_oficial ≠ "Ausente" / "NÃO COMPARECEU"). Denominador distinto do Score de Coerência, que usa apenas votações analisadas.
_Avoid_: Frequência, assiduidade.

**Benchmark de Coerência**:
Contexto comparativo exibido no Dossiê (aba Perfil) junto ao Score de Coerência. Compara o score do parlamentar contra dois referenciais: média do partido (primária) e média do cargo (secundária). Calculado apenas sobre parlamentares com Dados Suficientes.
_Avoid_: Média geral, ranking comparativo.

**Tendência Recente**:
Indicador de momentum calculado no frontend a partir da Timeline de Coerência. Compara o score acumulado das últimas 10 votações analisadas contra o score histórico total. Exibido apenas quando o parlamentar possui ao menos 15 votações analisadas. Aparece no Dossiê (aba Perfil) e na página de Comparação.
_Avoid_: Histórico recente, evolução curta.

**Parlamentar Similar**:
Parlamentar que apresenta alta concordância com outro, com ao menos 5 proposições analisadas em comum.
_Avoid_: Parlamentar aliado, votante parecido.

### Proposições

**Proposição**:
Projeto de Lei (PL) ou Proposta de Emenda à Constituição (PEC) com votação nominal registrada no período 2023–2026.
_Avoid_: Lei, matéria, projeto.

**Resumo Executivo**:
Síntese temática de uma Proposição gerada pelo LLM (Llama 3.1), limitada a 512 tokens, usada como base para vetorização semântica.
_Avoid_: Ementa, sumário.
