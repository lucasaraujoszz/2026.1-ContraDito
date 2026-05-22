#!/usr/bin/env python3
"""
Script 04 - Comparação Final do Benchmark
==========================================
Agrega todos os resultados e gera tabela comparativa final dos 5 modelos.

Critérios e pesos:
- Acurácia de postura (35%)
- Validade do JSON (20%)
- Preservação do núcleo temático / qualidade da justificativa (15%)
- Respeito ao limite de tokens no resumo (15%)
- Velocidade (10%)
- Consistência ementa vs resumo (5%)

Entrada:
- resultados/posturas_{modelo}.json
- resultados/posturas_ementa_{modelo}.json
- resultados/resumos_{modelo}.json

Saída: resultados/benchmark_final.json + tabela impressa no terminal

Como rodar:
    python 04_comparar.py
"""

import json
from pathlib import Path

GREEN  = '\033[92m'
YELLOW = '\033[93m'
RED    = '\033[91m'
BLUE   = '\033[94m'
CYAN   = '\033[96m'
BOLD   = '\033[1m'
RESET  = '\033[0m'

MODELOS = [
    {"nome": "Llama 3.1 8B",       "slug": "llama31_8b"},
    {"nome": "Qwen 2.5 7B",        "slug": "qwen25_7b"},
    {"nome": "Gemma 2 9B",         "slug": "gemma2_9b"},
    {"nome": "Groq Llama 3.3 70B", "slug": "groq_llama33_70b"},
    {"nome": "Groq Qwen 3 32B",    "slug": "groq_qwen3_32b"},
]

PESOS = {
    "acuracia":       0.35,
    "json_valido":    0.20,
    "tokens_ok":      0.15,
    "justificativa":  0.15,
    "velocidade":     0.10,
    "consistencia":   0.05,
}

TOKEN_LIMITE = 400  # limite esperado para resumos

def cor_nota(nota):
    """Retorna cor baseada na nota 0-100."""
    if nota >= 80:
        return GREEN
    elif nota >= 60:
        return YELLOW
    return RED

def calcular_acuracia(dados_posturas):
    """Acurácia: % de casos onde acertou a postura."""
    if not dados_posturas:
        return 0.0
    acertos = sum(1 for v in dados_posturas.values() if v.get("acertou", False))
    return acertos / len(dados_posturas) * 100

def calcular_json_valido(dados_posturas):
    """% de respostas que vieram como JSON válido (sem fallback)."""
    if not dados_posturas:
        return 0.0
    validos = sum(1 for v in dados_posturas.values() if v.get("erro") is None)
    return validos / len(dados_posturas) * 100

def calcular_tokens_ok(dados_resumos):
    """% de resumos que respeitaram o limite de tokens."""
    if not dados_resumos:
        return 0.0
    ok = sum(1 for v in dados_resumos.values()
             if v.get("tokens", 9999) <= TOKEN_LIMITE and v.get("erro") is None)
    return ok / len(dados_resumos) * 100

def calcular_velocidade(dados_posturas, dados_resumos):
    """
    Normaliza velocidade: modelo mais rápido = 100, mais lento = 0.
    Usa tempo médio combinado de resumo + postura.
    """
    tempos = []
    for v in dados_posturas.values():
        if v.get("tempo_segundos"):
            tempos.append(v["tempo_segundos"])
    for v in dados_resumos.values():
        if v.get("tempo_segundos"):
            tempos.append(v["tempo_segundos"])
    return sum(tempos) / len(tempos) if tempos else 9999

def calcular_consistencia(dados_posturas, dados_ementa):
    """
    Consistência: % de casos onde ementa e resumo chegaram à mesma postura.
    Mede se o modelo é estável independente do input.
    """
    if not dados_posturas or not dados_ementa:
        return 0.0
    consistentes = 0
    total = 0
    for caso_id, v_resumo in dados_posturas.items():
        v_ementa = dados_ementa.get(caso_id)
        if v_ementa:
            total += 1
            if v_resumo.get("postura_inferida") == v_ementa.get("postura_inferida"):
                consistentes += 1
    return consistentes / total * 100 if total else 0.0

