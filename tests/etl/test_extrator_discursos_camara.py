import respx
import httpx
import pytest
from unittest.mock import patch, MagicMock

# Importação da função que ainda será implementada (esperado falhar com ImportError)
from etl.extrator_discursos_camara import extrair_pagina_discursos, executar_extracao_deputado, executar_pipeline_completo

@respx.mock
def test_pagina_links_next():
    """
    Testa a extração de uma página de discursos da API da Câmara.
    Garante que a função captura os dados brutos e extrai corretamente a URL da próxima página (rel='next').
    """
    url_base = "https://dadosabertos.camara.leg.br/api/v2/deputados/74646/discursos?dataInicio=2023-01-01&dataFim=2023-06-30"
    url_proxima = url_base + "&pagina=2"
    
    mock_json = {
        "dados": [
            {
                "dataHoraInicio": "2023-05-31T19:24",
                "faseEvento": {"titulo": "Breves Comunicações"},
                "transcricao": "O SR. AÉCIO NEVES - Discurso de teste."
            }
        ],
        "links": [
            {"rel": "next", "href": url_proxima}
        ]
    }
    
    respx.get(url_base).respond(status_code=200, json=mock_json)
    
    dados, next_url = extrair_pagina_discursos(url_base)
    
    assert len(dados) == 1
    assert dados[0]["dataHoraInicio"] == "2023-05-31T19:24"
    assert next_url == url_proxima


@respx.mock
@patch("time.sleep")
def test_pagina_retry_falhas(mock_sleep):
    """
    Testa se a função recupera de falhas do servidor (500, 503) na terceira tentativa,
    aplicando os backoffs (ex: 2s e 4s) antes de tentar novamente.
    """
    url = "https://dadosabertos.camara.leg.br/api/v2/deputados/74646/discursos"
    mock_json = {"dados": [{"dataHoraInicio": "2023-05-31T19:24"}], "links": []}
    
    route = respx.get(url)
    # Simula a Câmara caindo nas 2 primeiras requisições e voltando na 3ª
    route.side_effect = [
        httpx.Response(500),
        httpx.Response(503),
        httpx.Response(200, json=mock_json)
    ]
    
    dados, next_url = extrair_pagina_discursos(url)
    
    # Deve ter tentado 3 vezes na mesma URL
    assert route.call_count == 3
    # Deve ter feito sleep de 2s na primeira falha e 4s na segunda
    assert mock_sleep.call_count == 2
    mock_sleep.assert_any_call(2)
    mock_sleep.assert_any_call(4)
    assert len(dados) == 1


@respx.mock
@patch("time.sleep")
def test_orquestracao_extracao_upsert(mock_sleep):
    """
    Testa a orquestração da extração de um deputado (paginação completa).
    Garante que o loop varre todas as páginas (rel='next'), higieniza e faz o bulk upsert no banco.
    """
    id_deputado = 74646
    data_inicio = "2023-01-01"
    data_fim = "2023-06-30"
    
    url_pag_1 = f"https://dadosabertos.camara.leg.br/api/v2/deputados/{id_deputado}/discursos?dataInicio={data_inicio}&dataFim={data_fim}&itens=100"
    url_pag_2 = f"https://dadosabertos.camara.leg.br/api/v2/deputados/{id_deputado}/discursos?dataInicio={data_inicio}&dataFim={data_fim}&itens=100&pagina=2"
    
    mock_json_pag_1 = {
        "dados": [
            {
                "dataHoraInicio": "2023-05-31T19:24",
                "faseEvento": {"titulo": "Breves Comunicações"},
                "transcricao": "O SR. AÉCIO NEVES (PSDB - MG) - Discurso 1."
            }
        ],
        "links": [{"rel": "next", "href": url_pag_2}]
    }
    
    mock_json_pag_2 = {
        "dados": [
            {
                "dataHoraInicio": "2023-06-01T15:00",
                "faseEvento": {"titulo": "Homenagem"},
                "transcricao": "O SR. AÉCIO NEVES - Discurso 2."
            }
        ],
        "links": []
    }
    
    respx.get(url_pag_1).respond(status_code=200, json=mock_json_pag_1)
    respx.get(url_pag_2).respond(status_code=200, json=mock_json_pag_2)
    
    mock_supabase = MagicMock()
    
    linhas = executar_extracao_deputado(id_deputado, data_inicio, data_fim, mock_supabase)
    
    # Verificações
    assert linhas == 2
    mock_supabase.table.assert_called_with("discurso")
    mock_supabase.table().upsert.assert_called_once()
    
    args, _ = mock_supabase.table().upsert.call_args
    lote_enviado = args[0]
    
    assert len(lote_enviado) == 2
    assert lote_enviado[0]["texto_bruto"] == "Discurso 1."
    assert lote_enviado[1]["texto_bruto"] == "Discurso 2."


