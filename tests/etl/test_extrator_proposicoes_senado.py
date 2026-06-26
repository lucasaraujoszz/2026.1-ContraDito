import uuid
import pytest
import respx
import httpx
import asyncio
from unittest.mock import MagicMock, patch
from etl.extrator_proposicoes_senado import (
    gerar_hash_id_proposicao,
    obter_data_primeira_votacao_valida,
    validar_corte_temporal,
    transformar_proposicao_senado,
)


def test_determinismo_hash_proposicao_senado():
    """
    Ciclo 1: Dada uma combinação de sigla, número e ano, a função
    deve gerar sempre a mesma chave de negócio (snake_case)
    e o exato mesmo identificador UUID v5.
    """
    sigla = "PLS"
    numero = 67
    ano = 2015

    proposicao_id, proposicao_uuid = gerar_hash_id_proposicao(sigla, numero, ano)

    # Verifica a chave de negócio (padronizada em minúsculas e snake_case)
    assert proposicao_id == "pls_67_2015"

    # Verifica a integridade e determinismo do UUID v5 gerado
    expected_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, "pls_67_2015"))
    assert proposicao_uuid == expected_uuid

    # Garante que rodar novamente produz o EXATO mesmo resultado (Idempotência)
    _, uuid_repetido = gerar_hash_id_proposicao("PLS", 67, 2015)
    assert proposicao_uuid == uuid_repetido


def test_filtro_votacao_whitelist_cronologica():
    """
    Ciclo 2: O filtro deve vasculhar as listas aninhadas (autuacoes -> situacoes),
    ignorar eventos irrelevantes e retornar a data (inicio) do primeiro evento
    (mais antigo) que corresponda à whitelist do Senado.
    """
    autuacoes_mock = [
        {
            "situacoes": [
                {"idTipo": 999, "inicio": "2021-01-01"},  # Irrelevante (ignorado)
                {"idTipo": 25, "inicio": "2023-05-15"},  # Valido, mas mais recente
            ]
        },
        {
            "situacoes": [
                {
                    "idTipo": 49,
                    "inicio": "2022-10-10",
                },  # Valido e é o MAIS ANTIGO da linha do tempo
                {
                    "idTipo": 888,
                    "inicio": "2020-01-01",
                },  # Irrelevante, embora seja a data mais antiga geral
            ]
        },
    ]

    data = obter_data_primeira_votacao_valida(autuacoes_mock)
    assert data == "2022-10-10"


def test_filtro_votacao_sem_whitelist():
    autuacoes_mock = [{"situacoes": [{"idTipo": 999, "inicio": "2023-05-15"}]}]
    assert obter_data_primeira_votacao_valida(autuacoes_mock) is None


def test_corte_temporal_defensivo():
    """
    Ciclo 3: Se a data retornada pelo filtro for inferior a 2023-01-01 ou nula,
    a função deve retornar False para forçar o descarte silencioso da proposição.
    """
    assert validar_corte_temporal("2023-05-10") is True
    assert validar_corte_temporal("2023-01-01") is True
    assert validar_corte_temporal("2022-12-31") is False
    assert validar_corte_temporal(None) is False


def test_transformar_proposicao_senado_sucesso():
    """
    Ciclo 4: O mapeamento deve resultar num dicionário Python que obedece
    a 100% das chaves do Data Contract.
    """
    payload_mock = {
        "codigoMateria": 999888,
        "sigla": "PL",
        "numero": 123,
        "ano": 2023,
        "autuacoes": [{"situacoes": [{"idTipo": 25, "inicio": "2023-06-01"}]}],
    }
    url_documento = "https://legis.senado.leg.br/pdf/123"
    ementa_etapa_1 = "Ementa teste"

    resultado = transformar_proposicao_senado(
        payload_mock, url_documento, ementa_etapa_1
    )

    assert resultado is not None
    chaves_exigidas = {
        "id",
        "proposicao_id",
        "id_senado",
        "tipo",
        "numero",
        "ano",
        "ementa",
        "data_votacao",
        "url_texto_inteiro",
        "resumo_executivo",
        "erro_resumo",
    }
    assert set(resultado.keys()) == chaves_exigidas
    assert resultado["proposicao_id"] == "pl_123_2023"
    assert resultado["id_senado"] == 999888
    assert resultado["data_votacao"] == "2023-06-01"
    assert resultado["url_texto_inteiro"] == url_documento
    assert resultado["resumo_executivo"] is None


def test_transformar_proposicao_senado_descarte():
    """
    Ciclo 4: Se a data de votação for anterior a 2023 ou nula,
    a transformação deve retornar None (descarte silencioso).
    """
    payload_mock = {
        "codigoMateria": 111,
        "sigla": "PL",
        "numero": 1,
        "ano": 2020,
        "autuacoes": [{"situacoes": [{"idTipo": 25, "inicio": "2022-12-31"}]}],
    }

    resultado = transformar_proposicao_senado(payload_mock, "http://url", "Teste")
    assert resultado is None


def test_transformar_proposicao_senado_descarte_tipo_invalido():
    """
    Se a sigla não pertencer ao conjunto de tipos permitidos,
    a função deve retornar None (descarte silencioso).
    """
    payload_mock = {
        "codigoMateria": 111,
        "sigla": "SUBSTITUTIVO",
        "numero": 1,
        "ano": 2023,
        "autuacoes": [{"situacoes": [{"idTipo": 25, "inicio": "2023-05-15"}]}],
    }

    resultado = transformar_proposicao_senado(payload_mock, "http://url", "Teste")
    assert resultado is None


def test_upsert_parcial_e_deduplicacao_senado():
    """
    Ciclo 5: O worker do Senado deve salvar os dados em blocos parciais para
    mitigar quedas. Antes do upsert, o lote deve ser deduplicado em memória.
    """
    from etl.extrator_proposicoes_senado import salvar_lote_parcial

    mock_supabase = MagicMock()

    lote_com_duplicatas = [
        {"id": "uuid-1", "proposicao_id": "pl_1"},
        {"id": "uuid-2", "proposicao_id": "pl_2"},
        {"id": "uuid-1", "proposicao_id": "pl_1"},  # Duplicata exata
    ]

    lote_limpo = [{"id": "uuid-3", "proposicao_id": "pl_3"}]

    linhas_1 = salvar_lote_parcial(mock_supabase, lote_com_duplicatas)
    linhas_2 = salvar_lote_parcial(mock_supabase, lote_limpo)

    assert linhas_1 == 2
    assert linhas_2 == 1
    mock_supabase.table.assert_called_with("senado_proposicoes")
    assert mock_supabase.table().upsert.call_count == 2


@pytest.mark.asyncio
@patch("etl.extrator_proposicoes_senado.processar_pagina_arrasto")
async def test_recuperacao_de_falhas_e_log_senado(mock_processar):
    """
    Ciclo 6: Se ocorrer uma exceção fatal, o worker deve capturar o erro,
    abortar e registrar no etl_logs o status de Erro com as linhas afetadas
    até o momento do crash.
    """
    from etl.extrator_proposicoes_senado import executar_pipeline_completo

    mock_supabase = MagicMock()

    # Simula o processamento: Página 1 salva 15 registros. Página 2 sofre crash de rede.
    mock_processar.side_effect = [
        (15, "http://url-pagina-2"),
        Exception("Timeout na API do Senado"),
    ]

    await executar_pipeline_completo(mock_supabase, "2023-01-01", "2023-01-31")

    mock_supabase.table.assert_any_call("etl_logs")
    mock_supabase.table().insert.assert_called_once()

    args, _ = mock_supabase.table().insert.call_args
    log_enviado = args[0]

    assert log_enviado["nome_rotina"] == "extrator_proposicoes_senado"
    assert log_enviado["status"] == "Erro"
    assert "Timeout na API do Senado" in log_enviado["detalhe_erro"]
    assert log_enviado["linhas_afetadas"] == 15


@pytest.mark.asyncio
@respx.mock
async def test_resiliencia_e_rate_limit_api_senado():
    """
    Ciclo 7: A chamada N+1 para buscar o detalhe da proposição deve respeitar
    o Rate Limit (asyncio.Semaphore) e aplicar retentativas (Tenacity)
    em caso de falhas transientes (ex: 500, 429).
    """
    from etl.extrator_proposicoes_senado import extrair_detalhe_proposicao

    url = "https://legis.senado.leg.br/dadosabertos/processo/12345"
    route = respx.get(url)
    route.side_effect = [
        httpx.Response(500),
        httpx.Response(429),
        httpx.Response(200, json={"processo": {"codigoMateria": 12345}}),
    ]

    semaphore = asyncio.Semaphore(5)
    async with httpx.AsyncClient() as client:
        resultado = await extrair_detalhe_proposicao(client, 12345, semaphore)

        assert route.call_count == 3
        assert resultado.get("processo", {}).get("codigoMateria") == 12345


@pytest.mark.asyncio
@patch("etl.extrator_proposicoes_senado.fetch_pagina_arrasto")
@patch("etl.extrator_proposicoes_senado.extrair_detalhe_proposicao")
@patch("etl.extrator_proposicoes_senado.transformar_proposicao_senado")
@patch("etl.extrator_proposicoes_senado.salvar_lote_parcial")
async def test_processar_pagina_arrasto_completo(
    mock_salvar, mock_transformar, mock_extrair, mock_fetch
):
    from etl.extrator_proposicoes_senado import processar_pagina_arrasto

    mock_client = MagicMock()
    mock_supabase = MagicMock()
    semaphore = asyncio.Semaphore(5)

    mock_fetch.return_value = {
        "processo": [{"id": "123", "urlDocumento": "http://doc", "ementa": "Ementa 1"}]
    }

    mock_extrair.return_value = {
        "processo": {
            "codigoMateria": 123,
            "sigla": "PL",
            "numero": 123,
            "ano": 2023,
            "autuacoes": [{"situacoes": [{"idTipo": 25, "inicio": "2023-05-15"}]}],
        }
    }

    mock_transformar.return_value = {"id": "uuid-1", "proposicao_id": "PL 123/2023"}
    mock_salvar.return_value = 1

    linhas, prox_url = await processar_pagina_arrasto(
        mock_client, "http://arrasto-url", mock_supabase, semaphore
    )

    assert linhas == 1
    assert prox_url is None
    mock_fetch.assert_called_once()
    mock_extrair.assert_called_once()
    mock_transformar.assert_called_once()
    mock_salvar.assert_called_once()


@pytest.mark.asyncio
@patch("etl.extrator_proposicoes_senado.processar_pagina_arrasto")
async def test_executar_pipeline_completo_sucesso(mock_processar):
    from etl.extrator_proposicoes_senado import executar_pipeline_completo

    mock_supabase = MagicMock()
    mock_processar.return_value = (10, None)

    await executar_pipeline_completo(mock_supabase, "2023-01-01", "2023-01-31")

    mock_supabase.table.assert_any_call("etl_logs")
    mock_supabase.table().insert.assert_called_once()
    args, _ = mock_supabase.table().insert.call_args
    log_enviado = args[0]
    assert log_enviado["nome_rotina"] == "extrator_proposicoes_senado"
    assert log_enviado["status"] == "Concluído"
    assert log_enviado["linhas_afetadas"] == 10
