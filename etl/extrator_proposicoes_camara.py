import httpx
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Tuple, List, Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from etl.transformadores_proposicoes_camara import (
    transformar_proposicao,
    obter_data_votacao_merito,
    validar_corte_temporal,
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
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception(_is_transient_error),
    reraise=True,
)
async def extrair_pagina_proposicoes(
    client: httpx.AsyncClient, url: str
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Acessa a API da Câmara para extrair uma página de proposições.
    Retorna a lista de dados brutos e a URL da próxima página (se houver).
    É decorado com 'tenacity' para resiliência de rede.
    """
    response = await client.get(url, timeout=30.0)
    response.raise_for_status()

    payload = response.json()
    dados = payload.get("dados", [])

    next_url = None
    for link in payload.get("links", []):
        if link.get("rel") == "next":
            next_url = link.get("href")
            break

    return dados, next_url


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception(_is_transient_error),
    reraise=True,
)
async def extrair_tramitacoes_proposicao(
    client: httpx.AsyncClient, id_proposicao: int, semaphore: asyncio.Semaphore
) -> List[Dict[str, Any]]:
    """
    Acessa a API da Câmara para extrair o histórico de tramitações de uma proposição.
    É decorado com 'tenacity' para resiliência de rede.
    """
    async with semaphore:
        # Freio de mão explícito para não tomar 429
        await asyncio.sleep(0.5)
        url = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes/{id_proposicao}/tramitacoes"
        response = await client.get(url, timeout=30.0)
        response.raise_for_status()

        payload = response.json()
        return payload.get("dados", [])


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception(_is_transient_error),
    reraise=True,
)
async def extrair_detalhes_proposicao(
    client: httpx.AsyncClient, id_proposicao: int, semaphore: asyncio.Semaphore
) -> Dict[str, Any]:
    """
    Acessa a API da Câmara para extrair os detalhes ricos de uma proposição (incluindo urlInteiroTeor).
    É decorado com 'tenacity' para resiliência de rede.
    """
    async with semaphore:
        await asyncio.sleep(0.5)
        url = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes/{id_proposicao}"
        response = await client.get(url, timeout=30.0)
        response.raise_for_status()

        payload = response.json()
        return payload.get("dados", {})


async def processar_pagina_proposicoes(
    client: httpx.AsyncClient, url: str, semaphore: asyncio.Semaphore
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Orquestra a extração de uma página de proposições de forma concorrente.
    Busca a página, dispara as requisições N+1 (tramitações) de forma controlada,
    aplica as regras de transformação e retorna apenas as proposições válidas
    (dentro do escopo temporal e com votação de mérito) junto com a URL da próxima página.
    """
    dados_brutos, next_url = await extrair_pagina_proposicoes(client, url)

    tarefas_tramitacao = []
    payloads_ativos = []
    for payload in dados_brutos:
        id_proposicao = payload.get("id")
        if id_proposicao:
            tarefas_tramitacao.append(
                extrair_tramitacoes_proposicao(client, id_proposicao, semaphore)
            )
            payloads_ativos.append(payload)

    # Executa todas as buscas de tramitações concorrentemente
    resultados_tramitacoes = await asyncio.gather(
        *tarefas_tramitacao, return_exceptions=True
    )

    resultados_validos = []
    for i, payload in enumerate(payloads_ativos):
        tramitacoes = resultados_tramitacoes[i]
        if not isinstance(tramitacoes, Exception) and tramitacoes is not None:
            # Pré-filtro: aplica as regras de negócio ANTES de pedir o payload rico para a Câmara (Poupa 429)
            data_votacao = obter_data_votacao_merito(tramitacoes)
            if validar_corte_temporal(data_votacao):
                detalhes = await extrair_detalhes_proposicao(
                    client, payload.get("id"), semaphore
                )
                payload.update(
                    detalhes
                )  # Injeta a urlInteiroTeor e a ementa enriquecida no dict original

                proposicao_transformada = transformar_proposicao(payload, tramitacoes)
                if proposicao_transformada:
                    logger.info(
                        f"Proposição aprovada no filtro: {proposicao_transformada['proposicao_id']} (Votação: {proposicao_transformada['data_votacao']})"
                    )
                    resultados_validos.append(proposicao_transformada)
        elif isinstance(tramitacoes, Exception):
            logger.error(
                f"Falha ao buscar tramitação para proposição {payload.get('id')}: {tramitacoes}"
            )

    return resultados_validos, next_url


def deduplicar_lote(lote: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove duplicatas de um lote de proposições usando a chave 'id' (UUID) como referência.
    Mantém apenas itens únicos para evitar o erro 21000 no banco de dados.
    """
    return list({item["id"]: item for item in lote}.values())


async def executar_pipeline_completo(
    supabase_client: Any, data_inicio: str, data_fim: str
) -> None:
    """
    Executa o pipeline completo de extração de proposições da Câmara.
    1. Monta a URL inicial.
    2. Consome as páginas recursivamente.
    3. Deduplica o lote em memória e realiza o upsert no Supabase.
    4. Registra o log final na tabela etl_logs.
    """
    exec_inicio = datetime.now(timezone.utc).isoformat()
    lote_completo = []
    total_linhas = 0

    try:
        async with httpx.AsyncClient() as client:
            # Controla a concorrência para no máximo 5 requisições simultâneas (evita picos do WAF)
            semaphore = asyncio.Semaphore(5)

            inicio_dt = datetime.strptime(data_inicio, "%Y-%m-%d")
            fim_dt = datetime.strptime(data_fim, "%Y-%m-%d")
            atual_dt = inicio_dt

            while atual_dt <= fim_dt:
                proximo_dt = atual_dt + timedelta(days=30)
                if proximo_dt > fim_dt:
                    proximo_dt = fim_dt

                fatia_inicio = atual_dt.strftime("%Y-%m-%d")
                fatia_fim = proximo_dt.strftime("%Y-%m-%d")

                logger.info(
                    f"Processando fatia temporal: {fatia_inicio} a {fatia_fim}..."
                )
                url_atual = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes?siglaTipo=PL,PEC&dataInicio={fatia_inicio}&dataFim={fatia_fim}&itens=15"

                while url_atual:
                    resultados_validos, next_url = await processar_pagina_proposicoes(
                        client, url_atual, semaphore
                    )
                    lote_completo.extend(resultados_validos)
                    url_atual = next_url

                atual_dt = proximo_dt + timedelta(days=1)

        if lote_completo:
            lote_deduplicado = deduplicar_lote(lote_completo)
            try:
                supabase_client.table("camara_proposicoes").upsert(
                    lote_deduplicado
                ).execute()
                total_linhas = len(lote_deduplicado)
                logger.info(
                    f"Upsert concluído! {total_linhas} proposições salvas com sucesso no banco de dados."
                )
            except Exception as erro_db:
                logger.error(
                    f"Falha de Banco de Dados: Erro no momento de fazer o Bulk Upsert: {erro_db}"
                )
                raise erro_db
        else:
            logger.info(
                "O lote terminou vazio. Nenhuma proposição atendeu ao filtro rigoroso de Texto-Base no período."
            )

        status = "Concluído"
        detalhe_erro = None
    except Exception as e:
        status = "Erro"
        detalhe_erro = str(e)
        logger.error(f"Erro crítico no pipeline de proposições: {e}")

    exec_fim = datetime.now(timezone.utc).isoformat()

    supabase_client.table("etl_logs").insert(
        {
            "nome_rotina": "extrator_proposicoes_camara",
            "data_inicio": exec_inicio,
            "data_fim": exec_fim,
            "status": status,
            "detalhe_erro": detalhe_erro,
            "linhas_afetadas": total_linhas,
        }
    ).execute()


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
    data_inicio_arg = "2023-01-01"
    data_fim_arg = "2023-12-31"

    logger.info(
        f"Iniciando pipeline de extração de Proposições da Câmara ({data_inicio_arg} a {data_fim_arg})..."
    )
    asyncio.run(
        executar_pipeline_completo(cliente_banco, data_inicio_arg, data_fim_arg)
    )
    logger.info("Pipeline de Proposições finalizado!")
