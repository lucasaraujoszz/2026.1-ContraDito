import pytest
import respx
import httpx
from unittest.mock import MagicMock, AsyncMock, patch

from etl.pipeline_resumo_proposicoes import executar_pipeline_resumo


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
    parts.append(b"5 0 obj\n<</Type /Font /Subtype /Type1 /BaseFont /Helvetica>>\nendobj\n")
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


def _make_supabase_mock(proposicoes: list):
    tabela = MagicMock()
    tabela.select.return_value.is_.return_value.not_.is_.return_value.execute.return_value.data = proposicoes
    tabela.select.return_value.is_.return_value.not_.is_.return_value.limit.return_value.execute.return_value.data = proposicoes
    tabela.update.return_value.eq.return_value.execute.return_value = MagicMock()

    supabase = MagicMock()
    supabase.table.return_value = tabela
    return supabase, tabela


def _make_motor_nlp_mock(embedding=None):
    motor = MagicMock()
    motor.gerar_embedding = AsyncMock(return_value=embedding or [0.1] * 768)
    return motor


def _make_groq_mock(resumo: str = "Resumo gerado."):
    choice = MagicMock()
    choice.message.content = resumo
    response = MagicMock()
    response.choices = [choice]
    cliente = MagicMock()
    cliente.chat.completions.create.return_value = response
    return cliente


@pytest.mark.asyncio
async def test_pipeline_sem_proposicoes_pendentes_retorna_zero():
    """
    Tracer bullet: quando não há proposições pendentes no banco,
    o pipeline retorna 0 e não aciona nenhum update.
    """
    supabase, tabela = _make_supabase_mock(proposicoes=[])

    total = await executar_pipeline_resumo(
        supabase=supabase,
        motor_nlp=_make_motor_nlp_mock(),
        groq_client=_make_groq_mock(),
    )

    assert total == 0
    tabela.update.assert_not_called()


@pytest.mark.asyncio
@respx.mock
async def test_pipeline_processa_proposicao_e_salva_resumo_e_embedding():
    """
    Com uma proposição pendente, o pipeline deve:
    - baixar o PDF da url_texto_inteiro
    - salvar o resumo e o embedding via update no banco
    - retornar 1
    """
    url = "https://camara.leg.br/proposicao/abc.pdf"
    pdf_bytes = _make_pdf("Proposicao sobre educacao basica")
    respx.get(url).respond(status_code=200, content=pdf_bytes)

    proposicoes = [{"id": "uuid-prop-1", "url_texto_inteiro": url}]
    supabase, tabela = _make_supabase_mock(proposicoes)
    motor = _make_motor_nlp_mock()
    groq = _make_groq_mock("Esta proposicao trata de educacao.")

    total = await executar_pipeline_resumo(
        supabase=supabase,
        motor_nlp=motor,
        groq_client=groq,
    )

    assert total == 1
    tabela.update.assert_called_once()
    payload = tabela.update.call_args[0][0]
    assert payload["resumo_executivo"] == "Esta proposicao trata de educacao."
    assert len(payload["embedding_resumo_executivo"]) == 768
    tabela.update.return_value.eq.assert_called_once_with("id", "uuid-prop-1")


@pytest.mark.asyncio
@respx.mock
async def test_pipeline_ignora_proposicao_com_pdf_sem_texto():
    """
    Uma proposição cujo PDF não contém texto extraível deve ser silenciosamente
    ignorada — sem update no banco e sem contar no total.
    """
    url = "https://camara.leg.br/proposicao/escaneado.pdf"
    respx.get(url).respond(status_code=200, content=b"%PDF-1.4 arquivo vazio sem texto")

    proposicoes = [{"id": "uuid-prop-2", "url_texto_inteiro": url}]
    supabase, tabela = _make_supabase_mock(proposicoes)

    total = await executar_pipeline_resumo(
        supabase=supabase,
        motor_nlp=_make_motor_nlp_mock(),
        groq_client=_make_groq_mock(),
    )

    assert total == 0
    tabela.update.assert_not_called()


@pytest.mark.asyncio
@respx.mock
async def test_pipeline_continua_apos_falha_em_uma_proposicao():
    """
    Se uma proposição falhar (ex: PDF inacessível), o pipeline deve continuar
    processando as demais e não propagar a exceção.
    """
    url_ok = "https://camara.leg.br/proposicao/ok.pdf"
    url_falha = "https://camara.leg.br/proposicao/falha.pdf"

    respx.get(url_falha).respond(status_code=404)
    respx.get(url_ok).respond(status_code=200, content=_make_pdf("Proposicao valida"))

    proposicoes = [
        {"id": "uuid-falha", "url_texto_inteiro": url_falha},
        {"id": "uuid-ok", "url_texto_inteiro": url_ok},
    ]
    supabase, tabela = _make_supabase_mock(proposicoes)

    total = await executar_pipeline_resumo(
        supabase=supabase,
        motor_nlp=_make_motor_nlp_mock(),
        groq_client=_make_groq_mock("Resumo da proposicao valida."),
    )

    assert total == 1
    tabela.update.assert_called_once()
