# PRD: Extrator de Discursos (Câmara dos Deputados)

**Labels:** `ready-for-agent`, `etl`, `worker`

---

## Problem Statement

O sistema precisa extrair em massa o histórico e o fluxo diário de discursos em texto não estruturado dos parlamentares por meio da API da Câmara dos Deputados.
A API governamental foca em endpoints por entidade (deputado) e carece de rotas globais eficientes por dia. Além disso, o texto da transcrição chega "sujo", repleto de artefatos HTML, entidades não codificadas e cabeçalhos protocolares longos ("preâmbulos") que consomem armazenamento inútil e oneram tokens no futuro processamento de IA.
Há ainda a necessidade de realizar a carga massiva histórica de anos inteiros sem estourar *rate-limits* ou perder dados em interrupções no meio da madrugada.

---

## Solution

Criar um script Python autônomo (Worker) que inverte o eixo tradicional de extração: em vez de consultar a Câmara de forma global, ele iterará sobre a tabela local de deputados e consultará os discursos em fatias temporais (Janelas).
A carga inicial (Backfill) consumirá janelas de 1 semestre, e a carga contínua (Incremental) será diária (D-1). O texto de cada discurso passará por um pipeline rigoroso de higienização de 3 estágios (com fallback de completude) e será salvo via Bulk Upsert no Supabase, utilizando um Hash Determinístico (UUID v5) para garantir idempotência perfeita. O avanço do controle de estado (*watermarker*) apenas ocorrerá ao fim do ciclo de cada janela.

---

## User Stories

1. Como **engenheiro de dados**, quero inverter o eixo de busca iterando sobre todos os deputados da base local (513 ativos + suplentes/inativos) consultando as rotas `/api/v2/deputados/{id}/discursos`, para contornar a ausência de endpoints globais na API da Câmara.
2. Como **engenheiro de dados**, quero garantir que o script capte os links de paginação interna (usando `rel="next"`) dentro da resposta de cada deputado, para que nenhum discurso fique para trás se o volume exceder os limites da página na janela solicitada.
3. Como **administrador do banco**, quero processar a carga histórica (Backfill) em fatias de 1 Semestre, para realizar a ingestão de todo o escopo a partir de janeiro de 2023 de forma rápida e agrupada.
4. Como **administrador do sistema**, quero que a carga Incremental ocorra diariamente pegando apenas a janela do dia anterior (D-1), mantendo as requisições HTTP seguras, leves e velozes.
5. Como **arquiteto de software**, quero gerar a chave primária de cada discurso via um Hash Determinístico (UUID v5), concatenando estritamente os campos `id_deputado`, `dataHoraInicio` e `faseEvento`, para permitir Bulk Upserts idempotentes mesmo sem um ID formal da Câmara.
6. Como **engenheiro de dados**, quero que o avanço da data do `watermarker` global na tabela `etl_logs` aconteça apenas quando a janela temporal inteira (para todos os deputados da iteração) for inserida com sucesso com 100% de completude, para blindar o estado contra falhas no meio de um lote.
7. Como **analista de dados (NLP)**, quero que os textos passem pelo Estágio 1 de higienização (BeautifulSoup), para remover marcações e decodificar qualquer entidade HTML (como `&#x97;`).
8. Como **analista de dados (NLP)**, quero que os textos passem pelo Estágio 2 de higienização (Regex agressivo), para decepar cabeçalhos protocolares que não agregam valor (ex: `"O SR. AÉCIO NEVES (Bloco/PSDB - MG. Para discursar...) - Sr. Presidente..."`).
9. Como **analista de dados (NLP)**, quero que os textos passem pelo Estágio 3, normalizando duplos espaços, quebras de linha e executando `strip()`, para enxugar o texto bruto final.
10. Como **engenheiro de dados**, quero um comportamento de *Fallback* que garanta a completude: se a Regex do Estágio 2 falhar em fatiar o texto, o sistema não deve descartar o discurso; ele deve salvar o texto do Estágio 1 + 3 (sem HTML, com cabeçalho original) e disparar um `logger.warning`, garantindo retenção de 100% dos dados da câmara na tabela `camara_discursos`.
11. Como **desenvolvedor**, quero que o contrato de dados gerado para o Bulk Upsert no banco siga estritamente as colunas acordadas no schema relacional da IA.
12. Como **engenheiro de dados**, quero que o lote de discursos extraídos seja deduplicado em memória antes do envio ao banco, para evitar falhas de transação por colisão de chave primária (Erro 21000) no PostgreSQL.
13. Como **engenheiro de software**, quero que o sistema detecte vazamentos binários (arquivos DOCX crus) vindos da API antes de tentar processar o HTML, descartando a sujeira pesada para evitar estouro de memória e crashes.
14. Como **analista de dados (NLP)**, quero que notas taquigráficas curtas e reações da plateia (ex: `(Risos)`, `[Palmas]`) sejam normalizadas para um padrão único com chaves (`{Risos}`), facilitando o manuseio futuro pelos modelos de linguagem.
15. Como **engenheiro de dados**, quero que requisições HTTP falhas (ex: 500, 503, 429) sejam retentadas com backoff progressivo antes de declarar erro irreversível, garantindo resiliência da extração noturna.
16. Como **engenheiro de dados**, quero que a limpeza de transcrições nulas ou vazias retorne uma string vazia instantaneamente sem disparar exceções, mantendo a estabilidade do pipeline.

