#!/usr/bin/env python3
"""
Script de Auditoria - v6 (filtros reais)
=========================================
Aplica filtros do escopo do projeto diretamente nos dados bulk:
- Só plenário (remove comissões)
- Só primeira votação por proposição (remove 2º turno)
- Taxa de presença real calculada dos dados
- Filtro RN04: só votos Sim/Não

Como rodar:
    python auditar_estimativas.py
"""

import requests
import json
import time
from datetime import datetime
from pathlib import Path
from collections import defaultdict

GREEN  = '\033[92m'
YELLOW = '\033[93m'
RED    = '\033[91m'
BLUE   = '\033[94m'
BOLD   = '\033[1m'
RESET  = '\033[0m'

def p(msg, cor=YELLOW): print(f"{cor}{msg}{RESET}")
def header(t): print(f"\n{BOLD}{BLUE}{'='*60}\n  {t}\n{'='*60}{RESET}\n")

SESSION = requests.Session()
SESSION.headers.update({"Accept": "application/json"})

ANOS = [2023, 2024, 2025, 2026]

# ─────────────────────────────────────────────
# CÂMARA — PARLAMENTARES
# ─────────────────────────────────────────────

def get_deputados():
    p("Buscando deputados...", YELLOW)
    try:
        r = SESSION.get(
            "https://dadosabertos.camara.leg.br/api/v2/deputados",
            params={"idLegislatura": 57, "itens": 600}, timeout=30
        )
        dados = r.json().get("dados", [])
        p(f"  ✓ {len(dados)} deputados", GREEN)
        return dados
    except Exception as e:
        p(f"  ✗ {e}", RED)
        return []

# ─────────────────────────────────────────────
# CÂMARA — BULK COMPLETO
# ─────────────────────────────────────────────

def get_bulk_camara(anos=ANOS):
    """
    Baixa arquivos bulk de votações e votos.
    Retorna:
      - votacoes_raw: lista de todas as votações
      - votos_raw:    lista de todos os votos individuais
    """
    p("Baixando bulk de votações da Câmara...", YELLOW)
    votacoes_raw = []
    votos_raw    = []

    for ano in anos:
        # Votações (metadados)
        url = f"https://dadosabertos.camara.leg.br/arquivos/votacoes/json/votacoes-{ano}.json"
        try:
            r = SESSION.get(url, timeout=60)
            if r.status_code == 200:
                lote = r.json().get("dados", [])
                votacoes_raw.extend(lote)
                p(f"  → votacoes-{ano}: {len(lote)} votações", GREEN)
            else:
                p(f"  ⚠ votacoes-{ano}: HTTP {r.status_code}", YELLOW)
        except Exception as e:
            p(f"  ✗ votacoes-{ano}: {e}", RED)

        # Votos individuais
        url = f"https://dadosabertos.camara.leg.br/arquivos/votacoesVotos/json/votacoesVotos-{ano}.json"
        try:
            r = SESSION.get(url, timeout=120)
            if r.status_code == 200:
                lote = r.json().get("dados", [])
                votos_raw.extend(lote)
                p(f"  → votacoesVotos-{ano}: {len(lote)} votos", GREEN)
            else:
                p(f"  ⚠ votacoesVotos-{ano}: HTTP {r.status_code}", YELLOW)
        except Exception as e:
            p(f"  ✗ votacoesVotos-{ano}: {e}", RED)

        time.sleep(1)

    p(f"\n  Total bruto: {len(votacoes_raw)} votações, {len(votos_raw)} votos", GREEN)
    return votacoes_raw, votos_raw

# ─────────────────────────────────────────────
# FILTROS
# ─────────────────────────────────────────────

def filtrar_plenario(votacoes):
    """
    Remove votações em comissões.
    Plenário = siglaOrgao em ['PLEN', 'CN'] ou ausente/vazio.
    """
    resultado = []
    for v in votacoes:
        orgao = (v.get("siglaOrgao") or "").upper()
        # Plenário da Câmara = 'PLEN', Congresso Nacional = 'CN'
        if orgao in ["PLEN", "CN", ""]:
            resultado.append(v)
    return resultado