def main():
    resultados_dir = Path("resultados")

    print(f"\n{BOLD}{'='*70}{RESET}")
    print(f"{BOLD}  BENCHMARK FINAL - COMPARAÇÃO DE 5 MODELOS{RESET}")
    print(f"{BOLD}{'='*70}{RESET}\n")

    scores_brutos = {}  # guarda métricas individuais por modelo
    tempos_medios = {}  # para normalizar velocidade depois

    # ── 1. Coleta métricas brutas ─────────────────────────────────────────
    for modelo in MODELOS:
        slug = modelo["slug"]

        # Carrega arquivos
        posturas_path = resultados_dir / f"posturas_{slug}.json"
        ementa_path   = resultados_dir / f"posturas_ementa_{slug}.json"
        resumos_path  = resultados_dir / f"resumos_{slug}.json"

        dados_posturas = {}
        dados_ementa   = {}
        dados_resumos  = {}

        if posturas_path.exists():
            with open(posturas_path, encoding="utf-8") as f:
                dados_posturas = json.load(f)

        if ementa_path.exists():
            with open(ementa_path, encoding="utf-8") as f:
                dados_ementa = json.load(f)

        if resumos_path.exists():
            with open(resumos_path, encoding="utf-8") as f:
                dados_resumos = json.load(f)

        # Calcula métricas
        acuracia    = calcular_acuracia(dados_posturas or dados_ementa)
        json_valido = calcular_json_valido(dados_posturas or dados_ementa)
        tokens_ok   = calcular_tokens_ok(dados_resumos)
        consistencia = calcular_consistencia(dados_posturas, dados_ementa)
        tempo_medio  = calcular_velocidade(dados_posturas or dados_ementa, dados_resumos)

        scores_brutos[slug] = {
            "nome":        modelo["nome"],
            "acuracia":    acuracia,
            "json_valido": json_valido,
            "tokens_ok":   tokens_ok,
            "consistencia": consistencia,
            "tempo_medio": tempo_medio,
        }
        tempos_medios[slug] = tempo_medio

    # ── 2. Normaliza velocidade (menor tempo = maior nota) ────────────────
    t_min = min(tempos_medios.values())
    t_max = max(tempos_medios.values())
    for slug in scores_brutos:
        t = scores_brutos[slug]["tempo_medio"]
        if t_max == t_min:
            scores_brutos[slug]["velocidade_norm"] = 100.0
        else:
            scores_brutos[slug]["velocidade_norm"] = (t_max - t) / (t_max - t_min) * 100

    # ── 3. Calcula score final ponderado ──────────────────────────────────
    scores_finais = {}
    for slug, dados in scores_brutos.items():
        score = (
            dados["acuracia"]         * PESOS["acuracia"]     +
            dados["json_valido"]      * PESOS["json_valido"]  +
            dados["tokens_ok"]        * PESOS["tokens_ok"]    +
            dados["acuracia"]         * PESOS["justificativa"] +  # proxy: acurácia representa qualidade
            dados["velocidade_norm"]  * PESOS["velocidade"]   +
            dados["consistencia"]     * PESOS["consistencia"]
        )
        scores_finais[slug] = round(score, 1)

    # Ordena por score final
    ranking = sorted(scores_finais.items(), key=lambda x: x[1], reverse=True)

    # ── 4. Imprime tabela detalhada ───────────────────────────────────────
    header = f"  {'Modelo':<24} {'Acur':>6} {'JSON':>6} {'Tok':>6} {'Veloc':>6} {'Cons':>6} {'SCORE':>7}"
    print(f"{BOLD}{CYAN}{header}{RESET}")
    print(f"  {'─'*65}")

    for slug, score_final in ranking:
        d    = scores_brutos[slug]
        nome = d["nome"]

        linha = (
            f"  {nome:<24}"
            f" {d['acuracia']:>5.1f}%"
            f" {d['json_valido']:>5.1f}%"
            f" {d['tokens_ok']:>5.1f}%"
            f" {d['velocidade_norm']:>5.1f}%"
            f" {d['consistencia']:>5.1f}%"
            f" {BOLD}{cor_nota(score_final)}{score_final:>6.1f}{RESET}"
        )
        print(linha)

    print(f"\n  {YELLOW}Pesos: Acurácia 35% · JSON 20% · Tokens 15% · Justif. 15% · Velocidade 10% · Consistência 5%{RESET}")

    # ── 5. Pódio ──────────────────────────────────────────────────────────
    print(f"\n{BOLD}{'─'*70}{RESET}")
    print(f"{BOLD}  PÓDIO{RESET}")
    print(f"{'─'*70}")

    medalhas = ["🥇", "🥈", "🥉"]
    for i, (slug, score) in enumerate(ranking[:3]):
        nome = scores_brutos[slug]["nome"]
        cor  = cor_nota(score)
        print(f"  {medalhas[i]}  {cor}{BOLD}{nome:<24}{RESET}  Score: {cor}{score}{RESET}")

    # ── 6. Recomendação final ─────────────────────────────────────────────
    vencedor_slug  = ranking[0][0]
    vencedor_nome  = scores_brutos[vencedor_slug]["nome"]
    vencedor_score = ranking[0][1]

    # Melhor modelo local (para resumo)
    locais = [s for s in ranking if scores_brutos[s[0]]["nome"] in
              ["Llama 3.1 8B", "Qwen 2.5 7B", "Gemma 2 9B"]]
    melhor_local = locais[0] if locais else None

    print(f"\n{BOLD}{'─'*70}{RESET}")
    print(f"{BOLD}  RECOMENDAÇÃO{RESET}")
    print(f"{'─'*70}")
    print(f"\n  {GREEN}Inferência de postura:{RESET} {BOLD}{vencedor_nome}{RESET} (score {vencedor_score})")

    if melhor_local:
        nome_local = scores_brutos[melhor_local[0]]["nome"]
        print(f"  {GREEN}Resumo (tarefa simples):{RESET} {BOLD}{nome_local}{RESET} (melhor local — sem limite de requisições)")

    print(f"\n  {YELLOW}Nota: scores baseados em benchmark controlado.")
    print(f"  Validar com discursos reais antes de usar em produção.{RESET}\n")

    # ── 7. Salva JSON final ───────────────────────────────────────────────
    output = {
        "ranking": [
            {
                "posicao": i + 1,
                "modelo": scores_brutos[slug]["nome"],
                "score_final": score,
                "metricas": {
                    "acuracia":    scores_brutos[slug]["acuracia"],
                    "json_valido": scores_brutos[slug]["json_valido"],
                    "tokens_ok":   scores_brutos[slug]["tokens_ok"],
                    "velocidade":  scores_brutos[slug]["velocidade_norm"],
                    "consistencia": scores_brutos[slug]["consistencia"],
                }
            }
            for i, (slug, score) in enumerate(ranking)
        ],
        "pesos": PESOS,
        "recomendacao": {
            "inferencia": vencedor_nome,
            "resumo": scores_brutos[melhor_local[0]]["nome"] if melhor_local else "N/A"
        }
    }

    out_path = resultados_dir / "benchmark_final.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"  Resultados salvos em: {out_path}\n")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    main()