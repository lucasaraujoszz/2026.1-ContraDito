#!/usr/bin/env python3
"""
Inspeciona o formato real dos arquivos bulk da Câmara.
Mostra os primeiros 3 registros de votações e votos
para identificar os campos corretos.

Como rodar:
    python inspecionar_bulk.py
"""

import requests
import json

SESSION = requests.Session()
SESSION.headers.update({"Accept": "application/json"})

def inspecionar(label, url):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"  {url}")
    print(f"{'='*60}")
    try:
        r = SESSION.get(url, timeout=60)
        if r.status_code != 200:
            print(f"  HTTP {r.status_code}")
            return

        data = r.json()

        # Mostra chaves do topo
        print(f"\n  Chaves raiz: {list(data.keys())}")

        # Pega os dados
        dados = data.get("dados", [])
        print(f"  Total de registros: {len(dados)}")

        if not dados:
            print("  (vazio)")
            return

        # Mostra primeiros 3 registros completos
        print(f"\n  Primeiros 3 registros:")
        for i, item in enumerate(dados[:3]):
            print(f"\n  [{i+1}] {json.dumps(item, ensure_ascii=False, indent=4)}")

    except Exception as e:
        print(f"  ERRO: {e}")

def main():
    # Votações de 2025 (mais recente, menor arquivo)
    inspecionar(
        "CÂMARA — Votações 2025 (metadados)",
        "https://dadosabertos.camara.leg.br/arquivos/votacoes/json/votacoes-2025.json"
    )

    inspecionar(
        "CÂMARA — Votos 2025 (por parlamentar)",
        "https://dadosabertos.camara.leg.br/arquivos/votacoesVotos/json/votacoesVotos-2025.json"
    )

if __name__ == "__main__":
    main()