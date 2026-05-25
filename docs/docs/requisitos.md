
## Épico 1: Pipeline de Dados e Ingestão (ETL)

### Requisitos Funcionais (RF)
* **RF01 – Pipeline de Ingestão Incremental e Resiliência (ETL):** O sistema deve possuir rotinas automatizadas para extrair discursos e votações da API da Câmara, calcular os embeddings no Worker e atualizar o banco de dados. Para garantir eficiência computacional e tolerância a falhas, o ETL não deve operar em tempo real; a extração deve ser estritamente incremental (baseada no watermark da data da última execução bem-sucedida) e implementar retentativas automáticas utilizando Exponential Backoff em caso de instabilidade na API governamental.
* **RF02 - Coleta e Tipagem de Proposições:** O pipeline ETL deve somente extrair, tipar e armazenar Projetos de Lei (PLs) e Propostas de Emenda à Constituição (PECs).
* **RF03 - Mapeamento de Votos Nominais:** O sistema deve extrair de forma relacional o posicionamento exato de cada parlamentar (Sim, Não, Abstenção e Ausente) vinculado à respectiva proposição.
* **RF04 - Sanitização e Prevenção de Ruídos:** O pipeline deve aplicar filtros rigorosos (limpeza HTML, notas taquigráficas) nos textos brutos dos discursos antes do registro no banco de dados.
* **RF05 - Geração de Resumo Executivo:** Durante a etapa de extração das proposições, o sistema deve utilizar um modelo LLM (Llama 3.1) para processar o texto original da proposição e gerar um resumo executivo que contenha o núcleo temático do documento.
* **RF06 - Vetorização da Proposição:** O sistema deve submeter o resumo executivo (já validado quanto ao dimensionamento de tokens) ao modelo BGE-M3 para gerar a representação vetorial (embedding) da proposição, armazenando o resultado no banco de dados vetorial.
* **RF07 - Escopo de Coleta de Políticos (Cargos Abrangidos):** O pipeline ETL deve restringir a extração de dados, perfis, discursos e votações exclusivamente para os cargos de nível federal. O sistema deverá consumir a API da Câmara dos Deputados para Deputados Federais e a API do Senado Federal para Senadores da República. *(Nota: Para a versão atual do sistema, Deputados Estaduais, Distritais, Prefeitos e Vereadores estão fora do escopo e não devem ser processados).*

### Regras de Negócio (RN)
* **RN01 - Limite de Contexto do Resumo:** O resumo executivo gerado pelo LLM deve ser estritamente limitado ao limite máximo de tokens (512 tokens) suportado pelo modelo de vetorização (BGE-M3), garantindo que todo o texto seja vetorizável em uma única requisição, eliminando a necessidade de chunking da proposição.
* **RN02 - Escopo Temporal da Legislatura:** A extração de dados (ETL) deve filtrar obrigatoriamente parlamentares, discursos e votações restringindo-os ao período exato da legislatura vigente (2023 a 2026).
* **RN03 - Exclusividade para Matérias Votadas:** A extração de matérias legislativas (Proposições) deve estar estritamente atrelada à existência de um registro de votação concluída no painel eletrônico. Projetos em tramitação que não foram submetidos a voto nominal devem ser ignorados.
* **RN04 - Restrição de Fontes Oficiais:** O arcabouço textual extraído para compor o contexto do político deve provir unicamente das Notas Taquigráficas e discursos proferidos em plenário ou comissões extraídos das APIs governamentais oficiais. Textos oriundos de redes sociais (ex: Twitter, Instagram) ou publicações externas estão vetados no pipeline.

---

## Épico 2: Motor de Inteligência e NLP

