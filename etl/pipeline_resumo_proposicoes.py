import logging

import httpx
from groq import Groq

from etl.extrator_texto_proposicao import extrair_texto_de_url
from etl.resumidor_proposicoes import gerar_resumo_executivo

logger = logging.getLogger(__name__)


async def executar_pipeline_resumo(
    supabase,
    motor_nlp,
    groq_client: Groq,
    limite: int | None = None,
) -> int:
    """
    Busca proposições pendentes (resumo_executivo IS NULL e url_texto_inteiro NOT NULL),
    extrai o texto do PDF, gera resumo executivo via Groq e vetoriza via MotorNLP.
    Atualiza a linha no banco com resumo + embedding.
    Retorna o total de proposições processadas com sucesso.
    """
    query = (
        supabase.table("camara_proposicoes")
        .select("id, url_texto_inteiro")
        .is_("resumo_executivo", "null")
        .not_.is_("url_texto_inteiro", "null")
    )
    if limite:
        query = query.limit(limite)

    proposicoes = query.execute().data

    if not proposicoes:
        logger.info("Nenhuma proposição pendente de resumo.")
        return 0

    total = 0
    async with httpx.AsyncClient() as client:
        for proposicao in proposicoes:
            id_prop = proposicao["id"]
            url = proposicao["url_texto_inteiro"]
            try:
                texto = await extrair_texto_de_url(url, client)
                if not texto:
                    logger.warning(f"Proposição {id_prop}: PDF sem texto extraível, ignorando.")
                    continue

                resumo = await gerar_resumo_executivo(texto, groq_client)
                if not resumo:
                    logger.warning(f"Proposição {id_prop}: resumo vazio, ignorando.")
                    continue

                embedding = await motor_nlp.gerar_embedding(resumo)

                supabase.table("camara_proposicoes").update({
                    "resumo_executivo": resumo,
                    "embedding_resumo_executivo": embedding,
                }).eq("id", id_prop).execute()

                total += 1
                logger.info(f"Proposição {id_prop}: resumo e embedding salvos.")

            except Exception as e:
                logger.error(f"Proposição {id_prop}: erro ao processar — {e}")
                continue

    return total
