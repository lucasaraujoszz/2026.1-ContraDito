# Integração e API (Rotas e Swagger)

Esta documentação especifica todas as rotas ativas da API **ContraDito**. Ela serve como guia oficial de integração para a equipe de Front-end (Next.js).

---

## 1. Visão Geral da Integração
* **URL Base Local**: `http://localhost:8000`
* **Porta de Desenvolvimento (CORS)**: O frontend Next.js deve rodar em `http://localhost:3000` para estar coberto pelas regras de liberação de CORS.
* **Documentação Interativa (Swagger)**: Com os contêineres em execução, toda a documentação de schemas, contratos e testes de rotas está disponível automaticamente em `http://localhost:8000/docs` (ou na porta configurada para a API).
* **Caches**: Rotas de listagem geral possuem cache em memória com validade de 1 hora (`3600` segundos).
* **Ausência de Score**: As métricas de *Coherence Score* e a flag *dados_insuficientes* foram removidas definitivamente.

---

## 2. Detalhamento das Rotas por Categoria

---

### Categoria A: Parlamentares (Perfil, Votos e Afinidades)

#### 1. Listar e Filtrar Políticos
* **Método / Path**: `GET /api/{casa}/politicos`
* **Parâmetros**:
  * `{casa}` (Path): `"camara"` ou `"senado"` (obrigatório).
  * `busca` (Query, opcional): Busca por parte do nome de urna.
  * `partido` (Query, opcional): Sigla do partido (ex: `PL`, `PT`).
  * `estado` (Query, opcional): Sigla da UF com 2 letras (ex: `SP`, `DF`).
  * `pagina` (Query, opcional): Inteiro (padrão `1`).
  * `tamanho` (Query, opcional): Inteiro (padrão `20`).

#### 2. Obter Perfil Detalhado
* **Método / Path**: `GET /api/{casa}/politicos/{id_parlamentar}`
* **Parâmetros**:
  * `{casa}` (Path): `"camara"` ou `"senado"`.
  * `{id_parlamentar}` (Path): ID numérico do político.

#### 3. Linha do Tempo de Votações (Individual)
* **Método / Path**: `GET /api/{casa}/politicos/{id_parlamentar}/timeline`
* **Parâmetros**:
  * `{casa}` (Path): `"camara"` ou `"senado"`.
  * `{id_parlamentar}` (Path): ID do político.

#### 4. Afinidades Políticas (Gêmeo e Antípoda)
* **Método / Path**: `GET /api/{casa}/politicos/{id_parlamentar}/afinidades`
* **Parâmetros**:
  * `{casa}` (Path): `"camara"` ou `"senado"`.
  * `{id_parlamentar}` (Path): ID do político.

#### 5. Fidelidade Partidária Bruta
* **Método / Path**: `GET /api/{casa}/politicos/{id_parlamentar}/fidelidade`
* **Parâmetros**:
  * `{casa}` (Path): `"camara"` ou `"senado"`.
  * `{id_parlamentar}` (Path): ID do político.

---

### Categoria B: Análises Comparativas e Partidos

#### 6. Comparação Direta entre Dois Parlamentares
* **Método / Path**: `GET /api/comparar`
* **Parâmetros (Query)**:
  * `politico_id_1` (Query): ID do primeiro parlamentar (obrigatório).
  * `politico_id_2` (Query): ID do segundo parlamentar (obrigatório).
  * `casa` (Query): `"camara"` ou `"senado"` (obrigatório).

#### 7. Coesão de Voto dos Partidos
* **Método / Path**: `GET /api/{casa}/partidos/coesao`
* **Parâmetros**:
  * `{casa}` (Path): `"camara"` ou `"senado"`.

---

### Categoria C: Proposições (Matérias e Polarização)

#### 8. Listar Proposições
* **Método / Path**: `GET /api/{casa}/proposicoes`
* **Parâmetros**:
  * `{casa}` (Path): `"camara"` ou `"senado"`.
  * `ano` (Query, opcional): Filtro por ano.
  * `tipo` (Query, opcional): Tipo de matéria (ex: `PL`, `PEC`).
  * `pagina` (Query, opcional): Inteiro (padrão `1`).
  * `tamanho` (Query, opcional): Inteiro (padrão `20`).

#### 9. Obter Detalhes da Proposição
* **Método / Path**: `GET /api/{casa}/proposicoes/{id_proposicao}`
* **Parâmetros**:
  * `{casa}` (Path): `"camara"` ou `"senado"`.
  * `{id_proposicao}` (Path): UUID da proposição.

#### 10. Polarização de Plenário
* **Método / Path**: `GET /api/{casa}/proposicoes/{id_proposicao}/polarizacao`
* **Parâmetros**:
  * `{casa}` (Path): `"camara"` ou `"senado"`.
  * `{id_proposicao}` (Path): UUID da proposição.

---

### Categoria D: Discursos, Chunks e Votos Brutos

#### 11. Listar Discursos Gerais
* **Método / Path**: `GET /api/{casa}/discursos`
* **Parâmetros**:
  * `{casa}` (Path): `"camara"` ou `"senado"`.
  * `politico_id` (Query, opcional): Filtro por ID do parlamentar.
  * `pagina` (Query, opcional): Inteiro (padrão `1`).
  * `tamanho` (Query, opcional): Inteiro (padrão `20`).

#### 12. Listar Discursos de um Político
* **Método / Path**: `GET /api/{casa}/politicos/{id_parlamentar}/discursos`
* **Parâmetros**:
  * `{casa}` (Path): `"camara"` ou `"senado"`.
  * `{id_parlamentar}` (Path): ID do político.
  * `pagina` (Query, opcional): Inteiro (padrão `1`).
  * `tamanho` (Query, opcional): Inteiro (padrão `20`).

#### 13. Obter Detalhes do Discurso
* **Método / Path**: `GET /api/{casa}/discursos/{discurso_id}`
* **Parâmetros**:
  * `{casa}` (Path): `"camara"` ou `"senado"`.
  * `{discurso_id}` (Path): UUID do discurso.

#### 14. Chunks de um Discurso
* **Método / Path**: `GET /api/{casa}/discursos/{discurso_id}/chunks`
* **Parâmetros**:
  * `{casa}` (Path): `"camara"` ou `"senado"`.
  * `{discurso_id}` (Path): UUID do discurso.

#### 15. Listar Votos Nominais Brutos
* **Método / Path**: `GET /api/{casa}/votos`
* **Parâmetros**:
  * `{casa}` (Path): `"camara"` ou `"senado"`.
  * `politico_id` (Query, opcional): Filtro por político.
  * `proposicao_id` (Query, opcional): Filtro por proposição.
  * `pagina` (Query, opcional): Inteiro (padrão `1`).
  * `tamanho` (Query, opcional): Inteiro (padrão `20`).