import pytest
from qdrant_client.models import ScoredPoint
from etl.vinculador_discursos_votos_senado import (
    filtrar_chunks_validos,
    resolver_textos_chunks,
    executar_pipeline_vinculo_senado,
)


def test_filtrar_chunks_ignora_abaixo_do_threshold_e_limita_tres():
    # Arrange: List of ScoredPoints from Qdrant with mixed scores
    chunks_brutos = [
        ScoredPoint(
            id="chunk-1",
            score=0.90,
            version=1,
            payload={"discurso_id": "disc-1", "data_discurso": 1000},
        ),
        ScoredPoint(
            id="chunk-2",
            score=0.74,
            version=1,
            payload={"discurso_id": "disc-2", "data_discurso": 2000},
        ),
        ScoredPoint(
            id="chunk-3",
            score=0.85,
            version=1,
            payload={"discurso_id": "disc-3", "data_discurso": 3000},
        ),
        ScoredPoint(
            id="chunk-4",
            score=0.76,
            version=1,
            payload={"discurso_id": "disc-4", "data_discurso": 4000},
        ),
        ScoredPoint(
            id="chunk-5",
            score=0.80,
            version=1,
            payload={"discurso_id": "disc-5", "data_discurso": 5000},
        ),
        ScoredPoint(
            id="chunk-6",
            score=0.60,
            version=1,
            payload={"discurso_id": "disc-6", "data_discurso": 6000},
        ),
    ]

    # Act: Run the filtering logic
    resultado = filtrar_chunks_validos(chunks_brutos, threshold=0.75, limit=3)

    # Assert
    assert len(resultado) == 3
    assert resultado[0]["id"] == "chunk-1"
    assert resultado[0]["score"] == 0.90
    assert resultado[0]["discurso_id"] == "disc-1"
    assert resultado[0]["data_discurso"] == 1000

    assert resultado[1]["id"] == "chunk-3"
    assert resultado[1]["score"] == 0.85
    assert resultado[1]["discurso_id"] == "disc-3"
    assert resultado[1]["data_discurso"] == 3000

    assert resultado[2]["id"] == "chunk-5"
    assert resultado[2]["score"] == 0.80
    assert resultado[2]["discurso_id"] == "disc-5"
    assert resultado[2]["data_discurso"] == 5000


def test_voto_sem_discursos_acima_do_threshold_retorna_lista_vazia():
    # Scenario A: Qdrant returns empty list
    resultado_vazio = filtrar_chunks_validos([], threshold=0.75)
    assert resultado_vazio == []

    # Scenario B: Qdrant returns results but all are below threshold
    chunks_baixos = [
        ScoredPoint(id="chunk-1", score=0.70, version=1),
        ScoredPoint(id="chunk-2", score=0.65, version=1),
    ]
    resultado_baixos = filtrar_chunks_validos(chunks_baixos, threshold=0.75)
    assert resultado_baixos == []


def test_filtrar_chunks_sem_limite_retorna_todos_acima_do_threshold():
    chunks_brutos = [
        ScoredPoint(
            id="chunk-1",
            score=0.90,
            version=1,
            payload={"discurso_id": "disc-1", "data_discurso": 1000},
        ),
        ScoredPoint(
            id="chunk-2",
            score=0.74,
            version=1,
            payload={"discurso_id": "disc-2", "data_discurso": 2000},
        ),
        ScoredPoint(
            id="chunk-3",
            score=0.85,
            version=1,
            payload={"discurso_id": "disc-3", "data_discurso": 3000},
        ),
        ScoredPoint(
            id="chunk-4",
            score=0.76,
            version=1,
            payload={"discurso_id": "disc-4", "data_discurso": 4000},
        ),
    ]
    resultado = filtrar_chunks_validos(chunks_brutos, threshold=0.75, limit=None)
    assert len(resultado) == 3
    assert resultado[0]["id"] == "chunk-1"
    assert resultado[1]["id"] == "chunk-3"
    assert resultado[2]["id"] == "chunk-4"


