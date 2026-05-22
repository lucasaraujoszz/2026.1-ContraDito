# Experimento: Validação de LLM para Inferência de Postura Parlamentar

Esta pasta contém os scripts, dados de teste e resultados de um *Spike* realizado para validar o uso de LLMs na inferência de postura parlamentar (A FAVOR / CONTRA) com base em ementas/resumos de proposições e discursos.

## Decisão Arquitetural
O modelo escolhido para produção foi o **Llama 3.1 8B**. A validação comprovou acurácia de 100% nas amostras testadas. Para viabilizar o tempo de processamento em massa (~42.5k inferências), a abordagem sequencial local foi substituída por um pipeline em **Google Colab (GPU T4)** utilizando processamento em *batching*, *Chain of Thought* e extração em *Regex*.

## Estrutura de Arquivos

### Fluxo Principal de Teste
* `00_teste_conexao.py`: Validação de comunicação com os modelos locais (Ollama) e remotos (API Groq).
* `01_extrair_texto.py`: Extração de textos (ementa, artigos, justificativa) das proposições em PDF.
* `02_gerar_resumo.py`: Geração de resumos executivos (limite de tokens) por cada modelo candidato.
* `03_avaliar_postura.py`: Inferência principal utilizando o resumo completo vs. discursos mockados.
* `03b_avaliar_ementa.py`: Teste de estresse para checar se apenas a ementa seria suficiente para uma inferência correta.
* `04_comparar.py`: Agregação dos resultados e geração do benchmark final (`benchmark_final.json`).

### Otimização em Nuvem
* `benchmark_llama31_8b_colab.ipynb`: Notebook utilizado para otimizar o tempo de inferência de 19s (M1 local) para ~3s via GPU T4 com processamento em lote.

### Utilitários
* `auditar_estimativas.py`, `comparar_justificativas.py`, `diagnostico_api.py`, `inspecionar_bulk.py`: Scripts auxiliares de diagnóstico e métricas de qualidade.

### Dados
* `/proposicoes/textos/`: Extratos em formato txt de 4 Proposições (PLs) reais.
* `/discursos/`: 8 discursos mockados (2 para cada PL, sendo um implícito a favor e um implícito contra).
* `/resultados/`: Arquivos `.json` de saída com os resumos e inferências geradas por cada modelo avaliado (Gemma 2, Qwen 2.5, Qwen 3, Llama 3.3 e Llama 3.1).

## Como reproduzir os testes locais

1. Certifique-se de ter o [Ollama](https://ollama.com/) instalado e os modelos rodando (`llama3.1:8b`, etc).
2. (Opcional) Configure sua chave da Groq em um arquivo `.env` para rodar os modelos em nuvem.
3. Crie e ative um ambiente virtual:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows