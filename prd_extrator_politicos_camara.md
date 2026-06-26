# PRD: Extrator de Políticos (Câmara dos Deputados)

**Labels:** `ready-for-agent`, `etl`, `worker`

---

## Problem Statement

O sistema necessita de uma rotina automatizada e isolada para popular a tabela `camara_politicos` com os dados atualizados dos deputados federais em exercício.

A fonte primária (API de Dados Abertos da Câmara) possui rate-limits estritos e payloads com excesso de dados irrelevantes, enquanto o banco de dados destino (Supabase) possui limites transacionais que penalizam inserções unitárias sucessivas.

A ausência de uma rotina resiliente pode gerar bloqueios de IP (banimento do governo) ou dados incompletos/corrompidos na base que alimentará a IA do domínio (conforme modelo estabelecido no MkDocs do projeto).

---

## Solution

Criar um script Python puro, rodando de forma procedimental (padrão Pipe and Filter documentado no Worker) via cron no container do Worker.

O script extrairá a lista de deputados da legislatura atual de forma paginada.

Para cada página, buscará de forma síncrona, conservadora (com sleeps) e com resiliência (backoff de 3 retries) os detalhes individuais de cada político para extrair o `nome_civil` e adequar o `status_mandato`.

Os dados serão limpos, transformados para o schema exato do banco e acumulados em memória.

O envio ao Supabase ocorrerá por meio de um único Bulk Upsert por página via SDK Oficial (REST API), garantindo eficiência e evitando duplicações via chave `id`.

Falhas completas em políticos específicos serão descartadas e geradas em log nativo.

O status da rotina será persistido na tabela `etl_logs`.

---

## User Stories

- Como **administrador do sistema**, quero que o script de extração seja executado em background via agendador do sistema (cron), para manter a arquitetura plana e sem dependência prematura de mensageria (Celery).

- Como **engenheiro de dados**, quero que a chamada primária à API da Câmara filtre unicamente a legislatura atual (`idLegislatura=57`), para limitar o escopo de ingestão à manutenção contínua da base de políticos ativos/recentes.

- Como **engenheiro de dados**, quero que a paginação seja controlada dinamicamente lendo o atributo `rel="next"` do array de links da API, para evitar chamadas extras ou erros 404 de força bruta.

- Como **arquiteto**, quero que as chamadas secundárias para buscar detalhes do político (`/api/v2/deputados/{id}`) ocorram de forma síncrona dentro de um loop, com pausas (`time.sleep`) de `0.5s` a `1s` entre elas, para respeitar implicitamente o rate-limit do provedor governamental.

- Como **engenheiro de dados**, quero que qualquer chamada de rede à API do governo conte com um mecanismo de repetição (retries) de no máximo 3 tentativas com backoff exponencial, para assegurar tolerância a falhas temporárias da infraestrutura externa.

- Como **analista de qualidade de dados**, quero que, se um deputado falhar as 3 tentativas de detalhamento, ele seja ignorado e não entre no lote da página (gerando apenas um registro no logging nativo), para impedir que registros pela metade sejam salvos no banco.

- Como **engenheiro de dados**, quero que as propriedades recebidas da API passem por um filtro e transformação estritos (descartando o payload original) antes de irem para memória, para garantir conformidade exata com as regras da tabela `camara_politicos` e evitar vazamento de lixo de dados.

- Como **administrador de banco de dados**, quero que o script realize um único envio transacional (Bulk Upsert) por página para o Supabase usando a SDK Oficial do Python (`supabase-py`), para otimizar conexões HTTP/REST.

- Como **administrador de banco de dados**, quero que o upsert resolva conflitos utilizando a chave primária `id` (ID da Câmara), para garantir a idempotência da rotina sem duplicar registros.

- Como **desenvolvedor**, quero que ao final da execução do script (com sucesso ou erro), os metadados da rotina sejam registrados em um insert na tabela `etl_logs` (ignorando temporariamente o campo `watermarker`), para permitir auditoria e monitoramento do pipeline.

