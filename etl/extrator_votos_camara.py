import httpx
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, Tuple, Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from etl.transformadores_votos_camara import (
    eh_votacao_merito_nominal,
    filtrar_votos_validos,
    transformar_voto_camara,
    contem_manobra_regimental
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
    reraise=True
)
async def obter_id_votacao_camada_1(client: httpx.AsyncClient, id_camara_proposicao: int) -> Optional[Tuple[str, Optional[str]]]:
    """
    Busca as votações da proposição na API da Câmara e tenta encontrar a votação 
    de mérito nominal usando a Camada 1 (Regex agressiva na descrição).
    Retorna a tupla (ID da votação, Data da Votação) caso encontre, ou None se falhar.
    """
    url = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes/{id_camara_proposicao}/votacoes"
    response = await client.get(url, timeout=30.0)
    response.raise_for_status()
    
    dados = response.json().get("dados", [])
    for votacao in dados:
        if eh_votacao_merito_nominal(votacao.get("descricao", "")):
            data_votacao = votacao.get("dataHoraRegistro") or votacao.get("data")
            return str(votacao.get("id")), str(data_votacao) if data_votacao else None
            
    return None

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception(_is_transient_error),
    reraise=True
)
async def obter_id_votacao_camada_2_sweep(client: httpx.AsyncClient, id_camara_proposicao: int) -> Optional[Tuple[str, Optional[str]]]:
    """
    Camada 2 (Fallback): Varre todas as votações da proposição e faz chamadas N+1 
    aos endpoints de votos até encontrar o primeiro que possua votos nominais registrados.
    Retorna a tupla (ID da votação, Data da Votação) ou None se for matéria simbólica (sem votos).
    """
    url_votacoes = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes/{id_camara_proposicao}/votacoes"
    resp_votacoes = await client.get(url_votacoes, timeout=30.0)
    resp_votacoes.raise_for_status()
    
    votacoes = resp_votacoes.json().get("dados", [])
    for votacao in votacoes:
        if contem_manobra_regimental(votacao.get("descricao", "")):
            continue
            
        id_votacao = str(votacao.get("id"))
        url_votos = f"https://dadosabertos.camara.leg.br/api/v2/votacoes/{id_votacao}/votos"
        resp_votos = await client.get(url_votos, timeout=30.0)
        
        if resp_votos.status_code == 200:
            votos = resp_votos.json().get("dados", [])
            if votos:
                data_votacao = votacao.get("dataHoraRegistro") or votacao.get("data")
                return id_votacao, str(data_votacao) if data_votacao else None
                
    return None

async def extrair_votos_proposicao(
    client: httpx.AsyncClient, 
    proposicao_id: str, 
    id_camara_proposicao: int, 
    ids_validos_banco: set
) -> Tuple[list, Optional[str], Optional[str]]:
    """
    Orquestra a busca de votos de uma proposição. Tenta achar a sessão pela 
    Camada 1, faz fallback para a Camada 2, aplica o Soft Drop, transforma 
    os dados pro Data Contract e lida com Poison Pills (Skip-and-Continue).
    """
    try:
        resultado_busca = await obter_id_votacao_camada_1(client, id_camara_proposicao)
        if not resultado_busca:
            resultado_busca = await obter_id_votacao_camada_2_sweep(client, id_camara_proposicao)
            
        if not resultado_busca:
            return [], None, None
            
        id_votacao, data_votacao = resultado_busca
            
        url_votos = f"https://dadosabertos.camara.leg.br/api/v2/votacoes/{id_votacao}/votos"
        resp_votos = await client.get(url_votos, timeout=30.0)
        resp_votos.raise_for_status()
        
        votos_brutos = resp_votos.json().get("dados", [])
        votos_validos = filtrar_votos_validos(votos_brutos, ids_validos_banco)
        
        votos_transformados = [
            transformar_voto_camara(voto, proposicao_id) 
            for voto in votos_validos
        ]
        
        return votos_transformados, id_votacao, data_votacao
        
    except Exception as e:
        logger.error(f"Falha isolada (Poison Pill) ao extrair votos da proposição {proposicao_id}: {e}")
        return [], None, None

