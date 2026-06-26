# PRD: Extrator de Proposições (Senado Federal)

**Labels:** `ready-for-agent`, `etl`, `worker`

---

## Problem Statement

O sistema precisa extrair em massa as proposições legislativas (PEC, PL, PLS, PLP, PLC) do Senado Federal que tiveram a sua primeira votação de mérito a partir de 01/01/2023 (Legislatura 57). Essa extração é pré-requisito para o cruzamento futuro de votos nominais.
A API de Dados Abertos do Senado possui um modelo de domínio complexo e divergente da Câmara dos Deputados. O termo "deliberação" é usado como guarda-chuva para qualquer despacho, tornando inviável um filtro direto na primeira chamada. Além disso, a infraestrutura governamental (WAF) do Senado apresenta instabilidades severas e *rate-limits* agressivos, o que inviabiliza abordagens que acumulam milhares de dados em memória por horas antes de salvar no banco, arriscando perdas completas do trabalho (*OOM Kill* ou interrupções de rede).

---

## Solution

Criar um script Python autônomo (Worker) focado no Senado Federal que utilize uma arquitetura de pipeline em duas etapas (Rede de Arrasto e Detalhamento).
Na Etapa 1, o sistema varrerá o endpoint temporal `/dadosabertos/processo` assumindo o risco de falsos positivos para capturar movimentações recentes e resgatar o link original do PDF (`urlDocumento`). 
Na Etapa 2, fará requisições N+1 ao detalhamento da matéria (`/processo/{id}`) para extrair os metadados limpos e varrer as `autuacoes` e `situacoes` em busca de uma *whitelist* estrita de votações de mérito (`idTipo`: 25, 49, 89, 96, 97, 113, 146).
Para mitigar as quedas de rede do Senado, a rotina de persistência abandonará o modelo de inserção no final do lote adotado na Câmara e adotará o **Upsert Parcial**, salvando os registros na tabela `senado_proposicoes` a cada bloco concluído.

---

## User Stories

1. Como **engenheiro de dados**, quero que o script possua um modo de varredura ampla (Etapa 1) que consulte `/dadosabertos/processo?sigla=PEC&sigla=PL&sigla=PLP&sigla=PLC&sigla=PLS&dataInicioDeliberacao={data}&v=1`, filtrando diretamente na URL os tipos desejados e criando uma "rede de arrasto" para matérias movimentadas.
2. Como **analista de negócio**, quero que, ainda na Etapa 1, a `urlDocumento` seja salva temporariamente na memória, assumindo o texto inicial como um "Ponto Cego Calculado" simétrico à Câmara (ignorando eventuais substitutivos posteriores).
3. Como **arquiteto de dados**, quero que a Etapa 2 (N+1) consulte o endpoint `/dadosabertos/processo/{id}` para capturar atributos atômicos (`sigla`, `numero`, `ano`), pois a *identificação* originada da Etapa 1 é concatenada e não confiável.
4. Como **analista de regras de negócio**, quero que o filtro de mérito vasculhe listas aninhadas (nó `autuacoes` -> nó `situacoes`) comparando o campo `idTipo` contra a *whitelist* do Senado (25, 49, 89, 96, 97, 113, 146).
5. Como **engenheiro de dados**, quero que todas as situações de todas as autuações sejam agrupadas e ordenadas cronologicamente pelo campo `inicio` (YYYY-MM-DD), estabelecendo a verdadeira linha do tempo da matéria.
6. Como **arquiteto de software**, quero que a proposição seja sumariamente descartada caso a data da *primeira* votação histórica presente na *whitelist* seja anterior a 01/01/2023, mantendo aderência ao limite temporal da Legislatura 57.
7. Como **administrador de banco de dados**, quero que a coluna `id_senado` no banco seja preenchida pelo `codigoMateria` (identificador raiz imutável), enquanto o `id` da API serve apenas como ponte de roteamento e depois é descartado.
8. Como **arquiteto de dados**, quero gerar a chave primária (`id`) da tabela via UUID v5 determinístico originado do `proposicao_id` padronizado em snake_case (ex: `pls_67_2015`), facilitando upserts futuros.
9. Como **engenheiro de confiabilidade**, quero envelopar todas as requisições HTTP em um bloco da biblioteca `tenacity` com concorrência estrangulada via `asyncio.Semaphore(5)` e pausas explícitas (`asyncio.sleep(0.5)`) para ludibriar o WAF do Senado.
10. Como **engenheiro de dados**, quero que a persistência das proposições extraídas ocorra através de **Upserts Parciais** (por página de requisição ou blocos de dias), para proteger as horas de processamento caso o *worker* falhe fatalmente.
11. Como **administrador do sistema**, quero que a auditoria final na tabela `etl_logs` grave um único registro monolítico ao final da execução. Em caso de *crash*, o script deve salvar o log com status de "Erro", mas contabilizando as `linhas_afetadas` dos upserts parciais que tiveram sucesso.
12. Como **engenheiro de dados**, quero que as execuções diárias (D-1) continuem alterando dinamicamente apenas o parâmetro `dataInicioDeliberacao` da Etapa 1, para alimentar progressivamente o banco sem reprocessamento massivo.

