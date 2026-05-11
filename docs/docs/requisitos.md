# Backlog e Requisitos do Sistema

Este documento centraliza os Requisitos Funcionais (RFs), Requisitos Não-Funcionais (RNFs) e Regras de Negócio (RNs) que guiam o escopo e o desenvolvimento do ContraDito. A arquitetura foi dividida em Épicos para facilitar o gerenciamento das Sprints e a rastreabilidade do produto.

---

## Épico 1: Pipeline de Dados e Ingestão (ETL)

Responsável por coletar, higienizar e estruturar os dados governamentais de forma automatizada e resiliente.

* **RF19 – Atualização de Dados (ETL):** O sistema deve possuir rotinas automatizadas (ou acionadas manualmente) para extrair novos discursos e votações da API da Câmara, calcular os novos embeddings no Worker e atualizar a base do Supabase periodicamente.
* **RF20 – Coleta e Tipagem de Proposições:** O pipeline ETL deve extrair, tipar e armazenar matérias legislativas, separando claramente Projetos de Lei (PLs) de Propostas de Emenda à Constituição (PECs).
* **RF21 – Mapeamento de Votos Nominais:** O sistema deve extrair de forma relacional o posicionamento exato de cada parlamentar (Sim, Não, Abstenção) vinculado à respectiva proposição.
* **RF22 – Sanitização e Prevenção de Ruídos:** O pipeline deve aplicar filtros rigorosos (limpeza HTML, notas taquigráficas) no texto bruto antes da vetorização.
* **RF23 – Rastreabilidade e Fonte Primária (Fallback):** O sistema deve capturar links diretos para a mídia original (URL do vídeo na TV Câmara ou PDF do Diário Oficial). Na ausência de vídeo, aplica-se uma lógica de fallback para salvar o documento oficial ou perfil.
* **RF24 – Tolerância a Falhas e Watermarking:** O pipeline deve implementar tentativas automáticas (Exponential Backoff) em caso de instabilidade das APIs do governo, e salvar um watermark (data/hora) da última extração para guiar a Carga Delta.
* **RF28 – Escopo de Coleta de Políticos (Cargos Abrangidos):** O pipeline ETL deve restringir a extração de dados, perfis, discursos e votações exclusivamente para os cargos de nível federal. O sistema deverá consumir a API da Câmara dos Deputados para Deputados Federais e a API do Senado Federal para Senadores da República. *(Nota: Deputados Estaduais, Distritais, Prefeitos e Vereadores estão fora do escopo).*

---

## Épico 2: Motor de Inteligência e NLP

Responsável pela vetorização de textos, busca semântica e inferência lógica de coerência utilizando Inteligência Artificial (RAG).

* **RF25 – Tratamento de Busca Semântica Vazia:** Se o termo pesquisado não encontrar nenhum discurso que atinja o limiar de similaridade (threshold), a API deve retornar um Status 200 (OK) com um array vazio `[]`, para que o Front-end exiba uma mensagem amigável.
* **RF29 – Fragmentação e Vetorização Contínua:** O Motor NLP deve processar os textos limpos dividindo textos longos em fragmentos menores (chunking) com sobreposição de conteúdo (overlap). Em seguida, transformará esses fragmentos em embeddings vetoriais, persistindo-os no banco de dados via extensão pgvector.
* **RF30 – Recuperação de Contexto (Busca Semântica Interna):** Para cada parlamentar que registrou voto, o sistema deve executar uma busca vetorial recuperando os chunks de discursos do próprio parlamentar que estejam mais próximos semanticamente do texto da matéria em votação.
* **RF31 – Orquestração de Prompt (Filter):** O sistema deve concatenar o texto da matéria legislativa com os *top-k* chunks recuperados no RF30, montando dinamicamente o prompt de contexto que será enviado ao LLM.
* **RF32 – Inferência de Postura:** O sistema deve enviar o prompt orquestrado ao LLM (Llama 3) para que a IA infira a postura teórica do deputado em relação à matéria (ex: A Favor, Contra, Neutro) estritamente com base nos discursos fornecidos.
* **RF33 – Avaliação Lógica de Coerência:** O pipeline deve cruzar a postura inferida pela IA com o voto nominal real do parlamentar no painel. O sistema classificará o voto final como "Coerente" ou "Incoerente".
* **RF34 – Persistência do Veredito:** O sistema deve salvar o resultado final da classificação e a justificativa textual gerada pela IA no banco de dados para posterior exibição.
* **RF35 – Processamento de Matérias Extensas:** Para matérias cujo texto integral exceda o limite de contexto do modelo de embedding, o sistema deve priorizar a vetorização da Ementa ou gerar um Resumo Global via LLM antes da persistência vetorial.

