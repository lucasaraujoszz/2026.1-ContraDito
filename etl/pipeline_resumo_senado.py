import logging
import httpx
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from etl.extrator_texto_senado import extrair_texto_senado
from etl.resumidor_senado import gerar_resumo_executivo_senado

logger = logging.getLogger(__name__)


def converter_data_para_timestamp_sp(data_str: str) -> int:
    """
    Converte uma data no formato 'YYYY-MM-DD' para Unix Timestamp (segundos)
    aplicando obrigatoriamente o fuso horário 'America/Sao_Paulo'.
    """
    dt = datetime.strptime(data_str[:10], "%Y-%m-%d")
    dt = dt.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
    return int(dt.timestamp())


async def executar_pipeline_resumo_senado(
    supabase_client, qdrant_client, motor_nlp, gemini_client, limite: int | None = None
) -> int:
    """
    Orquestra o pipeline de resumos do Senado.
    Adota a estratégia Qdrant-First para garantir a consistência vetorial.
    """
    query = (
        supabase_client.table("senado_proposicoes")
        .select("id, proposicao_id, url_texto_inteiro, data_votacao")
        .not_.is_("id_votacao_senado", "null")
        .is_("resumo_executivo", "null")
        .is_("erro_resumo", "null")
    )
    if limite:
        query = query.limit(limite)

    proposicoes = query.execute().data

    if not proposicoes:
        logger.info("Nenhuma proposição do Senado pendente de resumo.")
        return 0

    total = 0
    async with httpx.AsyncClient() as client:
        for prop in proposicoes:
            id_uuid = prop["id"]
            proposicao_id = prop["proposicao_id"]
            url = prop["url_texto_inteiro"]
            data_votacao = prop["data_votacao"]

            try:
                texto = await extrair_texto_senado(url, client)
                if not texto:
                    logger.warning(
                        f"Proposição {proposicao_id}: PDF sem texto extraível ou corrompido."
                    )
                    supabase_client.table("senado_proposicoes").update(
                        {"erro_resumo": "PDF sem texto extraível ou corrompido"}
                    ).eq("id", id_uuid).execute()
                    continue

                resumo = await gerar_resumo_executivo_senado(texto, gemini_client)
                if not resumo:
                    continue

                embedding = await motor_nlp.gerar_embedding(resumo)

                # Qdrant-First
                qdrant_client.upsert(
                    collection_name="proposicoes_embeddings",
                    points=[
                        {
                            "id": id_uuid,
                            "vector": embedding,
                            "payload": {
                                "proposicao_id_string": proposicao_id,
                                "data_votacao": converter_data_para_timestamp_sp(
                                    data_votacao
                                ),
                                "casa": "senado",
                            },
                        }
                    ],
                )

                # Persistência final no Supabase
                supabase_client.table("senado_proposicoes").update(
                    {"resumo_executivo": resumo}
                ).eq("id", id_uuid).execute()
                total += 1

                # Cooldown de 2s para agilidade
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Erro no pipeline (proposicao {proposicao_id}): {e}")

    return total
