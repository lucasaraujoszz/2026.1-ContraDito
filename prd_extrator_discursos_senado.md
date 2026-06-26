# PRD: Extrator de Discursos (Senado Federal)

**Labels:** `ready-for-agent`, `etl`, `worker`

---

## Problem Statement

O sistema precisa extrair em massa os discursos (pronunciamentos) dos senadores, seguindo o exato mesmo schema de dados (Data Contract) já validado para a Câmara dos Deputados, populando a tabela específica `senado_discursos` no Supabase.
A API de Dados Abertos do Senado Federal apresenta gargalos e comportamentos radicalmente diferentes da Câmara: o payload dos endpoints não entrega o texto integral do discurso (exigindo um Web Scraping complementar em N+1 requisições), a paginação é inexistente dentro de fatias de datas, a API frequentemente ignora os filtros de data passados na URL, as respostas JSON sofrem anomalias de formatação vindas do parser nativo de XML (além de comportamentos legados em janelas sem discursos, retornando cascas vazias ou HTTP 404), e o padrão de taquigrafia requer lógica de higienização própria.

---

## Solution

Criar um script Python autônomo (Worker) irmão ao da Câmara (`extrator_discursos_senado.py`), mantendo a inversão do eixo de extração (iteração sobre senadores locais na janela de tempo). 
O pipeline exigirá requisições N+1 para a raspagem em HTML das páginas do Senado, utilizando `tenacity` e `time.sleep` para proteção contra bloqueios de rede (WAF). Devido à anomalia da API, o script deverá filtrar manualmente as datas dos discursos antes de iniciar a raspagem. A inserção em banco continuará sendo via Bulk Upsert idempotente na tabela `senado_discursos`, utilizando o `CodigoPronunciamento` nativo da API do Senado como semente do UUID v5. O pipeline de transformação isolará uma lógica dedicada de Regex e BeautifulSoup para a Casa.

---

## User Stories

1. Como **engenheiro de dados**, quero manter o eixo invertido de busca, iterando apenas sobre os senadores mapeados na base local, consultando seus pronunciamentos em fatias temporais (Semestre para Backfill, D-1 para Incremental).
3. Como **engenheiro de dados**, quero forçar o header `Accept: application/json` nas requisições HTTP, mas desejo que o código aplique um tratamento defensivo para garantir que chaves com um único discurso vindo do Senado (que retornam como `Dict` em vez de `List`) sejam sempre normalizadas para `List` antes da iteração.
4. Como **arquiteto de dados**, quero que a chave primária (UUID v5) seja garantida determinística e sem colisões mediante a concatenação do `id_senador` com o `CodigoPronunciamento` fornecido pela API.
5. Como **engenheiro de dados**, quero realizar uma segunda requisição HTTP (Scraping N+1) apontando para a `UrlTexto` de cada pronunciamento, a fim de extrair o `texto_bruto`, limitando a concorrência e respeitando pausas para não agredir a rede governamental.
6. Como **analista de NLP**, quero que o Estágio 1 de higienização seja focado e direcional, usando BeautifulSoup para encontrar o bloco/div HTML contendo o discurso, ignorando o layout inútil do portal.
7. Como **analista de NLP**, quero criar uma função isolada (`limpar_transcricao_senado`) com um pool novo de Expressões Regulares dedicadas, capazes de decepar os cabeçalhos e as idiossincrasias taquigráficas exclusivas do Diário do Senado.
8. Como **arquiteto de banco de dados**, quero mapear e injetar o campo aninhado `TipoUsoPalavra` na coluna `fase_evento` e o campo `TextoResumo` na coluna `sumario`, garantindo simetria completa de Schema com o data contract da Câmara.
9. Como **engenheiro de dados**, quero garantir a *Completude Soberana* (Fallback HTML): caso o Web Scraping N+1 retorne status HTTP 200, mas a tag contendo o texto não seja encontrada (ou o texto final extraído possuir menos de 20 caracteres/exibir mensagens de indisponibilidade), o sistema NÃO deve descartar o discurso. Deve realizar o Upsert com os metadados valiosos, inserir `[FALHA NO PARSER HTML]` no `texto_bruto` e acionar um alerta no `logger.error` listando a URL anômala para investigação manual.
10. Como **engenheiro de dados**, quero que a rotina seja defensiva contra janelas de tempo sem discursos: se a API retornar HTTP 200 sem a chave de pronunciamentos, ou HTTP 404/204, o script deve tratar silenciosamente como um "passo em branco", retornando uma lista vazia sem acionar as retentativas de rede, reservando a `tenacity` apenas para falhas reais de infraestrutura (429, 5xx, timeouts).
11. Como **engenheiro de dados**, quero que o Worker realize um expurgo local de datas (filtrando via código o campo `DataPronunciamento` recebido) antes de acionar as custosas requisições N+1, uma vez que a API da casa é falha e frequentemente devolve todo o histórico do parlamentar independentemente dos parâmetros informados.
12. Como **engenheiro de dados**, quero um *Fallback de Rede* explícito: caso as retentativas do Tenacity esgotem e haja falha de conexão (Timeout/Erro Irrecuperável), o metadado deve ser salvo injetando o valor `[ERRO DE REDE]` no `texto_bruto` para diferenciar falhas estruturais do portal de instabilidades de conectividade da máquina host.
13. Como **engenheiro de dados**, quero que o lote de discursos do Senado, após a raspagem HTML, seja deduplicado em memória (filtrando pelo ID único gerado) antes da requisição ao banco, evitando falhas de transação (Erro 21000) por duplicação em um mesmo payload da API.
14. Como **analista de NLP**, quero que as reações da plateia (ex: `(Risos)`, `[Palmas]`, `(Vozes)`) e marcações como `(Ininteligível)` capturadas nas notas taquigráficas do Senado sejam normalizadas para o padrão de chaves (`{Risos}`), mantendo a integridade e simetria de formato com a Câmara.

