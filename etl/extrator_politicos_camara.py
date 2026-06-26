import httpx
import time
import logging
from datetime import datetime, timezone
from typing import Tuple, List, Optional

logger = logging.getLogger(__name__)


def _fetch_com_retry(url: str, headers: Optional[dict] = None) -> Optional[dict]:
    """
    Função auxiliar que faz a requisição HTTP e aplica o mecanismo de retry em caso de falha (Erro 500+).
    """
    backoffs = [2, 4]

    for tentativa in range(3):
        try:
            resposta = httpx.get(url, headers=headers)
            resposta.raise_for_status()
            return resposta.json()

        except httpx.HTTPError as e:
            if tentativa < 2:
                logger.warning(
                    f"Erro ao acessar {url}. Retentando em {backoffs[tentativa]}s..."
                )
                time.sleep(backoffs[tentativa])
            else:
                logger.error(f"Falha crítica ao acessar {url} após 3 tentativas: {e}")
                return None


def extrair_pagina_deputados(url: str) -> Tuple[List[dict], Optional[str]]:
    """
    Extrai uma página de deputados da API da Câmara e retorna os dados brutos e o link para a próxima página.
    """
    dados_json = _fetch_com_retry(url)
    if not dados_json:
        return [], None

    dados = dados_json.get("dados", [])

    next_url = None
    for link in dados_json.get("links", []):
        if link.get("rel") == "next":
            next_url = link.get("href")
            break

    return dados, next_url


def extrair_detalhes_deputado(id_deputado: int) -> Optional[dict]:
    """
    Busca os detalhes de um deputado, aplica sleep de rate-limit e transforma os dados para o schema do banco.
    """
    time.sleep(0.5)

    url = f"https://dadosabertos.camara.leg.br/api/v2/deputados/{id_deputado}"
    dados_json = _fetch_com_retry(url)
    if not dados_json:
        return None

    dados = dados_json.get("dados", {})
    status = dados.get("ultimoStatus", {})

    # Mapeamento de status da Câmara para o nosso domínio
    situacao_governo = status.get("situacao", "")
    if situacao_governo == "Exercício":
        status_mandato = "Ativo"
    elif situacao_governo == "Suplência":
        status_mandato = "Suplente"
    else:
        status_mandato = "Inativo"

    return {
        "id": dados.get("id"),
        "nome_civil": dados.get("nomeCivil"),
        "nome_urna": status.get("nomeEleitoral"),
        "partido": status.get("siglaPartido"),
        "estado": status.get("siglaUf"),
        "url_foto": status.get("urlFoto"),
        "cargo": "Deputado Federal",
        "status_mandato": status_mandato,
        "data_ultima_atualizacao": datetime.now(timezone.utc).isoformat(),
    }


def executar_extracao_pagina(
    url: str, supabase_client, ids_processados: set
) -> Tuple[Optional[str], int]:
    """
    Orquestra a extração de uma página, busca os detalhes de cada deputado encontrado e
    realiza um Bulk Upsert no Supabase. Retorna a URL da próxima página (se houver) e a quantidade de linhas afetadas.
    """
    dados_pagina, next_url = extrair_pagina_deputados(url)

    lote_deputados = []
    for item in dados_pagina:
        id_deputado = item.get("id")
        if id_deputado and id_deputado not in ids_processados:
            ids_processados.add(id_deputado)
            detalhes = extrair_detalhes_deputado(id_deputado)
            # Se falhou as 3 vezes, detalhes será None e não entrará no lote
            if detalhes:
                print(
                    f"Deputado extraído com sucesso: {detalhes.get('nome_urna')} ({detalhes.get('partido')}-{detalhes.get('estado')})"
                )
                lote_deputados.append(detalhes)
            else:
                print(f"Falha ao extrair deputado ID: {id_deputado}")

    if lote_deputados:
        supabase_client.table("camara_politicos").upsert(lote_deputados).execute()

    return next_url, len(lote_deputados)


def executar_pipeline_completo(supabase_client) -> None:
    """
    Executa o pipeline completo de extração de deputados, paginando até o fim,
    e registra o resultado na tabela etl_logs.
    """
    data_inicio = datetime.now(timezone.utc).isoformat()
    url_inicial = "https://dadosabertos.camara.leg.br/api/v2/deputados?idLegislatura=57"
    total_linhas = 0
    ids_processados = set()

    try:
        next_url = url_inicial
        while next_url:
            next_url, linhas = executar_extracao_pagina(
                next_url, supabase_client, ids_processados
            )
            total_linhas += linhas

        status = "Concluído"
        detalhe_erro = None
    except Exception as e:
        status = "Erro"
        detalhe_erro = str(e)
        logger.error(f"Erro crítico no pipeline: {e}")

    data_fim = datetime.now(timezone.utc).isoformat()

    supabase_client.table("etl_logs").insert(
        {
            "nome_rotina": "extrator_politicos_camara",
            "data_inicio": data_inicio,
            "data_fim": data_fim,
            "status": status,
            "detalhe_erro": detalhe_erro,
            "linhas_afetadas": total_linhas,
        }
    ).execute()
