# PRD: Extrator de Votos Nominais (Senado Federal)

**Labels:** `ready-for-agent`, `etl`, `worker`

---

## Problem Statement

Após a extração massiva das proposições legislativas do Senado Federal, o sistema necessita capturar as votações nominais atreladas a essas matérias (PECs, PLs, PLPs, etc.) julgadas a partir da Legislatura 57 (01/01/2023). 
O processo enfrenta grandes desafios devido às especificidades do Senado: 
1. A API é instável e as datas entre os endpoints de proposições e de votações frequentemente não coincidem, inviabilizando o uso de âncoras temporais rígidas.
2. Múltiplas votações nominais podem ocorrer para uma mesma matéria (1º Turno, 2º Turno, Destaques, Emendas), exigindo inteligência para identificar o voto de mérito principal.
3. O vocabulário de votação do Senado é regimentalmente distinto da Câmara ("P-OD", "Votou").
4. O uso da API REST do Supabase impede transações SQL atômicas em múltiplas tabelas, criando risco de corrupção do estado caso a rede caia no meio do processamento.
5. A esmagadora maioria das matérias é votada de forma simbólica, podendo gerar milhares de requisições inúteis se não houver um controle de estado eficiente.

---

## Solution

Criar um script Python autônomo (Worker) focado na extração de votos do Senado. O script lerá a tabela `senado_proposicoes` filtrando apenas os registros cujo `id_votacao_senado IS NULL`. 

Para suprir a ausência de integridade temporal da API, o script baterá no endpoint `/votacao`, ordenará todas as sessões cronologicamente (da mais antiga para a mais nova, limitadas a >= 2023) e aplicará um sistema de Regex duplo (*Blocklist* para barrar manobras regimentais e *Allowlist* para exigir termos de mérito). 

Para garantir a estabilidade do pipeline e evitar falhas transacionais na API REST, o sistema adotará o método de **Descarte Silencioso (Soft Drop)** para parlamentares órfãos (suplentes não mapeados) e persistirá os dados utilizando **Consistência Eventual (Inversão de Ordem)**: efetuando primeiro o Upsert dos votos extraídos no estado cru (*Raw*) e apenas em caso de sucesso executando um `UPDATE` na tabela pai (`senado_proposicoes`) para preencher o `id_votacao_senado` e, obrigatoriamente, sobrescrever a `data_votacao` provisória pela `dataSessao` real da votação encontrada. O processamento das votações puramente simbólicas será refeito nas execuções (overhead de rede), assumindo o princípio KISS para não alterar o schema do banco.
Adicionalmente, o Worker emprega mecanismos de engenharia de confiabilidade (SRE) com retentativas (Tenacity), estrangulamento de requisições (Semaphore) e isolamento de falhas para contornar a notória instabilidade da API governamental.

---

## User Stories

