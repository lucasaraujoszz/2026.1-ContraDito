import respx
import httpx
from unittest.mock import patch, MagicMock
from etl.extrator_politicos_camara import (
    extrair_pagina_deputados,
    extrair_detalhes_deputado,
    executar_extracao_pagina,
    executar_pipeline_completo,
)


@respx.mock
def test_pagina_sucesso():
    """
    Testa a extração de uma página de deputados da API da Câmara,
    garantindo que os dados brutos e o link de paginação (rel='next') sejam retornados corretamente.
    """
    url = "https://dadosabertos.camara.leg.br/api/v2/deputados?idLegislatura=57"

    mock_json = {
        "dados": [
            {
                "id": 12345,
                "uri": "https://dadosabertos.camara.leg.br/api/v2/deputados/12345",
                "nome": "Deputado Teste",
                "siglaPartido": "PT",
                "siglaUf": "SP",
                "idLegislatura": 57,
                "urlFoto": "https://www.camara.leg.br/internet/deputado/bandep/12345.jpg",
            }
        ],
        "links": [
            {
                "rel": "self",
                "href": "https://dadosabertos.camara.leg.br/api/v2/deputados?idLegislatura=57&pagina=1",
            },
            {
                "rel": "next",
                "href": "https://dadosabertos.camara.leg.br/api/v2/deputados?idLegislatura=57&pagina=2",
            },
        ],
    }

    respx.get(url).respond(status_code=200, json=mock_json)

    dados, next_url = extrair_pagina_deputados(url)

    assert len(dados) == 1
    assert dados[0]["id"] == 12345
    assert (
        next_url
        == "https://dadosabertos.camara.leg.br/api/v2/deputados?idLegislatura=57&pagina=2"
    )


@respx.mock
def test_ultima_pagina_sem_next():
    """
    Testa o cenário onde não há rel='next', indicando ser a última página.
    O loop de paginação futuro interpretará o None como fim de extração.
    """
    url = (
        "https://dadosabertos.camara.leg.br/api/v2/deputados?idLegislatura=57&pagina=5"
    )

    mock_json = {
        "dados": [{"id": 99999}],
        "links": [{"rel": "self", "href": url}],  # Sem rel="next"
    }

    respx.get(url).respond(status_code=200, json=mock_json)

    dados, next_url = extrair_pagina_deputados(url)

    assert len(dados) == 1
    assert next_url is None


@respx.mock
@patch("time.sleep")
def test_pagina_retry_falhas(mock_sleep):
    """
    Testa se a função recupera de falhas do servidor (500) na terceira tentativa,
    aplicando os backoffs de 2s e 4s.
    """
    url = "https://dadosabertos.camara.leg.br/api/v2/deputados?idLegislatura=57"
    mock_json = {"dados": [{"id": 1}], "links": []}

    route = respx.get(url)
    route.side_effect = [
        httpx.Response(500),
        httpx.Response(503),
        httpx.Response(200, json=mock_json),
    ]

    dados, next_url = extrair_pagina_deputados(url)

    # Deve ter tentado 3 vezes
    assert route.call_count == 3
    # Deve ter feito sleep de 2s na primeira falha e 4s na segunda
    assert mock_sleep.call_count == 2
    mock_sleep.assert_any_call(2)
    mock_sleep.assert_any_call(4)
    # No final de tudo, deve ter conseguido retornar os dados
    assert len(dados) == 1


@respx.mock
@patch("time.sleep")
def test_pagina_falha_critica(mock_sleep):
    """
    Testa se a função retorna listas vazias e None após 3 falhas consecutivas, sem quebrar a execução.
    """
    url = "https://dadosabertos.camara.leg.br/api/v2/deputados?idLegislatura=57"
    route = respx.get(url).respond(status_code=500)

    dados, next_url = extrair_pagina_deputados(url)

    assert route.call_count == 3
    assert dados == []
    assert next_url is None


@respx.mock
@patch("time.sleep")
def test_detalhes_sucesso_rate_limit(mock_sleep):
    """
    Testa a extração dos detalhes de um deputado, garantindo o rate-limit e a correta
    transformação do payload da Câmara para o schema do nosso banco.
    """
    url = "https://dadosabertos.camara.leg.br/api/v2/deputados/12345"
    mock_json = {
        "dados": {
            "id": 12345,
            "nomeCivil": "Nome Civil Completo",
            "ultimoStatus": {
                "nomeEleitoral": "Nome de Urna",
                "siglaPartido": "PT",
                "siglaUf": "SP",
                "urlFoto": "http://foto.com/12345.jpg",
                "situacao": "Exercício",
            },
        }
    }
    respx.get(url).respond(status_code=200, json=mock_json)

    resultado = extrair_detalhes_deputado(12345)

    # Garante que respeitou o Rate Limit
    mock_sleep.assert_called_once_with(0.5)

    # Garante a transformação do Schema e mapeamento de domínio
    assert resultado["id"] == 12345
    assert resultado["nome_civil"] == "Nome Civil Completo"
    assert resultado["nome_urna"] == "Nome de Urna"
    assert resultado["partido"] == "PT"
    assert resultado["estado"] == "SP"
    assert resultado["url_foto"] == "http://foto.com/12345.jpg"
    assert resultado["cargo"] == "Deputado Federal"
    assert resultado["status_mandato"] == "Ativo"
    assert "data_ultima_atualizacao" in resultado


