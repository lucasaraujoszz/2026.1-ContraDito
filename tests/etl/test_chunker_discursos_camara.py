import uuid
from unittest.mock import MagicMock
from etl.chunker_discursos_camara import (
    dividir_em_chunks,
    processar_discurso,
    executar_pipeline_chunking,
)
from etl.utils import para_timestamp


def _make_supabase_mock(discursos_data: list, ids_ja_processados: list | None = None):
    """
    Monta um cliente Supabase falso que responde às queries do pipeline de chunking.
    Retorna (supabase_mock, chunks_table_mock, discursos_table_mock) — o segundo permite verificar se upsert foi chamado.
    """
    if ids_ja_processados is None:
        ids_ja_processados = []

    # Garante que os IDs estejam no formato de dicionário esperado
    ids_processados_dicts = []
    for item in ids_ja_processados:
        if isinstance(item, str):
            ids_processados_dicts.append({"discurso_id": item})
        else:
            ids_processados_dicts.append(item)

    chunks_table = MagicMock()
    chunks_page_1 = MagicMock(data=ids_processados_dicts)
    chunks_page_2 = MagicMock(data=[])
    chunks_table.select.return_value.range.return_value.execute.side_effect = [
        chunks_page_1,
        chunks_page_2,
    ]

    discursos_table = MagicMock()
    disc_page_1 = MagicMock(data=discursos_data)
    disc_page_2 = MagicMock(data=[])
    discursos_table.select.return_value.order.return_value.range.return_value.execute.side_effect = [
        disc_page_1,
        disc_page_2,
    ]

    supabase = MagicMock()
    supabase.table.side_effect = lambda name: (
        chunks_table if name == "camara_discurso_chunks" else discursos_table
    )

    return supabase, chunks_table, discursos_table


def _modelo_mock():
    modelo = MagicMock()
    modelo.encode.return_value = [0.1] * 1024
    return modelo


def _qdrant_mock():
    qdrant = MagicMock()
    qdrant.upsert.return_value = MagicMock()
    return qdrant


def test_dividir_texto_vazio_retorna_lista_vazia():
    """
    Tracer bullet: texto vazio não produz nenhum chunk.
    """
    assert dividir_em_chunks("", chunk_size=1000, chunk_overlap=200) == []


def test_dividir_texto_corrompido_retorna_lista_vazia():
    """
    Textos marcados como corrompidos na origem não devem gerar chunks.
    """
    assert (
        dividir_em_chunks(
            "[ARQUIVO CORROMPIDO NA ORIGEM]", chunk_size=1000, chunk_overlap=200
        )
        == []
    )


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


def test_processar_discurso_retorna_chaves_corretas():
    """
    processar_discurso deve retornar lista de dicts com as chaves
    id, discurso_id e texto_chunk (o embedding vai só para o Qdrant).
    """
    discurso_id = "abc-123"
    texto = "Sr. Presidente, apoio o projeto de educação básica."

    resultado = processar_discurso(
        discurso_id=discurso_id,
        politico_id=475,
        data_discurso="2025-07-09",
        texto_bruto=texto,
        modelo=_modelo_mock(),
        qdrant_client=_qdrant_mock(),
        chunk_size=1000,
        chunk_overlap=200,
    )

    assert len(resultado) == 1
    chunk = resultado[0]
    assert set(chunk.keys()) == {"id", "discurso_id", "texto_chunk"}
    assert chunk["discurso_id"] == discurso_id
    assert chunk["texto_chunk"] == texto


def test_processar_discurso_corrompido_retorna_lista_vazia():
    """
    Discurso marcado como corrompido não deve produzir nenhum chunk, não
    deve acionar o modelo de embedding nem o upsert no Qdrant.
    """
    modelo = _modelo_mock()
    qdrant = _qdrant_mock()

    resultado = processar_discurso(
        discurso_id="xyz-999",
        politico_id=1,
        data_discurso=None,
        texto_bruto="[ARQUIVO CORROMPIDO NA ORIGEM]",
        modelo=modelo,
        qdrant_client=qdrant,
        chunk_size=1000,
        chunk_overlap=200,
    )

    assert resultado == []
    modelo.encode.assert_not_called()
    qdrant.upsert.assert_not_called()