---

## Implementation Decisions

### Eixo de Extração e Janelas Temporais
- O script acessará inicialmente a tabela interna `camara_politicos` do Supabase para coletar a lista de IDs oficiais a serem percorridos.
- Para cada deputado, a consulta à Câmara (`GET /discursos`) conterá os parâmetros `dataInicio` e `dataFim`.
- Se no payload original houver paginação na tag `links`, o script deve seguir recursivamente as URLs em `rel="next"` até esgotar a página daquele deputado dentro do semestre/dia.
- A execução será semestral para backfill e em D-1 contínuo via cron para o incremental diário.

### Idempotência e Checkpointing
- **UUID v5 Sintético:** Implementar no módulo de transformação uma lógica baseada na biblioteca `uuid` que receba os identificadores unívocos do contexto da câmara.
  - **Fórmula rígida de concatenação:** `id_deputado` + `dataHoraInicio` + `faseEvento`.
- **Deduplicação em Memória:** Antes da inserção no banco, o script realiza um filtro em memória no array gerado para reter apenas valores únicos (por chave ID), impedindo que dados duplicados devolvidos erroneamente no payload da API quebrem o *Bulk Upsert*.
- O *Bulk Upsert* resolverá os conflitos com base nesse UUID `id` pelo método oficial do Supabase em Python.
- O UPDATE no `watermarker` dentro da tabela `etl_logs` só rodará no final da execução bem-sucedida do loop principal, garantindo que "janelas caídas pela metade" refaçam todo o seu conteúdo na próxima vez através de sobreposições limpas (Upsert).

### Resiliência de Rede e Tratamento Defensivo
- **Estratégia de Retry/Backoff:** Implementar no módulo extrator retentativas mecânicas (ex: `time.sleep` progressivo) utilizando a biblioteca `httpx` para contornar instabilidades do servidor governamental (Erros 500, 503 e 429).
- **Tipagem Defensiva (`faseEvento`):** A extração do payload deve prever e contornar a anomalia da API da Câmara em que o campo `faseEvento` pode vir como um Dicionário (ex: `{"titulo": "Evento"}`) ou erroneamente como uma String direta.
- **Nulos e Vazios:** Tratar entradas `None` ou `""` de antemão na função de limpeza de transcrição, retornando `""` precocemente.