### Requisitos Não-Funcionais e Regras de Negócio (Motor NLP)
* **RNF06 – Limiar de Similaridade Vetorial (Threshold):** O banco de dados vetorial deve ser configurado com um threshold rigoroso (ex: 0.2 de distância de cosseno). Discursos abaixo dessa linha de corte não serão retornados.
* **RNF08 – Isolamento do Backend:** O roteamento (FastAPI) e o Motor NLP devem executar em contêineres Docker distintos comunicando-se via HTTP interno (porta 8001), impedindo acesso externo direto à IA.
* **RNF10 – Resiliência e Timeout no Microsserviço NLP:** A requisição HTTP interna do FastAPI para o Worker deve ter um Timeout estrito (ex: 5 a 10 segundos). Caso o tempo estoure, a API deve abortar a conexão e retornar HTTP 503.
* **RNF11 – Padronização do Modelo de Embedding:** Utilização obrigatória do modelo `paraphrase-multilingual-mpnet-base-v2` (via SBERT).
* **RNF12 – Estruturação de Saída da IA (JSON):** A comunicação com o LLM deve exigir Structured Outputs (JSON) para garantir o parsing programático da "postura" e "justificativa".
* **RNF13 – Framework de Orquestração LLM:** Utilização do framework LangChain para a construção das cadeias de processamento (chains).
* **RNF14 – Adaptação de Domínio do LLM (Fine-Tuning com LoRA):** O modelo Llama 3 utilizará uma versão refinada via Fine-Tuning com a técnica LoRA, adequando a IA ao contexto legislativo brasileiro.
* **RNF15 – Limite de Contexto e Estratégia de Fragmentação:** A divisão de textos deve utilizar algoritmos (ex: `RecursiveCharacterTextSplitter`) configurados para respeitar o limite máximo de tokens do modelo SBERT (512 tokens).
* **RN01 – Restrição de Viés Temporal:** A recuperação de contexto deve considerar apenas discursos proferidos em datas anteriores ou iguais à data da votação. É estritamente proibido utilizar discursos futuros para julgar um voto passado.
* **RN02 – Aborto por Dados Insuficientes:** Se a busca vetorial não retornar nenhum discurso que respeite o limite rigoroso estipulado, o acionamento do LLM deve ser abortado e o voto não entrará no denominador de cálculo do Score.

---

## Épico 3: Busca e Filtros

Responsável pela usabilidade, descoberta de políticos e ordenação dos dados na interface.

* **RF01:** O sistema deve possuir uma barra de busca global que permita pesquisar políticos por nome, sobrenome ou "nome de urna".
* **RF02:** O sistema deve permitir a filtragem da listagem de políticos por Partido (ex: PL, PT, PSDB).
* **RF03:** O sistema deve permitir a filtragem por Cargo Político (ex: Deputado Federal, Senador).
* **RF04:** O sistema deve permitir a filtragem cruzada por Estado/UF.
* **RF05:** A página inicial deve exibir um ranking ou carrossel de destaque (ex: "Top 5 mais coerentes").
* **RF14:** A listagem geral de políticos na página inicial deve ser ordenada por padrão (default) exibindo primeiro os parlamentares com o maior "Score de Coerência".
* **RF26 – Padronização de Filtros Restritos:** O Front-end deve obrigatoriamente implementar componentes de seleção fechada (Dropdowns) para garantir que o usuário só consiga pesquisar por Partidos, Cargos e UFs que existam no sistema, evitando sobrecarga no banco.
* **RNF02 – Performance:** A listagem e o filtro de políticos devem ter paginação (lazy loading) via FastAPI, para não travar o navegador do usuário.

