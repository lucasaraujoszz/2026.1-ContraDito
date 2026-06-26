import respx
import httpx
import asyncio
import pytest
from unittest.mock import patch, MagicMock

# Importaremos a função do módulo de extração que iremos implementar (Fase GREEN)
from etl.extrator_proposicoes_camara import (
    extrair_pagina_proposicoes,
    extrair_tramitacoes_proposicao,
    extrair_detalhes_proposicao,
    processar_pagina_proposicoes,
    deduplicar_lote,
    executar_pipeline_completo,
)


@pytest.mark.asyncio
@respx.mock
async def test_extrair_pagina_proposicoes_sucesso_e_paginacao():
    """
    Garante que a função acessa a API da Câmara, extrai os dados brutos
    das proposições e identifica corretamente o link para a próxima página (rel='next').
    """
    url = "https://dadosabertos.camara.leg.br/api/v2/proposicoes?siglaTipo=PL,PEC&dataInicio=2023-01-01&dataFim=2023-01-01"
    url_proxima = url + "&pagina=2"

    mock_json = {
        "dados": [{"id": 123, "siglaTipo": "PL", "numero": 10, "ano": 2023}],
        "links": [{"rel": "next", "href": url_proxima}],
    }

    respx.get(url).respond(status_code=200, json=mock_json)

    async with httpx.AsyncClient() as client:
        dados, next_url = await extrair_pagina_proposicoes(client, url)

        assert len(dados) == 1
        assert dados[0]["id"] == 123
        assert next_url == url_proxima


@pytest.mark.asyncio
@respx.mock
async def test_extrair_pagina_proposicoes_resiliencia_rede():
    """
    Garante que a função tenta novamente em caso de erros 500/503 da API
    e consegue retornar os dados se uma tentativa subsequente funcionar.
    """
    url = "https://dadosabertos.camara.leg.br/api/v2/proposicoes"
    mock_json = {"dados": [{"id": 999}], "links": []}

    route = respx.get(url)
    route.side_effect = [
        httpx.Response(500),
        httpx.Response(503),
        httpx.Response(200, json=mock_json),
    ]

    async with httpx.AsyncClient() as client:
        dados, next_url = await extrair_pagina_proposicoes(client, url)

        assert route.call_count == 3
        assert len(dados) == 1
        assert dados[0]["id"] == 999


@pytest.mark.asyncio
@respx.mock
async def test_extrair_tramitacoes_proposicao_sucesso():
    """
    Garante que a função monta a URL correta e extrai a lista de tramitações da proposição.
    """
    id_proposicao = 2265213
    url = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes/{id_proposicao}/tramitacoes"

    mock_json = {
        "dados": [{"codTipoTramitacao": 231, "dataHora": "2023-01-01T10:00:00"}]
    }

    respx.get(url).respond(status_code=200, json=mock_json)

    async with httpx.AsyncClient() as client:
        semaphore = asyncio.Semaphore(1)
        tramitacoes = await extrair_tramitacoes_proposicao(
            client, id_proposicao, semaphore
        )

        assert len(tramitacoes) == 1
        assert tramitacoes[0]["codTipoTramitacao"] == 231


@pytest.mark.asyncio
@respx.mock
async def test_extrair_tramitacoes_proposicao_resiliencia():
    """
    Garante que a extração de tramitações também possui resiliência de rede (Tenacity)
    em caso de falha 500/503 da API.
    """
    id_proposicao = 999
    url = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes/{id_proposicao}/tramitacoes"

    route = respx.get(url)
    route.side_effect = [
        httpx.Response(500),
        httpx.Response(503),
        httpx.Response(200, json={"dados": [{"id": 1}]}),
    ]

    async with httpx.AsyncClient() as client:
        semaphore = asyncio.Semaphore(1)
        tramitacoes = await extrair_tramitacoes_proposicao(
            client, id_proposicao, semaphore
        )

        assert route.call_count == 3
        assert len(tramitacoes) == 1


@pytest.mark.asyncio
@respx.mock
async def test_extrair_detalhes_proposicao_sucesso():
    """
    Garante que a função acessa o endpoint de detalhamento para obter o payload rico
    (que inclui urlInteiroTeor).
    """
    id_proposicao = 14244
    url = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes/{id_proposicao}"

    mock_json = {
        "dados": {
            "id": id_proposicao,
            "urlInteiroTeor": "http://camara.gov.br/pec45.pdf",
        }
    }
    respx.get(url).respond(status_code=200, json=mock_json)

    async with httpx.AsyncClient() as client:
        semaphore = asyncio.Semaphore(1)
        detalhes = await extrair_detalhes_proposicao(client, id_proposicao, semaphore)

        assert detalhes.get("urlInteiroTeor") == "http://camara.gov.br/pec45.pdf"


