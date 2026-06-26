# PRD: Chunker e Vetorizador de Discursos (Senado Federal)

**Labels:** `ready-for-agent`, `etl`, `worker`

---

## Problem Statement

O sistema precisa processar o texto bruto dos discursos históricos e diários dos parlamentares do Senado Federal, dividindo-os em fragmentos menores (chunks) e gerando seus respectivos vetores dimensionais (embeddings). Diferentemente do pipeline existente da Câmara dos Deputados (que armazena tanto o texto quanto o vetor em um banco relacional), a arquitetura para o Senado exige uma "dupla escrita" (*dual-write*): o texto fatiado deve ir para o Supabase, enquanto os vetores e seus metadados atrelados devem ir para um banco de dados vetorial especializado (Qdrant).

Essa dupla escrita introduz um problema crítico de sistemas distribuídos: a suscetibilidade a falhas parciais (ex: transação de texto concluída com sucesso no relacional, mas falha de rede/timeout na inserção vetorial). O uso da abordagem legada de IDs aleatórios resultaria em perda irreparável de sincronia, duplicação de dados nas retentativas e "sujeira" nos bancos. Além disso, precisamos carregar as propriedades do discurso pai diretamente no payload do vetor para garantir o funcionamento do filtro de metadados em futuras arquiteturas de RAG (Geração Aumentada de Recuperação).

## Solution

Criar um script autônomo (Worker) denominado `chunker_discursos_senado` que fará a leitura incremental dos discursos do Senado já higienizados. A solução utilizará um filtro em memória de baixa latência para identificar discursos ainda não processados. A inovação central arquitetural será o abandono completo de identificadores aleatórios para os chunks; em vez disso, o sistema fará uso de Hashes Determinísticos (UUID v5) baseados na composição exata do ID do discurso original e no índice do chunk.

Dessa forma, o texto será fatiado usando `RecursiveCharacterTextSplitter`, os embeddings gerados pelo modelo `BAAI/bge-m3`, e as inserções ocorrerão rigorosamente por operações de Upsert nas duas pontas (Supabase e Qdrant). Qualquer falha de rede interromperá o lote, mas na re-execução, a propriedade idempotente do UUID garantirá a sobreposição pacífica dos dados parciais, reparando o espelhamento das bases sem criar registros fantasmas.

## User Stories

1. Como **engenheiro de dados**, quero que o pipeline busque em memória os IDs dos discursos já processados no Supabase e utilize a instrução `NOT IN` na query de busca, para garantir a leitura incremental ignorando o que já foi fatiado, aproveitando a baixa volumetria histórica do Senado (~3500 discursos).
2. Como **engenheiro de dados**, quero que a query primária no banco relacional já traga de imediato as colunas `id`, `texto_bruto`, `politico_id` e `data_discurso`, para que eu tenha todo o contexto necessário em memória sem precisar de custosos `JOINs` posteriores.
3. Como **arquiteto de sistemas**, quero que o `politico_id` permaneça estritamente com sua tipagem original (Integer) durante todo o ciclo e no payload final, para manter simetria de chaves estrangeiras com a API oficial do Senado.
4. Como **cientista de dados**, quero que o fatiamento do texto bruto seja feito com o `RecursiveCharacterTextSplitter` (LangChain), utilizando tamanho de chunk de 1000 caracteres e sobreposição de 200, para preservar a integridade semântica da fala do parlamentar.
5. Como **cientista de dados**, quero que cada chunk de texto seja submetido ao modelo local `BAAI/bge-m3` via `SentenceTransformers` para a geração de sua representação vetorial.
6. Como **arquiteto de software**, quero que o ID gerado para cada chunk seja estritamente um UUID v5 Determinístico originado do formato `"{discurso_id}_chunk_{indice}"`, garantindo que múltiplas passagens pela mesma string resultem num identificador inalterável.
7. Como **engenheiro de dados**, quero que a inserção no banco de dados relacional (Supabase) utilize o método `Upsert` em vez de `Insert`, para que re-execuções de contingência sobreponham registros antigos sem quebrar restrições de chaves únicas.
8. Como **engenheiro de dados**, quero que o Upsert dos vetores no Qdrant ocorra de forma síncrona imediatamente após o sucesso da transação correspondente no Supabase, contornando a armadilha do Dual-Write.
9. Como **cientista de dados**, quero que o Payload injetado em cada vetor no Qdrant seja composto imperativamente pelas chaves `"politico_id"` (Integer), `"discurso_id"` (UUID) e `"data_discurso"` (Data/Timestamp), permitindo filtros avançados durante processos de RAG.
10. Como **engenheiro de DevOps**, quero que o script parta da premissa arquitetural de que a coleção vetorial já existe no Qdrant, limitando o escopo do código apenas ao tráfego de dados e delegando a responsabilidade de infraestrutura para scripts migratórios.