def filtrar_pl_pec(votacoes):
    """Filtra só PL, PEC, PLP."""
    resultado = []
    for v in votacoes:
        prop = (v.get("proposicaoObjeto") or "").upper()
        desc = (v.get("descricao") or "").upper()
        if (prop.startswith(("PL ", "PEC ", "PLP ")) or
                "PROJETO DE LEI" in desc or
                "PROPOSTA DE EMENDA" in desc):
            resultado.append(v)
    return resultado

def filtrar_primeira_votacao(votacoes):
    """
    Para cada proposição, mantém só a PRIMEIRA votação cronologicamente.
    Resolve: PEC com 2 turnos, votações repetidas por destaque, etc.
    """
    # Agrupa por proposição
    por_proposicao = defaultdict(list)
    for v in votacoes:
        prop = (v.get("proposicaoObjeto") or "sem_proposicao").upper().strip()
        por_proposicao[prop].append(v)

    # Pega a mais antiga de cada grupo
    resultado = []
    for prop, lista in por_proposicao.items():
        if prop == "SEM_PROPOSICAO":
            continue
        # Ordena por data e pega a primeira
        try:
            lista_ord = sorted(lista, key=lambda x: x.get("data") or x.get("dataHoraInicio") or "")
            resultado.append(lista_ord[0])
        except Exception:
            resultado.append(lista[0])

    return resultado

def calcular_taxa_presenca_real(votos_raw, votacoes_escopo):
    """
    Calcula taxa de presença real:
    - Para cada deputado, conta quantas votações do escopo ele votou
    - Divide pelo total de votações do escopo
    """
    ids_votacoes_escopo = {v.get("id") for v in votacoes_escopo}
    n_votacoes_escopo   = len(ids_votacoes_escopo)

    if n_votacoes_escopo == 0:
        return 0.75, {}

    # Conta votos por deputado DENTRO do escopo
    votos_por_dep = defaultdict(int)
    votos_sim_nao_por_dep = defaultdict(int)

    for voto in votos_raw:
        id_vot = voto.get("idVotacao")
        if id_vot not in ids_votacoes_escopo:
            continue

        id_dep = str(voto.get("idDeputado", ""))
        if not id_dep:
            continue

        votos_por_dep[id_dep] += 1

        # RN04: só conta Sim/Não
        tipo_voto = (voto.get("voto") or "").upper().strip()
        if tipo_voto in ["SIM", "NÃO", "NAO", "NÃO", "SIM"]:
            votos_sim_nao_por_dep[id_dep] += 1

    if not votos_por_dep:
        return 0.75, {}

    # Taxa de presença = média de (votos do dep / total votações escopo)
    taxas = [min(n / n_votacoes_escopo, 1.0) for n in votos_por_dep.values()]
    taxa_media = sum(taxas) / len(taxas)

    # Taxa RN04 = proporção de votos que são Sim/Não
    total_votos  = sum(votos_por_dep.values())
    total_simnao = sum(votos_sim_nao_por_dep.values())
    taxa_rn04 = total_simnao / total_votos if total_votos > 0 else 0.75

    stats = {
        "deputados_votaram":    len(votos_por_dep),
        "media_votos_por_dep":  round(sum(votos_por_dep.values()) / len(votos_por_dep), 1),
        "min_votos":            min(votos_por_dep.values()),
        "max_votos":            max(votos_por_dep.values()),
        "taxa_presenca_media":  round(taxa_media, 3),
        "taxa_rn04_real":       round(taxa_rn04, 3),
    }

    return taxa_media, stats

# ─────────────────────────────────────────────
# SENADO
# ─────────────────────────────────────────────

def get_senadores():
    p("Buscando senadores...", YELLOW)
    try:
        r = SESSION.get(
            "https://legis.senado.leg.br/dadosabertos/senador/lista/atual",
            timeout=30
        )
        parl = (r.json()
                 .get("ListaParlamentarEmExercicio", {})
                 .get("Parlamentares", {})
                 .get("Parlamentar", []))
        p(f"  ✓ {len(parl)} senadores", GREEN)
        return parl
    except Exception as e:
        p(f"  ✗ {e}", RED)
        return []

