from unittest.mock import MagicMock, patch
from qdrant_client.models import ScoredPoint

# Importa funções da Câmara
from etl.vinculador_discursos_votos_camara import (
    filtrar_chunks_validos as filtrar_camara,
    resolver_textos_chunks as resolver_camara,
    _buscar_embedding_proposicao as buscar_camara,
    executar_pipeline_vinculo_camara,
)

# Importa funções do Senado
from etl.vinculador_discursos_votos_senado import (
    filtrar_chunks_validos as filtrar_senado,
    resolver_textos_chunks as resolver_senado,
    _buscar_embedding_proposicao as buscar_senado,
    executar_pipeline_vinculo_senado,
)


def test_booster_filtrar_chunks_validos_limit():
    chunks = [
        ScoredPoint(
            id="c1",
            score=0.9,
            version=1,
            payload={"discurso_id": "d1", "data_discurso": 100},
        ),
        ScoredPoint(
            id="c2",
            score=0.8,
            version=1,
            payload={"discurso_id": "d2", "data_discurso": 200},
        ),
    ]

    res1 = filtrar_camara(chunks, threshold=0.7, limit=1)
    assert len(res1) == 1

    res2 = filtrar_senado(chunks, threshold=0.7, limit=1)
    assert len(res2) == 1


def test_booster_resolver_textos_chunks_empty_or_error():
    mock_supabase = MagicMock()

    assert resolver_camara(mock_supabase, [], [], "camara_chunks") == []
    assert resolver_senado(mock_supabase, [], [], "senado_chunks") == []

    mock_supabase.table.return_value.select.return_value.in_.return_value.execute.side_effect = Exception(
        "Erro DB"
    )
    assert (
        resolver_camara(mock_supabase, ["c1"], [{"chunk_id": "c1"}], "camara_chunks")
        == []
    )
    assert (
        resolver_senado(mock_supabase, ["c1"], [{"chunk_id": "c1"}], "senado_chunks")
        == []
    )


def test_booster_buscar_embedding_proposicao_empty_or_error():
    mock_qdrant = MagicMock()

    mock_qdrant.scroll.return_value = ([], None)
    assert buscar_camara(mock_qdrant, "prop-1") is None
    assert buscar_senado(mock_qdrant, "prop-1") is None

    mock_qdrant.scroll.side_effect = Exception("Erro Qdrant")
    assert buscar_camara(mock_qdrant, "prop-1") is None
    assert buscar_senado(mock_qdrant, "prop-1") is None


def test_booster_executar_pipeline_empty_votos():
    mock_supabase = MagicMock()
    mock_qdrant = MagicMock()

    mock_supabase.table.return_value.select.return_value.is_.return_value.in_.return_value.range.return_value.execute.return_value.data = (
        []
    )

    assert executar_pipeline_vinculo_camara(mock_supabase, mock_qdrant) == 0
    assert executar_pipeline_vinculo_senado(mock_supabase, mock_qdrant) == 0


def test_booster_executar_pipeline_limite_votos():
    mock_supabase = MagicMock()
    mock_qdrant = MagicMock()

    votos = [{"id": "v1", "proposicao_id": "p1", "politico_id": 1}] * 5
    mock_supabase.table.return_value.select.return_value.is_.return_value.in_.return_value.range.return_value.execute.return_value.data = (
        votos
    )

    with patch(
        "etl.vinculador_discursos_votos_camara._buscar_embedding_proposicao"
    ) as mock_embed_camara:
        mock_embed_camara.return_value = None
        res_camara = executar_pipeline_vinculo_camara(
            mock_supabase, mock_qdrant, limite_votos=2
        )
        assert res_camara == 0

    with patch(
        "etl.vinculador_discursos_votos_senado._buscar_embedding_proposicao"
    ) as mock_embed_senado:
        mock_embed_senado.return_value = None
        res_senado = executar_pipeline_vinculo_senado(
            mock_supabase, mock_qdrant, limite_votos=2
        )
        assert res_senado == 0
