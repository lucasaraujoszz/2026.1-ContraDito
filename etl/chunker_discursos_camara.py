import uuid
import logging
from langchain_text_splitters import RecursiveCharacterTextSplitter

TEXTO_CORROMPIDO = "[ARQUIVO CORROMPIDO NA ORIGEM]"


def dividir_em_chunks(texto: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    if not texto or texto.strip() == TEXTO_CORROMPIDO:
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return splitter.split_text(texto)


def processar_discurso(
    discurso_id: str,
    texto_bruto: str,
    modelo,
    chunk_size: int,
    chunk_overlap: int,
) -> list[dict]:
    chunks = dividir_em_chunks(texto_bruto, chunk_size, chunk_overlap)
    resultado = []
    for texto_chunk in chunks:
        embedding = modelo.encode(texto_chunk)
        if hasattr(embedding, "tolist"):
            embedding = embedding.tolist()
        resultado.append({
            "id": str(uuid.uuid4()),
            "discurso_id": discurso_id,
            "texto_chunk": texto_chunk,
            "embedding_chunk": embedding,
        })
    return resultado


def executar_pipeline_chunking(
    supabase,
    modelo,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    limite: int | None = None,
) -> int:
    resp = supabase.table("camara_discurso_chunks").select("discurso_id").execute()
    ids_processados = {row["discurso_id"] for row in resp.data}

    query = supabase.table("camara_discursos").select("id, texto_bruto")
    if ids_processados:
        query = query.not_.in_("id", list(ids_processados))
    if limite:
        query = query.limit(limite)
    discursos = query.execute().data

    total = 0
    for discurso in discursos:
        chunks = processar_discurso(
            discurso_id=discurso["id"],
            texto_bruto=discurso.get("texto_bruto") or "",
            modelo=modelo,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        if chunks:
            supabase.table("camara_discurso_chunks").insert(chunks).execute()
            total += len(chunks)
            logging.info(f"Discurso {discurso['id']}: {len(chunks)} chunk(s) inserido(s).")

    return total
