 # Entendendo o Score de Coerência


O **Score de Coerência** é a principal métrica do ContraDito. Ele não é baseado em opiniões políticas ou viés ideológico, mas sim em um cruzamento analítico e matemático rigoroso entre as declarações públicas do parlamentar e suas ações no painel de votação eletrônico.


Abaixo, detalhamos as regras de negócio e os critérios matemáticos que definem como essa pontuação é calculada.


---


## A Fórmula Matemática


O índice de coerência de um parlamentar é calculado percentualmente, resultando em uma nota de **0 a 100**. A fórmula é baseada exclusivamente nos cruzamentos validados com sucesso pela nossa Inteligência Artificial:


$$

Score = \left( \frac{\text{Quantidade de Votos Coerentes}}{\text{Total de Votações Válidas Analisadas}} \right) \times 100

$$


### Critério de Votação Válida (Filtro do Denominador)


Para garantir a precisão analítica e não penalizar parlamentares indevidamente, o sistema aplica um filtro estrito sobre o denominador da fórmula:


* **Posicionamento Ativo Obrigatório:** Apenas votações em que o parlamentar expressou um posicionamento ativo no painel eletrônico, seja votando **"Sim"** ou **"Não"**, são consideradas votações válidas.

* **Abstenções e Faltas:** Registros oficiais de **"Ausente"** ou **"Abstenção"** são rigorosamente ignorados pela IA. Eles não compõem o denominador da fórmula, evitando distorções no cálculo.


---


## Estado de Ausência de Dados


A plataforma necessita de massa de dados para que o cruzamento semântico seja estatisticamente relevante. Para lidar com recortes escassos, o sistema prevê o estado de **Ausência de Dados**:


* **Critério de Nulidade:** Políticos que não possuam volume suficiente de discursos na base de dados (ex: menos de 10% da média do banco) ou que possuam baixíssima participação nas votações listadas, não terão o perfil processado pela IA.

* **Reflexo na Interface:** Para esses parlamentares, o `score_coerencia` é retornado como nulo pela API. No Front-end, o perfil é exibido com um indicador neutro (ex: "N/A" ou silhueta cinza). Isso impede que a plataforma emita um "Falso Incoerente" (Score 0) apenas por falta de registros de atividade legislativa.


---


## Limitações e Mitigações


Para garantir que o cálculo seja justo e tecnicamente viável, o sistema adota os seguintes parâmetros complementares:


* **Recorte Temporal (Legislatura Vigente):** Para mitigar os efeitos de mudanças naturais de posicionamento ao longo de carreiras extensas, o sistema limita a coleta de dados ao período do mandato atual (2023 a 2026). Isso garante que o parlamentar seja avaliado com base em sua atuação recente.


----
