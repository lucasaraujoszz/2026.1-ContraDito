import logging

from groq import Groq

from etl.inferidor_postura import calcular_coerencia, inferir_postura

logger = logging.getLogger(__name__)

_VOTOS_INVALIDOS = {"AUSENTE", "ABSTENÇÃO", "NÃO COMPARECEU", "ART. 17", "OBSTRUÇÃO"}

_MATCH_THRESHOLD = 0.46
_MATCH_COUNT = 5


async def executar_pipeline_inferencia(
    supabase,
    groq_client: Groq,
    match_threshold: float = _MATCH_THRESHOLD,
    match_count: int = _MATCH_COUNT,
    limite: int | None = None,
) -> int:
    """
    Para cada voto pendente (inferencia_ia IS NULL):
      1. Busca os top-k chunks do deputado via RPC (com filtro temporal)
      2. Infere a postura esperada via LLM
      3. Calcula coerência entre voto real e postura inferida
      4. Salva inferencia_ia, justificativa e eh_coerente em camara_votos
    Retorna o total de votos processados.
    """
    # Só processa votos cujas proposições já têm resumo gerado
    props_com_resumo = (
        supabase.table("camara_proposicoes")
        .select("proposicao_id")
        .not_.is_("resumo_executivo", "null")
        .execute()
        .data
    )
    ids_props = [p["proposicao_id"] for p in props_com_resumo]
    if not ids_props:
        logger.info("Nenhuma proposição com resumo disponível.")
        return 0

    query = (
        supabase.table("camara_votos")
        .select("id, proposicao_id, politico_id, voto_oficial")
        .is_("inferencia_ia", "null")
        .in_("proposicao_id", ids_props)
    )
    if limite:
        query = query.limit(limite)
    votos = query.execute().data

    if not votos:
        logger.info("Nenhum voto pendente de inferência.")
        return 0

    total = 0
    for voto in votos:
        id_voto = voto["id"]
        politico_id = voto["politico_id"]
        voto_oficial = voto["voto_oficial"]
        proposicao_id = voto["proposicao_id"]

        # RF27: ignora votos que não entram no denominador
        if voto_oficial.strip().upper() in _VOTOS_INVALIDOS:
            logger.info(f"Voto {id_voto}: ignorado ({voto_oficial}).")
            continue

        try:
            prop = (
                supabase.table("camara_proposicoes")
                .select("resumo_executivo, embedding_resumo_executivo, data_votacao")
                .eq("proposicao_id", proposicao_id)
                .single()
                .execute()
                .data
            )
            if not prop or not prop.get("resumo_executivo") or not prop.get("embedding_resumo_executivo"):
                logger.warning(f"Voto {id_voto}: proposição {proposicao_id} sem resumo/embedding, ignorando.")
                continue

            chunks_data = supabase.rpc("buscar_discursos_similares", {
                "query_embedding": prop["embedding_resumo_executivo"],
                "p_politico_id": politico_id,
                "match_threshold": match_threshold,
                "match_count": match_count,
                "data_corte": prop["data_votacao"],
            }).execute().data

            chunks = [c["texto_chunk"] for c in chunks_data]

            resultado = await inferir_postura(
                resumo_proposicao=prop["resumo_executivo"],
                chunks=chunks,
                groq_client=groq_client,
            )

            if resultado is None:
                logger.warning(f"Voto {id_voto}: sem chunks suficientes para inferir postura.")
                continue

            postura = resultado["postura"]
            justificativa = resultado["justificativa"]
            eh_coerente = calcular_coerencia(voto_oficial, postura)

            supabase.table("camara_votos").update({
                "inferencia_ia": postura,
                "justificativa": justificativa,
                "eh_coerente": eh_coerente,
            }).eq("id", id_voto).execute()

            total += 1
            logger.info(f"Voto {id_voto}: {voto_oficial} vs {postura} → coerente={eh_coerente}")

        except Exception as e:
            logger.error(f"Voto {id_voto}: erro ao processar — {e}")
            continue

    return total
