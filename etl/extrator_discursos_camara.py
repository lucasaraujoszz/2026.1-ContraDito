import httpx
import time
import logging
from typing import List, Dict, Any, Optional, Tuple

from etl.transformadores_discursos_camara import transformar_discurso


def extrair_pagina_discursos(url: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Acessa a API da Câmara dos Deputados para extrair uma página de discursos.
    Retorna os dados brutos encontrados e a URL da próxima página (se existir).
    """
    backoffs = [2, 4]
    max_tentativas = len(backoffs) + 1

    for tentativa in range(max_tentativas):
        try:
            # Timeout de 30s para evitar travamentos em caso de lentidão na rede governamental
            response = httpx.get(url, timeout=30.0)
            response.raise_for_status()

            payload = response.json()
            dados = payload.get("dados", [])

            next_url = None
            for link in payload.get("links", []):
                if link.get("rel") == "next":
                    next_url = link.get("href")
                    break

            return dados, next_url

        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            status = (
                getattr(e.response, "status_code", None)
                if hasattr(e, "response")
                else "Rede/Timeout"
            )

            # Só insistimos se for erro de Servidor (5xx), Rate Limit (429) ou falha bruta de rede
            if isinstance(status, str) or status >= 500 or status == 429:
                if tentativa < len(backoffs):
                    espera = backoffs[tentativa]
                    logging.warning(
                        f"Erro {status} na API da Câmara. Retentando em {espera}s... URL: {url}"
                    )
                    time.sleep(espera)
                    continue

            logging.error(
                f"Falha irrecuperável ou limite de tentativas esgotado ({status}). URL: {url}"
            )
            return [], None


def executar_extracao_deputado(
    id_deputado: int, data_inicio: str, data_fim: str, supabase: Any
) -> int:
    """
    Orquestra a extração de todas as páginas de discursos de um único deputado,
    aplica o pipeline de transformação e salva no Supabase em lote (Bulk Upsert).
    Retorna a quantidade de discursos extraídos e salvos.
    """
    url = f"https://dadosabertos.camara.leg.br/api/v2/deputados/{id_deputado}/discursos?dataInicio={data_inicio}&dataFim={data_fim}&itens=100"

    lote_discursos = []

    while url:
        # Freio de mão para não estourar o Rate Limit da Câmara (max ~1 req/seg)
        time.sleep(0.5)
        dados_brutos, proxima_url = extrair_pagina_discursos(url)

        for discurso_bruto in dados_brutos:
            discurso_limpo = transformar_discurso(discurso_bruto, id_deputado)
            lote_discursos.append(discurso_limpo)

        url = proxima_url

    if lote_discursos:
        # Deduplicação: Mantém apenas um discurso por ID (evita erro 21000 ON CONFLICT do PostgreSQL)
        lote_deduplicado = list({d["id"]: d for d in lote_discursos}.values())
        supabase.table("camara_discursos").upsert(lote_deduplicado).execute()
        return len(lote_deduplicado)

    return 0


def executar_pipeline_completo(supabase: Any, data_inicio: str, data_fim: str) -> None:
    """
    Executa o pipeline completo de extração de discursos.
    1. Busca os deputados na base local (Supabase).
    2. Extrai os discursos de cada um na janela de tempo especificada (Backfill ou Incremental).
    3. Grava o log final de execução (Watermarker).
    """
    resposta = supabase.table("camara_politicos").select("id").execute()
    deputados = resposta.data or []

    total_linhas = 0
    for deputado in deputados:
        linhas = executar_extracao_deputado(
            deputado["id"], data_inicio, data_fim, supabase
        )
        total_linhas += linhas

    supabase.table("etl_logs").insert(
        {
            "nome_rotina": "extrator_discursos_camara",
            "status": "Concluído",
            "data_inicio": data_inicio,
            "data_fim": data_fim,
            "linhas_afetadas": total_linhas,
        }
    ).execute()
