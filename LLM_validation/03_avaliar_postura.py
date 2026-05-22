#!/usr/bin/env python3
"""
Script 03 - Avaliação de Postura
=================================
Testa a capacidade dos 5 modelos de inferir postura política a partir de discursos.

Para cada proposição:
1. Carrega o resumo executivo (gerado no script 02)
2. Carrega os 2 discursos mockados (a favor e contra)
3. Envia para cada modelo: resumo + discurso
4. Modelo infere: o deputado é A FAVOR ou CONTRA?
5. Compara com gabarito (nome do arquivo)

Entrada:
- resultados/resumos_{modelo}.json
- discursos/pl_001_a_favor.txt até pl_004_contra.txt

Saída: resultados/posturas_{modelo}.json

Como rodar:
    python 03_avaliar_postura.py

Estrutura do JSON de saída:
    {
        "pl_001_a_favor": {
            "postura_inferida": "A FAVOR",
            "justificativa": "...",
            "gabarito": "A FAVOR",
            "acertou": true,
            "tempo_segundos": 3.2
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

def create_prompt(resumo_proposicao, discurso):
    """
    Cria o prompt de inferência de postura.
    """
    prompt = f"""Você é um analista político especializado em inferir posicionamentos de parlamentares.

Sua tarefa: analisar um discurso histórico de um deputado e inferir se ele votaria A FAVOR ou CONTRA da proposição descrita abaixo.

IMPORTANTE:
- O discurso NÃO menciona a proposição explicitamente
- Você deve INFERIR a postura com base nos valores, argumentos e posicionamentos do deputado
- Responda APENAS em formato JSON válido, sem texto adicional

PROPOSIÇÃO (resumo):

{resumo_proposicao}

---

DISCURSO DO DEPUTADO (histórico):

{discurso}

---

Baseado no discurso acima, o deputado votaria A FAVOR ou CONTRA desta proposição?

Responda em JSON:
{{
    "postura": "A FAVOR" ou "CONTRA",
    "justificativa": "Explique em 1-2 frases por que você inferiu essa postura"
}}

