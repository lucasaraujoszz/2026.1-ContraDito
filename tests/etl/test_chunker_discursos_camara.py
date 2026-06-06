import uuid
import pytest
from unittest.mock import MagicMock
from etl.chunker_discursos_camara import dividir_em_chunks, processar_discurso, executar_pipeline_chunking


def _make_supabase_mock(discursos_data: list, ids_ja_processados: list | None = None):
    """
    Monta um cliente Supabase falso que responde às queries do pipeline de chunking.
    Retorna (supabase_mock, chunks_table_mock) — o segundo permite verificar se insert foi chamado.
    """
    if ids_ja_processados is None:
        ids_ja_processados = []

    chunks_table = MagicMock()
    chunks_table.select.return_value.execute.return_value.data = ids_ja_processados

    execute_result = MagicMock()
    execute_result.data = discursos_data

    discursos_table = MagicMock()
    # select().execute()                         — sem ids_processados
    discursos_table.select.return_value.execute.return_value = execute_result
    # select().not_.in_().execute()              — com ids_processados
    discursos_table.select.return_value.not_.in_.return_value.execute.return_value = execute_result
    # select().limit().execute()                 — com limite
    discursos_table.select.return_value.limit.return_value.execute.return_value = execute_result
    # select().not_.in_().limit().execute()      — com ambos
    discursos_table.select.return_value.not_.in_.return_value.limit.return_value.execute.return_value = execute_result

    supabase = MagicMock()
    supabase.table.side_effect = lambda name: (
        chunks_table if name == "camara_discurso_chunks" else discursos_table
    )

    return supabase, chunks_table


def test_dividir_texto_vazio_retorna_lista_vazia():
    """
    Tracer bullet: texto vazio não produz nenhum chunk.
    """
    assert dividir_em_chunks("", chunk_size=1000, chunk_overlap=200) == []


def test_dividir_texto_corrompido_retorna_lista_vazia():
    """
    Textos marcados como corrompidos na origem não devem gerar chunks.
    """
    assert dividir_em_chunks("[ARQUIVO CORROMPIDO NA ORIGEM]", chunk_size=1000, chunk_overlap=200) == []


def test_dividir_texto_curto_retorna_um_fragmento():
    """
    Discurso menor que chunk_size deve sair inteiro em um único fragmento.
    """
    texto = "Sr. Presidente, sou favorável ao projeto de lei em questão."
    chunks = dividir_em_chunks(texto, chunk_size=1000, chunk_overlap=200)
    assert len(chunks) == 1
    assert chunks[0] == texto


def test_dividir_texto_longo_respeita_chunk_size():
    """
    Texto maior que chunk_size deve ser dividido em múltiplos fragmentos,
    nenhum deles excedendo chunk_size caracteres.
    """
    chunk_size = 100
    texto = "Parágrafo sobre a reforma tributária. " * 20  # ~760 chars
    chunks = dividir_em_chunks(texto, chunk_size=chunk_size, chunk_overlap=20)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= chunk_size


def _modelo_mock():
    modelo = MagicMock()
    modelo.encode.return_value = [0.1] * 1024
    return modelo


def test_processar_discurso_retorna_chaves_corretas():
    """
    processar_discurso deve retornar lista de dicts com as chaves
    id, discurso_id, texto_chunk e embedding_chunk.
    """
    discurso_id = "abc-123"
    texto = "Sr. Presidente, apoio o projeto de educação básica."

    resultado = processar_discurso(
        discurso_id=discurso_id,
        texto_bruto=texto,
        modelo=_modelo_mock(),
        chunk_size=1000,
        chunk_overlap=200,
    )

    assert len(resultado) == 1
    chunk = resultado[0]
    assert set(chunk.keys()) == {"id", "discurso_id", "texto_chunk", "embedding_chunk"}
    assert chunk["discurso_id"] == discurso_id
    assert chunk["texto_chunk"] == texto


def test_processar_discurso_corrompido_retorna_lista_vazia():
    """
    Discurso marcado como corrompido não deve produzir nenhum chunk nem
    acionar o modelo de embedding.
    """
    modelo = _modelo_mock()

    resultado = processar_discurso(
        discurso_id="xyz-999",
        texto_bruto="[ARQUIVO CORROMPIDO NA ORIGEM]",
        modelo=modelo,
        chunk_size=1000,
        chunk_overlap=200,
    )

    assert resultado == []
    modelo.encode.assert_not_called()


def test_processar_discurso_ids_sao_uuids_validos():
    """
    Cada chunk deve ter um id único e válido no formato UUID v4.
    """
    texto = "Parágrafo sobre a reforma tributária. " * 10
    resultado = processar_discurso(
        discurso_id="def-456",
        texto_bruto=texto,
        modelo=_modelo_mock(),
        chunk_size=100,
        chunk_overlap=20,
    )

    assert len(resultado) > 1
    ids = [chunk["id"] for chunk in resultado]
    for chunk_id in ids:
        parsed = uuid.UUID(chunk_id)
        assert parsed.version == 4
    assert len(set(ids)) == len(ids), "IDs duplicados entre chunks do mesmo discurso"


def test_pipeline_sem_discursos_pendentes_retorna_zero():
    """
    Quando não há discursos para processar, o pipeline retorna 0
    e não aciona nenhum insert.
    """
    supabase, chunks_table = _make_supabase_mock(discursos_data=[])

    total = executar_pipeline_chunking(
        supabase=supabase,
        modelo=_modelo_mock(),
        chunk_size=1000,
        chunk_overlap=200,
    )

    assert total == 0
    chunks_table.insert.assert_not_called()


def test_pipeline_processa_discurso_valido_e_retorna_contagem():
    """
    Um discurso com texto válido deve gerar chunks, acionar o insert
    e retornar a quantidade exata de chunks inseridos.
    """
    discurso_id = "discurso-uuid-001"
    texto = "Sr. Presidente, apoio integralmente o projeto de reforma agrária."
    supabase, chunks_table = _make_supabase_mock(
        discursos_data=[{"id": discurso_id, "texto_bruto": texto}]
    )

    total = executar_pipeline_chunking(
        supabase=supabase,
        modelo=_modelo_mock(),
        chunk_size=1000,
        chunk_overlap=200,
    )

    assert total == 1
    chunks_table.insert.assert_called_once()
    payload = chunks_table.insert.call_args[0][0]
    assert len(payload) == 1
    assert payload[0]["discurso_id"] == discurso_id
    assert payload[0]["texto_chunk"] == texto


def test_pipeline_descarta_discurso_corrompido():
    """
    Discurso com texto corrompido não deve gerar nenhum insert
    e o pipeline deve retornar 0.
    """
    supabase, chunks_table = _make_supabase_mock(
        discursos_data=[{"id": "uuid-corrompido", "texto_bruto": "[ARQUIVO CORROMPIDO NA ORIGEM]"}]
    )

    total = executar_pipeline_chunking(
        supabase=supabase,
        modelo=_modelo_mock(),
        chunk_size=1000,
        chunk_overlap=200,
    )

    assert total == 0
    chunks_table.insert.assert_not_called()