def get_votacoes_senado_bulk():
    """Tenta arquivo bulk XML/JSON do Senado por ano."""
    p("Buscando votações do Senado...", YELLOW)
    todas = []

    for ano in ANOS:
        urls = [
            f"https://legis.senado.leg.br/dadosabertos/dados/ListaVotacoes{ano}.json",
            f"https://legis.senado.leg.br/dadosabertos/plenario/lista/votacao/{ano}",
        ]
        for url in urls:
            try:
                r = SESSION.get(url, timeout=30)
                if r.status_code == 200:
                    data = r.json()
                    lote = (data.get("ListaVotacoes", {})
                                .get("Votacoes", {})
                                .get("Votacao", []))
                    if isinstance(lote, dict):
                        lote = [lote]
                    if lote:
                        todas.extend(lote)
                        p(f"  → {ano}: {len(lote)} votações ({url.split('/')[-1]})", GREEN)
                        break
            except Exception:
                pass
        else:
            p(f"  ⚠ {ano}: nenhum endpoint respondeu", YELLOW)

        time.sleep(0.5)

    p(f"  ✓ {len(todas)} votações totais no Senado", GREEN)
    return todas

def filtrar_pl_pec_senado(votacoes):
    return [v for v in votacoes
            if any(t in (v.get("SiglaMateria") or
                         v.get("IdentificacaoMateria", {}).get("SiglaSubtipoMateria") or
                         v.get("Materia", {}).get("Sigla") or "").upper()
                   for t in ["PL", "PEC", "PLP"])]