---

## Implementation Decisions

### Infraestrutura e Orquestração

- O script viverá no contexto do Worker documentado no nosso MkDocs, porém como um executável Python isolado (ex: `extrator_deputados.py`).
- Nenhum setup de Celery será feito agora. A chamada ocorrerá por cron padrão de container Linux.

---

### Conexão de Banco

- Será instalada e configurada a biblioteca oficial `supabase`.
- A autenticação usará a `SUPABASE_URL` e `SUPABASE_SERVICE_ROLE_KEY` mapeadas nas variáveis de ambiente.

---

### Controle de Fluxo (ETL Pipeline)

#### Extract (Página)

Requisição `GET` na rota base com `idLegislatura=57`.

#### Extract (Detalhes)

Iteração no array de dados.

Aplicação da biblioteca `tenacity` (ou implementação manual) para gerenciar o retry (3 tentativas, backoff).

#### Rate-Limit

Uso obrigatório de `time.sleep` entre as chamadas individuais dentro da mesma página.

#### Transform

O payload montado **NÃO** espelhará a API.

As chaves serão hardcoded no script conforme o modelo:

- `id`
- `nome_civil`
- `nome_urna`
- `partido`
- `cargo = 'deputado'`
- `estado`
- `url_foto`
- `status_mandato`

#### Regra de Domínio (Mapeamento de Status)

Será necessário implementar uma lógica que traduza os status retornados pela Câmara em nosso enum de domínio:

- `ativo`
- `inativo`
- `suplente`

#### Load

O array processado de dicionários Python será enviado via:

```python
supabase.table('camara_politicos').upsert(lista_deputados).execute()
```

---

### Tratamento de Erros e Logs

- O bloco `try/except` isolará os deputados.
- Uma falha final dispara:

```python
logger.error("Falha ao processar ID {id}")
```

- Em seguida, usa o comando `continue` no loop.
- Ao final do laço `while` global (quando não houver `rel="next"`), constrói-se o payload para `etl_logs`:
  - `id_execução`
  - `nome_rotina`
  - `data_inicio`
  - `data_fim`
  - `status`
  - `linhas_afetadas`
  - `detalhe_erro`
- Por fim, executa um insert único.

---

## Testing Decisions

### Unidade

- Testar a função de transformação de payload (entrando JSON sujo da Câmara, saindo dicionário estrito do Supabase).
- Testar a função mapeadora do `status_mandato`, certificando-se de que diferentes strings do governo se convertem corretamente para `ativo`, `inativo` e `suplente`.

### Mocking

- Testes de fluxo de extração não devem bater na API real.
- Usar bibliotecas como `responses` ou `httpx-mock` para simular:
  - Retornos da lista (incluindo `rel="next"`)
  - Retornos de detalhes
- Simular o limite de exceções:
  - Forçar a API mockada a dar timeout ou `500`
  - Repetir 3 vezes seguidas
  - Garantir (por assert) que o método não quebra o script, apenas gera log e ignora o item

---

## Out of Scope

- Implementação ou refatoração no Celery / Celery Beat.
- Extração de Senadores ou de políticos de legislaturas anteriores à 57.
- Atualização das colunas `score_coerencia` e `dados_insuficientes` (pertencerão a rotinas/workers futuros baseados em IA).
- Lógica e preenchimento da coluna `watermarker` na tabela `etl_logs`.
- Uso de ORMs pesados (`SQLAlchemy`) ou conexão PostgreSQL direta via porta relacional (`5432`) para este worker específico.

---

## Further Notes

- Consulte os esquemas de entidade e padrões de separação arquitetural na pasta `docs/` do projeto (MkDocs) para manter o alinhamento com a arquitetura macro.
- A coluna `cargo` sempre será preenchida com a string literal `'deputado'` para futuras diferenciações de domínio na mesma tabela.