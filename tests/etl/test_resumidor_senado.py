import pytest
from unittest.mock import MagicMock
from google.genai import types

# Importação da função que será implementada na fase GREEN (atualmente deve causar ImportError)
from etl.resumidor_senado import gerar_resumo_executivo_senado


@pytest.mark.asyncio
async def test_gerar_resumo_senado_configuracoes_seguranca():
    """
    Tracer bullet: Garante que o resumidor do Senado chama o Gemini 2.5 Flash Lite
    com os filtros de segurança desligados (BLOCK_NONE) e o prompt correto.
    """
    # Mock do cliente google-genai
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Resumo seguro do Senado gerado pelo Gemini."
    mock_client.models.generate_content.return_value = mock_response

    texto_pdf = "Art. 1º Fica instituído o programa polêmico..."

    resumo = await gerar_resumo_executivo_senado(texto_pdf, mock_client)

    assert resumo == "Resumo seguro do Senado gerado pelo Gemini."

    # Verifica a chamada do client
    mock_client.models.generate_content.assert_called_once()
    call_kwargs = mock_client.models.generate_content.call_args.kwargs

    assert call_kwargs["model"] == "gemini-2.5-flash-lite"

    # Valida se o conteúdo enviado possui a essência do prompt da Câmara
    conteudo = call_kwargs["contents"]
    assert "RESUMO EXECUTIVO" in conteudo
    assert (
        "PROIBIDO" in conteudo
    ), "O prompt deve proibir explicitamente o uso de markdown"
    assert texto_pdf in conteudo

    # Valida rigorosamente se as configurações de segurança (BLOCK_NONE) foram injetadas
    config = call_kwargs.get("config")
    assert config is not None, "As configurações do Gemini devem ser repassadas."
    assert isinstance(
        config, types.GenerateContentConfig
    ), "O objeto de configuração deve ser do SDK do Google."

    safety_settings = config.safety_settings
    assert safety_settings is not None
    assert len(safety_settings) > 0

    # Checa as strings/enums configurados na lista (garante que tudo está como BLOCK_NONE)
    thresholds = [str(s.threshold) for s in safety_settings]
    assert all(
        "BLOCK_NONE" in t for t in thresholds
    ), "Um ou mais filtros não foram desativados!"


@pytest.mark.asyncio
async def test_gerar_resumo_senado_texto_vazio_retorna_vazio():
    """
    Textos vazios (indicando erros permanentes de extração, PDFs puramente de imagem)
    não devem acionar a LLM para não gerar desperdício e devem retornar string vazia.
    """
    mock_client = MagicMock()
    resumo = await gerar_resumo_executivo_senado("", mock_client)

    assert resumo == ""
    mock_client.models.generate_content.assert_not_called()


@pytest.mark.asyncio
async def test_gerar_resumo_senado_resiliencia_erro_api():
    """
    Tracer bullet (Fase 3): Garante que falhas transientes na API do Gemini
    (ex: 503, 429) disparam retentativas (Tenacity) antes de falhar definitivamente.
    """
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Resumo após retry."

    # Simula a API falhando 2 vezes e dando sucesso na 3ª
    mock_client.models.generate_content.side_effect = [
        Exception("503 Service Unavailable"),
        Exception("429 Too Many Requests"),
        mock_response,
    ]

    resumo = await gerar_resumo_executivo_senado(
        "Texto para teste de retry.", mock_client
    )

    assert resumo == "Resumo após retry."
    assert mock_client.models.generate_content.call_count == 3
