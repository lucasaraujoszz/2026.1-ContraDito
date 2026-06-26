#!/usr/bin/env python3
"""
Script aux - Comparação de Justificativas
==========================================
Imprime justificativas da inferência com EMENTA vs RESUMO lado a lado.
Permite avaliar se o modelo está acertando pelo motivo correto.

Como rodar:
    python comparar_justificativas.py
"""

import json
from pathlib import Path

YELLOW = "\033[93m"
GREEN = "\033[92m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

MODELOS = [
    {"nome": "Llama 3.1 8B", "slug": "llama31_8b"},
    {"nome": "Qwen 2.5 7B", "slug": "qwen25_7b"},
    {"nome": "Gemma 2 9B", "slug": "gemma2_9b"},
    {"nome": "Groq Llama 3.3 70B", "slug": "groq_llama33_70b"},
    {"nome": "Groq Qwen 3 32B", "slug": "groq_qwen3_32b"},
]


def wrap(text, width=55):
    """Quebra texto em linhas de até `width` caracteres."""
    if not text:
        return ["(sem justificativa)"]
    words = text.split()
    lines, line = [], ""
    for word in words:
        if len(line) + len(word) + 1 <= width:
            line = f"{line} {word}".strip()
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines or ["(vazio)"]


def print_justificativas(caso_id, gabarito, dados_ementa, dados_resumo):
    acertou_ementa = dados_ementa.get("acertou", False)
    acertou_resumo = dados_resumo.get("acertou", False) if dados_resumo else None

    print(f"\n{BOLD}{'─'*120}{RESET}")
    print(f"{BOLD}CASO: {caso_id.upper():<40} GABARITO: {gabarito}{RESET}")
    print(f"{'─'*120}")

    # Cabeçalho das colunas
    print(f"  {'EMENTA':<60}  {'RESUMO COMPLETO':<60}")
    print(f"  {'─'*58}  {'─'*58}")

    # Postura inferida
    pos_e = dados_ementa.get("postura_inferida", "N/A")
    pos_r = dados_resumo.get("postura_inferida", "N/A") if dados_resumo else "N/A"
    cor_e = GREEN if acertou_ementa else RED
    cor_r = (GREEN if acertou_resumo else RED) if dados_resumo else YELLOW

    print(f"  {cor_e}Postura: {pos_e:<51}{RESET}  {cor_r}Postura: {pos_r:<51}{RESET}")
    print()

    # Justificativas lado a lado
    linhas_e = wrap(dados_ementa.get("justificativa", ""), 56)
    linhas_r = wrap(
        (
            dados_resumo.get("justificativa", "N/A — rode script 03 primeiro")
            if dados_resumo
            else "N/A — rode script 03 primeiro"
        ),
        56,
    )

    max_linhas = max(len(linhas_e), len(linhas_r))
    linhas_e += [""] * (max_linhas - len(linhas_e))
    linhas_r += [""] * (max_linhas - len(linhas_r))

    for le, lr in zip(linhas_e, linhas_r):
        print(f"  {CYAN}{le:<58}{RESET}  {CYAN}{lr:<58}{RESET}")


def main():
    resultados_dir = Path("resultados")

    for modelo in MODELOS:
        slug = modelo["slug"]

        ementa_path = resultados_dir / f"posturas_ementa_{slug}.json"
        resumo_path = resultados_dir / f"posturas_{slug}.json"

        if not ementa_path.exists():
            print(f"{RED}Arquivo não encontrado: {ementa_path}{RESET}")
            continue

        with open(ementa_path, encoding="utf-8") as f:
            dados_ementa = json.load(f)

        dados_resumo_completo = {}
        if resumo_path.exists():
            with open(resumo_path, encoding="utf-8") as f:
                dados_resumo_completo = json.load(f)

        print(f"\n\n{'='*120}")
        print(f"{BOLD}  MODELO: {modelo['nome']}{RESET}")
        print(f"{'='*120}")

        for caso_id, dado_e in sorted(dados_ementa.items()):
            gabarito = dado_e.get("gabarito", "?")
            dado_r = dados_resumo_completo.get(caso_id)
            print_justificativas(caso_id, gabarito, dado_e, dado_r)

        # Acurácia do modelo
        total = len(dados_ementa)
        acertos = sum(1 for v in dados_ementa.values() if v["acertou"])
        print(
            f"\n  {GREEN if acertos == total else YELLOW}Acurácia: {acertos}/{total}{RESET}"
        )

    print(f"\n{'='*120}\n")


if __name__ == "__main__":
    main()