@respx.mock
@patch("time.sleep")
def test_detalhes_retry_falhas(mock_sleep):
    """
    Testa a resiliência na extração de detalhes: recupera de erros 500 e 503
    nas primeiras tentativas e retorna os dados transformados na terceira.
    """
    url = "https://dadosabertos.camara.leg.br/api/v2/deputados/12345"
    mock_json = {"dados": {"id": 12345, "ultimoStatus": {"situacao": "Exercício"}}}

    route = respx.get(url)
    route.side_effect = [
        httpx.Response(500),
        httpx.Response(503),
        httpx.Response(200, json=mock_json),
    ]

    resultado = extrair_detalhes_deputado(12345)

    assert route.call_count == 3
    assert resultado["id"] == 12345


@respx.mock
@patch("time.sleep")
def test_detalhes_falha_critica(mock_sleep):
    """
    Garante que, se as 3 tentativas falharem, a função não quebra o script,
    mas retorna None para que o loop principal ignore este deputado.
    """
    url = "https://dadosabertos.camara.leg.br/api/v2/deputados/12345"
    route = respx.get(url).respond(status_code=500)

    resultado = extrair_detalhes_deputado(12345)

    assert route.call_count == 3
    assert resultado is None


@respx.mock
@patch("time.sleep")
def test_orquestracao_pagina_upsert(mock_sleep):
    """
    Testa a orquestração de uma página inteira: busca a lista, itera buscando
    os detalhes de cada deputado, e realiza o bulk upsert no banco (mockado).
    """
    url_pagina = (
        "https://dadosabertos.camara.leg.br/api/v2/deputados?idLegislatura=57&pagina=1"
    )

    mock_json_pagina = {
        "dados": [{"id": 12345}],
        "links": [
            {
                "rel": "next",
                "href": "https://dadosabertos.camara.leg.br/api/v2/deputados?idLegislatura=57&pagina=2",
            }
        ],
    }
    respx.get(url_pagina).respond(status_code=200, json=mock_json_pagina)

    url_detalhes = "https://dadosabertos.camara.leg.br/api/v2/deputados/12345"
    mock_json_detalhes = {
        "dados": {
            "id": 12345,
            "nomeCivil": "Nome Teste",
            "ultimoStatus": {"nomeEleitoral": "Teste Urna", "situacao": "Exercício"},
        }
    }
    respx.get(url_detalhes).respond(status_code=200, json=mock_json_detalhes)

    mock_supabase = MagicMock()

    proxima_url, linhas = executar_extracao_pagina(url_pagina, mock_supabase, set())

    # Garante que ele leu a página corretamente e achou a próxima
    assert (
        proxima_url
        == "https://dadosabertos.camara.leg.br/api/v2/deputados?idLegislatura=57&pagina=2"
    )

    # Garante que ele tentou salvar na tabela 'camara_politicos' realizando um upsert
    mock_supabase.table.assert_called_once_with("camara_politicos")
    mock_supabase.table().upsert.assert_called_once()

    assert linhas == 1
    # Inspeciona o que foi enviado para o banco
    args, _ = mock_supabase.table().upsert.call_args
    lote_enviado = args[0]
    assert len(lote_enviado) == 1
    assert lote_enviado[0]["id"] == 12345


@respx.mock
@patch("time.sleep")
def test_orquestracao_pipeline_completo(mock_sleep):
    """
    Testa a execução completa do pipeline, garantindo que o laço de paginação funciona
    e que o log de sucesso é inserido na tabela etl_logs ao final.
    """
    url_pag_1 = "https://dadosabertos.camara.leg.br/api/v2/deputados?idLegislatura=57"
    url_pag_2 = (
        "https://dadosabertos.camara.leg.br/api/v2/deputados?idLegislatura=57&pagina=2"
    )

    respx.get(url_pag_1).respond(
        status_code=200,
        json={"dados": [{"id": 1}], "links": [{"rel": "next", "href": url_pag_2}]},
    )

    respx.get(url_pag_2).respond(
        status_code=200, json={"dados": [{"id": 2}], "links": []}  # Sem próxima página
    )

    respx.get("https://dadosabertos.camara.leg.br/api/v2/deputados/1").respond(
        status_code=200,
        json={"dados": {"id": 1, "ultimoStatus": {"situacao": "Exercício"}}},
    )
    respx.get("https://dadosabertos.camara.leg.br/api/v2/deputados/2").respond(
        status_code=200,
        json={"dados": {"id": 2, "ultimoStatus": {"situacao": "Exercício"}}},
    )

    mock_supabase = MagicMock()

    executar_pipeline_completo(mock_supabase)

    # Verifica a inserção do log final
    mock_supabase.table.assert_any_call("etl_logs")
    mock_supabase.table().insert.assert_called_once()

    args_log, _ = mock_supabase.table().insert.call_args
    log_enviado = args_log[0]

    assert log_enviado["nome_rotina"] == "extrator_politicos_camara"
    assert log_enviado["status"] == "Concluído"
    assert "data_inicio" in log_enviado
    assert "data_fim" in log_enviado
    assert log_enviado.get("linhas_afetadas") == 2
