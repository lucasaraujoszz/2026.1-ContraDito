# PRD: Extrator de Votos Nominais (Câmara dos Deputados)

**Labels:** `ready-for-agent`, `etl`, `worker`

---

## Problem Statement

Após a extração em massa das proposições legislativas (PLs e PECs) e a identificação do evento de votação de mérito, o sistema precisa agora extrair os votos nominais de cada deputado federal que participou dessas sessões. 
O desafio central reside em três fatores: 
1. O ID do evento de tramitação que extraímos anteriormente pode não ser exatamente o ID da sessão nominal aceito pelo endpoint de votos, exigindo uma busca inteligente e não destrutiva.
2. A base de dados do governo frequentemente retorna votos de suplentes efêmeros que não constam em nossa base de políticos consolidados, o que resultaria em falhas transacionais (Erro 23503 de Violação de Chave Estrangeira) ao tentar realizar um *Bulk Upsert*.
3. A existência de matérias aprovadas de forma simbólica (sem contagem nominal de votos) e a presença de sessões corrompidas na API do governo ("Poison Pills") que retornam Erro 500 permanentemente.

---

## Solution

Criar um script Python autônomo (Worker) focado em extrair estritamente os votos nominais das proposições já salvas no banco. O script fará a leitura da nossa própria tabela `camara_proposicoes` e adotará uma estratégia de busca de *Graceful Degradation* (Duas Camadas) para localizar a sessão nominal exata (via Regex rápida ou Varredura de fallback).

Uma vez encontrada a sessão, o script fará um UPDATE retificando a `data_votacao` e o `id_votacao_camara` na matéria original, garantindo rastreabilidade absoluta. Em seguida, extrairá os votos, realizará o descarte silencioso (*Soft Drop*) de votos órfãos para proteger a integridade referencial, e persistirá os dados na tabela `camara_votos` usando *Bulk Upsert*. Nenhuma coluna de controle de estado será criada; o pipeline priorizará o princípio KISS (Keep It Simple, Stupid) devido à baixa volumetria estática.

---

## User Stories

1. Como **engenheiro de dados**, quero que o Worker inicie seu fluxo realizando uma query na tabela `camara_proposicoes`, buscando o lote de matérias para processar, em vez de varrer endpoints governamentais às cegas.
2. Como **arquiteto de dados**, quero utilizar uma estratégia de busca de duas camadas (*Graceful Degradation*) para encontrar o ID da sessão de votação nominal, otimizando requisições de rede.
3. Como **analista de dados**, quero que a **Camada 1 (Caminho Feliz)** busque o ID da votação usando uma Expressão Regular (Regex) no campo `descricao` do endpoint `/votacoes?idProposicao={id}`, procurando por padrões de contagem como "Sim: 343; Não: 97".
4. Como **engenheiro de software**, quero que a **Camada 2 (Fallback)** seja acionada caso a Regex falhe, onde o script varrerá os IDs retornados na rota de votações cronologicamente, batendo em `/votos` até encontrar uma lista nominal.
5. Como **administrador de banco de dados**, quero que, ao encontrar a sessão nominal definitiva, o script execute um `UPDATE` na tabela `camara_proposicoes`, corrigindo a `data_votacao` e populando o `id_votacao_camara`.
6. Como **arquiteto de software**, quero cruzar a lista de deputados votantes com a nossa tabela de políticos e ejetar do lote qualquer deputado não encontrado (**Descarte Silencioso / Soft Drop**), prevenindo o Erro 23503 no banco de dados.
7. Como **administrador do sistema**, quero persistir os votos validados na tabela `camara_votos` utilizando o método de `Bulk Upsert`.
8. Como **engenheiro de dados**, quero que o sistema lide pacificamente com o estado vazio (matérias simbólicas), ignorando as proposições que não possuam votos nominais e avançando para a próxima sem gerar logs de erro crítico.
9. Como **engenheiro de confiabilidade (SRE)**, quero implementar resiliência com a biblioteca `tenacity` (*exponential backoff*) e limitar a concorrência a 5 workers simultâneos via `asyncio.Semaphore(5)`.
10. Como **engenheiro de dados**, quero adotar a política de **Isolamento de Falha (Skip-and-Continue)** perante "Poison Pills" (Erros 500 consistentes da Câmara para uma sessão), logando o erro para auditoria, mas sem causar o crash do Worker.
11. Como **arquiteto de dados**, quero manter o schema do banco intocado (sem flags de `votos_processados`), aceitando que proposições vazias serão reprocessadas em execuções futuras, já que a volumetria (~1.300 registros) torna essa otimização um *overengineering*.

