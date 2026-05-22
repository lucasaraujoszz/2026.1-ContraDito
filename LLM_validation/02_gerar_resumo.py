#!/usr/bin/env python3
"""
Script 02 - Geração de Resumos Executivos
==========================================
Envia os textos extraídos para os 5 modelos e gera resumos executivos.

Modelos:
- Llama 3.1 8B (Ollama local)
- Qwen 2.5 7B (Ollama local)
- Gemma 2 9B (Ollama local)
- Groq Llama 3.3 70B (API Groq)
- Groq Qwen 3 32B (API Groq)

Entrada: proposicoes/textos/pl_001.txt até pl_004.txt
Saída: resultados/resumos_{modelo}.json

Como rodar:
    python 02_gerar_resumo.py

Estrutura do JSON de saída:
    {
        "pl_001": {
            "resumo": "texto do resumo",
            "tokens": 350,
            "tempo_segundos": 12.5
        },
        ...
    }
"""

import os
import json
import time
import requests
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

# Carrega variáveis de ambiente
load_dotenv()

# Cores para output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_status(message, color=YELLOW):
    """Imprime mensagem colorida"""
    print(f"{color}{message}{RESET}")

def count_tokens_approx(text):
    """Estimativa aproximada de tokens (1 token ≈ 4 caracteres)"""
    return len(text) // 4

def create_prompt(texto_completo):
    """
    Cria o prompt de resumo com limite de tokens claro.
    """
    prompt = f"""Você é um assistente especializado em resumir proposições legislativas brasileiras.

Sua tarefa: criar um RESUMO EXECUTIVO da proposição abaixo em NO MÁXIMO 400 tokens.

O resumo deve conter:
1. O que a proposição propõe fazer (objetivo principal)
2. Principais artigos e obrigações criadas
3. Argumentos centrais da justificativa

Regras OBRIGATÓRIAS:
- Máximo de 400 tokens
- Linguagem objetiva e clara
- Preservar o núcleo temático (do que trata a proposição)
- Não adicionar opiniões pessoais

PROPOSIÇÃO:

{texto_completo}

RESUMO EXECUTIVO:"""
    
    return prompt

def resumir_ollama(model_name, prompt):
    """Gera resumo usando modelo local via Ollama"""
    try:
        start = time.time()
        
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,  # Baixa temperatura para resumos objetivos
                    "num_predict": 500   # Limite de tokens (margem de segurança)
                }
            },
            timeout=120  # 2 minutos de timeout
        )
        
        elapsed = time.time() - start
        
        if response.status_code == 200:
            data = response.json()
            resumo = data.get("response", "").strip()
            tokens = count_tokens_approx(resumo)
            
            return {
                "resumo": resumo,
                "tokens": tokens,
                "tempo_segundos": round(elapsed, 2),
                "erro": None
            }
        else:
            return {
                "resumo": None,
                "tokens": 0,
                "tempo_segundos": round(elapsed, 2),
                "erro": f"HTTP {response.status_code}"
            }
    
    except Exception as e:
        return {
            "resumo": None,
            "tokens": 0,
            "tempo_segundos": 0,
            "erro": str(e)
        }

def resumir_groq(model_name, prompt):
    """Gera resumo usando API Groq"""
    try:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            return {
                "resumo": None,
                "tokens": 0,
                "tempo_segundos": 0,
                "erro": "GROQ_API_KEY não encontrada"
            }
        
        client = Groq(api_key=api_key)
        
        start = time.time()
        
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        elapsed = time.time() - start
        
        resumo = response.choices[0].message.content.strip()
        tokens = count_tokens_approx(resumo)
        
        return {
            "resumo": resumo,
            "tokens": tokens,
            "tempo_segundos": round(elapsed, 2),
            "erro": None
        }
    
    except Exception as e:
        return {
            "resumo": None,
            "tokens": 0,
            "tempo_segundos": 0,
            "erro": str(e)
        }