async def executar_pipeline_votos_camara(supabase_client: Any, limite_amostral: Optional[int] = None) -> None:
    """
    Rotina principal (Pipeline). Busca proposições e políticos locais, orquestra
    a extração na API da Câmara concorrentemente, atualiza o ID de votação nas proposições
    e faz o Bulk Upsert dos votos no banco de dados.
    """
    exec_inicio = datetime.now(timezone.utc).isoformat()
    total_linhas = 0
    status = "Concluído"
    detalhe_erro = None
    
    try:
        # 1. Puxa IDs válidos de deputados para o Soft Drop
        resp_politicos = supabase_client.table("camara_politicos").select("id").execute()
        ids_validos_banco = {p["id"] for p in resp_politicos.data} if resp_politicos.data else set()
        
        # 2. Puxa as proposições para orquestrar
        query_proposicoes = supabase_client.table("camara_proposicoes").select("proposicao_id, id_camara")
        if limite_amostral:
            query_proposicoes = query_proposicoes.limit(limite_amostral)
        resp_proposicoes = query_proposicoes.execute()
        proposicoes = resp_proposicoes.data or []
        
        votos_totais_upsert = []
        
        async with httpx.AsyncClient() as client:
            # 3. Concorrência controlada para evitar bloqueio WAF da Câmara (Max: 5 requisições paralelas)
            semaphore = asyncio.Semaphore(5)
            
            async def processar_proposicao_worker(prop: dict):
                async with semaphore:
                    await asyncio.sleep(0.5) # Respiro de Rate Limit
                    proposicao_id = prop["proposicao_id"]
                    id_camara = prop["id_camara"]
                    
                    try:
                        votos, id_votacao, data_votacao = await extrair_votos_proposicao(client, proposicao_id, id_camara, ids_validos_banco)
                        return proposicao_id, votos, id_votacao, data_votacao
                    except Exception as e:
                        logger.error(f"Erro não tratado no worker da proposição {proposicao_id}: {e}")
                        return proposicao_id, [], None, None

            tarefas = [processar_proposicao_worker(p) for p in proposicoes]
            resultados = await asyncio.gather(*tarefas, return_exceptions=True)
            
            for res in resultados:
                if isinstance(res, Exception):
                    logger.error(f"Erro crítico no processamento de uma task: {res}")
                    continue
                
                proposicao_id, votos, id_votacao, data_votacao = res
                
                if id_votacao:
                    # 4. Atualiza a proposição com a chave estrangeira e a data (Rastreabilidade)
                    payload_update = {"id_votacao_camara": id_votacao}
                    if data_votacao:
                        payload_update["data_votacao"] = data_votacao
                    supabase_client.table("camara_proposicoes").update(payload_update).eq("proposicao_id", proposicao_id).execute()
                        
                if votos:
                    votos_totais_upsert.extend(votos)

            if votos_totais_upsert:
                # 5. Deduplica e realiza o Bulk Upsert em Lotes de 1.000 para proteger o PostgREST
                votos_deduplicados = list({v["id"]: v for v in votos_totais_upsert}.values())
                
                chunk_size = 1000
                for i in range(0, len(votos_deduplicados), chunk_size):
                    chunk = votos_deduplicados[i:i + chunk_size]
                    supabase_client.table("camara_votos").upsert(chunk).execute()
                    
                total_linhas = len(votos_deduplicados)
                logger.info(f"Upsert concluído: {total_linhas} votos validados salvos na base.")
                
    except Exception as e:
        status = "Erro"
        detalhe_erro = str(e)
        logger.error(f"Erro crítico no pipeline de extração de votos: {e}")

    exec_fim = datetime.now(timezone.utc).isoformat()
    
    # 6. Gravação do Log de Execução (Watermarker)
    try:
        supabase_client.table("etl_logs").insert({
            "nome_rotina": "extrator_votos_camara",
            "data_inicio": exec_inicio,
            "data_fim": exec_fim,
            "status": status,
            "detalhe_erro": detalhe_erro,
            "linhas_afetadas": total_linhas
        }).execute()
    except Exception as log_e:
        logger.error(f"Falha ao registrar log no etl_logs: {log_e}")

if __name__ == "__main__":
    import os
    import sys
    from supabase import create_client, Client

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")

    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("As variáveis de ambiente SUPABASE_URL e SUPABASE_KEY precisam estar definidas.")
        sys.exit(1)

    cliente_banco: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    logger.info("Iniciando pipeline de extração de Votos Nominais da Câmara...")
    asyncio.run(executar_pipeline_votos_camara(cliente_banco))
    logger.info("Pipeline de Votos finalizado!")