1. Como **engenheiro de dados**, quero que o Worker inicie seu fluxo consultando a tabela `senado_proposicoes` para capturar os campos `id_senado` e `proposicao_id` de matérias não processadas (`id_votacao_senado IS NULL`).
2. Como **arquiteto de dados**, quero que o sistema abandone tentativas de fazer *match* exato da data do banco com a data da API e passe a ordenar os resultados do endpoint de votação do Senado cronologicamente pela `dataSessao` (do mais antigo para o mais novo).
3. Como **analista de negócio**, quero que o Worker garanta que apenas votações a partir de 2023-01-01 sejam avaliadas.
4. Como **analista de regras de negócio**, quero que a descrição da votação (`descricaoVotacao`) passe por uma **Blocklist** via Regex para rejeitar imediatamente manobras (ex: "requerimento", "urgência", "adiamento", "destaque", "questão de ordem").
5. Como **analista de regras de negócio**, quero que, após passar na Blocklist, a descrição seja avaliada por uma **Allowlist** via Regex, que aprovará a sessão se contiver termos de mérito (ex: "texto-base", "substitutivo", "parecer", "1º turno", "2º turno").
6. Como **arquiteto de software**, quero cruzar o `codigoParlamentar` dos votantes contra a tabela `senado_politicos` guardada em memória, descartando silenciosamente (*Soft Drop*) votos de parlamentares inexistentes antes de enviá-los ao banco para evitar Erro 23503.
7. Como **cientista de dados**, quero que o extrator preserve o vocabulário regimental original do Senado ao capturar a `siglaVotoParlamentar` e a `siglaPartidoParlamentar`, delegando a normalização semântica (cruzamento com padrão da Câmara) para o modelo de IA futuro.
8. Como **engenheiro de dados**, quero garantir a rastreabilidade temporal exata, fazendo com que o script sempre atualize a coluna `data_votacao` na tabela `senado_proposicoes` usando a `dataSessao` do endpoint de votos assim que uma sessão nominal de mérito for validada.
9. Como **administrador de banco de dados**, quero evitar falhas parciais por falta de transação atômica invertendo a ordem das operações: salvar primeiro na tabela `senado_votos` (Upsert) e depois dar o `UPDATE` na tabela `senado_proposicoes` (inserindo o `codigoSessao` e a nova `data_votacao`).
10. Como **engenheiro de confiabilidade**, quero garantir idempotência nos votos gerando um UUID v5 usando a concatenação do `proposicao_id` e o `codigoParlamentar`.
11. Como **arquiteto de dados**, quero que proposições simbólicas (sem votos nominais válidos) sejam graciosamente ignoradas e continuem com `id_votacao_senado IS NULL`, tolerando seu reprocessamento futuro em prol do princípio KISS, sem a necessidade de criar flags adicionais no schema atual.
12. Como **engenheiro de confiabilidade (SRE)**, quero implementar resiliência de rede com a biblioteca `tenacity` (*exponential backoff*) para contornar falhas transientes (Erros 500, 502, 503, 504 e 429) da API do Senado.
13. Como **arquiteto de software**, quero limitar a concorrência a 5 workers simultâneos via `asyncio.Semaphore(5)` e pausas assíncronas para evitar bloqueios severos pelo WAF governamental.
14. Como **engenheiro de dados**, quero adotar a política de **Isolamento de Falha (Skip-and-Continue)** perante "Poison Pills" (matérias corrompidas que geram erros contínuos), logando a exceção sem causar a queda sistêmica do Worker.
15. Como **administrador do sistema**, quero que o Worker registre um log sintético na tabela `etl_logs` ao final do processo, mantendo o padrão de rastreabilidade (Watermarker) dos demais extratores do projeto.

---

## Implementation Decisions

### Estratégia de Extração Temporal e Resolução de Turnos
- **Abandono da Âncora Temporal:** Empiricamente, a API do Senado apresentou divergências entre as datas dos endpoints. A busca de sessão correta dependerá da Regex.
- **Ordenação e Fitro Textual:** Array de votações ordenado via `dataSessao` ASC (limitado a >= 2023). Aplica-se:
  - *Blocklist Regex:* `(?i)(requerimento|urgência|adiamento|destaque|questão\sde\sordem|preferência)`
  - *Allowlist Regex:* `(?i)(texto[- ]base|substitutivo|parecer|1º\sturno|primeiro\sturno|turno\súnico|2º\sturno|segundo\sturno)`
  - A primeira votação (mais antiga) que não cair na Blocklist e bater na Allowlist é cravada como a votação de mérito principal do texto-base (vencendo questões de Destaques posteriores ou segundo turnos).

### Integridade Referencial
- **Descarte Silencioso (Soft Drop):** Análogo à Câmara, um `SELECT id FROM senado_politicos` é realizado no início do processamento. Os IDs formam um `Set` em memória. Votos cujo parlamentar não esteja neste conjunto são descartados do lote antes do Upsert para prevenir quebras de Foreign Key.

### Compatibilidade Semântica
- **Extração Raw (Crua):** Nenhuma normalização das siglas de voto do Senado (ex: "P-OD") será feita no nível do extrator. O dado será salvo exatamente como recebido, e o alinhamento com a Câmara ocorrerá no modelo cognitivo posterior.

### Controle de Estado
- **O Loop de Simbólicas:** Para evitar *overengineering* e manter o banco enxuto, usaremos a coluna `id_votacao_senado` (já existente) como sentinela. O sistema executará o fluxo focado no estado `NULL`. Caso não ache votos, ele simplesmente encerra e aceita processar novamente essa proposição "órfã" na próxima execução diária, apostando na resiliência da malha.

