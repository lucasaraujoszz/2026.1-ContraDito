import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from etl.pipeline_inferencia import executar_pipeline_inferencia


def _mock_groq(postura: str = "FAVORÁVEL", justificativa: str = "Justificativa teste."):
    choice = MagicMock()
    choice.message.content = f'{{"postura": "{postura}", "justificativa": "{justificativa}"}}'
    response = MagicMock()
    response.choices = [choice]
    cliente = MagicMock()
    cliente.chat.completions.create.return_value = response
    return cliente


def _make_supabase_mock(votos: list, proposicao: dict, chunks_rpc: list):
    sb = MagicMock()

    # proposicao_id das fixtures de votos para o pré-filtro
    ids_props = list({v["proposicao_id"] for v in votos}) if votos else ["pl_x"]

    votos_tabela = MagicMock()
    # select().is_().in_().execute()  — query filtrada por proposições com resumo
    votos_tabela.select.return_value.is_.return_value.in_.return_value.execute.return_value.data = votos
    votos_tabela.update.return_value.eq.return_value.execute.return_value = MagicMock()

    props_tabela = MagicMock()
    # select().not_.is_().execute()  — pré-filtro: proposições com resumo
    props_tabela.select.return_value.not_.is_.return_value.execute.return_value.data = [
        {"proposicao_id": pid} for pid in ids_props
    ]
    # select().eq().single().execute()  — busca detalhes da proposição
    props_tabela.select.return_value.eq.return_value.single.return_value.execute.return_value.data = proposicao

    sb.table.side_effect = lambda name: votos_tabela if name == "camara_votos" else props_tabela
    sb.rpc.return_value.execute.return_value.data = chunks_rpc

    return sb, votos_tabela


@pytest.mark.asyncio
async def test_pipeline_sem_votos_pendentes_retorna_zero():
    """
    Tracer bullet: sem votos pendentes o pipeline retorna 0 sem acionar o LLM.
    """
    sb, votos_tabela = _make_supabase_mock(votos=[], proposicao={}, chunks_rpc=[])

    total = await executar_pipeline_inferencia(sb, _mock_groq())

    assert total == 0
    votos_tabela.update.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_infere_e_salva_resultado():
    """
    Com um voto pendente e chunks disponíveis, o pipeline deve:
    - chamar a RPC de busca
    - invocar o LLM
    - salvar inferencia_ia, justificativa e eh_coerente no voto
    - retornar 1
    """
    voto = {
        "id": "voto-uuid-1",
        "proposicao_id": "pl_1042_2022",
        "politico_id": 220615,
        "voto_oficial": "Sim",
    }
    proposicao = {
        "resumo_executivo": "Propõe benefício social.",
        "embedding_resumo_executivo": [0.1] * 1024,
        "data_votacao": "2023-05-10T00:00:00",
    }
    chunks_rpc = [
        {"texto_chunk": "O deputado apoiou políticas sociais.", "similaridade": 0.6},
        {"texto_chunk": "Defendo programas de assistência.", "similaridade": 0.55},
    ]

    sb, votos_tabela = _make_supabase_mock([voto], proposicao, chunks_rpc)

    total = await executar_pipeline_inferencia(sb, _mock_groq("FAVORÁVEL", "Consistente com discursos."))

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
    voto = {"id": "v2", "proposicao_id": "pl_x", "politico_id": 1, "voto_oficial": "Não"}
    proposicao = {
        "resumo_executivo": "Texto.",
        "embedding_resumo_executivo": [0.0] * 1024,
        "data_votacao": "2023-01-01T00:00:00",
    }
    chunks_rpc = [{"texto_chunk": "Discurso favorável.", "similaridade": 0.7}]

    sb, votos_tabela = _make_supabase_mock([voto], proposicao, chunks_rpc)

    await executar_pipeline_inferencia(sb, _mock_groq("FAVORÁVEL"))

    payload = votos_tabela.update.call_args[0][0]
    assert payload["eh_coerente"] is False


@pytest.mark.asyncio
async def test_pipeline_pula_voto_sem_chunks():
    """
    Se a RPC não retornar chunks para aquele deputado, o voto é ignorado
    e não deve acionar o LLM nem fazer update.
    """
    voto = {"id": "v3", "proposicao_id": "pl_x", "politico_id": 999, "voto_oficial": "Sim"}
    proposicao = {
        "resumo_executivo": "Texto.",
        "embedding_resumo_executivo": [0.0] * 1024,
        "data_votacao": "2023-01-01T00:00:00",
    }

    sb, votos_tabela = _make_supabase_mock([voto], proposicao, chunks_rpc=[])

    total = await executar_pipeline_inferencia(sb, _mock_groq())

    assert total == 0
    votos_tabela.update.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_pula_voto_ausente():
    """
    Voto AUSENTE não deve acionar inferência (RF27).
    """
    voto = {"id": "v4", "proposicao_id": "pl_x", "politico_id": 1, "voto_oficial": "AUSENTE"}
    proposicao = {
        "resumo_executivo": "Texto.",
        "embedding_resumo_executivo": [0.0] * 1024,
        "data_votacao": "2023-01-01T00:00:00",
    }
    chunks_rpc = [{"texto_chunk": "Discurso qualquer.", "similaridade": 0.7}]

    sb, votos_tabela = _make_supabase_mock([voto], proposicao, chunks_rpc)
    groq = _mock_groq()

    total = await executar_pipeline_inferencia(sb, groq)

    assert total == 0
    groq.chat.completions.create.assert_not_called()