def processar_proposicao(pl_id, texto_completo, modelos):
    """
    Processa uma proposição enviando para todos os modelos.
    Retorna dict com resultados de cada modelo.
    """
    print_status(f"\n{'='*60}", BLUE)
    print_status(f"  Processando: {pl_id}", BLUE)
    print_status(f"{'='*60}", BLUE)
    
    prompt = create_prompt(texto_completo)
    resultados = {}
    
    for modelo_info in modelos:
        nome_display = modelo_info["nome"]
        print_status(f"\n  → {nome_display}...", YELLOW)
        
        if modelo_info["tipo"] == "ollama":
            resultado = resumir_ollama(modelo_info["id"], prompt)
        else:  # groq
            resultado = resumir_groq(modelo_info["id"], prompt)
        
        if resultado["erro"]:
            print_status(f"    ✗ Erro: {resultado['erro']}", RED)
        else:
            print_status(f"    ✓ {resultado['tokens']} tokens em {resultado['tempo_segundos']}s", GREEN)
        
        resultados[modelo_info["slug"]] = resultado
    
    return resultados

def main():
    print_status("="*60, BLUE)
    print_status("  GERAÇÃO DE RESUMOS EXECUTIVOS - 5 MODELOS", BLUE)
    print_status("="*60, BLUE)
    
    # Define os 5 modelos
    modelos = [
        {
            "nome": "Llama 3.1 8B",
            "slug": "llama31_8b",
            "tipo": "ollama",
            "id": "llama3.1:8b"
        },
        {
            "nome": "Qwen 2.5 7B",
            "slug": "qwen25_7b",
            "tipo": "ollama",
            "id": "qwen2.5:7b"
        },
        {
            "nome": "Gemma 2 9B",
            "slug": "gemma2_9b",
            "tipo": "ollama",
            "id": "gemma2:9b"
        },
        {
            "nome": "Groq Llama 3.3 70B",
            "slug": "groq_llama33_70b",
            "tipo": "groq",
            "id": "llama-3.3-70b-versatile"
        },
        {
            "nome": "Groq Qwen 3 32B",
            "slug": "groq_qwen3_32b",
            "tipo": "groq",
            "id": "qwen/qwen3-32b"
        }
    ]
    
    # Diretórios
    textos_dir = Path("proposicoes/textos")
    resultados_dir = Path("resultados")
    resultados_dir.mkdir(exist_ok=True)
    
    # Lista os arquivos .txt
    txt_files = sorted(textos_dir.glob("pl_*.txt"))
    
    if not txt_files:
        print_status("\n✗ Nenhum arquivo .txt encontrado em proposicoes/textos/", RED)
        return
    
    print_status(f"\nEncontrados {len(txt_files)} arquivos de texto", YELLOW)
    print_status(f"Testando {len(modelos)} modelos", YELLOW)
    
    # Processa cada proposição com cada modelo
    for txt_file in txt_files:
        pl_id = txt_file.stem  # pl_001
        
        # Lê o texto
        with open(txt_file, 'r', encoding='utf-8') as f:
            texto_completo = f.read()
        
        # Processa com todos os modelos
        resultados = processar_proposicao(pl_id, texto_completo, modelos)
        
        # Salva resultado de cada modelo em arquivo separado
        for modelo_info in modelos:
            slug = modelo_info["slug"]
            
            # Carrega JSON existente ou cria novo
            json_path = resultados_dir / f"resumos_{slug}.json"
            
            if json_path.exists():
                with open(json_path, 'r', encoding='utf-8') as f:
                    dados = json.load(f)
            else:
                dados = {}
            
            # Adiciona resultado desta proposição
            dados[pl_id] = resultados[slug]
            
            # Salva
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)
    
    # Resumo final
    print_status("\n" + "="*60, BLUE)
    print_status("  RESUMO FINAL", BLUE)
    print_status("="*60, BLUE)
    
    for modelo_info in modelos:
        slug = modelo_info["slug"]
        json_path = resultados_dir / f"resumos_{slug}.json"
        
        with open(json_path, 'r', encoding='utf-8') as f:
            dados = json.load(f)
        
        sucessos = sum(1 for v in dados.values() if v["erro"] is None)
        total = len(dados)
        
        print_status(f"\n{modelo_info['nome']}:", YELLOW)
        print_status(f"  → {sucessos}/{total} resumos gerados com sucesso", 
                    GREEN if sucessos == total else RED)
        print_status(f"  → Salvo em: resultados/resumos_{slug}.json", BLUE)
    
    print_status("\n✓ Geração de resumos concluída!", GREEN)
    print_status("\nPróximo passo: python 03_avaliar_postura.py\n", YELLOW)

if __name__ == "__main__":
    main()