def test_processar_discurso_ids_sao_uuid5_deterministicos():
    """
    Cada chunk deve ter um id único, válido em UUID v5, e reprodutível:
    reprocessar o mesmo discurso gera os mesmos ids (idempotência).
    """
    texto = "Parágrafo sobre a reforma tributária. " * 10

    resultado_1 = processar_discurso(
        discurso_id="def-456",
        politico_id=1,
        data_discurso=None,
        texto_bruto=texto,
        modelo=_modelo_mock(),
        qdrant_client=_qdrant_mock(),
        chunk_size=100,
        chunk_overlap=20,
    )
    resultado_2 = processar_discurso(
        discurso_id="def-456",
        politico_id=1,
        data_discurso=None,
        texto_bruto=texto,
        modelo=_modelo_mock(),
        qdrant_client=_qdrant_mock(),
        chunk_size=100,
        chunk_overlap=20,
    )

    assert len(resultado_1) > 1
    ids_1 = [chunk["id"] for chunk in resultado_1]
    ids_2 = [chunk["id"] for chunk in resultado_2]

    for chunk_id in ids_1:
        parsed = uuid.UUID(chunk_id)
        assert parsed.version == 5
    assert len(set(ids_1)) == len(
        ids_1
    ), "IDs duplicados entre chunks do mesmo discurso"
    assert ids_1 == ids_2, "reprocessar o mesmo discurso deve gerar os mesmos ids"


def test_processar_discurso_envia_payload_correto_ao_qdrant():
    """
    O payload upsertado no Qdrant deve conter politico_id, discurso_id e
    data_discurso (convertida para timestamp Unix em segundos).
    """
    qdrant = _qdrant_mock()

    processar_discurso(
        discurso_id="94bcde33-e9bf-5d42-a3c7-a4fe374c6f3b",
        politico_id=475,
        data_discurso="2025-07-09",
        texto_bruto="Sr. Presidente, apoio o projeto de educação básica.",
        modelo=_modelo_mock(),
        qdrant_client=qdrant,
        chunk_size=1000,
        chunk_overlap=200,
    )

    qdrant.upsert.assert_called_once()
    upsert_call = qdrant.upsert.call_args
    assert upsert_call.kwargs["collection_name"] == "chunks_discursos_embeddings"
    ponto = upsert_call.kwargs["points"][0]
    assert ponto.payload == {
        "politico_id": 475,
        "discurso_id": "94bcde33-e9bf-5d42-a3c7-a4fe374c6f3b",
        "data_discurso": para_timestamp("2025-07-09"),
    }


def test_processar_discurso_casting_defensivo_tipos():
    """
    Verifica se processar_discurso realiza o casting defensivo correto dos
    campos discurso_id (para str) e politico_id (para int ou None) tanto
    no retorno (Supabase) quanto no payload do Qdrant.
    """
    qdrant = _qdrant_mock()

    resultado = processar_discurso(
        discurso_id=12345,  # int que deve virar str
        politico_id="999",  # str que deve virar int
        data_discurso=None,
        texto_bruto="Discurso de teste para validar tipagem.",
        modelo=_modelo_mock(),
        qdrant_client=qdrant,
        chunk_size=1000,
        chunk_overlap=200,
    )

    # 1. Verifica no retorno para o Supabase
    assert len(resultado) == 1
    assert resultado[0]["discurso_id"] == "12345"

    # 2. Verifica no payload para o Qdrant
    qdrant.upsert.assert_called_once()
    ponto = qdrant.upsert.call_args.kwargs["points"][0]
    assert ponto.payload["discurso_id"] == "12345"
    assert ponto.payload["politico_id"] == 999

    # 3. Verifica se politico_id None é preservado sem causar erros
    qdrant_none = _qdrant_mock()
    processar_discurso(
        discurso_id=12345,
        politico_id=None,
        data_discurso=None,
        texto_bruto="Outro teste.",
        modelo=_modelo_mock(),
        qdrant_client=qdrant_none,
        chunk_size=1000,
        chunk_overlap=200,
    )
    ponto_none = qdrant_none.upsert.call_args.kwargs["points"][0]
    assert ponto_none.payload["politico_id"] is None


