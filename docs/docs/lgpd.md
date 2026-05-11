# Transparência, Governança de Dados e LGPD

O **ContraDito** possui um compromisso inegociável com a transparência pública, a ética algorítmica e a privacidade, operando em estrita conformidade com a **Lei Geral de Proteção de Dados Pessoais (Lei nº 13.709/2018 - LGPD)** e a **Lei de Acesso à Informação (Lei nº 12.527/2011 - LAI)**.

Este documento estabelece as diretrizes de governança do sistema, divididas entre o tratamento dos dados públicos analisados e a proteção da privacidade do cidadão que utiliza a plataforma.

---

## 1. Governança na Análise de Dados Públicos (O Alvo)

O objetivo central do ContraDito é promover o controle social e evidenciar a aderência entre o discurso proferido e a prática legislativa de figuras públicas. Para garantir a total imparcialidade e legalidade do processo, adotamos as seguintes premissas:

* **Enquadramento Legal (LGPD e LAI):** Embora a LGPD proteja dados de pessoas naturais, o processamento dos dados das autoridades políticas pela nossa plataforma ocorre sob as premissas do **interesse público** e da **transparência ativa** do Estado. O ContraDito atua com finalidade acadêmica, de pesquisa e controle social, enquadrando-se nas exceções do Artigo 4º da LGPD. Somente processamos dados estritamente relacionados ao exercício do mandato público (votos, discursos em plenário e propostas legislativas).
* **Fontes Primárias Oficiais:** O pipeline de dados (ETL) não realiza raspagem de sites de terceiros ou portais de notícias. A ingestão ocorre exclusivamente através das APIs de Dados Abertos mantidas pela infraestrutura do Governo Federal (Câmara dos Deputados e Senado Federal).
* **Isenção Algorítmica (Score de Coerência):** O cálculo do *Score de Coerência* não é uma avaliação subjetiva ou opinativa. A arquitetura utiliza **RAG (Retrieval-Augmented Generation)**, onde o motor de Inteligência Artificial opera como um leitor semântico. A pontuação é o resultado determinístico do cálculo de Similaridade de Cosseno em um banco de dados vetorial, que mede a distância matemática exata entre a intenção do discurso e o teor do voto registrado.
* **Rastreabilidade e Auditoria:** Todas as contradições apontadas pelo sistema ("Provas de Contradição") são acompanhadas de links diretos para a fonte governamental original (vídeos, notas taquigráficas ou diários oficiais), permitindo a auditoria completa por qualquer cidadão.

---

## 2. Privacidade e Proteção do Cidadão (O Usuário)

Se você é um cidadão navegando no ContraDito para fiscalizar seus representantes, a privacidade por padrão (*Privacy by Default*) é a nossa regra.

### Quais dados coletamos e por quê?
* **Minimização de Dados (MVP):** Visando garantir o acesso irrestrito e democrático à informação, a arquitetura atual do sistema **não exige criação de conta, login ou autenticação**. Não solicitamos, capturamos ou processamos Dados Pessoais Identificáveis (PII), como e-mail, nome ou CPF dos visitantes.
* **Métricas de Navegação:** Coletamos exclusivamente dados de telemetria básicos e anonimizados (ex: taxa de rejeição, tempo de carregamento de página) com a finalidade estrita de monitorar a estabilidade dos servidores e aprimorar a experiência de uso (UX).

### Compartilhamento de Dados e Natureza do Projeto
**O ContraDito não comercializa, aluga ou cede dados de tráfego para terceiros.** O projeto tem raízes no ambiente acadêmico da Universidade de Brasília (UnB), concebido por estudantes de Engenharia de Software. Todo o ecossistema é mantido com o propósito exclusivo de fomentar a inovação cívica, o uso da Ciência de Dados para o bem público e o fortalecimento do Estado Democrático de Direito.
