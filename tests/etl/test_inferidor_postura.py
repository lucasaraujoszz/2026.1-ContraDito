import pytest
from unittest.mock import MagicMock

from etl.inferidor_postura import inferir_postura, calcular_coerencia


def _mock_gemini(resposta_texto: str):
    response = MagicMock()
    response.text = resposta_texto
    cliente = MagicMock()
    cliente.models.generate_content.return_value = response
    return cliente


# --- inferir_postura ---


@pytest.mark.asyncio
async def test_inferir_postura_favoravel():
    """
    Tracer bullet: LLM retornando JSON válido com FAVORÁVEL deve ser
    parseado corretamente.
    """
    gemini = _mock_gemini(
        '{"postura": "FAVORÁVEL", "justificativa": "O parlamentar apoiou medidas similares."}'
    )

    resultado = await inferir_postura(
        resumo_proposicao="Propõe acompanhante para mulheres em consultas.",
        chunks=["O deputado defendeu os direitos das mulheres."],
        gemini_client=gemini,
    )

    assert resultado["postura"] == "FAVORÁVEL"
    assert "parlamentar" in resultado["justificativa"]


@pytest.mark.asyncio
async def test_inferir_postura_contrario():
    """
    LLM retornando CONTRÁRIO deve ser parseado corretamente.
    """
    gemini = _mock_gemini(
        '{"postura": "CONTRÁRIO", "justificativa": "Discursos indicam oposição."}'
    )

    resultado = await inferir_postura(
        resumo_proposicao="Propõe aumento de impostos.",
        chunks=["O deputado criticou o aumento da carga tributária."],
        gemini_client=gemini,
    )

    assert resultado["postura"] == "CONTRÁRIO"


@pytest.mark.asyncio
async def test_inferir_postura_com_ruido_no_json():
    """
    LLM às vezes retorna texto antes ou depois do JSON — o parser deve
    extrair o JSON mesmo assim.
    """
    gemini = _mock_gemini(
        'Aqui está minha análise:\n```json\n{"postura": "FAVORÁVEL", "justificativa": "Consistente."}\n```'
    )

    resultado = await inferir_postura(
        resumo_proposicao="Qualquer proposição.",
        chunks=["Qualquer discurso."],
        gemini_client=gemini,
    )

    assert resultado["postura"] == "FAVORÁVEL"


@pytest.mark.asyncio
async def test_inferir_postura_sem_chunks_retorna_none():
    """
    Sem chunks disponíveis não há contexto para inferir — deve retornar None.
    """
    gemini = _mock_gemini('{"postura": "FAVORÁVEL", "justificativa": "x"}')

    resultado = await inferir_postura(
        resumo_proposicao="Qualquer proposição.",
        chunks=[],
        gemini_client=gemini,
    )

    assert resultado is None
    gemini.models.generate_content.assert_not_called()


# --- calcular_coerencia ---


def test_coerencia_sim_favoravel():
    assert calcular_coerencia("Sim", "FAVORÁVEL") is True


def test_coerencia_nao_contrario():
    assert calcular_coerencia("Não", "CONTRÁRIO") is True


def test_coerencia_sim_contrario():
    assert calcular_coerencia("Sim", "CONTRÁRIO") is False


def test_coerencia_nao_favoravel():
    assert calcular_coerencia("Não", "FAVORÁVEL") is False


def test_coerencia_ausente_retorna_none():
    """Abstenções e ausências não entram no denominador (RF27)."""
    assert calcular_coerencia("AUSENTE", "FAVORÁVEL") is None
    assert calcular_coerencia("ABSTENÇÃO", "CONTRÁRIO") is None
    assert calcular_coerencia("NÃO COMPARECEU", "FAVORÁVEL") is None