---

## Implementation Decisions

### Estratégia de Endpoints e Busca (Graceful Degradation)
- **Camada 1 (Regex):** Avalia a descrição da votação buscando evidências textuais da contagem.
- **Camada 2 (Sweep):** Iteração cronológica N+1 em `/votacoes/{id}/votos` até que a resposta possua um array não vazio.
- Assim que a sessão for confirmada, acionamos o Supabase para dar o `UPDATE` na tabela `camara_proposicoes`.

### Integridade Referencial e Transformação
- **Descarte Silencioso (Soft Drop):** Os dados da Câmara contêm "suplentes relâmpago". Antes de realizar o `Bulk Upsert`, os IDs dos votantes (`politico_id`) serão verificados (em memória via query prévia ou validação setorial). Parlamentares inexistentes em nosso banco são removidos do lote de inserção, garantindo que o resto do lote seja salvo.
- O modelo de dados para a tabela `camara_votos` será preenchido com:
  - `id` (UUID - Gerado na aplicação)
  - `proposicao_id` (String - Formato snake_case, herdado da proposição)
  - `politico_id` (Integer - ID da API da Câmara)
  - `partido_na_epoca` (String)
  - `voto_oficial` (String)
  - Nota: `inferencia_ia`, `justificativa` e `eh_coerente` não serão populados nesta fase.

### Resiliência e Rede
- **Skip-and-Continue:** O `tenacity` fará o retries de erros transientes (429, 500, 503). Se um erro persistir e as tentativas se esgotarem (sessão corrompida / *Poison Pill*), a exceção é capturada, logada como ERROR, e o pipeline pula para o próximo ID, preservando o uptime do *Backfill*.
- A concorrência da aplicação será "estrangulada" em `asyncio.Semaphore(5)`.

### Controle de Estado
- O princípio KISS foi adotado. Devido ao número estático e baixo de proposições pendentes (cerca de 1.300), nenhuma tabela de controle, flag sentinela ou coluna adicional foi criada no banco de dados para evitar o reprocessamento de matérias sem voto nominal. O overhead de rede é preferível à complexidade arquitetural.

---

## Testing Decisions

### Unidade e Regras de Negócio
- **Regex de Votação Nominal:** Testar a função da Camada 1 contra descrições reais da Câmara (com e sem contagem de votos) para garantir que ela identifica corretamente sessões de mérito e rejeita pedidos de adiamento.
- **Soft Drop de Políticos:** Construir um teste unitário que recebe uma lista mista de IDs votantes (válidos e não válidos) e assegurar que a função de limpeza devolve apenas a intersecção de IDs válidos.
- **Identificação de UUID:** Garantir que o campo `id` gerado para o voto nominal seja único, possivelmente um UUIDv5 baseado na concatenação de `proposicao_id` e `politico_id`.

### Integração e Comportamento
- **Mock de Graceful Degradation:** Simular um cenário onde o endpoint de votações retorna dados sem match da Regex, forçando o worker a disparar a Camada 2 (Sweep).
- **Mocking de Poison Pill:** Simular uma sessão da API retornando Erro 500 crônico, garantindo que o sistema atinge o limite do `tenacity` e avança pacificamente para o próximo ID sem lançar crash global.
- **Mock de Votação Simbólica (Estado Vazio):** Simular o cenário em que esgotamos todas as sessões e nenhuma tem array de votos, validando que o worker sai silenciosamente e reporta o caso amigavelmente.

---

## Out of Scope

- Inferências de IA para justificar ou analisar a coerência do voto neste momento.
- Processamento de votações em comissões (apenas Plenário).
- Preenchimento dos campos `inferencia_ia`, `justificativa` e `eh_coerente` da tabela `camara_votos`.
- Adição de colunas estruturais em tabelas de controle de estado (`votos_processados`).
- Extração de votos atrelados ao Senado Federal.

---

## Further Notes

- A decisão de adotar o "Descarte Silencioso" e ignorar otimizações de controle de estado reflete um pragmatismo intencional. O foco é colocar a malha de dados principal de pé com estabilidade e alta disponibilidade, sem paralisar a esteira por conta de instabilidades ou minúcias governamentais (suplentes efêmeros).