def test_pipeline_sem_discursos_pendentes_retorna_zero():
    """
    Quando não há discursos para processar, o pipeline retorna 0
    e não aciona nenhum upsert.
    """
    supabase, chunks_table, _ = _make_supabase_mock(discursos_data=[])

    total = executar_pipeline_chunking(
        supabase=supabase,
        modelo=_modelo_mock(),
        qdrant_client=_qdrant_mock(),
        chunk_size=1000,
        chunk_overlap=200,
    )

    assert total == 0
    chunks_table.upsert.assert_not_called()


def test_pipeline_processa_discurso_valido_e_retorna_contagem():
    """
    Um discurso com texto válido deve gerar chunks, acionar o upsert
    e retornar a quantidade exata de chunks inseridos.
    """
    discurso_id = "discurso-uuid-001"
    texto = "Sr. Presidente, apoio integralmente o projeto de reforma agrária."
    supabase, chunks_table, _ = _make_supabase_mock(
        discursos_data=[
            {
                "id": discurso_id,
                "texto_bruto": texto,
                "politico_id": 1,
                "data_discurso": None,
            }
        ]
    )

    total = executar_pipeline_chunking(
        supabase=supabase,
        modelo=_modelo_mock(),
        qdrant_client=_qdrant_mock(),
        chunk_size=1000,
        chunk_overlap=200,
    )

    assert total == 1
    chunks_table.upsert.assert_called_once()
    payload = chunks_table.upsert.call_args[0][0]
    assert len(payload) == 1
    assert payload[0]["discurso_id"] == discurso_id
    assert payload[0]["texto_chunk"] == texto


def test_pipeline_descarta_discurso_corrompido():
    """
    Discurso com texto corrompido não deve gerar nenhum upsert
    e o pipeline deve retornar 0.
    """
    supabase, chunks_table, _ = _make_supabase_mock(
        discursos_data=[
            {
                "id": "uuid-corrompido",
                "texto_bruto": "[ARQUIVO CORROMPIDO NA ORIGEM]",
                "politico_id": 1,
                "data_discurso": None,
            }
        ]
    )

    total = executar_pipeline_chunking(
        supabase=supabase,
        modelo=_modelo_mock(),
        qdrant_client=_qdrant_mock(),
        chunk_size=1000,
        chunk_overlap=200,
    )

    assert total == 0
    chunks_table.upsert.assert_not_called()


def test_pipeline_ordena_discursos_do_mais_novo_para_o_mais_antigo():
    """
    A query de discursos pendentes deve ser ordenada por data_discurso
    decrescente, para processar do mais novo para o mais antigo.
    """
    supabase, _, discursos_table = _make_supabase_mock(discursos_data=[])

    executar_pipeline_chunking(
        supabase=supabase,
        modelo=_modelo_mock(),
        qdrant_client=_qdrant_mock(),
        chunk_size=1000,
        chunk_overlap=200,
    )

    discursos_table.select.return_value.order.assert_called_once_with(
        "data_discurso", desc=True
    )


def test_processar_discurso_camara_qdrant_sub_lotes():
    """
    Garante que a inserção no Qdrant é fatiada em lotes menores (ex: 50 pontos)
    para evitar timeout de rede em discursos muito longos.
    """
    qdrant = _qdrant_mock()
    modelo = _modelo_mock()

    # Texto grande o suficiente para gerar mais de 50 chunks (52 chunks)
    texto_grande = "A" * 52000

    processar_discurso(
        discurso_id="uuid-gigante",
        politico_id=1,
        data_discurso="2023-01-01",
        texto_bruto=texto_grande,
        modelo=modelo,
        qdrant_client=qdrant,
        chunk_size=1000,
        chunk_overlap=0,
    )

    # 52 chunks devem gerar 2 chamadas de upsert no Qdrant (50 no primeiro, 2 no segundo)
    assert qdrant.upsert.call_count == 2
