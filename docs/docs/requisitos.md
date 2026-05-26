# Requisitos do Sistema

---

## Épico 1: Pipeline de Dados e Ingestão (ETL)

### Requisitos Funcionais

- **RF01 – Pipeline de Ingestão Incremental:** O sistema executa rotinas automatizadas para extrair discursos e votações da API da Câmara, calcular embeddings no Worker e atualizar o banco. A extração é estritamente incremental (baseada em *watermark* da última execução bem-sucedida) e implementa retentativas com *Exponential Backoff* em caso de falha na API governamental.
- **RF02 – Coleta de Proposições:** O ETL extrai, tipa e armazena apenas Projetos de Lei (PLs) e Propostas de Emenda à Constituição (PECs).
- **RF03 – Mapeamento de Votos Nominais:** Extração relacional do posicionamento de cada parlamentar (Sim, Não, Abstenção, Ausente) vinculado à respectiva proposição.
- **RF04 – Sanitização de Textos:** Filtros rigorosos de limpeza (HTML, notas taquigráficas) antes de qualquer registro no banco.
- **RF05 – Geração de Resumo Executivo:** Utilização de LLM (Llama 3.1) para gerar um resumo temático de cada proposição extraída.
- **RF06 – Vetorização da Proposição:** O resumo executivo é submetido ao modelo BGE-M3, gerando sua representação vetorial (*embedding*) armazenada no Supabase.
- **RF07 – Escopo de Coleta:** Limitado a Deputados Federais (API da Câmara) e Senadores (API do Senado). Cargos estaduais e municipais estão fora do escopo.

### Regras de Negócio

- **RN01 – Limite de Contexto do Resumo:** O resumo gerado é limitado a 512 tokens para garantir vetorização em requisição única (sem *chunking* da proposição).
- **RN02 – Escopo Temporal:** Restrito à legislatura vigente (2023–2026).
- **RN03 – Exclusividade de Matérias Votadas:** Extrair apenas proposições com votação nominal concluída; projetos em tramitação são ignorados.
- **RN04 – Fontes Oficiais Exclusivas:** O contexto textual é extraído somente das APIs governamentais oficiais. Redes sociais e publicações externas são vetadas.

---

## Épico 2: Motor de Inteligência e NLP

### Requisitos Funcionais

- **RF08 – Fragmentação e Vetorização (Chunking):** O Worker divide discursos em fragmentos menores com sobreposição (*overlap*) e os vetoriza, persistindo no banco via `pgvector`.
- **RF09 – Recuperação de Contexto Vetorial (RAG):** Para cada voto de um parlamentar, o sistema realiza busca semântica para recuperar os *chunks* de discurso com maior proximidade à proposição. Fragmentos acima do limiar de distância de cosseno definido são descartados.
- **RF10 – Orquestração de Prompt:** O sistema concatena o resumo da matéria com os *top-k chunks* recuperados, montando o prompt de contexto enviado ao LLM.
- **RF11 – Inferência de Postura:** O LLM (Llama 3.1) analisa o contexto montado e infere a postura teórica do parlamentar (A Favor ou Contra), baseando-se exclusivamente nos discursos fornecidos.
- **RF12 – Avaliação de Coerência:** O pipeline cruza a postura inferida com o voto nominal real, classificando o voto como *Coerente* ou *Incoerente*.
- **RF13 – Persistência do Veredito:** O resultado final (classificação e justificativa textual da IA) é salvo no banco para exibição na interface.

### Regras de Negócio

- **RN05 – Restrição de Viés Temporal:** Apenas discursos proferidos até a data da votação são considerados. O sistema é proibido de julgar um voto com base em discursos futuros.
- **RN06 – Aborto por Dados Insuficientes:** Se nenhum fragmento atingir o limiar de similaridade, o LLM não é acionado e o voto é excluído do denominador do Score.
- **RN07 – Prevenção de Reprocessamento:** O LLM e a vetorização são acionados apenas para parlamentares com dados novos, evitando custo computacional desnecessário.

### Requisitos Não Funcionais

- **RNF01 – Modelo de Embeddings:** Uso obrigatório do `BAAI/bge-m3` — janela de 8.192 tokens sem truncamento, alta precisão para PT-BR.
- **RNF02 – Saída Estruturada (JSON):** O LLM deve retornar exclusivamente JSON válido com as chaves exatas. Qualquer desvio é tratado como falha de inferência.
- **RNF03 – Orquestração via LangChain:** O pipeline de recuperação, formatação de prompt e inferência é gerenciado pelo LangChain.
- **RNF04 – Estratégia de Fragmentação:** Uso do `RecursiveCharacterTextSplitter` calibrado para otimização do orçamento de tokens do prompt.
- **RNF05 – Motor de Inferência Agnóstico:** Alternância de provedor (local ou API externa) exclusivamente via variável de ambiente `LLM_PROVIDER`.

---

## Épico 3: Busca e Filtros

### Requisitos Funcionais

- **RF14 – Barra de Busca Global:** Pesquisa de políticos por nome e sobrenome.
- **RF15 – Filtros Dinâmicos e Independentes:** Seletores reativos (Nome, Partido, UF) e ordenação. Na tela de Comparação, os seletores operam de forma 100% independente para cada lado.
- **RF16 – Destaques da Home:** Exibição de um ranking (ex: *Top 5 mais coerentes*).
- **RF17 – Ordenação Padrão:** Listagem inicial ordenada de forma decrescente pelo Score de Coerência.
- **RF18 – Filtros via Dropdown Fechado:** A API valida filtros exatos. O front-end usa *dropdowns* fechados para garantir que o usuário só busque por partidos, cargos e UFs existentes no sistema.
- **RF31 – Busca Aproximada (Fuzzy Search):** Tolerância a erros ortográficos na pesquisa de parlamentares.

