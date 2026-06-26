import pytest
import respx
import httpx
from unittest.mock import patch, MagicMock

# Importação da função que será implementada na fase GREEN (atualmente deve causar ImportError)
from etl.extrator_texto_senado import extrair_texto_senado


@pytest.mark.asyncio
@respx.mock
@patch("etl.extrator_texto_senado.pdfplumber.open")
async def test_extrair_texto_truncado_100k(mock_pdfplumber_open):
    """
    Garante que o extrator de texto do Senado baixa o PDF e trunca
    o resultado estritamente em 100.000 caracteres para poupar memória da LLM.
    """
    url_fake = "https://legis.senado.leg.br/fake.pdf"

    # Simula o download do arquivo binário com sucesso (HTTP 200)
    respx.get(url_fake).respond(status_code=200, content=b"fake_pdf_bytes")

    # Mock do pdfplumber para retornar um texto gigante (150.000 caracteres)
    mock_pdf = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "A" * 150000
    mock_pdf.pages = [mock_page]
    mock_pdfplumber_open.return_value.__enter__.return_value = mock_pdf

    async with httpx.AsyncClient() as client:
        texto_extraido = await extrair_texto_senado(url_fake, client)

    # O texto final DEVE respeitar o limite exato de 100.000 caracteres
    assert len(texto_extraido) == 100000
    assert texto_extraido == "A" * 100000


@pytest.mark.asyncio
@respx.mock
@patch("etl.extrator_texto_senado.pdfplumber.open")
async def test_extrair_texto_pdf_sem_texto_retorna_vazio(mock_pdfplumber_open):
    """
    Garante que PDFs perfeitamente válidos mas compostos apenas por imagens (escaneados)
    retornem uma string vazia, caracterizando um Erro Permanente mais à frente.
    """
    url_fake = "https://legis.senado.leg.br/fake_escaneado.pdf"
    respx.get(url_fake).respond(status_code=200, content=b"fake_pdf_bytes")

    mock_pdf = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text.return_value = ""  # Simula página sem texto extraível
    mock_pdf.pages = [mock_page]
    mock_pdfplumber_open.return_value.__enter__.return_value = mock_pdf

    async with httpx.AsyncClient() as client:
        texto_extraido = await extrair_texto_senado(url_fake, client)

    assert texto_extraido == ""


@pytest.mark.asyncio
@respx.mock
@patch("etl.extrator_texto_senado.pdfplumber.open")
async def test_extrair_texto_pdf_corrompido_retorna_vazio(mock_pdfplumber_open):
    """
    Garante que se o parseador falhar em abrir o arquivo (PDF corrompido),
    a exceção é engolida e retorna-se string vazia (Erro Permanente).
    """
    url_fake = "https://legis.senado.leg.br/fake_corrompido.pdf"
    respx.get(url_fake).respond(status_code=200, content=b"lixo_binario")

    # Simula o pdfplumber levantando uma exceção ao tentar abrir os bytes
    mock_pdfplumber_open.side_effect = Exception("PDFSyntaxError")

    async with httpx.AsyncClient() as client:
        texto_extraido = await extrair_texto_senado(url_fake, client)

    assert texto_extraido == ""


@pytest.mark.asyncio
@respx.mock
async def test_extrair_texto_resiliencia_transitoria():
    """
    Garante que erros de rede ou de servidor (500, 503) disparam as retentativas (Tenacity),
    não falhando de imediato o pipeline.
    """
    url_fake = "https://legis.senado.leg.br/fake_retry.pdf"
    route = respx.get(url_fake)

    # Simula 2 quedas de servidor seguidas de 1 sucesso na 3ª tentativa
    route.side_effect = [
        httpx.Response(500),
        httpx.Response(503),
        httpx.Response(200, content=b"%PDF-1.4 arquivo valido simulado"),
    ]

    # O pdfplumber tentará abrir o mock binário, então vamos interceptar o parse
    with patch("etl.extrator_texto_senado.pdfplumber.open") as mock_pdfplumber_open:
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Sucesso após retry"
        mock_pdf.pages = [mock_page]
        mock_pdfplumber_open.return_value.__enter__.return_value = mock_pdf

        async with httpx.AsyncClient() as client:
            texto_extraido = await extrair_texto_senado(url_fake, client)

    # Deve ter chamado a API 3 vezes até conseguir
    assert route.call_count == 3
    assert "Sucesso" in texto_extraido