### Requisitos Funcionais (RF)
* **RF08 – Fragmentação e Vetorização Contínua:** Complementando as rotinas do ETL, o Motor NLP deve dividir os discursos em fragmentos menores (chunking) com sobreposição de conteúdo (overlap). Em seguida, transformará esses fragmentos em embeddings vetoriais, persistindo-os no banco de dados via extensão pgvector.
* **RF09 – Recuperação de Contexto Vetorial:** Para cada parlamentar que registrou voto em uma matéria, o sistema deve executar uma busca vetorial no banco de dados recuperando os chunks de discursos do próprio parlamentar com maior proximidade semântica ao texto da proposição. Apenas chunks cuja distância de cosseno em relação ao resumo da proposição seja igual ou inferior ao limite definido após os testes serão considerados válidos. Fragmentos que ultrapassarem esse limiar deverão ser descartados antes da montagem do prompt.
* **RF10 – Orquestração de Prompt (Filter):** O sistema deve concatenar o texto da matéria legislativa com os top-k chunks recuperados no RF10, montando dinamicamente o prompt de contexto que será enviado ao modelo de linguagem.
* **RF11 – Inferência de Postura:** O sistema deve enviar o prompt orquestrado ao LLM (LLama 3.1) para que a IA analise os textos e infira a postura teórica do deputado em relação à matéria (ex: A Favor ou Contra) estritamente com base nos discursos fornecidos.
* **RF12 – Avaliação Lógica de Coerência:** O pipeline deve cruzar a postura inferida pela IA com o voto nominal real do parlamentar no painel da Câmara/Senado. O sistema classificará o voto final como "Coerente" ou "Incoerente".
* **RF13 – Persistência do Veredito:** O sistema deve salvar o resultado final da classificação (RF13) e a justificativa textual gerada pela IA no banco de dados, para posterior exibição na interface de "Provas da Contradição".

### Regras de Negócio (RN)
* **RN05 – Restrição de Viés Temporal:** A recuperação de contexto deve considerar apenas discursos proferidos em datas anteriores ou iguais à data da votação da matéria. O sistema é estritamente proibido de utilizar discursos futuros para julgar um voto passado.
* **RN06 – Aborto por Dados Insuficientes:** Se a busca vetorial para um deputado não retornar nenhum discurso que respeite o limite rigoroso estipulado após testes, o acionamento do LLM deve ser abortado para aquele parlamentar. O voto não entrará no denominador de cálculo do Score de Coerência.
* **RN07 - Prevenção de Reprocessamento:** A IA (LLM) e a vetorização só devem ser acionadas para parlamentares que tiverem dados novos (discursos ou votos). Perfis inalterados não serão reprocessados, poupando recursos.

### Requisitos Não Funcionais (RNF)
* **RNF03 - Motor de Embeddings BGE-M3:** O sistema deve obrigatoriamente utilizar o modelo de linguagem BAAI/bge-m3 para a geração dos tensores matemáticos (embeddings). A escolha justifica-se pela sua capacidade nativa de processar janelas extensas de contexto (até 8.192 tokens) sem truncamento silencioso, além de sua precisão superior na separação de similaridade semântica (mitigação de anisotropia) para o idioma Português Brasileiro.
* **RNF04 – Estruturação Obrigatória da Saída do LLM (JSON):** A comunicação de inferência entre o backend e o modelo LLM deve exigir e aceitar exclusivamente um objeto JSON perfeitamente formatado, contendo as chaves exatas esperadas pelo sistema. O modelo é expressamente proibido de retornar texto livre, saudações ou qualquer conteúdo fora desse esquema. Qualquer resposta que não esteja em conformidade com o formato estruturado deve ser tratada como falha de inferência e lançar uma exceção, sem demandar interpretação humana.
* **RNF05 – Framework de Orquestração LLM:** O módulo de Inteligência deve utilizar o framework LangChain que integrará a recuperação vetorial, a formatação do prompt e a chamada de inferência.
* **RNF06 – Estratégia de Fragmentação de Textos (Chunking):** A divisão de textos dos discursos deve utilizar algoritmos especializados de particionamento (ex: RecursiveCharacterTextSplitter do LangChain) configurados para gerar fragmentos enxutos. Essa fragmentação é obrigatória para o gerenciamento rigoroso do orçamento de tokens do prompt. Os tamanhos dos recortes devem ser calibrados para garantir que a soma dos trechos recuperados (top-k) alimente o LLM de forma eficiente, preservando o tempo de inferência e a estabilidade da memória da GPU.
* **RNF07 - Agnosticismo e Gestão de Custos do Motor de Inferência:** O módulo de inteligência deve implementar uma interface agnóstica para a comunicação com o LLM (Llama 3.1 8B), permitindo a alternância transparente entre diferentes provedores de inferência unicamente via variáveis de ambiente. A arquitetura deve suportar o uso de infraestruturas locais/dedicadas (para processamento massivo em lote sem custo de tokens) e APIs externas de alta disponibilidade (para execução autônoma de rotinas incrementais), garantindo que a aplicação se mantenha sustentável financeiramente e resiliente a quedas de provedores.