---

## Épico 4: Raio-X Parlamentar e Transparência

Responsável por exibir o perfil individual do político, seu score e as provas auditáveis de suas ações.

* **RF06:** O sistema deve exibir um cabeçalho com a foto oficial, nome, partido, UF e situação do mandato atual.
* **RF07:** O sistema deve exibir o Score de Coerência em formato visual.
* **RF08:** O sistema deve listar as "Provas da Contradição" — uma tabela lado a lado mostrando o trecho do discurso extraído (o que ele disse) vs. o voto oficial na Câmara (o que ele fez).
* **RF09:** O sistema deve permitir que o usuário clique em um voto específico e seja redirecionado para a fonte original (Portal de Dados Abertos da Câmara).
* **RF10 – Acesso à Fonte Primária:** Além do texto do discurso, o sistema deve fornecer o link direto para o vídeo da sessão na TV Câmara ou o PDF oficial do Diário da Câmara.
* **RF15 – Estado de Ausência de Dados:** Políticos sem volume suficiente de discursos ou votações devem ter o `score_coerencia` retornado como "Nulo" (Null) pela API, exibindo um indicador neutro na interface.
* **RF27 – Lógica de Cálculo do Score de Coerência:** O Score deve ser calculado numa escala de 0 a 10. A fórmula considerará apenas votações em que o parlamentar estava ativamente presente (`(Quantidade de Votos Coerentes / Total de Votações Válidas Analisadas) * 10`). Votos "Ausente" ou "Abstenção" serão ignorados do denominador.
* **RNF03 – Atualização de Dados:** O sistema deve deixar explícito na interface a data da "Última Atualização dos Dados".

---

## Épico 5: O Ringue de Comparação

Responsável por promover o contraste direto entre as posturas de dois parlamentares diferentes.

* **RF11:** O sistema deve permitir que o usuário selecione 2 políticos para uma visualização "Lado a Lado".
* **RF12 – O Ringue de Comparação Profunda:** A tela de comparação deve contrastar 2 políticos exibindo: Score de Coerência geral de ambos, data do último cálculo, principais PLs/PECs em que divergiram/convergiram, e o contraste direto dos votos reais dados por eles nas mesmas pautas.

---

## Épico 6: Performance, Escalabilidade e Governança

Responsável pelos requisitos de infraestrutura, segurança e design responsivo da aplicação.

* **RF16 – Invalidação Global de Cache Pós-ETL:** Após a conclusão da rotina do ETL, o script deve disparar uma requisição administrativa que executa `FastAPICache.clear()`, garantindo dados atualizados instantaneamente no Frontend.
* **RNF04 – Escalabilidade e Paridade Local:** O Supabase deve suportar consultas complexas rápidas. Localmente, a infraestrutura deve emular essas capacidades usando a imagem `pgvector:pg15` no Docker.
* **RNF05 – LGPD e Transparência:** O portal deve ter uma página estática explicando de forma clara que os dados são públicos e como a IA calcula o Score.
* **RNF07 – Performance e Cache:** Requisições estáticas ou de busca exata devem utilizar estratégia de Cache em Memória com tempo de expiração definido.
* **RNF09 – Proteção contra Abuso (Rate Limiting):** A API principal deve implementar bloqueio de limite de requisições baseado em IP, com foco especial na rota de "Busca Semântica".
* **RNF16 – Otimização de Build e Caching:** Uso obrigatório de Layer Caching e adoção de um arquivo `.dockerignore` rigoroso.
* **RNF17 – Suporte Multi-Arquitetura:** Adoção de imagens base leves e multiplataforma (`python:3.12-slim`) para garantir execução nativa em processadores ARM64 e AMD64/x86.
* **Design Responsivo:** O layout de toda a aplicação (incluindo o Ringue de Comparação e o Raio-X Parlamentar) precisa funcionar perfeitamente em telas de dispositivos móveis.

