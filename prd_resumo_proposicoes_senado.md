# PRD: Pipeline de Resumo de Proposições do Senado

## Problem Statement

O sistema atual processa e resume proposições da Câmara dos Deputados extraindo o texto de PDFs e enviando para a LLM (Groq/Llama 3.1). Toda a persistência ocorre em uma única tabela no Supabase. 
Agora, é necessário criar um ecossistema irmão voltado exclusivamente para as proposições do Senado. O domínio do Senado apresenta desafios críticos específicos: PDFs colossais repletos de anexos (causando Out of Memory), proposições puramente escaneadas sem camada de texto, temas sensíveis que engatilham filtros de segurança das LLMs e a necessidade de dividir a persistência entre dois bancos de dados distintos (Supabase para texto, Qdrant para vetores), exigindo forte controle de consistência e gestão de falhas.

## Solution

Construir um pipeline ETL sequencial, resiliente e específico para as proposições do Senado. A solução fará o download do PDF, truncará a extração de texto em 100.000 caracteres para blindar o uso de RAM/CPU e enviará esse texto ao Gemini 2.5 Flash Lite (com filtros de segurança desativados) usando o mesmo System Prompt da Câmara. 
O pipeline adotará um modelo de sincronização *Qdrant-First*, onde o vetor gerado pelo BAAI/bge-m3 é persistido antes do resumo textual no Supabase, garantindo que não existam resumos sem vetores associados. Além disso, o sistema fará uma distinção categórica entre erros transitórios (que devem ser ignorados para retentativas futuras) e erros permanentes (que devem ser registrados no banco para impedir loops de falha).

## User Stories

1. Como engenheiro de dados, quero que o script processe as proposições de forma estritamente sequencial, para que a máquina não sofra um *Out Of Memory* (OOM) ao tentar abrir múltiplos PDFs pesados simultaneamente.
2. Como administrador do sistema, quero que o texto extraído do PDF seja truncado no limite de 100.000 caracteres, para poupar memória RAM e evitar custos e latências desnecessárias na inferência da LLM.
3. Como desenvolvedor, quero que a gravação do embedding no banco vetorial Qdrant ocorra *antes* da gravação do texto no Supabase, para que, em caso de falha no meio do processo, o sistema tolere um vetor órfão no Qdrant, mas jamais permita um resumo salvo sem o seu respectivo vetor de busca.
4. Como analista de dados, quero que falhas definitivas do documento (ex: PDFs puramente escaneados, links 404) sejam salvas na coluna `erro_resumo` do Supabase, para que o sistema desista definitivamente desses arquivos e não desperdice recursos nas próximas execuções.
5. Como engenheiro de operações, quero que falhas temporárias (ex: Timeout de rede, indisponibilidade da API do Gemini ou Supabase) sejam apenas logadas e *não* salvas no banco, para que a proposição permaneça elegível e seja reprocessada automaticamente no futuro.
6. Como product owner, quero que a LLM responsável pelos resumos do Senado seja a Gemini 2.5 Flash Lite (via SDK oficial do Google) com todos os filtros de segurança (`Hate Speech`, `Harassment`, etc.) configurados para `BLOCK_NONE`, para que textos legislativos com temas políticos e sensíveis não sejam censurados ou bloqueados com falsos positivos.
7. Como usuário do sistema, quero que o resumo executivo do Senado seja gerado utilizando o mesmíssimo *System Prompt* usado na Câmara (máx 400 tokens, 3 tópicos), para manter o tom de voz e o padrão de leitura da aplicação.
8. Como engenheiro de backend, quero que a `data_votacao` vinda do Supabase seja convertida para Unix Timestamp (segundos) aplicando obrigatoriamente o *timezone* `America/Sao_Paulo`, para que o payload do Qdrant reflita a temporalidade exata do momento da votação em Brasília.
9. Como engenheiro de dados, quero que o banco de dados seja consultado filtrando registros onde `id_votacao_senado IS NOT NULL`, e que não possuam dados preenchidos em `resumo_executivo` ou `erro_resumo`, para garantir que processaremos apenas o escopo pendente e válido de mérito.

