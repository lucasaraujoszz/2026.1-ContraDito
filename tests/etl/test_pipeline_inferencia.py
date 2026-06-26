import pytest
from unittest.mock import MagicMock

from etl.pipeline_inferencia import executar_pipeline_inferencia


def _mock_gemini(
    postura: str = "FAVORÁVEL", justificativa: str = "Justificativa teste."
):
    response = MagicMock()
    response.text = f'{{"postura": "{postura}", "justificativa": "{justificativa}"}}'
    cliente = MagicMock()
    cliente.models.generate_content.return_value = response
    return cliente


def _make_qdrant_mock(vetor_proposicao: list | None, chunk_ids: list[str]):
    qdrant = MagicMock()

    if vetor_proposicao is None:
        qdrant.scroll.return_value = ([], None)
    else:
        ponto_proposicao = MagicMock()
        ponto_proposicao.vector = vetor_proposicao
        qdrant.scroll.return_value = ([ponto_proposicao], None)

    pontos_chunks = []
    for chunk_id in chunk_ids:
        ponto = MagicMock()
        ponto.id = chunk_id
        pontos_chunks.append(ponto)
    resposta_query = MagicMock()
    resposta_query.points = pontos_chunks
    qdrant.query_points.return_value = resposta_query

    return qdrant


def _make_supabase_mock(votos: list, proposicao: dict, chunks: list):
    sb = MagicMock()

    # proposicao_id das fixtures de votos para o pré-filtro de proposições com resumo
    ids_props = list({v["proposicao_id"] for v in votos}) if votos else ["pl_x"]

    votos_tabela = MagicMock()
    # select().is_().in_().execute() ou .limit().execute() — votos pendentes de inferência
    filtro_votos = votos_tabela.select.return_value.is_.return_value.in_.return_value
    filtro_votos.execute.return_value.data = votos
    filtro_votos.limit.return_value.execute.return_value.data = votos
    votos_tabela.update.return_value.eq.return_value.execute.return_value = MagicMock()

    props_tabela = MagicMock()
    # select().not_.is_().execute() — pré-filtro: proposições com resumo
    props_tabela.select.return_value.not_.is_.return_value.execute.return_value.data = [
        {"proposicao_id": pid} for pid in ids_props
    ]
    # select().eq().single().execute() — busca detalhes da proposição
    props_tabela.select.return_value.eq.return_value.single.return_value.execute.return_value.data = (
        proposicao
    )

    chunks_tabela = MagicMock()
    # select().in_().execute() — textos dos chunks encontrados no Qdrant
    chunks_tabela.select.return_value.in_.return_value.execute.return_value.data = (
        chunks
    )

    def _table(nome: str):
        return {
            "camara_votos": votos_tabela,
            "camara_proposicoes": props_tabela,
            "camara_discurso_chunks": chunks_tabela,
        }[nome]

    sb.table.side_effect = _table

    return sb, votos_tabela


@pytest.mark.asyncio
async def test_pipeline_sem_votos_pendentes_retorna_zero():
    """
    Tracer bullet: sem votos pendentes o pipeline retorna 0 sem acionar o LLM.
    """
    sb, votos_tabela = _make_supabase_mock(votos=[], proposicao={}, chunks=[])
    qdrant = _make_qdrant_mock(vetor_proposicao=None, chunk_ids=[])

    total = await executar_pipeline_inferencia(sb, _mock_gemini(), qdrant)

    assert total == 0
    votos_tabela.update.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_infere_e_salva_resultado():
    """
    Com um voto pendente, embedding da proposição e chunks disponíveis no
    Qdrant, o pipeline deve inferir a postura via Gemini e salvar o
    resultado em camara_votos.
    """
    voto = {
        "id": "voto-uuid-1",
        "proposicao_id": "pl_1042_2022",
        "politico_id": 220615,
        "voto_oficial": "Sim",
    }
    proposicao = {
        "resumo_executivo": "Propõe benefício social.",
        "data_votacao": "2023-05-10",
    }
    chunks = [
        {"texto_chunk": "O deputado apoiou políticas sociais."},
        {"texto_chunk": "Defendo programas de assistência."},
    ]

    sb, votos_tabela = _make_supabase_mock([voto], proposicao, chunks)
    qdrant = _make_qdrant_mock(
        vetor_proposicao=[0.1] * 8, chunk_ids=["chunk-1", "chunk-2"]
    )
    gemini = _mock_gemini("FAVORÁVEL", "Consistente com discursos.")

    total = await executar_pipeline_inferencia(sb, gemini, qdrant)

    assert total == 1
    votos_tabela.update.assert_called_once()
    payload = votos_tabela.update.call_args[0][0]
    assert payload["inferencia_ia"] == "FAVORÁVEL"
    assert payload["justificativa"] == "Consistente com discursos."
    assert payload["eh_coerente"] is True  # Sim + FAVORÁVEL = coerente


