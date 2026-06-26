import pytest
from unittest.mock import MagicMock

from etl.resumidor_proposicoes import gerar_resumo_executivo


def _mock_gemini_client(resumo: str = "Resumo da proposicao gerado pelo LLM."):
    response = MagicMock()
    response.text = resumo
    client = MagicMock()
    client.models.generate_content.return_value = response
    return client


@pytest.mark.asyncio
async def test_gerar_resumo_executivo_sucesso():
    """
    Tracer bullet: dado um texto válido e um modelo Gemini mockado,
    a função deve retornar a string de resumo produzida pelo LLM.
    """
    texto = "Art. 1º Fica criado o Fundo Nacional de Educação Básica..."
    esperado = "Esta proposição cria o Fundo Nacional de Educação Básica."
    cliente = _mock_gemini_client(esperado)

    resumo = await gerar_resumo_executivo(texto, cliente)

    assert resumo == esperado
    cliente.models.generate_content.assert_called_once()


@pytest.mark.asyncio
async def test_gerar_resumo_texto_vazio_retorna_string_vazia():
    """
    Texto vazio não deve acionar a API Gemini e deve retornar string vazia.
    """
    cliente = _mock_gemini_client()

    resumo = await gerar_resumo_executivo("", cliente)

    assert resumo == ""
    cliente.models.generate_content.assert_not_called()


@pytest.mark.asyncio
async def test_gerar_resumo_usa_modelo_correto():
    """
    A chamada deve usar gemini-1.5-flash (verificado via model_name do objeto).
    """
    cliente = _mock_gemini_client("Resumo qualquer.")
    cliente.model_name = "gemini-2.0-flash"

    await gerar_resumo_executivo("Texto da proposição.", cliente)

    assert cliente.model_name == "gemini-2.0-flash"


@pytest.mark.asyncio
async def test_gerar_resumo_chama_generate_content_com_prompt():
    """
    A chamada deve passar o texto como parte do prompt para generate_content.
    """
    cliente = _mock_gemini_client("Resumo simples.")

    await gerar_resumo_executivo("Texto da proposição.", cliente)

    cliente.models.generate_content.assert_called_once()
    call_kwargs = cliente.models.generate_content.call_args
    prompt_enviado = call_kwargs.kwargs.get("contents") or call_kwargs[1].get(
        "contents", ""
    )
    assert "Texto da proposição." in prompt_enviado


@pytest.mark.asyncio
async def test_gerar_resumo_texto_longo_chamada_unica():
    """
    Textos longos devem ser processados em uma chamada única ao Gemini
    sem a necessidade de Map-Reduce, truncando em 100.000 caracteres.
    """
    texto_longo = "Artigo da proposição legislativa. " * 5000
    esperado = "Resumo da chamada única final."
    cliente = _mock_gemini_client(esperado)

    resultado = await gerar_resumo_executivo(texto_longo, cliente)

    assert resultado == esperado
    cliente.models.generate_content.assert_called_once()
    call_kwargs = cliente.models.generate_content.call_args
    prompt_enviado = call_kwargs.kwargs.get("contents") or call_kwargs[1].get(
        "contents", ""
    )
    assert len(prompt_enviado) <= 105_000