JSON:"""
    
    return prompt

def inferir_postura_ollama(model_name, prompt):
    """Infere postura usando modelo local via Ollama"""
    try:
        start = time.time()
        
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,  # Baixa temperatura para respostas objetivas
                    "num_predict": 200   # Limite de tokens
                }
            },
            timeout=90
        )
        
        elapsed = time.time() - start
        
        if response.status_code == 200:
            data = response.json()
            resposta_raw = data.get("response", "").strip()
            
            # Tenta extrair JSON
            try:
                # Remove markdown se houver
                resposta_clean = resposta_raw
                if "```json" in resposta_clean:
                    resposta_clean = resposta_clean.split("```json")[1].split("```")[0].strip()
                elif "```" in resposta_clean:
                    resposta_clean = resposta_clean.split("```")[1].split("```")[0].strip()
                
                resultado = json.loads(resposta_clean)
                
                return {
                    "postura_inferida": resultado.get("postura", "").upper(),
                    "justificativa": resultado.get("justificativa", ""),
                    "tempo_segundos": round(elapsed, 2),
                    "erro": None
                }
            except json.JSONDecodeError:
                # Fallback: tenta extrair postura do texto
                postura = "INDEFINIDO"
                if "A FAVOR" in resposta_raw.upper():
                    postura = "A FAVOR"
                elif "CONTRA" in resposta_raw.upper():
                    postura = "CONTRA"
                
                return {
                    "postura_inferida": postura,
                    "justificativa": resposta_raw[:200],
                    "tempo_segundos": round(elapsed, 2),
                    "erro": "JSON inválido (fallback aplicado)"
                }
        else:
            return {
                "postura_inferida": "ERRO",
                "justificativa": "",
                "tempo_segundos": round(elapsed, 2),
                "erro": f"HTTP {response.status_code}"
            }
    
    except Exception as e:
        return {
            "postura_inferida": "ERRO",
            "justificativa": "",
            "tempo_segundos": 0,
            "erro": str(e)
        }

def inferir_postura_groq(model_name, prompt):
    """Infere postura usando API Groq"""
    try:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            return {
                "postura_inferida": "ERRO",
                "justificativa": "",
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
            temperature=0.2,
            max_tokens=200
        )
        
        elapsed = time.time() - start
        
        resposta_raw = response.choices[0].message.content.strip()
        
        # Tenta extrair JSON
        try:
            resposta_clean = resposta_raw
            if "```json" in resposta_clean:
                resposta_clean = resposta_clean.split("```json")[1].split("```")[0].strip()
            elif "```" in resposta_clean:
                resposta_clean = resposta_clean.split("```")[1].split("```")[0].strip()
            
            resultado = json.loads(resposta_clean)
            
            return {
                "postura_inferida": resultado.get("postura", "").upper(),
                "justificativa": resultado.get("justificativa", ""),
                "tempo_segundos": round(elapsed, 2),
                "erro": None
            }
        except json.JSONDecodeError:
            # Fallback
            postura = "INDEFINIDO"
            if "A FAVOR" in resposta_raw.upper():
                postura = "A FAVOR"
            elif "CONTRA" in resposta_raw.upper():
                postura = "CONTRA"
            
            return {
                "postura_inferida": postura,
                "justificativa": resposta_raw[:200],
                "tempo_segundos": round(elapsed, 2),
                "erro": "JSON inválido (fallback aplicado)"
            }
    
    except Exception as e:
        return {
            "postura_inferida": "ERRO",
            "justificativa": "",
            "tempo_segundos": 0,
            "erro": str(e)
        }

def processar_caso(pl_id, postura_esperada, resumo, discurso, modelos):
    """
    Processa um caso de teste (1 proposição + 1 discurso) com todos os modelos.
    """
    caso_id = f"{pl_id}_{postura_esperada.lower().replace(' ', '_')}"
    
    print_status(f"\n  → Testando: {caso_id} (gabarito: {postura_esperada})", YELLOW)
    
    prompt = create_prompt(resumo, discurso)
    resultados = {}
    
    for modelo_info in modelos:
        nome_display = modelo_info["nome"]
        
        if modelo_info["tipo"] == "ollama":
            resultado = inferir_postura_ollama(modelo_info["id"], prompt)
        else:  # groq
            resultado = inferir_postura_groq(modelo_info["id"], prompt)
        
        # Adiciona gabarito e acerto
        resultado["gabarito"] = postura_esperada
        resultado["acertou"] = resultado["postura_inferida"] == postura_esperada
        
        # Exibe resultado
        simbolo = "✓" if resultado["acertou"] else "✗"
        cor = GREEN if resultado["acertou"] else RED
        print_status(f"    {simbolo} {nome_display}: {resultado['postura_inferida']}", cor)
        
        if resultado["erro"]:
            print_status(f"      Aviso: {resultado['erro']}", YELLOW)
        
        resultados[modelo_info["slug"]] = resultado
    
    return resultados

def main():
    print_status("="*60, BLUE)
    print_status("  AVALIAÇÃO DE POSTURA - 5 MODELOS", BLUE)
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
    resultados_dir = Path("resultados")
    discursos_dir = Path("discursos")
    
    # Lista os discursos (gabarito)
    casos_teste = []
    for discurso_file in sorted(discursos_dir.glob("pl_*_*.txt")):
        nome = discurso_file.stem  # pl_001_a_favor
        partes = nome.split("_")
        pl_id = f"{partes[0]}_{partes[1]}"  # pl_001
        postura = " ".join(partes[2:]).upper()  # A FAVOR
        
        casos_teste.append({
            "pl_id": pl_id,
            "postura_esperada": postura,
            "discurso_path": discurso_file
        })
    
    print_status(f"\nEncontrados {len(casos_teste)} casos de teste (4 PLs × 2 posturas)", YELLOW)
    
    # Carrega os resumos de cada modelo
    resumos_por_modelo = {}
    for modelo_info in modelos:
        slug = modelo_info["slug"]
        json_path = resultados_dir / f"resumos_{slug}.json"
        
        with open(json_path, 'r', encoding='utf-8') as f:
            resumos_por_modelo[slug] = json.load(f)
    
    # Processa cada caso de teste
    for caso in casos_teste:
        pl_id = caso["pl_id"]
        postura_esperada = caso["postura_esperada"]
        
        print_status(f"\n{'='*60}", BLUE)
        print_status(f"  {pl_id.upper()} - Postura esperada: {postura_esperada}", BLUE)
        print_status(f"{'='*60}", BLUE)
        
        # Lê o discurso
        with open(caso["discurso_path"], 'r', encoding='utf-8') as f:
            discurso = f.read()
        
        # Processa com cada modelo
        for modelo_info in modelos:
            slug = modelo_info["slug"]
            
            # Pega o resumo deste modelo para esta proposição
            resumo = resumos_por_modelo[slug][pl_id]["resumo"]
            
            if not resumo:
                print_status(f"  ⚠ Pulando {modelo_info['nome']}: resumo não encontrado", YELLOW)
                continue
            
            # Infere postura
            resultado = processar_caso(pl_id, postura_esperada, resumo, discurso, [modelo_info])
            
            # Salva resultado
            json_path = resultados_dir / f"posturas_{slug}.json"
            
            if json_path.exists():
                with open(json_path, 'r', encoding='utf-8') as f:
                    dados = json.load(f)
            else:
                dados = {}
            
            caso_id = f"{pl_id}_{postura_esperada.lower().replace(' ', '_')}"
            dados[caso_id] = resultado[slug]
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)
    
    # Resumo final
    print_status("\n" + "="*60, BLUE)
    print_status("  RESUMO DE ACURÁCIA", BLUE)
    print_status("="*60, BLUE)
    
    for modelo_info in modelos:
        slug = modelo_info["slug"]
        json_path = resultados_dir / f"posturas_{slug}.json"
        
        with open(json_path, 'r', encoding='utf-8') as f:
            dados = json.load(f)
        
        total = len(dados)
        acertos = sum(1 for v in dados.values() if v.get("acertou", False))
        acuracia = (acertos / total * 100) if total > 0 else 0
        
        cor = GREEN if acuracia >= 75 else (YELLOW if acuracia >= 50 else RED)
        
        print_status(f"\n{modelo_info['nome']}:", YELLOW)
        print_status(f"  → Acurácia: {acertos}/{total} ({acuracia:.1f}%)", cor)
        print_status(f"  → Salvo em: resultados/posturas_{slug}.json", BLUE)
    
    print_status("\n✓ Avaliação de postura concluída!", GREEN)
    print_status("\nPróximo passo: python 04_comparar.py\n", YELLOW)

if __name__ == "__main__":
    main()