---

## Implementation Decisions

### Eixo de Extração e Integração
- Consulta base à tabela `senado_politicos`.
- Geração da URL da API: `https://legis.senado.leg.br/dadosabertos/senador/{id_senador}/discursos?dataInicio={inicio}&dataFim={fim}`.
- Sem lógica de links `rel="next"`, uma vez que o Senado não pagina os retornos atrelados a blocos de data.
- Anomalia JSON/XML (Root Keys): Devido a mudanças estruturais da API, a normalização deve prever tanto a raiz `"PesquisaPronunciamentos"` quanto o fallback legado `"DiscursosParlamentar" -> "Parlamentar"`. Além disso, implementar verificação `if isinstance(pronunciamentos, dict): pronunciamentos = [pronunciamentos]`.
- Cenários sem Discursos: Capturar explicitamente HTTP 404/204 ou JSONs vazios na chave principal e retornar `[]` ignorando falhas, assegurando avanço do loop.
- **Proteção de Extração (Expurgo N+1):** Verificar manualmente se a data base (split no `"T"`) atende aos limitadores `data_inicio` e `data_fim` antes do scraping do HTML de fato.

### Mitigação do N+1 e Scraping
- O tráfego para acessar a `UrlTexto` deve ocorrer de forma síncrona.
- O scraping HTML deve ser blindado contra bloqueios básicos do WAF do Senado (Rate Limit/Bot protection) injetando obrigatoriamente o header `User-Agent: Mozilla/5.0` nas chamadas.
- Utilização obrigatória da biblioteca `tenacity` para encapsular requisições, parametrizando retentativas **apenas** em caso de *Rate Limits* (HTTP 429) ou instabilidades do portal governamental (HTTP 500, 502, 503, 504) e *timeouts*.
- Implementação de `time.sleep(0.5)` entre o processamento de parlamentares/discursos para polidez extrema de tráfego.

### Higienização e Transformação Isolada
- Módulo específico de transformação.
- **Scraping em Cascata (3 Níveis):** A extração do texto HTML deve seguir uma hierarquia de resiliência: 1) Busca direta por containers alvo (múltiplas classes/IDs como `textoIntegral` e `texto-pronunciamento`); 2) Caso falhe, buscar por título âncora "Texto integral" e capturar os parágrafos irmãos subjacentes; 3) Varredura cega nos parágrafos da página por expressões regulares de taquigrafia (ex: `O SR.`).
- Limpeza (Regex) das aberturas de oradores do Senado, remoção de lixo sistêmico injetado pelo portal (ex: prefixo `Texto integral não disponível!`) e conversão de anomalias taquigráficas para chaves (`{Reação}`).
- Mapeamento direto de metadados para garantir integridade do Bulk Upsert em lote. `url_video` será populado como `None`.

### Idempotência
- UUID v5 usando namespace próprio da aplicação gerado via string: `f"{id_senador}_{CodigoPronunciamento}"`.
- Deduplicação em memória do array de dicionários mapeados (garantindo valores únicos pela chave `id`) antes de disparar o método `upsert` na biblioteca cliente do Supabase.

---

## Testing Decisions

### Unidade (Transformação e Scraping)
- **TDD de Hash Determinístico:** Garantir que o mesmo ID de senador e mesmo `CodigoPronunciamento` gerem o idêntico UUIDv5.
- **Normalização de Payload:** Testar função de parse validando que ela converte adequadamente tanto uma resposta `Dict` (1 discurso) quanto uma `List` (n discursos) para o iterador padrão.
- **Fallback de Layout:** Mocar o carregamento de uma página HTML perfeitamente válida estruturalmente, mas que não contenha as tags mapeadas para o texto. O teste deve aferir que `[FALHA NO PARSER HTML]` foi assinalado, os metadados mantidos e o `logger.error` devidamente invocado.
- **Fallback de Conexão:** Testar e garantir que instabilidades severas que esgotem o limitador do pacote tenacity registrem devidamente o metadado `[ERRO DE REDE]`.
- **Limpeza Taquigráfica:** Validar com base em amostras HTML brutas do portal do Senado, assegurando o bypass de rodapés ou lixos da página.
- **Janelas Vazias Defensivas:** Testar que um retorno HTTP 404 ou um JSON vazio devolva uma lista vazia sem disparar exceções nem ativar a `tenacity`.

### Integração (Resiliência N+1)
- **Rate Limit Mock:** Simular a `UrlTexto` devolvendo erros HTTP 429/500 nas primeiras tentativas e um 200 de sucesso na tentativa final, garantindo o disparo e recuperação corretos pelo módulo `tenacity`.

---

## Out of Scope

- Busca de mídias atreladas ao "Senado Multimídia" ou links de Youtube.
- Migração/refatoração do script já estável `extrator_discursos.py` (Câmara).
- Rotinas genéricas de Data/NLP já externalizadas em bibliotecas auxiliares de IA.

---

## Further Notes

- O código-fonte acompanhará o mesmo esqueleto e assinaturas do pipeline irmão, injetando ao final na tabela `senado_discursos` e finalizando o ciclo gravando métricas de orquestração na tabela `etl_logs` (registrando `status`, a somatória de `linhas_afetadas` processadas e o `detalhe_erro` caso o processo aborte).