import pytest
from unittest.mock import MagicMock

from etl.resumidor_proposicoes import gerar_resumo_executivo


def _mock_groq_client(resumo: str = "Resumo da proposicao gerado pelo LLM."):
    choice = MagicMock()
    choice.message.content = resumo
    response = MagicMock()
    response.choices = [choice]
    client = MagicMock()
    client.chat.completions.create.return_value = response
    return client


@pytest.mark.asyncio
async def test_gerar_resumo_executivo_sucesso():
    """
    Tracer bullet: dado um texto válido e um cliente Groq mockado,
    a função deve retornar a string de resumo produzida pelo LLM.
    """
    texto = "Art. 1º Fica criado o Fundo Nacional de Educação Básica..."
    esperado = "Esta proposição cria o Fundo Nacional de Educação Básica."
    cliente = _mock_groq_client(esperado)

    resumo = await gerar_resumo_executivo(texto, cliente)

    assert resumo == esperado
    cliente.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_gerar_resumo_texto_vazio_retorna_string_vazia():
    """
    Texto vazio não deve acionar a API Groq e deve retornar string vazia.
    """
    cliente = _mock_groq_client()

    resumo = await gerar_resumo_executivo("", cliente)

    assert resumo == ""
    cliente.chat.completions.create.assert_not_called()


@pytest.mark.asyncio
async def test_gerar_resumo_usa_modelo_correto():
    """
    A chamada à API Groq deve usar o modelo llama-3.1-8b-instant.
    """
    cliente = _mock_groq_client("Resumo qualquer.")

    await gerar_resumo_executivo("Texto da proposição.", cliente)

    call_kwargs = cliente.chat.completions.create.call_args
    assert call_kwargs.kwargs["model"] == "llama-3.1-8b-instant"
