import pytest
import respx
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
from zoneinfo import ZoneInfo

# Importação da função que será implementada na fase GREEN
from etl.pipeline_resumo_senado import (
    converter_data_para_timestamp_sp,
    executar_pipeline_resumo_senado,
)


def _make_supabase_mock(proposicoes: list):
    """Gera um Mock robusto da cadeia de queries do Supabase (PostgREST)."""
    tabela = MagicMock()

    # Simula a cadeia de selects e filtros exigida pelo PRD
    chain = (
        tabela.select.return_value.not_.is_.return_value.is_.return_value.is_.return_value
    )
    chain.execute.return_value.data = proposicoes
    chain.limit.return_value.execute.return_value.data = proposicoes

    tabela.update.return_value.eq.return_value.execute.return_value = MagicMock()

    supabase = MagicMock()
    supabase.table.return_value = tabela
    return supabase, tabela


def test_converter_data_para_timestamp_sp():
    """
    Garante que uma string de data 'YYYY-MM-DD' seja convertida
    precisamente para o Unix Timestamp considerando o fuso de Brasília.
    """
    data_str = "2023-05-10"

    # Resultado esperado dinâmico usando o zoneinfo nativo
    dt_esperada = datetime(2023, 5, 10, tzinfo=ZoneInfo("America/Sao_Paulo"))
    timestamp_esperado = int(dt_esperada.timestamp())

    resultado = converter_data_para_timestamp_sp(data_str)

    assert resultado == timestamp_esperado


@pytest.mark.asyncio
@respx.mock
@patch("etl.extrator_texto_senado.pdfplumber.open")
@patch("etl.pipeline_resumo_senado.asyncio.sleep", new_callable=AsyncMock)
async def test_pipeline_senado_caminho_feliz_qdrant_first(
    mock_sleep, mock_pdfplumber_open
):
    """
    Garante o caminho feliz: extrai o texto, gera o resumo no Gemini, o embedding no BAAI
    e SALVA NO QDRANT PRIMEIRO, antes de dar o update final no Supabase.
    """
    # Mock PDF
    mock_pdf = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Texto do PDF do Senado"
    mock_pdf.pages = [mock_page]
    mock_pdfplumber_open.return_value.__enter__.return_value = mock_pdf

    url_pdf = "https://legis.senado.leg.br/fake.pdf"
    respx.get(url_pdf).respond(status_code=200, content=b"fake_pdf_bytes")

    # Mock Supabase com 1 proposição na fila
    prop_fake = {
        "id": "uuid-vetor-123",
        "proposicao_id": "pl_123_2023",
        "url_texto_inteiro": url_pdf,
        "data_votacao": "2023-05-10",
    }
    supabase_mock, tabela_mock = _make_supabase_mock([prop_fake])

    # Mock Dependências Externas (Qdrant, MotorNLP e Gemini)
    qdrant_mock = MagicMock()
    motor_mock = MagicMock()
    motor_mock.gerar_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])

    gemini_mock = MagicMock()
    gemini_mock.models.generate_content.return_value.text = "Resumo executivo do Senado"

    total = await executar_pipeline_resumo_senado(
        supabase_client=supabase_mock,
        qdrant_client=qdrant_mock,
        motor_nlp=motor_mock,
        gemini_client=gemini_mock,
    )

    assert total == 1

    # 1. Valida se o Qdrant-First foi respeitado e o schema enviado ao vetor está correto
    qdrant_mock.upsert.assert_called_once()
    kwargs_qdrant = qdrant_mock.upsert.call_args.kwargs
    assert kwargs_qdrant["collection_name"] == "proposicoes_embeddings"
    assert kwargs_qdrant["points"][0]["payload"][
        "data_votacao"
    ] == converter_data_para_timestamp_sp("2023-05-10")
    assert (
        kwargs_qdrant["points"][0]["payload"]["proposicao_id_string"] == "pl_123_2023"
    )
    assert kwargs_qdrant["points"][0]["payload"]["casa"] == "senado"

    # 2. Valida se a persistência final no Supabase foi acionada com o resumo
    tabela_mock.update.assert_called_once()
    assert (
        tabela_mock.update.call_args[0][0]["resumo_executivo"]
        == "Resumo executivo do Senado"
    )

    # 3. Valida se o cooldown (Rate Limit mitigation) foi aplicado para poupar a API
    mock_sleep.assert_called_once_with(5)


@pytest.mark.asyncio
@respx.mock
@patch("etl.extrator_texto_senado.pdfplumber.open")
async def test_pipeline_senado_erro_permanente_extracao(mock_pdfplumber_open):
    """
    Garante que se a extração retornar texto vazio (erro permanente),
    o pipeline atualiza o Supabase com a justificativa do erro para não reprocessar,
    e NÃO aciona a LLM nem o banco vetorial (Qdrant).
    """
    # Mock PDF vazio (simulando documento apenas com imagens)
    mock_pdf = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text.return_value = ""
    mock_pdf.pages = [mock_page]
    mock_pdfplumber_open.return_value.__enter__.return_value = mock_pdf

    url_pdf = "https://legis.senado.leg.br/vazio.pdf"
    respx.get(url_pdf).respond(status_code=200, content=b"fake_pdf_bytes")

    prop_fake = {
        "id": "uuid-erro-123",
        "proposicao_id": "pl_vazia_2023",
        "url_texto_inteiro": url_pdf,
        "data_votacao": "2023-05-10",
    }
    supabase_mock, tabela_mock = _make_supabase_mock([prop_fake])

    qdrant_mock = MagicMock()
    motor_mock = MagicMock()
    gemini_mock = MagicMock()

    total = await executar_pipeline_resumo_senado(
        supabase_mock, qdrant_mock, motor_mock, gemini_mock
    )

    assert total == 0, "O processamento com erro não deve contabilizar como sucesso."

    gemini_mock.models.generate_content.assert_not_called()
    qdrant_mock.upsert.assert_not_called()

    # Valida o assinalamento do Erro Permanente no Supabase
    tabela_mock.update.assert_called_once()
    assert (
        tabela_mock.update.call_args[0][0]["erro_resumo"]
        == "PDF sem texto extraível ou corrompido"
    )


@pytest.mark.asyncio
@respx.mock
@patch("etl.extrator_texto_senado.pdfplumber.open")
async def test_pipeline_senado_erro_transitorio_nao_salva_no_banco(
    mock_pdfplumber_open,
):
    """
    Garante que erros de infraestrutura ou rede (transitórios) não atualizem o
    Supabase com erros definitivos, preservando a proposição para retentativas.
    """
    mock_pdf = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Texto perfeitamente válido"
    mock_pdf.pages = [mock_page]
    mock_pdfplumber_open.return_value.__enter__.return_value = mock_pdf

    url_pdf = "https://legis.senado.leg.br/transitorio.pdf"
    respx.get(url_pdf).respond(status_code=200, content=b"fake_pdf_bytes")

    prop_fake = {
        "id": "uuid-transitorio-123",
        "proposicao_id": "pl_transitoria_2023",
        "url_texto_inteiro": url_pdf,
        "data_votacao": "2023-05-10",
    }
    supabase_mock, tabela_mock = _make_supabase_mock([prop_fake])

    qdrant_mock = MagicMock()
    # Simula uma queda de rede (Timeout) exatamente na hora de salvar no Qdrant
    qdrant_mock.upsert.side_effect = Exception("Qdrant Timeout / Connection Error")

    motor_mock = MagicMock()
    gemini_mock = MagicMock()

    total = await executar_pipeline_resumo_senado(
        supabase_mock, qdrant_mock, motor_mock, gemini_mock
    )

    # 1. A proposição não deve ter sido computada como sucesso
    assert total == 0

    # 2. Como o Qdrant estourou erro, NÃO PODE ter havido nenhum update no Supabase (nem resumo, nem erro)
    tabela_mock.update.assert_not_called()
