#!/usr/bin/env python3
"""
Diagnóstico cirúrgico — mostra resposta RAW de cada endpoint
para identificar o formato correto da API.

Como rodar:
    python diagnostico_api.py
"""

import requests

SESSION = requests.Session()
SESSION.headers.update({"Accept": "application/json"})


def testar(nome, url, params=None):
    print(f"\n{'─'*60}")
    print(f"TESTE: {nome}")
    print(f"URL:   {url}")
    if params:
        print(f"PARAMS: {params}")
    try:
        r = SESSION.get(url, params=params, timeout=20)
        print(f"STATUS: {r.status_code}")
        print("RESPOSTA (primeiros 800 chars):")
        print(r.text[:800])
    except Exception as e:
        print(f"ERRO: {e}")


# ── CÂMARA ────────────────────────────────────────────────────

# Teste 1: votações sem filtro de data (pega as mais recentes)
testar(
    "Câmara — Votações sem filtro de data",
    "https://dadosabertos.camara.leg.br/api/v2/votacoes",
    {"itens": 3, "ordem": "DESC", "ordenarPor": "dataHoraInicio"},
)

# Teste 2: votações com período curto (1 semana)
testar(
    "Câmara — Votações maio 2025",
    "https://dadosabertos.camara.leg.br/api/v2/votacoes",
    {"dataInicio": "2025-05-01", "dataFim": "2025-05-15", "itens": 3},
)

# Teste 3: votos de um deputado (ID real: Lula era deputado, vamos usar um ID conhecido)
testar(
    "Câmara — Votos de deputado (id=204554)",
    "https://dadosabertos.camara.leg.br/api/v2/deputados/204554/votos",
    {"dataInicio": "2023-02-01", "dataFim": "2023-03-01", "itens": 3},
)

# Teste 4: proposições recentes
testar(
    "Câmara — Proposições recentes (PL)",
    "https://dadosabertos.camara.leg.br/api/v2/proposicoes",
    {
        "siglaTipo": "PL",
        "dataInicio": "2025-01-01",
        "dataFim": "2025-02-01",
        "itens": 3,
    },
)

# ── SENADO ────────────────────────────────────────────────────

# Teste 5: endpoint antigo
testar(
    "Senado — endpoint antigo (legis.senado.leg.br)",
    "https://legis.senado.leg.br/dadosabertos/plenario/votacao/nominal",
    {"dataInicio": "20250101", "dataFim": "20250131"},
)

# Teste 6: endpoint novo (www12)
testar(
    "Senado — endpoint novo (www12)",
    "https://www12.senado.leg.br/dados-abertos/api/plenario/votacoes-nominais",
    {"dataInicio": "20250101", "dataFim": "20250131"},
)

# Teste 7: senadores (confirma que funciona)
testar(
    "Senado — lista de senadores",
    "https://legis.senado.leg.br/dadosabertos/senador/lista/atual",
    {},
)

# Teste 8: votações por matéria (formato alternativo)
testar(
    "Senado — votações por matéria (PL 3/2023)",
    "https://legis.senado.leg.br/dadosabertos/materia/votacoes/3/2023/PL",
    {},
)

print(f"\n{'─'*60}")
print("Diagnóstico concluído.")
