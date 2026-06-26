import httpx
import logging
import time
from typing import Tuple, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from etl.transformadores_discursos_senado import (
    normalizar_payload_senado,
    mapear_discurso_senado,
)

logger = logging.getLogger(__name__)


def _is_transient_error(exception: BaseException) -> bool:
    """Avalia se a exceção é um Rate Limit, Erro de Servidor ou Falha de Conexão/Timeout."""
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in (429, 500, 502, 503, 504)
    if isinstance(exception, httpx.RequestError):
        return True
    return False


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception(_is_transient_error),
    reraise=True,
)
def _fetch_api_senado_com_retry(url: str, headers: dict = None) -> httpx.Response:
    if headers is None:
        headers = {"Accept": "application/json"}
    response = httpx.get(url, headers=headers, timeout=30.0, follow_redirects=True)
    response.raise_for_status()
    return response


def obter_discursos_senador_api(
    id_senador_banco: int, data_inicio: str, data_fim: str
) -> Tuple[int, Dict[str, Any]]:
    """
    Busca os discursos de um senador na API do Senado em uma janela de tempo.
    Injeta o header para forçar o retorno em JSON.
    """
    url = f"https://legis.senado.leg.br/dadosabertos/senador/{id_senador_banco}/discursos?dataInicio={data_inicio}&dataFim={data_fim}"

    try:
        response = _fetch_api_senado_com_retry(url)
        return response.status_code, response.json()
    except httpx.HTTPStatusError as e:
        return e.response.status_code, {}
    except Exception as e:
        logger.error(f"Falha de rede irrecuperável ao acessar API do Senado: {e}")
        return 0, {}


def obter_html_discurso_senado(url_texto: str) -> str:
    """
    Faz o Scraping N+1 da URL do texto do discurso, retornando o HTML bruto.
    Aplica retentativas (Rate Limit/WAF) via Tenacity.
    """
    if not url_texto:
        return ""

    try:
        response = _fetch_api_senado_com_retry(
            url_texto, headers={"User-Agent": "Mozilla/5.0"}
        )
        return response.text
    except Exception as e:
        logger.error(
            f"Falha irrecuperável ao raspar HTML do discurso ({url_texto}): {e}"
        )
        return "[ERRO DE REDE]"


def executar_extracao_senador(
    id_senador_banco: int, data_inicio: str, data_fim: str, supabase_client: Any
) -> int:
    """
    Orquestra a extração de discursos de um senador: busca a lista na API, raspa o HTML,
    aplica o mapeamento do Data Contract e faz o Upsert em lote no Supabase.
    """
    status_code, payload = obter_discursos_senador_api(
        id_senador_banco, data_inicio, data_fim
    )

    discursos_raw = normalizar_payload_senado(status_code, payload)

    if not discursos_raw:
        return 0

    lote_discursos = []
    for discurso_raw in discursos_raw:
        # Proteção: A API do Senado costuma ignorar filtros de data nesse endpoint e trazer a história toda
        data_discurso = discurso_raw.get("DataPronunciamento", "")
        if data_discurso:
            data_str = data_discurso.split("T")[0].split(" ")[0]
            if not (data_inicio <= data_str <= data_fim):
                continue

        time.sleep(0.5)  # Proteção N+1 (Freio de mão pro WAF)

        url_texto = discurso_raw.get("UrlTexto", "")
        html_bruto = obter_html_discurso_senado(url_texto)

        discurso_mapeado = mapear_discurso_senado(
            id_senador_banco, discurso_raw, html_bruto
        )
        lote_discursos.append(discurso_mapeado)

    if lote_discursos:
        lote_deduplicado = list({d["id"]: d for d in lote_discursos}.values())
        supabase_client.table("senado_discursos").upsert(lote_deduplicado).execute()
        return len(lote_deduplicado)

    return 0


def executar_pipeline_completo(
    supabase_client: Any, data_inicio: str, data_fim: str
) -> None:
    """
    Executa o pipeline completo de extração de discursos do Senado.
    1. Busca os senadores na base local (Supabase).
    2. Extrai os discursos de cada um na janela de tempo especificada.
    3. Grava o log final de execução (Watermarker).
    """
    total_linhas = 0
    try:
        resposta = supabase_client.table("senado_politicos").select("id").execute()
        senadores = resposta.data or []

        for senador in senadores:
            linhas = executar_extracao_senador(
                senador["id"], data_inicio, data_fim, supabase_client
            )
            total_linhas += linhas

        status = "Concluído"
        detalhe_erro = None
    except Exception as e:
        status = "Erro"
        detalhe_erro = str(e)
        logger.error(f"Erro crítico no pipeline do Senado: {e}")

    try:
        supabase_client.table("etl_logs").insert(
            {
                "nome_rotina": "extrator_discursos_senado",
                "data_inicio": data_inicio,
                "data_fim": data_fim,
                "status": status,
                "detalhe_erro": detalhe_erro,
                "linhas_afetadas": total_linhas,
            }
        ).execute()
    except Exception as e:
        logger.error(f"Falha irrecuperável ao salvar log no etl_logs: {e}")


if __name__ == "__main__":
    import os
    import sys
    from supabase import create_client, Client

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")

    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error(
            "As variáveis de ambiente SUPABASE_URL e SUPABASE_KEY precisam estar definidas."
        )
        sys.exit(1)

    cliente_banco: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    data_inicio_arg = sys.argv[1] if len(sys.argv) > 1 else "2023-01-01"
    data_fim_arg = sys.argv[2] if len(sys.argv) > 2 else "2023-12-31"

    logger.info(
        f"Iniciando pipeline de extração do Senado ({data_inicio_arg} a {data_fim_arg})..."
    )
    executar_pipeline_completo(cliente_banco, data_inicio_arg, data_fim_arg)
    logger.info("Pipeline do Senado finalizado com sucesso!")