def test_resolver_textos_combina_texto_com_score_e_ignora_itens_inexistentes():
    from unittest.mock import MagicMock

    # Arrange
    chunks_com_score = [
        {"id": "chunk-1", "score": 0.90, "discurso_id": "d-1", "data_discurso": 10},
        {"id": "chunk-2", "score": 0.85, "discurso_id": "d-2", "data_discurso": 20},
        {
            "id": "chunk-3",
            "score": 0.80,
            "discurso_id": "d-3",
            "data_discurso": 30,
        },  # Missing in Supabase
    ]
    chunk_ids = ["chunk-1", "chunk-2", "chunk-3"]

    # Mock database records
    db_data = [
        {"id": "chunk-2", "texto_chunk": "Texto do chunk 2"},
        {"id": "chunk-1", "texto_chunk": "Texto do chunk 1"},
    ]

    tabela_mock = MagicMock()
    tabela_mock.select.return_value.in_.return_value.execute.return_value.data = db_data
    supabase_mock = MagicMock()
    supabase_mock.table.return_value = tabela_mock

    # Act
    resultado = resolver_textos_chunks(
        supabase_client=supabase_mock,
        chunk_ids=chunk_ids,
        chunks_com_score=chunks_com_score,
        tabela_chunks="senado_discurso_chunks",
    )

    # Assert
    tabela_mock.select.assert_called_once_with("id, texto_chunk")
    tabela_mock.select.return_value.in_.assert_called_once_with("id", chunk_ids)

    assert len(resultado) == 2

    # Ordering must match chunks_com_score (chunk-1 first, then chunk-2)
    assert resultado[0]["chunk_id"] == "chunk-1"
    assert resultado[0]["texto_chunk"] == "Texto do chunk 1"
    assert resultado[0]["score"] == 0.90
    assert resultado[0]["discurso_id"] == "d-1"
    assert resultado[0]["data_discurso"] == 10

    assert resultado[1]["chunk_id"] == "chunk-2"
    assert resultado[1]["texto_chunk"] == "Texto do chunk 2"
    assert resultado[1]["score"] == 0.85
    assert resultado[1]["discurso_id"] == "d-2"
    assert resultado[1]["data_discurso"] == 20


def test_pipeline_reutiliza_embedding_da_proposicao_em_cache():
    from unittest.mock import MagicMock

    # Arrange
    votos_fake = [
        {
            "id": "voto-1",
            "proposicao_id": "prop-1",
            "politico_id": 101,
            "voto_oficial": "Sim",
        },
        {
            "id": "voto-2",
            "proposicao_id": "prop-1",
            "politico_id": 102,
            "voto_oficial": "Não",
        },
    ]

    tabela_votos_mock = MagicMock()
    tabela_votos_mock.select.return_value.is_.return_value.in_.return_value.range.return_value.execute.return_value.data = (
        votos_fake
    )
    tabela_votos_mock.update.return_value.eq.return_value.execute.return_value = (
        MagicMock()
    )

    tabela_chunks_mock = MagicMock()
    tabela_chunks_mock.select.return_value.in_.return_value.execute.return_value.data = [
        {"id": "chunk-1", "texto_chunk": "Texto chunk 1"}
    ]

    tabela_logs_mock = MagicMock()

    supabase_mock = MagicMock()

    def get_table(name):
        if name == "senado_votos":
            return tabela_votos_mock
        elif name == "senado_discurso_chunks":
            return tabela_chunks_mock
        elif name == "etl_logs":
            return tabela_logs_mock
        return MagicMock()

    supabase_mock.table.side_effect = get_table

    qdrant_mock = MagicMock()
    fake_point = MagicMock()
    fake_point.vector = [0.1, 0.2, 0.3]
    qdrant_mock.scroll.return_value = ([fake_point], None)

    fake_point_search = MagicMock()
    fake_point_search.id = "chunk-1"
    fake_point_search.score = 0.85

    query_response_mock = MagicMock()
    query_response_mock.points = [fake_point_search]
    qdrant_mock.query_points.return_value = query_response_mock

    # Act
    total_processados = executar_pipeline_vinculo_senado(
        supabase_client=supabase_mock, qdrant_client=qdrant_mock, threshold=0.75
    )

    # Assert
    assert total_processados == 2
    assert qdrant_mock.scroll.call_count == 1  # Verify caching
    assert qdrant_mock.query_points.call_count == 2


