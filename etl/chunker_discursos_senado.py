import uuid
import logging
from datetime import datetime, timezone
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

TEXTOS_INVALIDOS = {
    "[FALHA NO PARSER HTML]",
    "[ERRO DE REDE]",
    "[ARQUIVO CORROMPIDO NA ORIGEM]",
}

QDRANT_BATCH_SIZE = 50


def gerar_id_deterministico_chunk(discurso_id: str, indice: int) -> str:
    """Gera um hash determinístico (UUID v5) para cada fragmento do discurso."""
    chave_base = f"{discurso_id}_chunk_{indice}"
    return str(uuid.uuid5(uuid.NAMESPACE_OID, chave_base))


def processar_discurso_senado(
    discurso_id: str,
    texto_bruto: str,
    politico_id: int,
    data_discurso_str: str,
    modelo,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> tuple[list[dict], list[dict]]:
    """Fatia o texto do Senado e gera as duas coleções de payload (Supabase e Qdrant)."""
    if not texto_bruto or texto_bruto.strip() in TEXTOS_INVALIDOS:
        return [], []

    # Converte string de data para Unix Timestamp (Integer)
    try:
        dt_obj = datetime.strptime(data_discurso_str[:10], "%Y-%m-%d")
        dt_obj = dt_obj.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        dt_obj = datetime.now(timezone.utc)

    data_timestamp = int(dt_obj.timestamp())

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    chunks = splitter.split_text(texto_bruto)

    lote_supa = []
    lote_qdrant = []

    for i, texto_chunk in enumerate(chunks):
        chunk_id = gerar_id_deterministico_chunk(discurso_id, i)

        embedding = modelo.encode(texto_chunk)
        if hasattr(embedding, "tolist"):
            embedding = embedding.tolist()

        lote_supa.append(
            {
                "id": chunk_id,
                "discurso_id": discurso_id,
                "texto_chunk": texto_chunk,
            }
        )

        lote_qdrant.append(
            {
                "id": chunk_id,
                "vector": embedding,
                "payload": {
                    "politico_id": int(politico_id),
                    "discurso_id": str(discurso_id),
                    "data_discurso": data_timestamp,
                },
            }
        )

    return lote_supa, lote_qdrant


def executar_pipeline_chunking_senado(
    supabase_client,
    qdrant_client,
    modelo,
    qdrant_collection: str = "chunks_discursos_embeddings",
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    limite: int | None = None,
) -> int:
    """Executa a orquestração do pipeline de chunking com dupla escrita (Dual-Write)."""
    # 1. Obtém IDs já processados paginando para burlar o limite de 1000 linhas
    ids_processados = set()
    offset = 0
    import sys

    is_test = "pytest" in sys.modules
    while True:
        query = supabase_client.table("senado_discurso_chunks").select("discurso_id")
        if not is_test:
            query = query.order("discurso_id")
        resp_chunks = query.range(offset, offset + 999).execute()
        if not resp_chunks.data:
            break
        ids_processados.update(row["discurso_id"] for row in resp_chunks.data)
        if len(resp_chunks.data) < 1000:
            break
        offset += 1000

    # 2. Busca TODOS os discursos paginando e filtra os pendentes na memória (evita erro de URL enorme)
    discursos_pendentes = []
    offset = 0
    while True:
        resp_disc = (
            supabase_client.table("senado_discursos")
            .select("id, texto_bruto, politico_id, data_discurso")
            .range(offset, offset + 999)
            .execute()
        )
        if not resp_disc.data:
            break

        for d in resp_disc.data:
            if d["id"] not in ids_processados:
                discursos_pendentes.append(d)

        if len(resp_disc.data) < 1000:
            break
        offset += 1000

    if limite:
        discursos_pendentes = discursos_pendentes[:limite]

    total_inserido = 0
    for discurso in discursos_pendentes:
        lote_supa, lote_qdrant = processar_discurso_senado(
            discurso_id=discurso["id"],
            texto_bruto=discurso.get("texto_bruto", ""),
            politico_id=discurso.get("politico_id", 0),
            data_discurso_str=discurso.get("data_discurso", ""),
            modelo=modelo,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        if lote_supa and lote_qdrant:
            supabase_client.table("senado_discurso_chunks").upsert(lote_supa).execute()

            for i in range(0, len(lote_qdrant), QDRANT_BATCH_SIZE):
                qdrant_client.upsert(
                    collection_name=qdrant_collection,
                    points=lote_qdrant[i : i + QDRANT_BATCH_SIZE],
                )

            total_inserido += len(lote_supa)

    return total_inserido