## Implementation Decisions

### Controle de Estado (Watermarker na Memória)
- O script fará uma varredura inicial (SELECT) na tabela filha `senado_discursos_chunks` extraindo todos os `discurso_id` já registrados, armazenando-os num `Set` do Python.
- Na consulta principal sobre `senado_discursos`, um filtro `not_.in_("id", list(ids_processados))` restringirá o universo pendente, contornando a necessidade de alterar as tabelas ou criar Views no PostgreSQL.

### Resiliência ao Dual-Write (Dupla Escrita)
- **Hash Determinístico:** O script abandonará o módulo `uuid.uuid4()` utilizado na Câmara. Aplicaremos namespace padronizado gerando um UUID v5 calcado na string `{discurso_id}_chunk_{i}`. O ID do Supabase e o ID do Qdrant serão exatamente o mesmo.
- **Inserção Idempotente:** Todas as requisições de persistência, via SDK do Supabase e via `qdrant-client`, serão de Upsert.

### Contrato de Dados (Supabase - Relacional)
A tabela `senado_discursos_chunks` receberá estritamente:
- `id`: UUID (v5, chave primária sintética)
- `discurso_id`: UUID (chave estrangeira atrelada à tabela pai)
- `texto_chunk`: String (trecho particionado do discurso original)

### Contrato de Dados (Qdrant - Vetorial)
A coleção alvo será `chunks_discursos_embeddings` recebendo o Point:
- `id`: UUID (idêntico ao gerado para o Supabase)
- `vector`: Float Array (gerado pelo encoder BAAI)
- `payload`: 
  ```json
  {
    "politico_id": <Integer>,
    "discurso_id": "<UUID>",
    "data_discurso": <Date/Timestamp>
  }
  ```

### Orquestração da Inserção
O laço lógico seguirá a sequência: Lote Limpo -> Quebra em Chunks -> Embeddings -> Geração do Hash v5 -> Upsert no Relacional -> Upsert no Vetorial. Falhas estourarão exceções não tradadas encarregando a próxima inicialização do CRON de aplicar a recuperação natural via idempotência.

## Testing Decisions

### Testes de Unidade e Idempotência
- Testar a fábrica de Hash garantindo que um mesmo `discurso_id` ("uuid-mock-123") e mesmo índice numérico (ex: `0`) resulte permanentemente em um hash estático e imutável.
- Testar a função de formatação do Payload, certificando-se de que nenhum tipo estranho de dado seja submetido para o Qdrant (especialmente certificando que o `politico_id` não seja convertido magicamente em string ou UUID e que permaneça Integer).

### Testes de Comportamento e Resiliência
- Mock das bibliotecas de rede (`supabase` e `qdrant-client`) para validar o fluxo de Upsert síncrono.
- Criação de um teste simulando uma falha de conexão com o Qdrant (Timeout Exception) disparada propositalmente *após* a resposta de sucesso do mock do Supabase. O teste deve assegurar que a execução seja imediatamente abortada e que não siga para o próximo discurso, atestando a proteção da integridade transacional.

## Out of Scope

- A criação programática das coleções no Qdrant (parâmetros de COSINE/1024 dims). A infraestrutura pré-existente será assumida como verdade.
- Refatoração ou readequação do antigo script `chunker_discursos_camara.py` (cujo funcionamento é unicamente relacional no Supabase).
- Consultas, LLMs interrogativos ou a aplicação de Geração Aumentada (Retrieval) sobre os dados gerados.

## Further Notes

- A decisão de manter o filtro na memória por `NOT IN` foi tomada sob a premissa quantitativa de que a volumetria máxima para o Senado orbita os 3.500 discursos, sendo perfeitamente suportada pelos Workers sem *Out of Memory*. Caso isso escalasse drasticamente no futuro, o design recomendaria a transição para uma procedure no Postgres (`RPC`).
- A aderência arquitetural baseada nos metadados de parlamentares segue a padronização oficial de IDs documentada nos repositórios irmãos da raspagem.