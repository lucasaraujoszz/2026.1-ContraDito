import io
import pytest
import httpx
import respx

from etl.extrator_texto_proposicao import extrair_texto_de_url


def _make_pdf(text: str = "Texto da proposicao") -> bytes:
    stream_content = f"BT /F1 12 Tf 100 700 Td ({text}) Tj ET".encode()
    stream_len = len(stream_content)

    parts = []
    offsets = []

    parts.append(b"%PDF-1.4\n")

    offsets.append(len(b"".join(parts)))
    parts.append(b"1 0 obj\n<</Type /Catalog /Pages 2 0 R>>\nendobj\n")

    offsets.append(len(b"".join(parts)))
    parts.append(b"2 0 obj\n<</Type /Pages /Kids [3 0 R] /Count 1>>\nendobj\n")

    offsets.append(len(b"".join(parts)))
    parts.append(
        b"3 0 obj\n<</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]"
        b" /Contents 4 0 R /Resources <</Font <</F1 5 0 R>>>>>>\nendobj\n"
    )

    offsets.append(len(b"".join(parts)))
    parts.append(
        b"4 0 obj\n<</Length "
        + str(stream_len).encode()
        + b">>\nstream\n"
        + stream_content
        + b"\nendstream\nendobj\n"
    )

    offsets.append(len(b"".join(parts)))
    parts.append(
        b"5 0 obj\n<</Type /Font /Subtype /Type1 /BaseFont /Helvetica>>\nendobj\n"
    )

    xref_offset = len(b"".join(parts))
    xref = b"xref\n0 6\n" + b"0000000000 65535 f \n"
    for off in offsets:
        xref += f"{off:010d} 00000 n \n".encode()
    trailer = (
        b"trailer\n<</Size 6 /Root 1 0 R>>\nstartxref\n"
        + str(xref_offset).encode()
        + b"\n%%EOF"
    )
    parts.append(xref + trailer)
    return b"".join(parts)


URL = "https://camara.leg.br/proposicao/123.pdf"


@pytest.mark.asyncio
@respx.mock
async def test_extrair_texto_de_url_pdf_digital_sucesso():
    """
    Tracer bullet: dado uma URL que aponta para um PDF digital,
    a função deve baixar e retornar o texto extraído como string não-vazia.
    """
    pdf_bytes = _make_pdf("Texto da proposicao legislativa")
    respx.get(URL).respond(status_code=200, content=pdf_bytes)

    async with httpx.AsyncClient() as client:
        texto = await extrair_texto_de_url(URL, client)

    assert isinstance(texto, str)
    assert "Texto da proposicao" in texto


@pytest.mark.asyncio
@respx.mock
async def test_extrair_texto_de_url_erro_404_levanta_excecao():
    """
    Uma URL que retorna 404 deve propagar HTTPStatusError após esgotar as retentativas,
    sinalizando que o PDF não existe na origem.
    """
    respx.get(URL).respond(status_code=404)

    async with httpx.AsyncClient() as client:
        with pytest.raises(httpx.HTTPStatusError):
            await extrair_texto_de_url(URL, client)


@pytest.mark.asyncio
@respx.mock
async def test_extrair_texto_de_url_resiliencia_erro_servidor():
    """
    Erros 500/503 devem acionar as retentativas do Tenacity.
    Após uma falha transiente, a função deve retornar o texto com sucesso.
    """
    pdf_bytes = _make_pdf("Proposicao apos retry")
    route = respx.get(URL)
    route.side_effect = [
        httpx.Response(500),
        httpx.Response(503),
        httpx.Response(200, content=pdf_bytes),
    ]

    async with httpx.AsyncClient() as client:
        texto = await extrair_texto_de_url(URL, client)

    assert route.call_count == 3
    assert "Proposicao apos retry" in texto
