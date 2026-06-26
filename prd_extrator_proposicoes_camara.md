# PRD: Extrator de Proposições (Câmara dos Deputados)

**Labels:** `ready-for-agent`, `etl`, `worker`

---

## Problem Statement

O sistema precisa extrair em massa Projetos de Lei (PLs) e Projetos de Emenda à Constituição (PECs) da Câmara dos Deputados que tiveram a sua primeira votação de mérito (texto-base) a partir de 01/01/2023. Essa extração é o pré-requisito fundamental para a futura coleta de votos nominais dos parlamentares.
A API de Dados Abertos da Câmara não possui uma flag ou endpoint que filtre diretamente "proposições votadas no mérito" ou que cruze facilmente com o texto-base que foi de fato à votação. O uso ingênuo dos endpoints pode gerar o gargalo do "N+1" (requisições excessivas de histórico para dezenas de milhares de projetos), o que estoura o rate-limit do governo e inviabiliza cargas diárias incrementais (D-1). 
Além disso, os projetos que tramitam nas duas Casas (Câmara e Senado) ganham IDs diferentes, por isso salvaremos em tabelas diferentes. 

---

## Solution

Criar um script Python autônomo (Worker) focado em extrair estritamente PLs e PECs da Câmara. O script contornará as limitações da API usando duas vias de busca otimizadas: uma varredura ampla em janelas (Backfill) e uma busca cirúrgica pelas proposições movimentadas ontem (Incremental D-1).
Para descobrir se o projeto foi à votação do mérito, o script adotará um "Ponto Cego Calculado": varrerá o endpoint cronológico `/tramitacoes` em busca de uma *whitelist* engessada de IDs de eventos (`codTipoTramitacao`: 231, 232, 233 e 1231). 
O script salvará o metadado estruturado e o link estático original do PDF (`url_texto_inteiro`) na tabela `camara_proposicoes` do Supabase utilizando Bulk Upsert e um UUID v5 sintético derivado da chave de negócio (ex: `pec_45_2019`). Esse modelo garante a blindagem contra duplicatas em processamentos repetitivos do pipeline. Nenhuma extração do conteúdo do PDF ou parse de texto ocorrerá nesta etapa.

---

## User Stories

1. Como **engenheiro de dados**, quero que o script possua um modo de Backfill que consulte `/proposicoes` em fatias temporais (ex: semestres), para capturar todo o histórico pendente desde 2023 sem sobrecarregar a memória.
2. Como **engenheiro de dados**, quero que o script possua um modo Incremental (D-1) que consulte `/proposicoes?dataInicio={ontem}&dataFim={ontem}`, para obter uma lista cirúrgica de matérias que se movimentaram, poupando requisições na rotina diária.
3. Como **arquiteto de dados**, quero que para cada proposição encontrada, o script faça uma requisição ao endpoint `/proposicoes/{id}/tramitacoes` e ordene os eventos do mais antigo para o mais recente, estabelecendo a linha do tempo do projeto.
4. Como **analista de regras de negócio**, quero aplicar o "Ponto Cego Calculado", iterando sobre as tramitações até encontrar o *primeiro* evento cujo `codTipoTramitacao` seja 231, 232, 233 ou 1231, assumindo este como a votação do Texto-Base/1º Turno.
5. Como **engenheiro de dados**, quero que, ao encontrar a data desse evento de votação principal, o script descarte silenciosamente a proposição se a data for anterior a 01/01/2023, mantendo apenas as de interesse.
6. Como **arquiteto de software**, quero gerar a chave primária (`id`) utilizando um Hash Determinístico (UUID v5) baseado na concatenação exata do tipo, número e ano da proposição (ex: `"pec_45_2019"`), consolidando a Chave de Negócio Universal.
7. Como **administrador de banco de dados**, quero salvar o `id_camara` (ID numérico interno, ex: 2265213) e o `id_votacao_camara` (ID da sessão) em colunas de restrição UNIQUE, provendo rastreabilidade para o futuro extrator de votos.
8. Como **analista de NLP**, quero que a URL original proveniente do endpoint primário da proposição seja extraída e salva como string na coluna `url_texto_inteiro`, servindo de metadado cru para download posterior em outro pipeline.
9. Como **engenheiro de dados**, quero que o campo `ementa` seja obrigatoriamente coletado e inserido no banco de dados, funcionando como fallback de contexto textual seguro caso a extração do PDF falhe futuramente.
11. Como **engenheiro de dados**, quero que as requisições HTTP sejam encapsuladas com resiliência utilizando a biblioteca `tenacity` e `time.sleep`, para suportar instabilidades, timeouts e Erros 500 recorrentes da API governamental.
12. Como **administrador do sistema**, quero que a inserção no Supabase seja feita via `Bulk Upsert` após a deduplicação em memória do lote de proposições, evitando falhas transacionais no banco (Erro 21000).
13. Como **engenheiro de dados**, quero que o `watermarker` e o log de status na tabela `etl_logs` só sejam atualizados *após* a confirmação de sucesso do lote inteiro no Upsert, protegendo a integridade da carga em caso de crash do Worker.