def filtrar_primeira_votacao_senado(votacoes):
    """Mesma lógica: uma votação por proposição."""
    por_proposicao = defaultdict(list)
    for v in votacoes:
        sigla  = (v.get("SiglaMateria") or "?").upper()
        numero = (v.get("NumeroMateria") or v.get("Numero") or "?")
        ano    = (v.get("AnoMateria") or v.get("Ano") or "?")
        chave  = f"{sigla}-{numero}-{ano}"
        por_proposicao[chave].append(v)

    resultado = []
    for chave, lista in por_proposicao.items():
        try:
            lista_ord = sorted(lista, key=lambda x: x.get("DataSessao") or x.get("Data") or "")
            resultado.append(lista_ord[0])
        except Exception:
            resultado.append(lista[0])
    return resultado

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    header("AUDITORIA DE ESTIMATIVAS v6 — FILTROS REAIS")
    resultado = {}

    # ── 1. Parlamentares ──────────────────────────────────────────
    header("1. PARLAMENTARES")
    deputados  = get_deputados()
    senadores  = get_senadores()
    total_parl = len(deputados) + len(senadores)

    p(f"  Deputados:           {len(deputados)}", GREEN)
    p(f"  Senadores:           {len(senadores)}", GREEN)
    p(f"  Total real:          {total_parl}", BOLD)
    p(f"  Estimativa original: 594  |  Diferença: {total_parl-594:+d}", YELLOW)

    resultado["parlamentares"] = {
        "deputados": len(deputados), "senadores": len(senadores),
        "total": total_parl, "estimativa_original": 594
    }

    # ── 2. Votações com filtros reais ─────────────────────────────
    header("2. VOTAÇÕES — FILTROS APLICADOS")

    # Câmara
    votacoes_raw, votos_raw = get_bulk_camara()

    p("\n  Aplicando filtros na Câmara:", YELLOW)
    v1 = votacoes_raw
    p(f"    Bruto:                   {len(v1):>6}", YELLOW)

    v2 = filtrar_plenario(v1)
    p(f"    Após filtro plenário:    {len(v2):>6}  (-{len(v1)-len(v2)} de comissões)", GREEN)

    v3 = filtrar_pl_pec(v2)
    p(f"    Após filtro PL/PEC:      {len(v3):>6}  (-{len(v2)-len(v3)} outros tipos)", GREEN)

    v4 = filtrar_primeira_votacao(v3)
    p(f"    Após 1ª votação apenas:  {len(v4):>6}  (-{len(v3)-len(v4)} turnos/repetições)", GREEN)

    # Senado
    print()
    vs_raw  = get_votacoes_senado_bulk()
    vs_fil  = filtrar_pl_pec_senado(vs_raw)
    vs_unic = filtrar_primeira_votacao_senado(vs_fil)

    p(f"\n  Senado bruto:            {len(vs_raw):>6}", YELLOW)
    p(f"  Senado PL/PEC:           {len(vs_fil):>6}", GREEN)
    p(f"  Senado 1ª votação:       {len(vs_unic):>6}", GREEN)

    total_v = len(v4) + len(vs_unic)
    p(f"\n  {'─'*40}", BOLD)
    p(f"  TOTAL VOTAÇÕES NO ESCOPO:{total_v:>6}", BOLD)
    p(f"  Estimativa original: 250  |  Diferença: {total_v-250:+d}", YELLOW)

    resultado["votacoes"] = {
        "camara_bruto":          len(v1),
        "camara_apos_plenario":  len(v2),
        "camara_apos_pl_pec":    len(v3),
        "camara_primeira_vot":   len(v4),
        "senado_bruto":          len(vs_raw),
        "senado_pl_pec":         len(vs_fil),
        "senado_primeira_vot":   len(vs_unic),
        "total_escopo":          total_v,
        "estimativa_original":   250
    }

    # ── 3. Participação real ──────────────────────────────────────
    header("3. PARTICIPAÇÃO REAL")

    votacoes_escopo = v4  # usa só Câmara para o cálculo (temos os votos individuais)
    taxa, stats = calcular_taxa_presenca_real(votos_raw, votacoes_escopo)

    if stats:
        p(f"  Deputados que votaram:       {stats['deputados_votaram']}", GREEN)
        p(f"  Média de votos por deputado: {stats['media_votos_por_dep']:.0f}", GREEN)
        p(f"  Mínimo / Máximo:             {stats['min_votos']} / {stats['max_votos']}", YELLOW)
        p(f"  Taxa presença real:          {taxa*100:.1f}%", GREEN)
        p(f"  Taxa RN04 real (Sim/Não):    {stats['taxa_rn04_real']*100:.1f}%", GREEN)
        taxa_rn04 = stats["taxa_rn04_real"]
    else:
        p("  Usando fallback 75%", YELLOW)
        taxa_rn04 = 0.75

    resultado["participacao"] = stats or {"taxa_presenca": taxa, "fonte": "fallback"}

    # ── 4. Estimativa revisada com dados reais ────────────────────
    header("4. ESTIMATIVA REVISADA — DADOS REAIS")

    pb = total_parl * total_v
    p1 = int(pb  * taxa)           # presença real
    p2 = int(p1  * taxa_rn04)      # RN04 real (Sim/Não)
    p3 = int(p2  * 0.90)           # RN01 temporal (estimado — depende de dados de discursos)
    p4 = int(p3  * 0.60)           # RN02 threshold semântico (estimado)
    p5 = int(p4  * 0.70)           # <5 discursos (estimado)

    p(f"  Parlamentares × Votações:        {pb:>10,}", YELLOW)
    p(f"  Após presença real ({taxa*100:.0f}%):      {p1:>10,}", GREEN)
    p(f"  Após RN04 real ({taxa_rn04*100:.0f}% Sim/Não):   {p2:>10,}", GREEN)
    p(f"  Após RN01 temporal (90%)*:       {p3:>10,}", YELLOW)
    p(f"  Após RN02 threshold (60%)*:      {p4:>10,}", YELLOW)
    p(f"  Após <5 discursos (70%)*:        {p5:>10,}", YELLOW)
    p(f"\n  * estimados — dependem de dados de discursos", YELLOW)
    p(f"\n  {'─'*48}", BOLD)
    p(f"  ESTIMATIVA ORIGINAL:             {42500:>10,}", YELLOW)
    p(f"  ESTIMATIVA REVISADA:             {p5:>10,}", GREEN)
    diff = p5 - 42500
    p(f"  DIFERENÇA:                       {diff:>+10,}",
      GREEN if abs(diff) < 50000 else RED)

    resultado["estimativa_revisada"] = {
        "pares_brutos": pb, "apos_presenca": p1,
        "apos_rn04": p2, "apos_rn01": p3, "apos_rn02": p4,
        "estimativa_final": p5, "estimativa_original": 42500,
        "diferenca": diff,
        "nota": "RN01/RN02/<5 discursos são estimados — RN04 e presença são dados reais"
    }

    resultado["gerado_em"] = datetime.now().isoformat()
    out = Path("auditoria_resultado.json")
    out.write_text(json.dumps(resultado, ensure_ascii=False, indent=2))
    p(f"\n  Salvo em: {out}", BLUE)
    header("CONCLUÍDO")

if __name__ == "__main__":
    main()