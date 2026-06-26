import httpx
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, Tuple, List, Dict, Any
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    wait_random,
    retry_if_exception,
)

from etl.transformadores_votos_senado import (
    encontrar_sessao_merito_senado,
    filtrar_votos_validos_senado,
    transformar_voto_senado,
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
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=30) + wait_random(0, 2),
    retry=retry_if_exception(_is_transient_error),
    reraise=True,
)
async def obter_sessao_votacao_senado(
    client: httpx.AsyncClient, id_senado: int
) -> Optional[Tuple[int, str]]:
    """
    Bate na API do Senado buscando as votações da matéria.
    Usa a regra de negócio para encontrar a sessão de mérito e retorna (codigo, data).
    """
    url = f"https://legis.senado.leg.br/dadosabertos/votacao?codigoMateria={id_senado}&v=1"

    response = await client.get(
        url, headers={"Accept": "application/json"}, timeout=30.0
    )
    response.raise_for_status()

    votacoes = response.json()
    if not isinstance(votacoes, list):
        votacoes = []

    sessao_valida = encontrar_sessao_merito_senado(votacoes)
    if sessao_valida:
        codigo_sessao = sessao_valida.get("codigoSessao")
        data_sessao = sessao_valida.get("dataSessao")
        return int(codigo_sessao) if codigo_sessao else None, data_sessao

    return None


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=30) + wait_random(0, 2),
    retry=retry_if_exception(_is_transient_error),
    reraise=True,
)
async def extrair_votos_proposicao_senado(
    client: httpx.AsyncClient,
    proposicao_id: str,
    id_senado: int,
    ids_validos_banco: set,
) -> Tuple[List[Dict[str, Any]], Optional[int], Optional[str]]:
    """
    Bate na API do Senado, encontra a sessão de mérito,
    extrai a lista de votos nominais, aplica o Soft Drop para deputados órfãos
    e converte para o Data Contract.
    """
    url = f"https://legis.senado.leg.br/dadosabertos/votacao?codigoMateria={id_senado}&v=1"

    response = await client.get(
        url, headers={"Accept": "application/json"}, timeout=30.0
    )
    response.raise_for_status()

    votacoes = response.json()
    if not isinstance(votacoes, list):
        votacoes = []

    sessao_valida = encontrar_sessao_merito_senado(votacoes)
    if not sessao_valida:
        return [], None, None

    codigo_sessao = sessao_valida.get("codigoSessao")
    data_sessao = sessao_valida.get("dataSessao")

    votos_brutos = sessao_valida.get("votos", [])

    votos_validos = filtrar_votos_validos_senado(votos_brutos, ids_validos_banco)
    votos_transformados = [
        transformar_voto_senado(voto, proposicao_id) for voto in votos_validos
    ]

    return (
        votos_transformados,
        int(codigo_sessao) if codigo_sessao else None,
        data_sessao,
    )


async def executar_pipeline_votos_senado(
    supabase_client: Any, limite_amostral: Optional[int] = None
) -> None:
    """
    Rotina principal (Pipeline). Busca proposições e políticos locais, orquestra
    a extração na API do Senado concorrentemente, faz o Upsert dos votos no banco de dados
    e, de forma consistente, atualiza o ID de votação nas proposições.
    """
    exec_inicio = datetime.now(timezone.utc).isoformat()
    total_linhas = 0
    status = "Concluído"
    detalhe_erro = None

    try:
        # 1. Puxa IDs válidos de senadores para o Soft Drop
        resp_politicos = (
            supabase_client.table("senado_politicos").select("id").execute()
        )
        ids_validos_banco = (
            {p["id"] for p in resp_politicos.data} if resp_politicos.data else set()
        )

        # 2. Puxa as proposições que ainda não foram processadas
        query_proposicoes = (
            supabase_client.table("senado_proposicoes")
            .select("proposicao_id, id_senado")
            .is_("id_votacao_senado", "null")
        )
        if limite_amostral:
            query_proposicoes = query_proposicoes.limit(limite_amostral)
        resp_proposicoes = query_proposicoes.execute()
        proposicoes = resp_proposicoes.data or []

        async with httpx.AsyncClient() as client:
            # 3. Concorrência controlada para evitar bloqueio do WAF do Senado
            semaphore = asyncio.Semaphore(5)

            async def processar_proposicao_worker(prop: dict):
                async with semaphore:
                    await asyncio.sleep(0.5)
                    proposicao_id = prop["proposicao_id"]
                    id_senado = prop["id_senado"]

                    try:
                        votos, id_votacao, data_votacao = (
                            await extrair_votos_proposicao_senado(
                                client, proposicao_id, id_senado, ids_validos_banco
                            )
                        )
                        return proposicao_id, votos, id_votacao, data_votacao
                    except Exception as e:
                        logger.error(
                            f"Erro não tratado no worker da proposição {proposicao_id}: {e}"
                        )
                        return proposicao_id, [], None, None

            tarefas = [processar_proposicao_worker(p) for p in proposicoes]
            resultados = await asyncio.gather(*tarefas, return_exceptions=True)

            for res in resultados:
                if isinstance(res, Exception):
                    logger.error(f"Erro crítico no processamento de uma task: {res}")
                    continue

                proposicao_id, votos, id_votacao, data_votacao = res

                # 4. Consistência Eventual: Salvar o filho ANTES do pai.
                if votos:
                    votos_deduplicados = list({v["id"]: v for v in votos}.values())
                    supabase_client.table("senado_votos").upsert(
                        votos_deduplicados
                    ).execute()
                    total_linhas += len(votos_deduplicados)

                if id_votacao:
                    payload_update = {"id_votacao_senado": id_votacao}
                    if data_votacao:
                        payload_update["data_votacao"] = data_votacao
                    supabase_client.table("senado_proposicoes").update(
                        payload_update
                    ).eq("proposicao_id", proposicao_id).execute()

    except Exception as e:
        status = "Erro"
        detalhe_erro = str(e)
        logger.error(f"Erro crítico no pipeline de extração de votos do Senado: {e}")

    exec_fim = datetime.now(timezone.utc).isoformat()

    # 5. Gravação do Log de Execução (Watermarker)
    try:
        supabase_client.table("etl_logs").insert(
            {
                "nome_rotina": "extrator_votos_senado",
                "data_inicio": exec_inicio,
                "data_fim": exec_fim,
                "status": status,
                "detalhe_erro": detalhe_erro,
                "linhas_afetadas": total_linhas,
            }
        ).execute()
    except Exception as log_e:
        logger.error(f"Falha ao registrar log no etl_logs: {log_e}")