## Implementation Decisions

* **Arquitetura de Sincronização (Qdrant-First):** 
  O pipeline gravará o `vector` e o `payload` na coleção `proposicoes_embeddings` do Qdrant. Apenas se esta operação for bem-sucedida, o update no Supabase (`resumo_executivo`) será disparado.
* **Gestão de Contexto e Memória:** 
  A lógica de extração que envolve o `pdfplumber` deverá possuir um limite rígido. O `string` final será truncado (`texto[:100000]`) antes de ser enviado para a integração da IA, abrangendo apenas o início do projeto e sua justificativa.
* **Classificação e Tratamento de Erros:**
  - *Erros Permanentes:* Retorno de texto vazio pelo `pdfplumber` (imagem/corrompido) ou falhas definitivas na requisição do arquivo. Atingem a tabela `senado_proposicoes` via update na coluna `erro_resumo`.
  - *Erros Transitórios:* HTTP 429, 500, 503, e `httpx.RequestError`. Atingem apenas os logs locais da aplicação; o registro continua pendente de processamento.
* **Integração com Gemini API:**
  Uso da biblioteca oficial `google-genai`. O envio de parâmetros de segurança será mapeado para garantir que a IA não faça triagem restritiva do conteúdo legislativo que recebe.
* **Parsing de Datas:**
  Considerando o contrato de que o Supabase não enviará nulos em `data_votacao`, a aplicação instanciará objetos de data baseados no fuso de Brasília (`America/Sao_Paulo`) para extrair de forma determinística a propriedade `.timestamp()`.
* **Contrato Qdrant (Payload):**
  O envio ao Qdrant respeitará o schema contendo `proposicao_id` e a data em Unix `data_votacao`, associados ao UUID raiz que vincula a tupla do Supabase ao documento no vetor.
* **Modelo de Execução:**
  Processamento estritamente sequencial. Foi deliberadamente decidido não usar concorrência (semáforos/async gather) para blindar totalmente o ambiente de exaustão de memória na etapa de I/O do PDF.

## Testing Decisions

* Os testes devem focar em isolar o comportamento de dependências externas (rede, APIs, DB).
* **Testes na extração:** Garantir que o envio de PDFs sem camada de texto retorne vazio, ativando posteriormente a marcação de "Erro Permanente" no Módulo de Processamento.
* **Testes de Integração Fake Qdrant/Supabase:** É preciso validar que, caso o driver do Supabase dispare uma exceção após uma gravação simulada bem-sucedida no Qdrant, a aplicação apenas trate o cenário como erro transitório.
* **Testes na conversão de Timestamps:** Confirmar que strings com e sem offset fornecidas simulando retornos do Supabase sempre geram o Timestamp Epoch correspondente ao horário real de Brasília, usando frameworks temporais robustos como o padrão do Python `zoneinfo`.
* **Prior Art:** A base de testes herdará os padrões em `pytest` identificados em `test_inferidor_postura.py`, usando mocks no cliente da LLM (neste caso o novo mock para o Client do Google ao invés do Groq).

## Out of Scope

* Implementação de soluções de OCR (Optical Character Recognition, ex: Tesseract) para decifrar anexos escaneados em PDF puro.
* Refatoração ou inclusão de concorrência massiva/Workers.
* Processar proposições antigas que não possuam `id_votacao_senado` populado.
* Tentar mesclar esse pipeline forçadamente com a pipeline da Câmara – eles serão scripts/módulos irmãos para facilitar manutenção independente.

## Further Notes

* O modelo de embeddings (BAAI/bge-m3) local utilizado na classe `MotorNLP` da arquitetura principal da Câmara será reutilizado exatamente da mesma forma.
* Este PRD serve como guia definitivo para iniciar o desenvolvimento dos scripts `extrator_texto_senado.py`, `resumidor_senado.py` e `pipeline_resumo_senado.py`.