---

## Épico 3: Busca e Filtros

### Requisitos Funcionais (RF)
* **RF14 - Barra de Busca:** O sistema deve possuir uma barra de busca global que permita pesquisar políticos por nome e sobrenome.
* **RF15 - Filtros Dinâmicos e Independentes:** A plataforma deve oferecer filtros de busca reativos (Nome, Partido, Estado/UF) e opções de ordenação (Mais Coerentes/Menos Coerentes). Na tela de Comparação (O Ringue), esses seletores devem atuar de forma 100% independente para cada um dos lados disputando a comparação.
* **RF16 - Destaques da Home:** A página inicial deve exibir um ranking (ex: “Top 5 mais coerentes").
* **RF17 - Ordenação Padrão:** A listagem geral de políticos na página inicial deve ser ordenada por padrão (default) exibindo primeiro os parlamentares com o maior "Score de Coerência".
* **RF18 - Padronização de Filtros Restritos:** Para evitar sobrecarga no banco de dados com buscas inválidas, a API validará filtragens exatas. O Front-end deve obrigatoriamente implementar componentes de seleção fechada (Dropdowns), garantindo que o usuário só consiga pesquisar por Partidos, Cargos e UFs que de fato existam no sistema.
* **RF34 – Busca Aproximada de Parlamentares (Fuzzy Search):** O sistema deve oferecer um mecanismo de busca tolerante a erros ortográficos na listagem de políticos.

### Requisitos Não Funcionais (RNF)
* **RNF08 - Performance e Lazy Loading:** A listagem e o filtro de políticos devem ter paginação (lazy loading) pela sua API FastAPI, para não travar o navegador carregando todos políticos de uma vez só.

---

## Épico 4: Raio-X Parlamentar e Transparência

### Requisitos Funcionais (RF)
* **RF19 - Cabeçalho do Perfil:** O sistema deve exibir um cabeçalho com a foto oficial (com sistema de fallback automático gerando iniciais caso a foto oficial não carregue), nome, partido, cargo e UF.
* **RF20 - Métricas de Análise e Score:** O sistema deve apresentar o Score de Coerência utilizando componentes em estilo Dark Glassmorphism. A renderização tipográfica do score (escala de 0 a 100, com máximo de uma casa decimal) deve aplicar regras de cores semânticas de forma reativa: índices iguais ou superiores a 70% recebem paleta verde (emerald-500), enquanto índices inferiores recebem paleta de alerta (rose-500).
* **RF21 - Provas da Contradição:** O sistema deve listar as "Provas da Contradição" — uma tabela dentro do dossiê do político mostrando o voto oficial, com data do evento e em qual proposição vs. a justificativa da IA.
* **RF22 - Estado de Ausência de Dados:** O sistema deve prever o "Estado de Ausência de Dados". Políticos que não possuam volume suficiente de discursos (ex.: 10% da média do banco) ou votações devem ter o `score_coerencia` retornado como "Nulo" pela API, e a interface visual deve exibir um indicador neutro.
* **RF23 – Processamento e Disponibilização do Score (Backend):** O backend (FastAPI) deve aplicar as lógicas descritas na RN09 e RN10 para calcular o Score de Coerência. A API deve retornar o valor numérico truncado ou arredondado com, no máximo, uma casa decimal (ex: 85.4).

### Regras de Negócio (RN)
* **RN09 – Fórmula do Score de Coerência:** O índice de coerência de um parlamentar deve ser calculado percentualmente, utilizando a fórmula: `(Quantidade de Votos Coerentes / Total de Votações Válidas Analisadas) * 100`.
* **RN10 – Critério de Votação Válida (Filtro do Denominador):** Para fins do cálculo do Score de Coerência, apenas votações em que o parlamentar expressou um posicionamento ativo (ex: "Sim" ou "Não") são consideradas válidas. Registros de "Ausente", "Abstenção" ou "Obstrução" devem ser estritamente ignorados e não podem compor o denominador da fórmula.

### Requisitos Não Funcionais (RNF)
* **RNF08 - Transparência de Atualização:** O sistema deve deixar explícito na interface a data da "Última Atualização dos Dados", para o usuário saber quão fresco é aquele Score.

---

## Épico 5: O Ringue de Comparação

### Requisitos Funcionais (RF)
* **RF24 - Seleção para Comparação:** O sistema deve permitir que o usuário selecione 2 políticos para uma visualização "Lado a Lado".
* **RF25 - O Ringue de Comparação Profunda:** A tela de comparação e o respectivo endpoint da API (Lado a Lado) devem contrastar 2 políticos de forma completa e contextualizada. O payload e a interface devem exibir o Score de Coerência geral de ambos e a data do último cálculo.

---

## Épico 6: Performance, Escalabilidade e Governança

### Requisitos Funcionais (RF)
* **RF26 - Invalidação Global de Cache Pós-ETL:** O sistema deve possuir um mecanismo de Invalidação de Cache no FastAPI. Após a conclusão da rotina do ETL, o script deve disparar uma requisição administrativa que limpa o cachê, garantindo dados atualizados instantaneamente.

### Requisitos Não Funcionais (RNF)
* **RNF09 - Macroarquitetura CQRS:** A aplicação deve ser obrigatoriamente dividida. A API Principal será responsável estritamente pela Leitura, consultando o banco de dados. O Motor de Processamento NLP (Worker) operará isolado em rede privada para Escrita e Processamento. A comunicação entre eles será totalmente assíncrona, mediada pelo banco de dados, eliminando requisições HTTP síncronas entre a API e a IA.
* **RNF10 - Resiliência do Worker e Fallback de Leitura:** A API Principal nunca deve travar por lentidão da IA; ela sempre retornará os dados cacheados ou o estado atual do banco. O controle de Timeout deve ser implementado exclusivamente dentro do Worker NLP. Se o processamento do LLama 3 para um parlamentar exceder o tempo limite estipulado, o Worker deve abortar aquele parlamentar e registrar o erro, prosseguir para o próximo, garantindo que o contêiner não congele.
* **RNF11 – Performance Vetorial e Paridade de Ambiente:** Em produção, o banco de dados (Supabase) deve utilizar o índice HNSW (Hierarchical Navigable Small World) sobre as matrizes de dados para garantir o cálculo de similaridade de cosseno em alta escala e baixa latência. O ambiente de desenvolvimento deve emular estritamente essa arquitetura vetorial do PostgreSQL via contêineres.
* **RNF12 - LGPD e Transparência:** O portal deve ter uma página estática explicando de forma clara e amigável que os dados são públicos e como a IA calcula o Score (mkdocs).
* **RNF13 - Performance e Cache:** Requisições estáticas ou de busca exata devem utilizar estratégia de Cache em Memória com tempo de expiração definido para aliviar o banco de dados.
* **RNF14 – Otimização de Build e Contêineres:** O empacotamento do Worker deve utilizar Layer Caching para isolar as dependências pesadas de IA do código-fonte, garantindo tempos de reconstrução ágeis. O processo de build deve bloquear ativamente artefatos de desenvolvimento local, gerando imagens finais seguras e enxutas.
* **RNF15 - Gerenciamento de Filas Assíncronas (Celery):** O Motor de Processamento NLP (Worker) deve utilizar o framework Celery para orquestrar e gerenciar a execução em background das rotinas pesadas de ETL e Inferência, garantindo a execução desacoplada, o agendamento de tarefas em lote e suporte a retentativas automáticas.

---

## Épico 7: Experiência do Usuário (UX) e Design System

### Requisitos Funcionais (RF)
* **RF27 - Feedback Visual de Carregamento (Skeleton Loaders):** Durante o tempo de espera da resposta da API (principalmente nas telas pesadas de Dossiê e Comparação), a interface gráfica deve exibir animações de carregamento do tipo Skeleton Screen (silhuetas cinzas piscantes) para informar ao usuário que o sistema está processando, evitando que a tela pareça "travada".
* **RF28 - Compartilhamento Social Dinâmico (Open Graph):** Aproveitando o Next.js, a página do Dossiê do Político (/politico/[id]) deve gerar metatags dinâmicas. Assim, quando um jornalista compartilhar o link no WhatsApp ou Twitter, o aplicativo deve gerar automaticamente um "card" de pré-visualização mostrando a foto do político, o nome e o seu Score de Coerência.
* **RF29 - Tratamento Visual de Erros (Error Boundaries):** O Front-end deve possuir telas ou componentes de erro amigáveis. Caso a API retorne uma falha crítica (como o erro 503 citado na RNF02), o sistema não deve exibir uma "tela branca" ou códigos técnicos, mas sim uma mensagem clara em interface, como: "Nossos servidores estão processando muitos dados no momento. Tente novamente em alguns segundos."
* **RF30 - Orientação em Estados Vazios (Empty States):** Complementando a regra de buscas vazias, o Front-end deve exibir ilustrações e textos de orientação amigáveis sempre que uma tabela não tiver dados ou um cruzamento de filtros (Ex: Partido X no Estado Y) não encontrar nenhum político, guiando o usuário a limpar os filtros.

### Requisitos Não Funcionais (RNF)
* **RNF16 - Responsividade e Abordagem Mobile First:** A interface deve adaptar-se perfeitamente a dispositivos móveis. Elementos complexos, como o layout de tela dividida (Split Screen) utilizado no Desktop para a tela de Comparação, devem ser empilhados de forma inteligente em telas menores, garantindo a legibilidade sem perda de contexto.
* **RNF17 - Acessibilidade Visual e Contraste (WCAG):** O Design System construído com Tailwind CSS deve respeitar as diretrizes internacionais de acessibilidade (WCAG nível AA). As cores utilizadas para o Score de Coerência (verde e vermelho) devem ter contraste suficiente com o fundo escuro (bg-slate-900) para garantir a legibilidade por pessoas com daltonismo ou baixa visão.
* **RNF18 - Navegação Acessível e ARIA:** Todos os elementos interativos do portal (filtros dropdown, barras de pesquisa, botões de comparação e paginação) devem ser totalmente navegáveis utilizando apenas o teclado (tecla Tab) e possuir atributos de leitura (ARIA labels) para compatibilidade com leitores de tela.
* **RNF19 - Otimização de Mídia (Next/Image):** Para garantir uma renderização ultrarrápida da página inicial (que possui dezenas de fotos de políticos), o Front-end deve obrigatoriamente utilizar o componente nativo <Image/> do Next.js. Ele fará o cache, a compressão (WebP) e o redimensionamento das fotos oficiais vindas da Câmara de forma automática (Lazy Loading de imagens).
* **RNF20 - Reusabilidade de Componentes (Design System):** A arquitetura do código no React deve ser estritamente modular. Elementos como o "Card do Político", a "Barra de Progresso do Score" e os "Botões Base" devem ser criados como componentes isolados, garantindo que qualquer alteração visual reflita automaticamente em todo o sistema, mantendo a consistência do Design System.
* **RNF21 - Estética Visual (Dark Glassmorphism) e Contraste (WCAG AA):** O Design System construído com Tailwind CSS deve utilizar a estética "Dark Glassmorphism" (fundos escuros, efeitos de vidro translúcido).