---

## Implementation Decisions

### Eixos de Extração e Estratégia de Rede
- **Modo Incremental D-1:** O script buscará proposições usando parâmetros estritos de data (`dataInicio` e `dataFim` iguais ao dia anterior). A API retorna projetos *movimentados* naquela data, reduzindo drasticamente o volume do laço N+1 nas `/tramitacoes`.
- **Resiliência:** Uso de `tenacity` (retry, backoff exponencial) para todas as requisições, somado a pausas de concorrência conservadoras para respeito ao rate-limit da Câmara.

### Transformação e Lógica de Negócio (O Filtro)
- A identificação do texto-base não dependerá de regex livre, mas sim de uma *whitelist* de identificadores de tramitação (`codTipoTramitacao` in `[231, 232, 233, 1231]`). Isso simplifica a manutenção e blinda o código contra ruídos de preâmbulos.
- Somente proposições classificadas como PL ou PEC entrarão na esteira de processamento.

### Idempotência e Data Contract
- A **Chave de Negócio** (`proposicao_id`) segue um padrão estrito de snake_case (ex: `pec_45_2019`).
- **UUIDv5:** Gerado injetando a string da chave de negócio na biblioteca padrão do Python `uuid`.
- **Modelo de Dados Mapeado (Dicionário do Upsert):**
  - `id` (UUID v5, PK)
  - `proposicao_id` (String, UNIQUE)
  - `id_camara` (Integer, UNIQUE, ID da API)
  - `id_votacao_camara` (String, UNIQUE, ID da sessão que validou o evento)
  - `tipo` (String)
  - `numero` (Integer)
  - `ano` (Integer)
  - `ementa` (String)
  - `data_votacao` (Date)
  - `url_texto_inteiro` (String)
  - `resumo_executivo` (String, preenchido como NULL)
  - `embedding_resumo_executivo` (Vector, preenchido como NULL)

### Controle de Estado
- O Worker isolará o estado de cada lote na memória. Caso falhe, a rotina quebra inteira, garantindo que o insert na tabela `etl_logs` nunca crie um "falso positivo" de sucesso.
- Na próxima execução, o `Bulk Upsert` varre o lote pendente e sobrescreve pacificamente as linhas pré-existentes.

---

## Testing Decisions

### Unidade e Regras de Negócio
- **Determinismo do Hash:** Testar se o gerador de UUID v5 entrega sempre a mesma string perante as mesmas chaves (ex: garantindo que PEC 45 2019 sempre culmine no mesmo ID de banco).
- **Filtro de Tramitação:** Construir testes que alimentam o motor com um array de *mocks* de tramitação (contendo destaques, emendas e a votação real no final). Afirmar que a função retorna a data correta ligada ao `codTipoTramitacao` validado e ignora os IDs irrelevantes.
- **Corte Temporal:** Testar que um mock contendo votação de mérito datada de 2022 ou anos anteriores gera um *descarte* silencioso da proposição, retornando `None` na camada de transformação.

### Integração e Comportamento
- **Mocking da API:** Simular a resposta inicial do D-1 onde nenhuma PEC/PL foi movimentada (lista vazia). Validar se o Worker encerra graciosamente registrando "0 linhas afetadas" no log.
- **Mocking de Rate-Limit:** Simular a resposta HTTP 503 e 429 do endpoint de tramitações. Assegurar que o algoritmo de backoff retenta a chamada antes de estourar a exceção geral do pipeline.
- **Supabase Upsert Mock:** Simular a chamada ao cliente Supabase assegurando que o dicionário enviado contém a coluna `url_texto_inteiro` preservada como string simples.

---

## Out of Scope

- Download, streaming, decodificação (PyPDF2/pdfplumber) ou persistência do conteúdo textual binário do PDF da proposição.
- A geração de resumos ou insumos de NLP baseados no documento.
- A criação ou uso da flag booleana `houve_substitutivo` (decisão revisada; a resiliência foca apenas no armazenamento do metadado cru original).
- Varredura de dados ou tramitações relativas ao Senado Federal.
- Coleta dos votos nominais de parlamentares (será alvo do PRD `extrator_votos`).

---

## Further Notes

- Este PRD obedece às premissas de arquitetura de dados consolidadas nos extractores predecessores (Discursos e Políticos). A resiliência de rede e a governança de log seguem estritamente a tabela `etl_logs`.
- A estratégia adotada de armazenar apenas a string da URL do texto e a Ementa age como um fallback prudente para não bloquear a fase de engenharia de dados em virtude de gargalos com scraping de PDFs quebrados do governo.