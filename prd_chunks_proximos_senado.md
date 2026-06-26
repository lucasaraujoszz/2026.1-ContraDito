# PRD: Vínculo de Chunks de Discursos Próximos aos Votos (Senado Federal)

**Labels:** `ready-for-agent`, `etl`, `worker`

---

## Problem Statement

Atualmente, o sistema possui as votações nominais registradas na tabela `senado_votos` (contendo o voto oficial SIM/NÃO de cada senador para cada proposição) e os discursos fragmentados e vetorizados na coleção `chunks_discursos_embeddings` do Qdrant e na tabela `senado_discurso_chunks` do Supabase. No entanto, não há um vínculo direto entre a postura de votação do parlamentar e suas falas públicas. 

Para viabilizar a análise de coerência política, é necessário identificar e armazenar quais discursos proferidos por um senador são mais semanticamente relacionados ao tema de cada proposição votada. Essa relação deve ser calculada usando busca vetorial. Os desafios centrais são:
1. **Falsos Positivos por Jargão:** O vocabulário político parlamentar é repleto de expressões comuns e formais ("Sr. Presidente", "pela ordem", "parabenizo o relator"), o que pode gerar alta similaridade matemática em discursos irrelevantes. Precisamos de um limiar (threshold) de corte rígido e testável.
2. **Custo de Busca (N+1 no Qdrant/Supabase):** Fazer buscas vetoriais individuais e atualizações no banco para cada um de milhares de registros de voto de forma ineficiente pode sobrecarregar as APIs de banco de dados e estourar cotas.
3. **Limitação do Qdrant:** A coleção de vetores de discursos no Qdrant não armazena o texto dos fragmentos, apenas referências e metadados, exigindo uma resolução híbrida de IDs.

## Solution

Criar uma rotina de ETL executada em background que processe de forma incremental os votos de mérito (`SIM` ou `NÃO`) dos senadores. O pipeline fará o cruzamento semântico de forma eficiente:
1. Buscará o embedding de resumo da proposição em questão na coleção `proposicoes_embeddings`.
2. Usará esse vetor para fazer uma busca de similaridade (Cosine Similarity) na coleção `chunks_discursos_embeddings` filtrada obrigatoriamente pelo `politico_id` do dono do voto.
3. Aplicará um limiar (threshold) mínimo de **0.75** de score de similaridade para mitigar falsos positivos.
4. Para os 3 fragmentos de maior score acima do limiar, recuperará o texto bruto dos discursos no Supabase (`senado_discurso_chunks`) usando os UUIDs retornados.
5. Persistirá a lista resultante no campo `chunks_proximos` (tipo `JSONB`) da tabela `senado_votos`.

## User Stories

1. As an analyst evaluating political coherence, I want the system to identify the 3 speech chunks most relevant to each vote, so that I can compare what the politician said with how they voted.
2. As a system engineer, I want the script to filter discursos using a similarity threshold of 0.75, so that we minimize false positives caused by generic legislative jargon.
3. As a developer, I want the script to only process votes where `chunks_proximos` is null, so that the script runs incrementally and efficiently without re-analyzing already processed votes.
4. As a database administrator, I want to save the closest chunks as a `JSONB` array in the `senado_votos` table, so that we can fetch the vote and its context in a single query without complex table joins.
5. As a backend engineer, I want to cache the proposition embeddings in memory during a single execution run, so that we don't query Qdrant redundantly for the same proposition across different politicians' votes.
6. As a data engineer, I want the script to fetch the actual text of the speech chunks from `senado_discurso_chunks` after getting the chunk IDs from Qdrant, so that the text is denormalized and stored directly inside the vote payload.
7. As a product owner, I want the script to save an empty array `[]` when no speeches exceed the similarity threshold, so that the vote is marked as processed and not retried in future incremental runs.
8. As a DevOps engineer, I want execution logs to be recorded at the end of the script in the `etl_logs` table, so that we can track execution status, running time, and count of votes updated.

## Implementation Decisions