@pytest.mark.asyncio
@respx.mock
async def test_processar_pagina_proposicoes_orquestracao():
    """
    Garante que a função orquestra a extração de uma página,
    busca as tramitações N+1, aplica a transformação e filtra os descartados.
    """
    url_pagina = "https://dadosabertos.camara.leg.br/api/v2/proposicoes?itens=15"

    # Mock da página com 2 proposições
    respx.get(url_pagina).respond(
        status_code=200,
        json={
            "dados": [
                {
                    "id": 1,
                    "siglaTipo": "PL",
                    "numero": 10,
                    "ano": 2023,
                },  # Payload simples sem url (como vem na API real)
                {"id": 2, "siglaTipo": "PL", "numero": 11, "ano": 2022},
            ],
            "links": [],
        },
    )

    # Mock das tramitações para a Proposição 1 (Válida - 2023)
    respx.get(
        "https://dadosabertos.camara.leg.br/api/v2/proposicoes/1/tramitacoes"
    ).respond(
        status_code=200,
        json={
            "dados": [
                {
                    "codTipoTramitacao": 231,
                    "dataHora": "2023-05-15T10:00:00",
                    "id": "t1",
                }
            ]
        },
    )

    # Mock das tramitações para a Proposição 2 (Inválida - 2022 - será descartada)
    respx.get(
        "https://dadosabertos.camara.leg.br/api/v2/proposicoes/2/tramitacoes"
    ).respond(
        status_code=200,
        json={
            "dados": [
                {
                    "codTipoTramitacao": 231,
                    "dataHora": "2022-12-31T10:00:00",
                    "id": "t2",
                }
            ]
        },
    )

    # Mock do detalhamento somente para a Proposição 1 (que é a Única que será aprovada no filtro)
    respx.get("https://dadosabertos.camara.leg.br/api/v2/proposicoes/1").respond(
        status_code=200,
        json={
            "dados": {
                "id": 1,
                "siglaTipo": "PL",
                "numero": 10,
                "ano": 2023,
                "ementa": "Ementa 1",
                "urlInteiroTeor": "url1",
            }
        },
    )

    async with httpx.AsyncClient() as client:
        semaphore = asyncio.Semaphore(2)
        resultados, next_url = await processar_pagina_proposicoes(
            client, url_pagina, semaphore
        )

        # Apenas 1 proposição deve sobreviver ao filtro e chegar aqui com o schema validado
        assert len(resultados) == 1
        assert resultados[0]["id_camara"] == 1
        assert resultados[0]["ano"] == 2023
        assert resultados[0]["url_texto_inteiro"] == "url1"
        assert next_url is None


def test_deduplicar_lote_com_sucesso():
    """
    Garante que a função remove duplicatas de um lote de proposições
    usando a chave 'id' (UUID) como referência, mantendo apenas itens únicos.
    """
    lote_duplicado = [
        {"id": "uuid-1", "proposicao_id": "pec_45_2019"},
        {"id": "uuid-2", "proposicao_id": "pl_123_2023"},
        {"id": "uuid-1", "proposicao_id": "pec_45_2019"},  # Duplicata exata
    ]

    lote_deduplicado = deduplicar_lote(lote_duplicado)

    assert len(lote_deduplicado) == 2
    ids = [item["id"] for item in lote_deduplicado]
    assert "uuid-1" in ids
    assert "uuid-2" in ids


def test_deduplicar_lote_vazio():
    """
    Garante que a função deduplicar_lote lida graciosamente com uma lista vazia,
    retornando uma lista vazia sem levantar exceções.
    """
    assert deduplicar_lote([]) == []


@pytest.mark.asyncio
@respx.mock
@patch("time.sleep")
async def test_executar_pipeline_completo_integracao(mock_sleep):
    """
    Testa a execução completa do pipeline, garantindo a orquestração de páginas,
    a deduplicação, o upsert na tabela correta e o registro final no etl_logs.
    """
    data_inicio = "2023-01-01"
    data_fim = "2023-01-31"  # Teste com fatia de 30 dias
    url_pag_1 = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes?siglaTipo=PL,PEC&dataInicio={data_inicio}&dataFim={data_fim}&itens=15"

    mock_json_pagina = {
        "dados": [
            {
                "id": 1,
                "siglaTipo": "PL",
                "numero": 10,
                "ano": 2023,
                "ementa": "Teste",
                "urlInteiroTeor": "url1",
            }
        ],
        "links": [],
    }
    respx.get(url_pag_1).respond(status_code=200, json=mock_json_pagina)

    url_tramitacao = (
        "https://dadosabertos.camara.leg.br/api/v2/proposicoes/1/tramitacoes"
    )
    respx.get(url_tramitacao).respond(
        status_code=200,
        json={
            "dados": [
                {
                    "codTipoTramitacao": 231,
                    "dataHora": "2023-05-15T10:00:00",
                    "id": "t1",
                }
            ]
        },
    )

    # Mock do detalhamento no pipeline completo
    respx.get("https://dadosabertos.camara.leg.br/api/v2/proposicoes/1").respond(
        status_code=200,
        json={
            "dados": {
                "id": 1,
                "siglaTipo": "PL",
                "numero": 10,
                "ano": 2023,
                "ementa": "Teste",
                "urlInteiroTeor": "url1",
            }
        },
    )

    mock_supabase = MagicMock()

    await executar_pipeline_completo(mock_supabase, data_inicio, data_fim)

    # Verifica se fez o upsert na tabela de proposições
    mock_supabase.table.assert_any_call("camara_proposicoes")
    mock_supabase.table().upsert.assert_called_once()

    # Verifica se os logs de auditoria foram salvos corretamente
    mock_supabase.table.assert_any_call("etl_logs")
    mock_supabase.table().insert.assert_called_once()
    args_log, _ = mock_supabase.table().insert.call_args
    log_enviado = args_log[0]

    assert log_enviado["nome_rotina"] == "extrator_proposicoes_camara"
    assert log_enviado["status"] == "Concluído"
    assert log_enviado["linhas_afetadas"] == 1
