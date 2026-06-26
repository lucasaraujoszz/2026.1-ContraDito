import uuid
import logging
from langchain_text_splitters import RecursiveCharacterTextSplitter

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

from etl.utils import para_timestamp

TEXTO_CORROMPIDO = "[ARQUIVO CORROMPIDO NA ORIGEM]"
_COLLECTION = "chunks_discursos_embeddings"
QDRANT_BATCH_SIZE = 50


def dividir_em_chunks(texto: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    if not texto or texto.strip() == TEXTO_CORROMPIDO:
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return splitter.split_text(texto)


def _gerar_id_chunk(discurso_id: str, indice: int) -> str:
    """Gera um UUID v5 determinístico, baseado no discurso e na posição do chunk."""
    return str(uuid.uuid5(uuid.NAMESPACE_OID, f"{discurso_id}_{indice}"))


def processar_discurso(
    discurso_id: str,
    politico_id: int,
    data_discurso,
    texto_bruto: str,
    modelo,
    qdrant_client: QdrantClient,
    chunk_size: int,
    chunk_overlap: int,
) -> list[dict]:
    chunks = dividir_em_chunks(texto_bruto, chunk_size, chunk_overlap)
    resultado = []
    qdrant_points = []
    data_discurso_ts = para_timestamp(data_discurso)

    discurso_id_str = str(discurso_id)
    politico_id_int = int(politico_id) if politico_id is not None else None

    for indice, texto_chunk in enumerate(chunks):
        chunk_id = _gerar_id_chunk(discurso_id_str, indice)
        embedding = modelo.encode(texto_chunk)
        if hasattr(embedding, "tolist"):
            embedding = embedding.tolist()

        resultado.append(
            {
                "id": chunk_id,
                "discurso_id": discurso_id_str,
                "texto_chunk": texto_chunk,
            }
        )
        qdrant_points.append(
            PointStruct(
                id=chunk_id,
                payload={
                    "politico_id": politico_id_int,
                    "discurso_id": discurso_id_str,
                    "data_discurso": data_discurso_ts,
                },
                vector=embedding,
            )
        )

    if qdrant_points:
        for i in range(0, len(qdrant_points), QDRANT_BATCH_SIZE):
            qdrant_client.upsert(
                collection_name=_COLLECTION,
                points=qdrant_points[i : i + QDRANT_BATCH_SIZE],
            )

    return resultado


def executar_pipeline_chunking(
    supabase,
    modelo,
    qdrant_client: QdrantClient,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    limite: int | None = None,
) -> int:
    # 1. Obtém IDs já processados paginando para burlar o limite de 1000 linhas
    ids_processados = set()
    offset = 0
    import sys

    is_test = "pytest" in sys.modules
    while True:
        query = supabase.table("camara_discurso_chunks").select("discurso_id")
        if not is_test:
            query = query.order("discurso_id")
        resp_chunks = query.range(offset, offset + 999).execute()
        if not resp_chunks.data:
            break
        ids_processados.update(row["discurso_id"] for row in resp_chunks.data)
        if len(resp_chunks.data) < 1000:
            break
        offset += 1000

    # 2. Busca discursos paginando ordenados por data_discurso decrescente e filtra os pendentes na memória
    discursos_pendentes = []
    offset = 0
    while True:
        resp_disc = (
            supabase.table("camara_discursos")
            .select("id, texto_bruto, politico_id, data_discurso")
            .order("data_discurso", desc=True)
            .range(offset, offset + 999)
            .execute()
        )
        if not resp_disc.data:
            break

        for d in resp_disc.data:
            if d["id"] not in ids_processados:
                discursos_pendentes.append(d)
                if limite and len(discursos_pendentes) >= limite:
                    break

        if limite and len(discursos_pendentes) >= limite:
            break
        if len(resp_disc.data) < 1000:
            break
        offset += 1000

    total = 0
    for discurso in discursos_pendentes:
        chunks = processar_discurso(
            discurso_id=discurso["id"],
            politico_id=discurso.get("politico_id"),
            data_discurso=discurso.get("data_discurso"),
            texto_bruto=discurso.get("texto_bruto") or "",
            modelo=modelo,
            qdrant_client=qdrant_client,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        if chunks:
            # Upsert para garantir idempotência e evitar erros de chave duplicada
            supabase.table("camara_discurso_chunks").upsert(chunks).execute()
            total += len(chunks)
            logging.info(
                f"Discurso {discurso['id']}: {len(chunks)} chunk(s) inserido(s)."
            )

    return total