### Requisitos Não Funcionais

- **RNF06 – Paginação (Lazy Loading):** A listagem e o filtro de políticos são paginados pela FastAPI para evitar sobrecarga no navegador.

---

## Épico 4: Raio-X Parlamentar e Transparência

### Requisitos Funcionais

- **RF19 – Cabeçalho do Perfil:** Foto oficial com *fallback* automático para iniciais, nome, partido, cargo e UF.
- **RF20 – Métricas e Score (Dark Glassmorphism):** O Score de Coerência (0–100, uma casa decimal) é exibido com cores semânticas: ≥ 70% → verde (`emerald-500`), < 70% → vermelho (`rose-500`).
- **RF21 – Provas da Contradição:** Tabela com voto oficial, data e proposição cruzados com a justificativa gerada pela IA.
- **RF22 – Estado de Ausência de Dados:** Políticos sem volume mínimo de discursos ou votações exibem `score_coerencia = Nulo` com indicador neutro na interface.
- **RF23 – Processamento do Score:** O cálculo e o arredondamento (máx. 1 casa decimal) são responsabilidade da FastAPI.

### Regras de Negócio

- **RN08 – Fórmula do Score:** `(Votos Coerentes / Total de Votações Válidas Analisadas) × 100`.
- **RN09 – Critério de Votação Válida:** Apenas votos "Sim" e "Não" compõem o denominador. "Ausente", "Abstenção" e "Obstrução" são ignorados.

### Requisitos Não Funcionais

- **RNF07 – Transparência da Atualização:** A interface exibe a data da *Última Atualização dos Dados* para o usuário entender a frescura do Score.

---

## Épico 5: O Ringue de Comparação

### Requisitos Funcionais

- **RF24 – Seleção para Comparação:** O usuário pode selecionar 2 políticos para visualização lado a lado.
- **RF25 – Comparação Profunda:** A tela exibe o Score de Coerência geral e a data do último cálculo de ambos de forma espelhada e contextualizada.

---

## Épico 6: Performance, Escalabilidade e Governança

### Requisitos Funcionais

- **RF26 – Invalidação Global de Cache:** Ao final do ETL, o Worker dispara automaticamente a limpeza do cache em memória da FastAPI, garantindo dados imediatamente atualizados.

### Requisitos Não Funcionais

- **RNF08 – Macroarquitetura CQRS:** FastAPI exclusiva para leitura; Worker NLP isolado para escrita e processamento. Comunicação entre os dois lados é estritamente assíncrona via banco de dados e Redis, sem chamadas HTTP diretas.
- **RNF09 – Resiliência do Worker:** Lentidão ou falha no Worker não pode afetar a FastAPI. O Worker gerencia seus próprios timeouts e aborta o processamento de parlamentares problemáticos individualmente, prosseguindo para o próximo.
- **RNF10 – Performance Vetorial (HNSW):** O Supabase usa o índice HNSW para busca vetorial por similaridade de cosseno em larga escala e baixa latência.
- **RNF11 – LGPD e Transparência:** Página estática no portal explicando de forma clara que os dados são públicos e como a IA calcula o Score.
- **RNF12 – Cache de Leitura:** Requisições estáticas e buscas exatas são cacheadas em memória com TTL definido para aliviar o banco.
- **RNF13 – Otimização de Build Docker:** O Dockerfile do Worker usa *Layer Caching* para isolar dependências pesadas de IA do código-fonte, mantendo builds ágeis.
- **RNF14 – Filas Assíncronas (Celery):** O Worker usa Celery para gerenciar rotinas pesadas em background com suporte a retentativas automáticas.

---

## Épico 7: Experiência do Usuário (UX) e Design System

### Requisitos Funcionais

- **RF27 – Skeleton Loaders:** Animações de carregamento (silhuetas piscantes) exibidas enquanto requisições pesadas (Dossiê, Comparação) estão em andamento.
- **RF28 – Compartilhamento Social (Open Graph):** A página do Dossiê (`/politico/[id]`) gera metatags dinâmicas. Ao compartilhar o link, plataformas como WhatsApp e Twitter exibem automaticamente o nome, foto e Score do político.
- **RF29 – Tratamento Visual de Erros:** Em caso de falha crítica da API, o front-end exibe mensagem amigável em vez de tela branca ou código de erro.
- **RF30 – Empty States:** Quando uma busca não retorna resultados, a interface exibe ilustrações e orientações para o usuário ajustar os filtros.

### Requisitos Não Funcionais

- **RNF15 – Responsividade Mobile First:** Layout adaptável; a tela de comparação (split screen) é empilhada verticalmente em dispositivos móveis.
- **RNF16 – Contraste e Acessibilidade Visual (WCAG AA):** As paletas de cores do Score (verde/vermelho) garantem contraste legível sobre o fundo escuro (`bg-slate-900`), incluindo para daltônicos.
- **RNF17 – Navegação ARIA:** Todos os elementos interativos suportam navegação por teclado (Tab) e atributos ARIA para leitores de tela.
- **RNF18 – Otimização de Imagens (Next/Image):** O componente `<Image/>` do Next.js gerencia automaticamente cache, compressão WebP e *lazy loading* das fotos dos parlamentares.
- **RNF19 – Design System Modular:** Componentes como "Card do Político" e "Barra do Score" são criados de forma isolada e reutilizável, garantindo consistência visual em todo o sistema.
- **RNF20 – Estética Dark Glassmorphism:** O Design System usa fundos escuros com efeitos de vidro translúcido como linguagem visual principal.
