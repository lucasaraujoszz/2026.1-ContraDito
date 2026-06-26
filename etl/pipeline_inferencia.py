import logging

from google import genai
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

from etl.inferidor_postura import calcular_coerencia, inferir_postura
from etl.utils import para_timestamp

logger = logging.getLogger(__name__)

_VOTOS_INVALIDOS = {"AUSENTE", "ABSTENÇÃO", "NÃO COMPARECEU", "ART. 17", "OBSTRUÇÃO"}

_MATCH_THRESHOLD = 0.46
_MATCH_COUNT = 5

_COLLECTION_PROPOSICOES = "proposicoes_embeddings"
_COLLECTION_CHUNKS = "chunks_discursos_embeddings"


def _buscar_embedding_proposicao(
    qdrant_client: QdrantClient, proposicao_id_string: str
) -> list[float] | None:
    """Recupera o vetor de uma proposição do Qdrant pelo proposicao_id_string do payload."""
    resultado = qdrant_client.scroll(
        collection_name=_COLLECTION_PROPOSICOES,
        scroll_filter=Filter(
            must=[
                FieldCondition(
                    key="proposicao_id_string",
                    match=MatchValue(value=proposicao_id_string),
                )
            ]
        ),
        with_vectors=True,
        limit=1,
    )
    points = resultado[0]
    if not points:
        return None
    return points[0].vector


async def executar_pipeline_inferencia(
    supabase,
    gemini_client: genai.Client,
    qdrant_client: QdrantClient,
    match_threshold: float = _MATCH_THRESHOLD,
    match_count: int = _MATCH_COUNT,
    limite: int | None = None,
) -> int:
    """
    Para cada voto pendente (inferencia_ia IS NULL):
      1. Busca o embedding da proposição no Qdrant
      2. Busca os top-k chunks do deputado via Qdrant (com filtro temporal)
      3. Infere a postura esperada via Gemini Flash
      4. Calcula coerência entre voto real e postura inferida
      5. Salva inferencia_ia, justificativa e eh_coerente em camara_votos
    Retorna o total de votos processados.
    """
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

        if voto_oficial.strip().upper() in _VOTOS_INVALIDOS:
            logger.info(f"Voto {id_voto}: ignorado ({voto_oficial}).")
            continue

        try:
            prop = (
                supabase.table("camara_proposicoes")
                .select("resumo_executivo, data_votacao")
                .eq("proposicao_id", proposicao_id)
                .single()
                .execute()
                .data
            )
            if not prop or not prop.get("resumo_executivo"):
                logger.warning(
                    f"Voto {id_voto}: proposição {proposicao_id} sem resumo, ignorando."
                )
                continue

            query_vector = _buscar_embedding_proposicao(qdrant_client, proposicao_id)
            if not query_vector:
                logger.warning(
                    f"Voto {id_voto}: embedding da proposição {proposicao_id} não encontrado no Qdrant."
                )
                continue

            data_corte = para_timestamp(prop.get("data_votacao"))
            qdrant_filter = Filter(
                must=[
                    FieldCondition(
                        key="politico_id", match=MatchValue(value=politico_id)
                    ),
                ]
            )
            if data_corte is not None:
                qdrant_filter.must.append(
                    FieldCondition(key="data_discurso", range=Range(lte=data_corte))
                )

            resultados_qdrant = qdrant_client.query_points(
                collection_name=_COLLECTION_CHUNKS,
                query=query_vector,
                query_filter=qdrant_filter,
                limit=match_count,
                score_threshold=match_threshold,
            )

            chunk_ids = [str(r.id) for r in resultados_qdrant.points]
            if not chunk_ids:
                logger.warning(
                    f"Voto {id_voto}: nenhum chunk encontrado no Qdrant para o parlamentar."
                )
                continue

            chunks_data = (
                supabase.table("camara_discurso_chunks")
                .select("texto_chunk")
                .in_("id", chunk_ids)
                .execute()
                .data
            )
            chunks = [c["texto_chunk"] for c in chunks_data]

            resultado = await inferir_postura(
                resumo_proposicao=prop["resumo_executivo"],
                chunks=chunks,
                gemini_client=gemini_client,
            )

            if resultado is None:
                logger.warning(
                    f"Voto {id_voto}: sem chunks suficientes para inferir postura."
                )
                continue

            postura = resultado["postura"]
            justificativa = resultado["justificativa"]
            eh_coerente = calcular_coerencia(voto_oficial, postura)

            supabase.table("camara_votos").update(
                {
                    "inferencia_ia": postura,
                    "justificativa": justificativa,
                    "eh_coerente": eh_coerente,
                }
            ).eq("id", id_voto).execute()

            total += 1
            logger.info(
                f"Voto {id_voto}: {voto_oficial} vs {postura} → coerente={eh_coerente}"
            )

        except Exception as e:
            logger.error(f"Voto {id_voto}: erro ao processar — {e}")
            continue

    return total
