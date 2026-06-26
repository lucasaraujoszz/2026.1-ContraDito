import logging
from datetime import datetime, timezone
from qdrant_client.models import Filter, FieldCondition, MatchValue

logger = logging.getLogger(__name__)


def filtrar_chunks_validos(
    chunks_qdrant: list, threshold: float = 0.72, limit: int | None = None
) -> list[dict]:
    """
    Filtra os chunks retornados pelo Qdrant com score >= threshold,
    ordena por score decrescente. Se limit for informado, retorna no máximo `limit` registros.
    """
    if not chunks_qdrant:
        return []

    validos = []
    for chunk in chunks_qdrant:
        if chunk.score >= threshold:
            payload = getattr(chunk, "payload", {}) or {}
            validos.append(
                {
                    "id": chunk.id,
                    "score": chunk.score,
                    "discurso_id": payload.get("discurso_id"),
                    "data_discurso": payload.get("data_discurso"),
                }
            )

    # Ordena por score decrescente
    validos.sort(key=lambda x: x["score"], reverse=True)

    if limit is not None:
        return validos[:limit]
    return validos


def resolver_textos_chunks(
    supabase_client,
    chunk_ids: list[str],
    chunks_com_score: list[dict],
    tabela_chunks: str,
) -> list[dict]:
    """
    Busca no Supabase os textos correspondentes aos IDs de chunks
    e retorna uma lista estruturada mesclando score, texto, data e id do discurso,
    preservando a ordenação original.
    """
    if not chunk_ids or not chunks_com_score:
        return []

    try:
        resp = (
            supabase_client.table(tabela_chunks)
            .select("id, texto_chunk")
            .in_("id", chunk_ids)
            .execute()
        )
        data = resp.data or []
    except Exception as e:
        logger.error(f"Erro ao buscar textos dos chunks no Supabase: {e}")
        return []

    # Mapeia ID -> texto
    text_map = {
        row["id"]: row["texto_chunk"]
        for row in data
        if "id" in row and "texto_chunk" in row
    }

    resultado = []
    for item in chunks_com_score:
        chunk_id = item["id"]
        if chunk_id in text_map:
            resultado.append(
                {
                    "chunk_id": chunk_id,
                    "discurso_id": item.get("discurso_id"),
                    "data_discurso": item.get("data_discurso"),
                    "texto_chunk": text_map[chunk_id],
                    "score": item["score"],
                }
            )

    return resultado


def _buscar_embedding_proposicao(
    qdrant_client, proposicao_id: str
) -> list[float] | None:
    """Recupera o vetor de uma proposição do Qdrant pelo proposicao_id_string do payload."""
    try:
        resultado = qdrant_client.scroll(
            collection_name="proposicoes_embeddings",
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="proposicao_id_string",
                        match=MatchValue(value=proposicao_id),
                    ),
                    FieldCondition(key="casa", match=MatchValue(value="senado")),
                ]
            ),
            with_vectors=True,
            limit=1,
        )
        points = resultado[0]
        if not points:
            return None
        return points[0].vector
    except Exception as e:
        logger.error(
            f"Erro ao buscar embedding da proposicao {proposicao_id} no Qdrant: {e}"
        )
        return None


def executar_pipeline_vinculo_senado(
    supabase_client,
    qdrant_client,
    threshold: float = 0.72,
    limite_votos: int | None = None,
) -> int:
    """
    Orquestra o vínculo de chunks aos votos do Senado Federal de forma incremental.
    Reutiliza embeddings obtidos no cache em memória.
    """
    exec_inicio = datetime.now(timezone.utc).isoformat()
    total_processados = 0

    try:
        # 1. Busca os votos elegíveis pendentes paginando para burlar o limite de 1000 linhas
        votos = []
        offset = 0
        while True:
            query = (
                supabase_client.table("senado_votos")
                .select("id, proposicao_id, politico_id")
                .is_("chunks_proximos", "null")
                .in_("voto_oficial", ["Sim", "Não", "SIM", "NAO"])
                .range(offset, offset + 999)
            )
            res_votos = query.execute()
            if not res_votos.data:
                break
            votos.extend(res_votos.data)
            if len(res_votos.data) < 1000:
                break
            offset += 1000

            if limite_votos and len(votos) >= limite_votos:
                votos = votos[:limite_votos]
                break

        if not votos:
            logger.info("Nenhum voto pendente de vínculo encontrado.")
            return 0

        cache_proposicoes = {}

        # 2. Processa cada voto
        for voto in votos:
            id_voto = voto["id"]
            proposicao_id = voto["proposicao_id"]
            politico_id = voto["politico_id"]

            # Recupera embedding da proposição (com cache)
            if proposicao_id not in cache_proposicoes:
                vector = _buscar_embedding_proposicao(qdrant_client, proposicao_id)
                cache_proposicoes[proposicao_id] = vector

            query_vector = cache_proposicoes[proposicao_id]

            if not query_vector:
                logger.warning(
                    f"Voto {id_voto}: embedding não encontrado para proposição {proposicao_id}. Ignorando."
                )
                continue

            # Busca chunks mais próximos no Qdrant para o senador
            qdrant_filter = Filter(
                must=[
                    FieldCondition(
                        key="politico_id", match=MatchValue(value=politico_id)
                    ),
                ]
            )

            try:
                resultados_qdrant = qdrant_client.query_points(
                    collection_name="chunks_discursos_embeddings",
                    query=query_vector,
                    query_filter=qdrant_filter,
                    limit=1000,
                    score_threshold=threshold,
                )
                points = resultados_qdrant.points or []
            except Exception as e:
                logger.error(f"Erro ao query Qdrant para politico {politico_id}: {e}")
                points = []

            # Filtra e ordena usando regras de domínio
            chunks_com_score = filtrar_chunks_validos(
                points, threshold=threshold, limit=None
            )

            # Resolve os textos associados
            chunk_ids = [item["id"] for item in chunks_com_score]
            chunks_com_texto = resolver_textos_chunks(
                supabase_client=supabase_client,
                chunk_ids=chunk_ids,
                chunks_com_score=chunks_com_score,
                tabela_chunks="senado_discurso_chunks",
            )

            # Salva o resultado no voto (mesmo que seja lista vazia [])
            supabase_client.table("senado_votos").update(
                {"chunks_proximos": chunks_com_texto}
            ).eq("id", id_voto).execute()

            total_processados += 1

        status = "Concluído"
        detalhe_erro = None

    except Exception as e:
        status = "Erro"
        detalhe_erro = str(e)
        logger.error(f"Erro crítico no pipeline de vínculo do Senado: {e}")

    # 3. Registra logs da execução
    exec_fim = datetime.now(timezone.utc).isoformat()
    try:
        supabase_client.table("etl_logs").insert(
            {
                "nome_rotina": "vinculo_chunks_votos_senado",
                "data_inicio": exec_inicio,
                "data_fim": exec_fim,
                "status": status,
                "detalhe_erro": detalhe_erro,
                "linhas_afetadas": total_processados,
            }
        ).execute()
    except Exception as log_e:
        logger.error(f"Falha ao registrar log no etl_logs: {log_e}")

    if status == "Erro":
        raise Exception(detalhe_erro)

    return total_processados
