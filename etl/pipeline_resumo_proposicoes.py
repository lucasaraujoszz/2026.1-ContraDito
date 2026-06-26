import logging
import asyncio
import uuid

import httpx
from google import genai
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

from etl.extrator_texto_proposicao import extrair_texto_de_url
from etl.resumidor_proposicoes import gerar_resumo_executivo
from etl.utils import para_timestamp

logger = logging.getLogger(__name__)

_COLLECTION = "proposicoes_embeddings"


async def executar_pipeline_resumo(
    supabase,
    motor_nlp,
    gemini_client: genai.Client,
    qdrant_client: QdrantClient,
    limite: int | None = None,
) -> int:
    """
    Busca proposições pendentes (resumo_executivo IS NULL, url_texto_inteiro NOT NULL
    e id_votacao_camara NOT NULL), extrai o texto do PDF, gera resumo executivo via
    Gemini Flash e vetoriza via MotorNLP.
    Salva o resumo no Supabase e o embedding no Qdrant (collection proposicoes_embeddings).
    Retorna o total de proposições processadas com sucesso.
    """
    query = (
        supabase.table("camara_proposicoes")
        .select("id, url_texto_inteiro, proposicao_id, data_votacao")
        .is_("resumo_executivo", "null")
        .not_.is_("url_texto_inteiro", "null")
        .not_.is_("id_votacao_camara", "null")
    )
    if limite:
        query = query.limit(limite)

    proposicoes = query.execute().data

    if not proposicoes:
        logger.info("Nenhuma proposição pendente de resumo.")
        return 0

    def _registrar_erro(id_prop: str, mensagem: str) -> None:
        supabase.table("camara_proposicoes").update({"erro_resumo": mensagem}).eq(
            "id", id_prop
        ).execute()
        logger.warning(f"Proposição {id_prop}: {mensagem}")

    total = 0
    async with httpx.AsyncClient() as client:
        for proposicao in proposicoes:
            id_prop = proposicao["id"]
            url = proposicao["url_texto_inteiro"]
            try:
                texto = await extrair_texto_de_url(url, client)
                if not texto:
                    _registrar_erro(id_prop, "PDF sem texto extraível")
                    continue

                resumo = await gerar_resumo_executivo(texto, gemini_client)
                if not resumo:
                    _registrar_erro(id_prop, "modelo retornou resumo vazio")
                    continue

                embedding = await motor_nlp.gerar_embedding(resumo)

                qdrant_client.upsert(
                    collection_name=_COLLECTION,
                    points=[
                        PointStruct(
                            id=str(uuid.UUID(id_prop)),
                            payload={
                                "proposicao_id_string": proposicao.get("proposicao_id"),
                                "data_votacao": para_timestamp(
                                    proposicao.get("data_votacao")
                                ),
                                "casa": "camara",
                            },
                            vector=embedding,
                        )
                    ],
                )

                supabase.table("camara_proposicoes").update(
                    {
                        "resumo_executivo": resumo,
                        "erro_resumo": None,
                    }
                ).eq("id", id_prop).execute()

                total += 1
                logger.info(f"Proposição {id_prop}: resumo saved, embedding in Qdrant.")

                await asyncio.sleep(5)

            except Exception as e:
                _registrar_erro(id_prop, str(e))
                continue

    return total