@pytest.mark.asyncio
async def test_pipeline_voto_incoerente():
    """
    Voto Não + postura FAVORÁVEL → eh_coerente deve ser False.
    """
    voto = {
        "id": "v2",
        "proposicao_id": "pl_x",
        "politico_id": 1,
        "voto_oficial": "Não",
    }
    proposicao = {"resumo_executivo": "Texto.", "data_votacao": "2023-01-01"}
    chunks = [{"texto_chunk": "Discurso favorável."}]

    sb, votos_tabela = _make_supabase_mock([voto], proposicao, chunks)
    qdrant = _make_qdrant_mock(vetor_proposicao=[0.0] * 8, chunk_ids=["chunk-1"])

    await executar_pipeline_inferencia(sb, _mock_gemini("FAVORÁVEL"), qdrant)

    payload = votos_tabela.update.call_args[0][0]
    assert payload["eh_coerente"] is False


@pytest.mark.asyncio
async def test_pipeline_pula_voto_sem_chunks():
    """
    Se a busca no Qdrant não retornar chunks para aquele deputado, o voto
    é ignorado e não deve acionar o LLM nem fazer update.
    """
    voto = {
        "id": "v3",
        "proposicao_id": "pl_x",
        "politico_id": 999,
        "voto_oficial": "Sim",
    }
    proposicao = {"resumo_executivo": "Texto.", "data_votacao": "2023-01-01"}

    sb, votos_tabela = _make_supabase_mock([voto], proposicao, chunks=[])
    qdrant = _make_qdrant_mock(vetor_proposicao=[0.0] * 8, chunk_ids=[])
    gemini = _mock_gemini()

    total = await executar_pipeline_inferencia(sb, gemini, qdrant)

    assert total == 0
    votos_tabela.update.assert_not_called()
    gemini.models.generate_content.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_pula_voto_sem_embedding_proposicao():
    """
    Se a proposição não tiver embedding indexado no Qdrant, o voto é
    ignorado antes de buscar chunks ou acionar o LLM.
    """
    voto = {
        "id": "v5",
        "proposicao_id": "pl_y",
        "politico_id": 1,
        "voto_oficial": "Sim",
    }
    proposicao = {"resumo_executivo": "Texto.", "data_votacao": "2023-01-01"}

    sb, votos_tabela = _make_supabase_mock([voto], proposicao, chunks=[])
    qdrant = _make_qdrant_mock(vetor_proposicao=None, chunk_ids=["chunk-1"])
    gemini = _mock_gemini()

    total = await executar_pipeline_inferencia(sb, gemini, qdrant)

    assert total == 0
    votos_tabela.update.assert_not_called()
    gemini.models.generate_content.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_pula_voto_ausente():
    """
    Voto AUSENTE não deve acionar inferência (RF27).
    """
    voto = {
        "id": "v4",
        "proposicao_id": "pl_x",
        "politico_id": 1,
        "voto_oficial": "AUSENTE",
    }
    proposicao = {"resumo_executivo": "Texto.", "data_votacao": "2023-01-01"}
    chunks = [{"texto_chunk": "Discurso qualquer."}]

    sb, votos_tabela = _make_supabase_mock([voto], proposicao, chunks)
    qdrant = _make_qdrant_mock(vetor_proposicao=[0.0] * 8, chunk_ids=["chunk-1"])
    gemini = _mock_gemini()

    total = await executar_pipeline_inferencia(sb, gemini, qdrant)

    assert total == 0
    votos_tabela.update.assert_not_called()
    gemini.models.generate_content.assert_not_called()