### Higienização de Texto e Fallback
- Criar uma função dedicada (ex: `limpar_transcricao`) no pacote/módulo de transformação isolado (Pipe and Filter).
- **Vazamento Binário (Pré-estágio):** Interceptação imediata de strings que contenham assinaturas de arquivos DOCX/ZIP (ex: `PK!`, `[Content_Types].xml`), substituindo-as por uma flag de arquivo corrompido para não quebrar o parser HTML.
- **Estágio 1:** `BeautifulSoup(texto, "html.parser").get_text(separator=" ", strip=True)` e `html.unescape`.
- **Estágio 2:** Aplicação de expressões regulares avançadas (uso de *lookahead* para parar cortes imediatamente antes de saudações como "Senhor Presidente", suporte flexível a chaves/colchetes e tolerância a erros ortográficos como `PRONUN?CIAMENTO`) para extirpar cabeçalhos protocolares.
- **Normalização Taquigráfica:** Aplicação de regex secundária para padronizar reações breves em parênteses ou colchetes convertendo-as para chaves `{}`.
- **Estágio 3:** Substituição de `\s+` por `" "` usando regex e aplicação do `strip()`.
- **Plano B:** Bloqueio transacional `try/except` local ou checagem de match na Regex. Falhando a expressão, loga-se usando a biblioteca de logging (`logger.warning("Regex falhou no discurso ID...")`) e retorna o texto contendo o cabeçalho bruto da Câmara preservado e sem HTML.

### Schema Estrito (Data Contract)
O modelo do dicionário final para a lista inserida em lote no Supabase deverá conter exclusivamente:
- `id` (UUID v5, string)
- `politico_id` (Integer, ID original da câmara mapeado como FK)
- `data_discurso` (Datetime, extraído do `dataHoraInicio`)
- `fase_evento` (String, título do momento do evento)
- `sumario` (String, opcional/nullable)
- `texto_bruto` (String, texto integral final pós-higienização)
- `url_video` (String, opcional/nullable)

---

## Testing Decisions

### Unidade e NLP
- Escrever cenários garantindo que a geração do Hash seja estritamente determinística (a mesma trinca de entradas devolve sempre a mesma string UUID).
- Testar a função de sanitização em isolamento:
  - **Caminho Feliz:** Enviar um *dummy text* com tags HTML sujas e um cabeçalho padrão simulado. Assert de que o texto final retornado perdeu o HTML, perdeu o cabeçalho, e de que não perdeu o conteúdo útil.
  - **Caminho Excepcional (Fallback):** Enviar um *dummy text* onde não há formatação reconhecível de orador. Assert de que a função limpa as sujeiras HTML, devolve o texto íntegro (com o cabeçalho irregular mantido) e não levanta nenhuma `Exception` ou descarte.
  - **Anomalias de Regex:** Testar resiliência contra lixo binário, erros de digitação da taquigrafia (ex: esquecimento de fechar parênteses) e injeção direta de ofícios ou palavras indevidas como "CÂMARA DOS DEPUTADOS".

### Comportamento e Mocks
- Mocagem (mock) da API para simular a resposta de um array vazio no semestre e garantir que o iterador avança para o próximo deputado graciosamente.
- Mocagem para simular paginação extra (presença da chave `rel="next"`), atestando que a recursividade/loop do script consome todas as ramificações de páginas de discursos.
- Mocagem para atestar que discursos duplicados entregues pela API em uma mesma requisição não atinjam a camada de Upsert do banco de dados (deduplicação no cliente ETL).
- Mocagem de falhas de servidor governamental (Status > 500 ou 429) via *mock* HTTP para validar a ativação correta do algoritmo de *backoff* progressivo antes do descarte ou sucesso da requisição.

---

## Out of Scope

- O fatiamento pragmático deste texto em trechos de análise (Chunking).
- A geração de Embeddings via IA baseada nesse discurso (OpenAI/Gemini/etc).
- Inserção dos Embeddings na infraestrutura vetorial nativa (`pgvector`).
- Alterações de schema das tabelas originais `camara_politicos` ou scripts já validados de extração do perfil dos deputados.

---

## Further Notes

- Apesar do código residir na mesma infraestrutura e utilizar as lógicas básicas de backoff e log de orquestração validadas em ferramentas prévias (`etl_logs`), este PRD não requer repetição dos arquivos ou regras de conexão macro-arquiteturais já consolidadas em `docs/`.
- Este script alimenta exclusivamente a nova entidade relacional `discursos`. O encerramento das responsabilidades deste ETL se dá rigorosamente após a inserção do texto higienizado íntegro (Bulk Upsert), sem interferência ou chamada direta a módulos de LLM.