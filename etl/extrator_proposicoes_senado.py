import uuid
import httpx
import asyncio
import logging
from datetime import datetime, timezone
from typing import Tuple, List, Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

logger = logging.getLogger(__name__)


def gerar_hash_id_proposicao(sigla: str, numero: int, ano: int) -> Tuple[str, str]:
    """
    Gera a chave de negócio e o UUIDv5 determinístico para uma proposição do Senado.
    """
    proposicao_id = (
        f"{str(sigla).lower().strip()}_{str(numero).strip()}_{str(ano).strip()}"
    )
    proposicao_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, proposicao_id))
    return proposicao_id, proposicao_uuid


def obter_data_primeira_votacao_valida(
    autuacoes: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Varre as autuações e situações de uma proposição do Senado, filtra pela whitelist
    de votações de mérito e retorna a data do primeiro evento cronológico.
    """
    whitelist = {25, 49, 89, 96, 97, 113, 146}
    datas_validas = []

    for autuacao in autuacoes:
        situacoes = autuacao.get("situacoes", [])
        for situacao in situacoes:
            id_tipo = situacao.get("idTipo")
            inicio = situacao.get("inicio")
            if id_tipo in whitelist and inicio:
                datas_validas.append(inicio)

    if not datas_validas:
        return None

    datas_validas.sort()
    return datas_validas[0]


def validar_corte_temporal(data_votacao: Optional[str]) -> bool:
    """
    Valida se a data da primeira votação de mérito atende ao corte da
    Legislatura 57 (>= 01/01/2023). Retorna False para datas antigas ou nulas.
    """
    if not data_votacao:
        return False
    return data_votacao[:10] >= "2023-01-01"


def transformar_proposicao_senado(
    payload: Dict[str, Any], url_documento: str, ementa: str
) -> Optional[Dict[str, Any]]:
    """
    Mapeia a proposição bruta do Senado e a URL do documento para o
    Data Contract, aplicando os filtros cronológicos e temporais.
    Retorna None se a proposição for descartada.
    """
    autuacoes = payload.get("autuacoes", [])
    data_votacao = obter_data_primeira_votacao_valida(autuacoes)

    if not validar_corte_temporal(data_votacao):
        return None

    sigla = payload.get("sigla", "")

    TIPOS_VALIDOS = {"PEC", "PL", "PLS", "PLP", "PLC"}
    if sigla not in TIPOS_VALIDOS:
        return None

    numero = int(payload.get("numero", 0))
    ano = int(payload.get("ano", 0))

    proposicao_id, proposicao_uuid = gerar_hash_id_proposicao(sigla, numero, ano)

    return {
        "id": proposicao_uuid,
        "proposicao_id": proposicao_id,
        "id_senado": int(payload.get("codigoMateria") or payload.get("id") or 0),
        "tipo": sigla,
        "numero": numero,
        "ano": ano,
        "ementa": ementa,
        "data_votacao": data_votacao,
        "url_texto_inteiro": url_documento,
        "resumo_executivo": None,
        "erro_resumo": None,
    }


def salvar_lote_parcial(supabase_client: Any, lote: List[Dict[str, Any]]) -> int:
    """
    Deduplica o lote em memória e realiza o upsert parcial no Supabase.
    Retorna o número de linhas salvas.
    """
    if not lote:
        return 0

    lote_deduplicado = list({item["id"]: item for item in lote}.values())
    supabase_client.table("senado_proposicoes").upsert(lote_deduplicado).execute()

    return len(lote_deduplicado)


def _is_transient_error(exception: BaseException) -> bool:
    """Avalia se a exceção é um Rate Limit, Erro de Servidor ou Falha de Conexão/Timeout."""
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in (429, 500, 502, 503, 504)
    if isinstance(exception, httpx.RequestError):
        return True
    return False


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception(_is_transient_error),
    reraise=True,
)
async def extrair_detalhe_proposicao(
    client: httpx.AsyncClient, id_proposicao: int, semaphore: asyncio.Semaphore
) -> Dict[str, Any]:
    """
    Acessa o detalhamento de uma proposição no Senado aplicando
    Rate Limit (Semaphore) e Retentativas (Tenacity).
    """
    async with semaphore:
        await asyncio.sleep(0.5)
        url = f"https://legis.senado.leg.br/dadosabertos/processo/{id_proposicao}"
        response = await client.get(
            url, headers={"Accept": "application/json"}, timeout=30.0
        )
        response.raise_for_status()
        return response.json()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception(_is_transient_error),
    reraise=True,
)
async def fetch_pagina_arrasto(client: httpx.AsyncClient, url: str) -> Dict[str, Any]:
    response = await client.get(
        url, headers={"Accept": "application/json"}, timeout=30.0
    )
    response.raise_for_status()
    return response.json()


async def processar_pagina_arrasto(
    client: httpx.AsyncClient,
    url: str,
    supabase_client: Any,
    semaphore: asyncio.Semaphore,
) -> Tuple[int, Optional[str]]:
    """
    Processa uma página da rede de arrasto, aciona o detalhamento N+1 e salva o lote.
    """
    payload = await fetch_pagina_arrasto(client, url)

    # Busca a lista de matérias a partir da raiz (camelCase)
    if isinstance(payload, list):
        materias_node = payload
    else:
        materias_node = payload.get("processo", [])

    if isinstance(materias_node, dict):
        materias_node = [materias_node]

    lote_validos = []
    tarefas = []

    for mat in materias_node:
        id_roteamento = mat.get("id")
        if id_roteamento:
            tarefas.append(extrair_detalhe_proposicao(client, id_roteamento, semaphore))

    resultados_detalhe = await asyncio.gather(*tarefas, return_exceptions=True)

    for i, res in enumerate(resultados_detalhe):
        mat_orig = materias_node[i]
        id_roteamento = mat_orig.get("id")

        if isinstance(res, Exception):
            logger.error(f"Erro N+1 (Proposição {id_roteamento}): {res}")
            continue

        if res:
            detalhe_materia = res.get("processo", res)
            if detalhe_materia:
                url_doc = mat_orig.get("urlDocumento", "")
                ementa = mat_orig.get("ementa", "")

                proposicao_transformada = transformar_proposicao_senado(
                    detalhe_materia, url_doc, ementa
                )
                if proposicao_transformada:
                    lote_validos.append(proposicao_transformada)

    linhas_salvas = salvar_lote_parcial(supabase_client, lote_validos)

    return linhas_salvas, None


async def executar_pipeline_completo(
    supabase_client: Any, data_inicio: str, data_fim: str
) -> None:
    """
    Orquestra a extração do Senado, processando os blocos, tratando falhas
    fatais e registrando logs de execução parciais ou totais.
    """
    exec_inicio = datetime.now(timezone.utc).isoformat()
    url_atual = f"https://legis.senado.leg.br/dadosabertos/processo?sigla=PEC&sigla=PL&sigla=PLP&sigla=PLC&sigla=PLS&dataInicioDeliberacao={data_inicio}&v=1"
    total_linhas = 0
    status = "Concluído"
    detalhe_erro = None

    try:
        async with httpx.AsyncClient() as client:
            semaphore = asyncio.Semaphore(5)
            while url_atual:
                linhas_salvas, url_atual = await processar_pagina_arrasto(
                    client, url_atual, supabase_client, semaphore
                )
                total_linhas += linhas_salvas
    except Exception as e:
        status = "Erro"
        detalhe_erro = str(e)

    exec_fim = datetime.now(timezone.utc).isoformat()

    supabase_client.table("etl_logs").insert(
        {
            "nome_rotina": "extrator_proposicoes_senado",
            "data_inicio": exec_inicio,
            "data_fim": exec_fim,
            "status": status,
            "detalhe_erro": detalhe_erro,
            "linhas_afetadas": total_linhas,
        }
    ).execute()