@respx.mock
@patch("time.sleep")
def test_orquestracao_remocao_duplicatas(mock_sleep):
    """
    Garante que o script remove discursos duplicados (mesmo UUID)
    vindos da API antes de enviar para o banco, evitando o erro 21000 do PostgreSQL.
    """
    id_deputado = 74646
    data_inicio = "2023-01-01"
    data_fim = "2023-06-30"
    
    url_pag = f"https://dadosabertos.camara.leg.br/api/v2/deputados/{id_deputado}/discursos?dataInicio={data_inicio}&dataFim={data_fim}&itens=100"
    
    mock_json = {
        "dados": [
            {
                "dataHoraInicio": "2023-05-31T19:24",
                "faseEvento": {"titulo": "Breves Comunicações"},
                "transcricao": "Discurso original."
            },
            {
                # Duplicata exata vinda da API
                "dataHoraInicio": "2023-05-31T19:24",
                "faseEvento": {"titulo": "Breves Comunicações"},
                "transcricao": "Discurso duplicado com sujeira."
            }
        ],
        "links": []
    }
    
    respx.get(url_pag).respond(status_code=200, json=mock_json)
    
    mock_supabase = MagicMock()
    linhas = executar_extracao_deputado(id_deputado, data_inicio, data_fim, mock_supabase)
    
    # O script deve ter filtrado a lista e enviado apenas 1 registro para o banco
    assert linhas == 1

@respx.mock
@patch("time.sleep")
def test_orquestracao_pipeline_completo(mock_sleep):
    """
    Testa a execução completa do pipeline de discursos.
    1. Busca deputados ativos no banco (Supabase).
    2. Executa a extração/transformação/upsert para cada deputado na janela de datas.
    3. Grava o log final na tabela etl_logs.
    """
    mock_supabase = MagicMock()
    # Simulando o banco retornando 2 deputados
    mock_supabase.table().select().eq().execute.return_value = MagicMock(
        data=[{"id": 1}, {"id": 2}]
    )
    
    # Mock das requisições para a amostra de 1 dia
    url_dep1 = "https://dadosabertos.camara.leg.br/api/v2/deputados/1/discursos?dataInicio=2023-01-01&dataFim=2023-01-02&itens=100"
    url_dep2 = "https://dadosabertos.camara.leg.br/api/v2/deputados/2/discursos?dataInicio=2023-01-01&dataFim=2023-01-02&itens=100"
    
    respx.get(url_dep1).respond(status_code=200, json={"dados": [], "links": []})
    respx.get(url_dep2).respond(status_code=200, json={"dados": [], "links": []})
    
    # Executamos o pipeline para a pequena amostra
    executar_pipeline_completo(mock_supabase, "2023-01-01", "2023-01-02")
    
    # Verifica se o log final foi inserido corretamente na tabela de auditoria
    mock_supabase.table.assert_any_call("etl_logs")
    mock_supabase.table().insert.assert_called_once()
    
    args_log, _ = mock_supabase.table().insert.call_args
    log_enviado = args_log[0]
    
    assert log_enviado["nome_rotina"] == "extrator_discursos_camara"
    assert log_enviado["status"] == "Concluído"
    assert "data_inicio" in log_enviado
    assert "data_fim" in log_enviado