---

## Implementation Decisions

### Eixos de Extração e Arquitetura N+1
- **Busca Ampla (Etapa 1):** O uso de `dataInicioDeliberacao` trará falsos positivos (despachos de comissão, arquivamentos). O filtro pelos tipos (PEC, PL, PLS, PLP, PLC) será resolvido via parâmetro na própria URL (`sigla=...`), poupando a necessidade de filtrá-los em memória. O script iterará apenas por essas respostas da rede de arrasto.
- **Busca Fina (Etapa 2):** Consulta isolada e estrangulada a cada `id` sobrevivente da Etapa 1. Capturará `sigla`, `numero` e `ano` da raiz do JSON de resposta.

### Filtro de Votação (Regra de Negócio)
- O script usará list comprehensions aninhadas para iterar por `payload["autuacoes"]` -> `autuacao["situacoes"]`.
- **Data Contract (Temporalidade):** A API do Senado devolve datas no formato nativo `YYYY-MM-DD` na chave `inicio`. Como o PostgreSQL aceita o tipo `DATE`, a string será usada de forma nativa e atribuída à coluna `data_votacao`, sem injeção artificial de horas.

### Controle de Estado e Persistência
- Diferente da Câmara (que salva no fim), adotaremos **Upsert Parcial**. A cada página da "rede de arrasto" processada e dedupada com sucesso, o lote resultante é enviado ao Supabase (`senado_proposicoes`).
- **Idempotência:** Baseada no UUIDv5 que concatena a sigla, o número e o ano da matéria em `snake_case`.

### Tratamento de Falhas (ETL Logs)
- Se a API retornar erros consecutivos que estourem o `tenacity`, uma exceção vai borbulhar. O bloco principal usará `try/except` para capturar o erro, finalizar a rotina prematuramente, mas o envio do log para `etl_logs` aproveitará a variável acumuladora `total_linhas` dos Upserts parciais e injetará o erro em `detalhe_erro`.

### Data Contract Mapeado
- `id` (UUID v5)
- `proposicao_id` (String - ex: `pl_985_2020`)
- `id_senado` (Integer - mapeado como o `codigoMateria` da API)
- `tipo` (String)
- `numero` (Integer)
- `ano` (Integer)
- `ementa` (String)
- `data_votacao` (Date - Formato YYYY-MM-DD)
- `url_texto_inteiro` (String - Capturado na Etapa 1 em `urlDocumento`)
- `resumo_executivo` (String - Nulo)
- `embedding_resumo_executivo` (Vector - Nulo)

---

## Testing Decisions

### Unidade (Transformadores)
- **Regra do Corte Temporal:** Alimentar a função de filtro com *mocks* de `autuacoes` contendo *situacoes* de 2022 e 2023 (ambas da *whitelist*). O teste deve afirmar que a função encontra primeiro a de 2022, falha no corte temporal e descarta toda a proposição (retorna `None`).
- **Mapeamento de Data e Id:** Assegurar via mock que a chave de negócio (`proposicao_id`) é formada pelas chaves do endpoint de detalhamento (`sigla`, `numero`, `ano`), e que a coluna `id_senado` recebe explicitamente o `codigoMateria`.
- **Determinismo:** Validar se a geração do UUIDv5 se comporta exata e simetricamente ao extrator da Câmara.

### Integração (Worker)
- **Mocking do Upsert Parcial:** Simular uma extração de duas páginas da Etapa 1. Garantir que a chamada de inserção do Supabase seja invocada **duas vezes** separadamente, diferentemente do script da Câmara.
- **Recuperação de Crash de Log:** Simular a quebra sistêmica no processamento da página 2, garantindo que o módulo de *logging* envia ao `etl_logs` o status "Erro" e `linhas_afetadas` relativo exclusivamente aos sucessos salvos na página 1.

---

## Out of Scope

- Download, parse, regex ou raspagem (scraping) do PDF da `urlDocumento`.
- Criação de sumarizações de IA da ementa (ocorrerá no módulo cognitivo posterior).
- Download dos arquivos atrelados em `documentosAssociados` (ex: substitutivos, ofícios) -> "Ponto Cego Calculado".
- Endpoint paralelo de histórico de votações nominais do Senado (escopo do extrator de votos).

---

## Further Notes

- O uso do `urlDocumento` extraído logo de partida e a exclusão da varredura complexa de PDF em `documentosAssociados` simplifica significativamente a rotina, mantendo forte coerência estrutural (simetria) com o princípio adotado na malha de dados da Câmara.