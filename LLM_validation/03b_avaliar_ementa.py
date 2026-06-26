#!/usr/bin/env python3
"""
Script 03b - Avaliação de Postura com APENAS A EMENTA
=======================================================
Testa se a ementa sozinha é suficiente para inferir postura.

Comparar resultados com posturas_{modelo}.json (que usou resumo completo).

Entrada:
- Ementas hardcoded abaixo
- discursos/pl_001_a_favor.txt até pl_004_contra.txt

Saída: resultados/posturas_ementa_{modelo}.json

Como rodar:
    python 03b_avaliar_ementa.py
"""

import os
import json
import time
import requests
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_status(message, color=YELLOW):
    print(f"{color}{message}{RESET}")


# ─────────────────────────────────────────────
# EMENTAS (input fixo para este teste)
# ─────────────────────────────────────────────
EMENTAS = {
    "pl_001": (
        'Cria o "Protocolo Não é Não" de atendimento à mulher vítima de violência sexual '
        "ou assédio em discotecas ou estabelecimentos noturnos, eventos festivos, bares, "
        "restaurantes ou qualquer outro estabelecimento de grande circulação de pessoas."
    ),
    "pl_002": (
        "Dispõe sobre a prioridade epidemiológica no tratamento de doenças neuromusculares "
        "com paralisia motora e dá outras providências."
    ),
    "pl_003": (
        "Dispõe sobre a substituição do símbolo indicativo representado por uma pessoa "
        "curvada de bengala em vagas, assentos, filas e outros lugares em que haja "
        "prioridade de atendimento à pessoa idosa."
    ),
    "pl_004": (
        "Dispõe sobre a criminalização de condutas atentatórias contra o Cristianismo e "
        "estabelece a reparação por dano moral objetivo à imagem do Cristianismo em caso "
        "de ofensa pública às religiões de matriz cristã, e dá outras providências."
    ),
}

MODELOS = [
    {
        "nome": "Llama 3.1 8B",
        "slug": "llama31_8b",
        "tipo": "ollama",
        "id": "llama3.1:8b",
    },
    {"nome": "Qwen 2.5 7B", "slug": "qwen25_7b", "tipo": "ollama", "id": "qwen2.5:7b"},
    {"nome": "Gemma 2 9B", "slug": "gemma2_9b", "tipo": "ollama", "id": "gemma2:9b"},
    {
        "nome": "Groq Llama 3.3 70B",
        "slug": "groq_llama33_70b",
        "tipo": "groq",
        "id": "llama-3.3-70b-versatile",
    },
    {
        "nome": "Groq Qwen 3 32B",
        "slug": "groq_qwen3_32b",
        "tipo": "groq",
        "id": "qwen/qwen3-32b",
    },
]


# ─────────────────────────────────────────────
# PROMPT
# ─────────────────────────────────────────────
def create_prompt(ementa, discurso):
    return f"""Você é um analista político especializado em inferir posicionamentos de parlamentares.

Sua tarefa: analisar um discurso histórico de um deputado e inferir se ele votaria A FAVOR ou CONTRA da proposição abaixo.

IMPORTANTE:
- O discurso NÃO menciona a proposição explicitamente
- Você deve INFERIR a postura com base nos valores e argumentos do deputado
- Responda APENAS em formato JSON válido, sem texto adicional

PROPOSIÇÃO (ementa):

{ementa}

---

DISCURSO DO DEPUTADO (histórico):

{discurso}

---

Responda em JSON:
{{
    "postura": "A FAVOR" ou "CONTRA",
    "justificativa": "Explique em 1-2 frases por que você inferiu essa postura"
}}

JSON:"""


# ─────────────────────────────────────────────
# CHAMADAS AOS MODELOS
# ─────────────────────────────────────────────
def parse_resposta(raw):
    """Extrai JSON da resposta, com fallback para leitura livre."""
    try:
        clean = raw
        if "```json" in clean:
            clean = clean.split("```json")[1].split("```")[0].strip()
        elif "```" in clean:
            clean = clean.split("```")[1].split("```")[0].strip()
        resultado = json.loads(clean)
        return (
            resultado.get("postura", "").upper(),
            resultado.get("justificativa", ""),
            None,
        )
    except json.JSONDecodeError:
        postura = "INDEFINIDO"
        if "A FAVOR" in raw.upper():
            postura = "A FAVOR"
        elif "CONTRA" in raw.upper():
            postura = "CONTRA"
        return postura, raw[:200], "JSON inválido (fallback)"


def chamar_ollama(model_id, prompt):
    start = time.time()
    try:
        r = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model_id,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": 200},
            },
            timeout=90,
        )
        elapsed = round(time.time() - start, 2)
        if r.status_code == 200:
            postura, justif, erro = parse_resposta(r.json().get("response", ""))
            return postura, justif, elapsed, erro
        return "ERRO", "", elapsed, f"HTTP {r.status_code}"
    except Exception as e:
        return "ERRO", "", round(time.time() - start, 2), str(e)


