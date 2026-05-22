#!/usr/bin/env python3
"""
Script 00 - Teste de Conexão
=============================
Valida se todos os 5 modelos do benchmark estão respondendo corretamente.

Modelos testados:
- Llama 3.1 8B (Ollama local)
- Qwen 2.5 7B (Ollama local)
- Gemma 2 9B (Ollama local)
- Groq Llama 3.3 70B (API Groq)
- Groq Qwen 3 32B (API Groq)

Como rodar:
    python 00_teste_conexao.py

O que esperar:
    ✅ para cada modelo que responder corretamente
    ❌ para modelos com erro (com mensagem de debug)
"""

import os
import sys
import requests
import time
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

# Cores para output no terminal
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def print_header(text):
    """Imprime um cabeçalho formatado"""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")

def print_result(model_name, success, message="", response_time=None):
    """Imprime resultado de um teste"""
    status = f"{GREEN}✅{RESET}" if success else f"{RED}❌{RESET}"
    time_str = f" ({response_time:.2f}s)" if response_time else ""
    print(f"{status} {model_name}{time_str}")
    if message:
        print(f"   → {message}\n")

def test_ollama_model(model_name):
    """Testa um modelo local via Ollama"""
    try:
        start = time.time()
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model_name,
                "prompt": "Responda apenas: OK",
                "stream": False
            },
            timeout=30
        )
        elapsed = time.time() - start
        
        if response.status_code == 200:
            data = response.json()
            if "response" in data:
                return True, elapsed, ""
        return False, elapsed, f"Status {response.status_code}"
    except requests.exceptions.ConnectionError:
        return False, 0, "Ollama não está rodando. Execute: ollama serve"
    except Exception as e:
        return False, 0, str(e)

def test_gemini():
    """Testa Gemini 2.0 Flash via API Google"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return False, 0, "GEMINI_API_KEY não encontrada no .env"
    
    try:
        import warnings
        warnings.filterwarnings('ignore', category=FutureWarning)
        
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        
        start = time.time()
        model = genai.GenerativeModel('gemini-2.0-flash-lite')
        response = model.generate_content("Responda apenas: OK")
        elapsed = time.time() - start
        
        if response.text:
            return True, elapsed, ""
        return False, elapsed, "Resposta vazia"
    except ImportError:
        return False, 0, "Biblioteca google-generativeai não instalada"
    except Exception as e:
        return False, 0, str(e)

def test_groq(model_name):
    """Testa modelos via API Groq"""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return False, 0, "GROQ_API_KEY não encontrada no .env"
    
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        
        start = time.time()
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "Responda apenas: OK"}],
            max_tokens=10
        )
        elapsed = time.time() - start
        
        if response.choices[0].message.content:
            return True, elapsed, ""
        return False, elapsed, "Resposta vazia"
    except ImportError:
        return False, 0, "Biblioteca groq não instalada"
    except Exception as e:
        return False, 0, str(e)

def test_jurema():
    """Testa Jurema 7B via Hugging Face Inference API"""
    api_key = os.getenv("HF_API_KEY")
    if not api_key:
        return False, 0, "HF_API_KEY não encontrada no .env"
    
    try:
        start = time.time()
        response = requests.post(
            "https://api-inference.huggingface.co/models/maritaca-ai/jurema-7b-chat",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"inputs": "Responda apenas: OK"},
            timeout=30
        )
        elapsed = time.time() - start
        
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                return True, elapsed, ""
            return False, elapsed, "Formato de resposta inesperado"
        elif response.status_code == 503:
            return False, elapsed, "Modelo está carregando (tente novamente em 30s)"
        else:
            return False, elapsed, f"Status {response.status_code}"
    except Exception as e:
        return False, 0, str(e)

def main():
    print_header("TESTE DE CONEXÃO - 7 MODELOS")
    
    print(f"{YELLOW}Validando ambiente...{RESET}")
    
    # Verifica se as chaves estão no .env
    required_keys = ["GROQ_API_KEY"]
    missing_keys = [key for key in required_keys if not os.getenv(key)]
    
    if missing_keys:
        print(f"\n{RED}❌ Chaves faltando no .env:{RESET}")
        for key in missing_keys:
            print(f"   - {key}")
        print(f"\n{YELLOW}Edite o arquivo .env e adicione as chaves faltantes.{RESET}\n")
        sys.exit(1)
    
    print(f"{GREEN}✅ Arquivo .env encontrado com GROQ_API_KEY{RESET}\n")
    
    # Lista de modelos para testar
    tests = [
        ("Modelos Locais (Ollama)", [
            ("Llama 3.1 8B", lambda: test_ollama_model("llama3.1:8b")),
            ("Qwen 2.5 7B", lambda: test_ollama_model("qwen2.5:7b")),
            ("Gemma 2 9B", lambda: test_ollama_model("gemma2:9b")),
        ]),
        ("APIs Gratuitas (Groq)", [
            ("Groq Llama 3.3 70B", lambda: test_groq("llama-3.3-70b-versatile")),
            ("Groq Qwen 3 32B", lambda: test_groq("qwen/qwen3-32b")),
        ])
    ]
    
    # Executa os testes
    total_success = 0
    total_tests = 0
    
    for category, category_tests in tests:
        print(f"\n{YELLOW}Testando: {category}{RESET}")
        print("-" * 60)
        
        for model_name, test_func in category_tests:
            total_tests += 1
            success, response_time, error_msg = test_func()
            
            if success:
                total_success += 1
            
            print_result(model_name, success, error_msg, response_time if success else None)
    
    # Resumo final
    print_header("RESUMO")
    print(f"Modelos funcionando: {total_success}/{total_tests}")
    
    if total_success == total_tests:
        print(f"\n{GREEN}🎉 Todos os modelos estão prontos para o benchmark!{RESET}\n")
        print(f"{YELLOW}Próximo passo:{RESET} python 01_extrair_texto.py\n")
    else:
        print(f"\n{RED}⚠️  Alguns modelos falharam. Corrija os erros acima antes de prosseguir.{RESET}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()