---

## Épico 7: Experiência do Usuário (UX) e Design System

Responsável por garantir interações fluidas, acessibilidade e partilha social nativa na aplicação.

### Requisitos Funcionais (RF) - Front-end e Interação
* **RF36 – Feedback Visual de Carregamento (Skeleton Loaders):** Durante o tempo de espera da resposta da API (principalmente nas telas pesadas de Dossiê e Comparação), a interface gráfica deve exibir animações de carregamento do tipo Skeleton Screen (silhuetas cinzas piscantes) para informar ao usuário que o sistema está processando, evitando que a tela pareça "travada".
* **RF37 – Compartilhamento Social Dinâmico (Open Graph):** Aproveitando o Next.js, a página do Dossiê do Político (`/politico/[id]`) deve gerar metatags dinâmicas. Assim, quando um jornalista compartilhar o link no WhatsApp ou Twitter, o aplicativo deve gerar automaticamente um "card" de pré-visualização mostrando a foto do político, o nome e o seu Score de Coerência.
* **RF38 – Tratamento Visual de Erros (Error Boundaries):** O Front-end deve possuir telas ou componentes de erro amigáveis. Caso a API retorne uma falha crítica (como o erro 503 citado no RNF10), o sistema não deve exibir uma "tela branca" ou códigos técnicos, mas sim uma mensagem clara em interface, como: *"Nossos servidores estão processando muitos dados no momento. Tente novamente em alguns segundos."*
* **RF39 – Orientação em Estados Vazios (Empty States):** Complementando a regra de buscas vazias, o Front-end deve exibir ilustrações e textos de orientação amigáveis sempre que uma tabela não tiver dados ou um cruzamento de filtros (Ex: Partido X no Estado Y) não encontrar nenhum político, guiando o usuário a limpar os filtros.

### Requisitos Não Funcionais (RNF) - UI/UX e Desempenho
* **RNF19 – Acessibilidade Visual e Contraste (WCAG):** O Design System construído com Tailwind CSS deve respeitar as diretrizes internacionais de acessibilidade (WCAG nível AA). As cores utilizadas para o Score de Coerência (verde e vermelho) devem ter contraste suficiente com o fundo escuro (`bg-slate-900`) para garantir a legibilidade por pessoas com daltonismo ou baixa visão.
* **RNF20 – Navegação Acessível e ARIA:** Todos os elementos interativos do portal (filtros dropdown, barras de pesquisa, botões de comparação e paginação) devem ser totalmente navegáveis utilizando apenas o teclado (tecla Tab) e possuir atributos de leitura (ARIA labels) para compatibilidade com leitores de tela.
* **RNF21 – Otimização de Mídia (Next/Image):** Para garantir uma renderização ultrarrápida da página inicial (que possui dezenas de fotos de políticos), o Front-end deve obrigatoriamente utilizar o componente nativo `<Image />` do Next.js. Ele fará o cache, a compressão (WebP) e o redimensionamento das fotos oficiais vindas da Câmara de forma automática (Lazy Loading de imagens).
* **RNF22 – Reusabilidade de Componentes (Design System):** A arquitetura do código no React deve ser estritamente modular. Elementos como o "Card do Político", a "Barra de Progresso do Score" e os "Botões Base" devem ser criados como componentes isolados, garantindo que qualquer alteração visual reflita automaticamente em todo o sistema, mantendo a consistência do Design System.