def chamar_groq(model_id, prompt):
    start = time.time()
    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        r = client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=200,
        )
        elapsed = round(time.time() - start, 2)
        postura, justif, erro = parse_resposta(r.choices[0].message.content.strip())
        return postura, justif, elapsed, erro
    except Exception as e:
        return "ERRO", "", round(time.time() - start, 2), str(e)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print_status("=" * 60, BLUE)
    print_status("  TESTE: INFERÊNCIA COM APENAS A EMENTA", BLUE)
    print_status("=" * 60, BLUE)

    resultados_dir = Path("resultados")
    discursos_dir = Path("discursos")

    # Monta lista de casos de teste a partir dos arquivos de discurso
    casos = []
    for f in sorted(discursos_dir.glob("pl_*_*.txt")):
        partes = f.stem.split("_")
        pl_id = f"{partes[0]}_{partes[1]}"  # pl_001
        postura = " ".join(partes[2:]).upper()  # A FAVOR | CONTRA
        if pl_id in EMENTAS:
            casos.append({"pl_id": pl_id, "postura_esperada": postura, "path": f})

    print_status(f"\n{len(casos)} casos de teste encontrados\n", YELLOW)

    for modelo in MODELOS:
        slug = modelo["slug"]
        dados_out = {}

        print_status(f"\n{'─'*60}", BLUE)
        print_status(f"  Modelo: {modelo['nome']}", BLUE)
        print_status(f"{'─'*60}", BLUE)

        for caso in casos:
            pl_id = caso["pl_id"]
            gabarito = caso["postura_esperada"]
            ementa = EMENTAS[pl_id]

            with open(caso["path"], encoding="utf-8") as f:
                discurso = f.read()

            prompt = create_prompt(ementa, discurso)

            if modelo["tipo"] == "ollama":
                postura, justif, elapsed, erro = chamar_ollama(modelo["id"], prompt)
            else:
                postura, justif, elapsed, erro = chamar_groq(modelo["id"], prompt)

            acertou = postura == gabarito
            caso_id = f"{pl_id}_{gabarito.lower().replace(' ', '_')}"
            simbolo = "✓" if acertou else "✗"
            cor = GREEN if acertou else RED

            print_status(
                f"  {simbolo} {caso_id:<30} inferido: {postura:<8} ({elapsed}s)", cor
            )
            if erro:
                print_status(f"      Aviso: {erro}", YELLOW)

            dados_out[caso_id] = {
                "postura_inferida": postura,
                "justificativa": justif,
                "gabarito": gabarito,
                "acertou": acertou,
                "tempo_segundos": elapsed,
                "erro": erro,
            }

        # Salva JSON
        out_path = resultados_dir / f"posturas_ementa_{slug}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(dados_out, f, ensure_ascii=False, indent=2)

        acertos = sum(1 for v in dados_out.values() if v["acertou"])
        total = len(dados_out)
        acuracia = acertos / total * 100 if total else 0
        cor = GREEN if acuracia >= 75 else (YELLOW if acuracia >= 50 else RED)
        print_status(f"\n  Acurácia: {acertos}/{total} ({acuracia:.1f}%)", cor)

    # ── Tabela comparativa final ──────────────────────────────────
    print_status("\n" + "=" * 60, BLUE)
    print_status("  COMPARAÇÃO: EMENTA vs RESUMO COMPLETO", BLUE)
    print_status("=" * 60, BLUE)

    print_status(f"\n{'Modelo':<25} {'Ementa':>8} {'Resumo':>8} {'Δ':>5}", YELLOW)
    print_status("─" * 50, YELLOW)

    for modelo in MODELOS:
        slug = modelo["slug"]

        # Acurácia com ementa
        ementa_path = resultados_dir / f"posturas_ementa_{slug}.json"
        with open(ementa_path, encoding="utf-8") as f:
            d_ementa = json.load(f)
        ac_ementa = (
            sum(1 for v in d_ementa.values() if v["acertou"]) / len(d_ementa) * 100
        )

        # Acurácia com resumo completo (pode não existir ainda)
        resumo_path = resultados_dir / f"posturas_{slug}.json"
        if resumo_path.exists():
            with open(resumo_path, encoding="utf-8") as f:
                d_resumo = json.load(f)
            ac_resumo = (
                sum(1 for v in d_resumo.values() if v["acertou"]) / len(d_resumo) * 100
            )
            delta = ac_resumo - ac_ementa
            delta_str = f"{delta:+.1f}%"
            resumo_str = f"{ac_resumo:.1f}%"
        else:
            resumo_str = "N/A"
            delta_str = "N/A"

        print_status(
            f"  {modelo['nome']:<23} {ac_ementa:>6.1f}%  {resumo_str:>7}  {delta_str:>6}",
            RESET,
        )

    print_status("\n✓ Teste concluído!", GREEN)
    print_status("Δ positivo = resumo completo foi melhor que ementa\n", YELLOW)


if __name__ == "__main__":
    main()