### Gerenciamento de Falhas Transacionais via REST
- **Consistência Eventual:** Sem *Stored Procedures* no Supabase, adotamos a regra: Grava-se o(s) filho(s) antes do pai. 
  1. `UPSERT` na tabela `senado_votos`.
  2. `UPDATE` na tabela `senado_proposicoes` (atualizando `id_votacao_senado` e sobrescrevendo `data_votacao` com a data real da sessão).
  Isso previne a condição de corrida onde o registro é marcado como concluído sem que os votos tenham sido salvos. Em caso de *crash* entre as etapas, o Upsert será feito de forma inofensiva no dia seguinte, graças ao UUIDv5 determinístico.

### Resiliência e Rede
- **Tenacity & WAF:** O endpoint de votos do Senado é protegido contra instabilidades usando tentativas exponenciais. Adicionalmente, a concorrência é limitada a 5 requisições simultâneas (`asyncio.Semaphore(5)`) com freios de `asyncio.sleep(0.5)`.
- **Isolamento de Falhas (Poison Pill):** Caso o Tenacity se esgote para uma matéria específica, a exceção é capturada no *Worker*, registrada no log como erro isolado, e a fila de processamento avança.

### Auditoria e Rastreabilidade
- **ETL Logs:** No final de toda execução do pipeline, um registro único é feito na tabela `etl_logs` informando `status`, `linhas_afetadas`, e datas de início e fim da extração.

### Data Contract Mapeado
- **Tabela senado_votos:**
  - `id` (UUID v5 baseado em `proposicao_id_politico_id`)
  - `proposicao_id` (String herdada)
  - `politico_id` (Integer vindo de `codigoParlamentar`)
  - `partido_na_epoca` (String de `siglaPartidoParlamentar`)
  - `voto_oficial` (String RAW de `siglaVotoParlamentar`)
  - *Colunas fora de escopo:* `inferencia_ia`, `justificativa`, `eh_coerente`

**Tabela senado_proposicoes (UPDATE):**
Ao encontrar votos válidos, o Worker **deve** realizar o update da matéria na tabela de proposições atualizando:
  - `id_votacao_senado` (Recebe o `codigoSessao` da votação nominal validada)
  - `data_votacao` (Sobrescrita e corrigida com a `dataSessao` da votação nominal validada)

---

## Testing Decisions

### Unidade (Transformadores)
- **Regras de Regex de Turnos:** Testar uma lista sintética contendo strings reais do Senado. Garantir que a função rejeite adiamentos, urgências e destaques, mas aprove substitutivos e 1º turno.
- **Ordenação Temporal:** Testar o recebimento de 3 votações no mesmo dia. Assegurar que após aplicar os filtros regex, a função sempre pinça a mais antiga.
- **Soft Drop e Idempotência:** Testar se um lote de votos com IDs espúrios tem seus votos filtrados corretamente, e se o UUIDv5 gerado é idêntico em chamadas consecutivas.

### Integração (Worker)
- **Consistência Eventual:** Realizar um mock do cliente Supabase para garantir que o envio para o endpoint de `senado_votos` (`upsert`) sempre ocorra antes da chamada de atualização na tabela `senado_proposicoes` (`update`).
- **Fallback Pacífico de Votação Simbólica:** Testar com um mock que retorne sessão vazia do Senado e assegurar que a rotina encerra sem invocar *crashes* sistêmicos e sem realizar nenhum *upsert*.
- **Resiliência e Isolamento:** Simular falhas 500 e 503 na API para testar os *retries* (Tenacity) e confirmar que o orquestrador engole a falha de uma "Poison Pill" sem vazar exceção fatal para o pipeline global.

---

## Out of Scope

- Normalização e tradução semântica dos tipos de votos (ex: converter o jargão do Senado para "Sim"/"Não").
- Modificação do Schema do banco para criar coluna sentinela (`votos_processados`).
- Extração de justificativas em texto livre ou relatórios gerados por IA.
- Tratamento de comissões (apenas votações nominais que o endpoint apontar).
- RPCs ou Stored Procedures do banco de dados (Transação SQL atômica delegada para eventualidade via lógica do código).

---

## Further Notes

- Apesar do conhecido risco de limitação pelo WAF do Senado (Rate Limit) devido ao reprocessamento massivo das votações simbólicas (órfãs), o trade-off pela simplicidade arquitetônica (KISS) foi deliberadamente acatado e complementado pelo uso de estrangulamento assíncrono (Semaphore e Sleep). Caso haja *bans* crônicos de IP em ambiente de produção, uma revisão para criar a coluna de sentinela será considerada.