def test_pipeline_completo_vincula_votos_e_registra_etl_log():
    from unittest.mock import MagicMock

    # Arrange
    votos_fake = [
        {
            "id": "voto-abc",
            "proposicao_id": "prop-x",
            "politico_id": 99,
            "voto_oficial": "Sim",
        }
    ]

    tabela_votos_mock = MagicMock()
    tabela_votos_mock.select.return_value.is_.return_value.in_.return_value.range.return_value.execute.return_value.data = (
        votos_fake
    )
    tabela_votos_mock.update.return_value.eq.return_value.execute.return_value = (
        MagicMock()
    )

    tabela_chunks_mock = MagicMock()
    tabela_chunks_mock.select.return_value.in_.return_value.execute.return_value.data = [
        {"id": "chunk-10", "texto_chunk": "Texto discurso relevante"}
    ]

    tabela_logs_mock = MagicMock()
    tabela_logs_mock.insert.return_value.execute.return_value = MagicMock()

    supabase_mock = MagicMock()

    def get_table(name):
        if name == "senado_votos":
            return tabela_votos_mock
        elif name == "senado_discurso_chunks":
            return tabela_chunks_mock
        elif name == "etl_logs":
            return tabela_logs_mock
        return MagicMock()

    supabase_mock.table.side_effect = get_table

    qdrant_mock = MagicMock()
    fake_point = MagicMock()
    fake_point.vector = [0.9, 0.9, 0.9]
    qdrant_mock.scroll.return_value = ([fake_point], None)

    fake_point_search = MagicMock()
    fake_point_search.id = "chunk-10"
    fake_point_search.score = 0.88
    fake_point_search.payload = {"discurso_id": "disc-abc", "data_discurso": 99999}

    query_response_mock = MagicMock()
    query_response_mock.points = [fake_point_search]
    qdrant_mock.query_points.return_value = query_response_mock

    # Act
    total_processados = executar_pipeline_vinculo_senado(
        supabase_client=supabase_mock, qdrant_client=qdrant_mock, threshold=0.75
    )

    # Assert
    assert total_processados == 1

    # Check that update was called with the correct payload containing resolved text, score, discurso_id and data_discurso
    tabela_votos_mock.update.assert_called_once_with(
        {
            "chunks_proximos": [
                {
                    "chunk_id": "chunk-10",
                    "discurso_id": "disc-abc",
                    "data_discurso": 99999,
                    "texto_chunk": "Texto discurso relevante",
                    "score": 0.88,
                }
            ]
        }
    )
    tabela_votos_mock.update.return_value.eq.assert_called_once_with("id", "voto-abc")

    # Check etl_logs call
    tabela_logs_mock.insert.assert_called_once()
    args_log = tabela_logs_mock.insert.call_args[0][0]
    assert args_log["nome_rotina"] == "vinculo_chunks_votos_senado"
    assert args_log["status"] == "Concluído"
    assert args_log["linhas_afetadas"] == 1
    assert args_log["detalhe_erro"] is None


def test_pipeline_erro_registra_etl_log_com_erro():
    from unittest.mock import MagicMock

    # Arrange
    tabela_votos_mock = MagicMock()
    tabela_votos_mock.select.side_effect = Exception("Supabase Database Disconnected")

    tabela_logs_mock = MagicMock()
    tabela_logs_mock.insert.return_value.execute.return_value = MagicMock()

    supabase_mock = MagicMock()

    def get_table(name):
        if name == "senado_votos":
            return tabela_votos_mock
        elif name == "etl_logs":
            return tabela_logs_mock
        return MagicMock()

    supabase_mock.table.side_effect = get_table

    qdrant_mock = MagicMock()

    # Act & Assert
    with pytest.raises(Exception) as exc_info:
        executar_pipeline_vinculo_senado(
            supabase_client=supabase_mock, qdrant_client=qdrant_mock, threshold=0.75
        )

    assert "Supabase Database Disconnected" in str(exc_info.value)

    # Check etl_logs call
    tabela_logs_mock.insert.assert_called_once()
    args_log = tabela_logs_mock.insert.call_args[0][0]
    assert args_log["nome_rotina"] == "vinculo_chunks_votos_senado"
    assert args_log["status"] == "Erro"
    assert args_log["linhas_afetadas"] == 0
    assert "Supabase Database Disconnected" in args_log["detalhe_erro"]