### Schema Changes (Supabase)
* Adicionar uma nova coluna na tabela `senado_votos`:
  * Nome: `chunks_proximos`
  * Tipo: `jsonb`
  * Valor padrão: `NULL`
  * Descrição: Armazena uma lista de até 3 dicionários contendo `chunk_id` (UUID), `texto_chunk` (String) e `score` (Float).

### Estratégia de Busca e Cache (Qdrant & Memória)
* **Busca Incremental:** O script processará registros onde `chunks_proximos IS NULL` e `voto_oficial IN ('SIM', 'NAO')`.
* **Cache de Proposições:** O script identificará as proposições únicas do lote de votos. Para cada uma, buscará o vetor uma única vez no Qdrant (coleção `proposicoes_embeddings`) e armazenará em um dicionário local na memória (`cache_proposicoes[proposicao_id] = vetor`).
* **Busca Vetorial por Senador:** A busca no Qdrant usará a coleção `chunks_discursos_embeddings`. Será aplicado um filtro no Qdrant (`Filter` -> `must` -> `FieldCondition` com `key="politico_id"`) para corrigir a busca aos discursos do próprio senador.
* **Corte por Limiar (Threshold):** Apenas pontos com score de similaridade superior ou igual a `0.75` serão considerados válidos.

### Resolução de Texto (Supabase)
* O Qdrant retornará apenas os IDs dos chunks. O script deve coletar todos os IDs de chunks sobreviventes e fazer uma única consulta `SELECT id, texto_chunk FROM senado_discurso_chunks WHERE id IN (...)` por lote para recuperar os textos associados, reduzindo o I/O.
* Caso um ID de chunk retornado pelo Qdrant não seja localizado no Supabase (ex: inconsistência temporária de sincronismo), o item será ignorado no payload final.

### Registro de Execução (Logs)
* Ao final do script, salvar na tabela `etl_logs` o registro com o `nome_rotina` `"vinculo_chunks_votos_senado"`, indicando `status`, `linhas_afetadas` (votos que receberam dados) e `detalhe_erro` em caso de exceção.

## Testing Decisions

### Princípios de TDD (Test-Driven Development)
* Os testes devem focar no comportamento do pipeline de vínculo de discursos de forma isolada, mockando a rede (Supabase e Qdrant).
* Seguir estritamente o ciclo RED-GREEN-REFACTOR adicionando um teste por vez.
* **Prior Art:** A infraestrutura de testes de ETL usará `pytest` seguindo padrões presentes em `tests/etl/`.

### Casos de Teste Principais
1. **Teste de Limiar de Similaridade (Threshold):** Garantir que chunks retornados pelo Qdrant com score `< 0.75` sejam sumariamente ignorados.
2. **Teste de Voto Sem Discurso Semântico:** Validar que, se o Qdrant não retornar nenhum chunk ou se nenhum atingir o limiar, o banco de dados recebe `[]` em `chunks_proximos` (garantindo que o registro não fique elegível para re-execução).
3. **Teste de Integração de Textos:** Garantir que o texto recuperado do Supabase baseado nos IDs do Qdrant é adequadamente acoplado ao score de similaridade e gravado no formato JSON correto.
4. **Teste de Cache de Vetores:** Validar que o script realiza apenas uma chamada à API do Qdrant para obter o embedding de uma proposição específica, mesmo que múltiplos parlamentares tenham votos no mesmo projeto.

## Out of Scope

* Atualização retrospectiva ou cálculo para discursos cujos chunks não foram processados ou estão com erros permanentes no banco.
* OCR de discursos não transcritos ou busca de áudio/vídeo.
* Geração de relatórios cognitivos explicativos de coerência por IA (limita-se estritamente à seleção e vínculo dos dados).
* Refatoração ou alteração nos pipelines existentes da Câmara de Deputados (será implementado um script/módulo irmão voltado ao Senado).

## Further Notes

* O limiar de `0.75` foi definido empiricamente para mitigar a interferência de termos genéricos de rito legislativo (jargões). Este valor poderá ser ajustado no futuro com base em análises de precisão qualitativa do cruzamento de postura.
