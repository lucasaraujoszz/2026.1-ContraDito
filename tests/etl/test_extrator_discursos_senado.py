import httpx
from unittest.mock import patch, MagicMock

# Importamos a função que ainda será implementada (Fase RED)
from etl.extrator_discursos_senado import (
    obter_discursos_senador_api,
    obter_html_discurso_senado,
    executar_extracao_senador,
    executar_pipeline_completo,
)


@patch("etl.extrator_discursos_senado.httpx.get")
def test_api_offset_e_headers(mock_get):
    """
    Garante que o id_senador da base é passado para o roteamento
    correto na API, e que o header JSON seja injetado.
    """
    # Simulamos um retorno 200 HTTP com JSON vazio para avaliar apenas a URL/Requisição
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}
    mock_get.return_value = mock_response

    id_senador_banco = 150
    data_inicio = "2023-01-01"
    data_fim = "2023-12-31"

    obter_discursos_senador_api(id_senador_banco, data_inicio, data_fim)

    # Verifica a montagem correta da URL (ID da API = 150) e a presença do header
    url_esperada = "https://legis.senado.leg.br/dadosabertos/senador/150/discursos?dataInicio=2023-01-01&dataFim=2023-12-31"
    mock_get.assert_called_once_with(
        url_esperada,
        headers={"Accept": "application/json"},
        timeout=30.0,
        follow_redirects=True,
    )


@patch("etl.extrator_discursos_senado.httpx.get")
def test_api_retry_falhas(mock_get):
    """
    Garante que a função aplica retentativas via Tenacity em caso de Rate Limit (429)
    ou erro de Servidor (500+), e consegue recuperar o dado na última tentativa.
    """
    mock_resp_500 = MagicMock()
    mock_resp_500.status_code = 500
    mock_resp_500.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500 Server Error", request=MagicMock(), response=mock_resp_500
    )

    mock_resp_429 = MagicMock()
    mock_resp_429.status_code = 429
    mock_resp_429.raise_for_status.side_effect = httpx.HTTPStatusError(
        "429 Rate Limit", request=MagicMock(), response=mock_resp_429
    )

    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.json.return_value = {"sucesso": True}

    # Simula 2 falhas (500 e 429) seguidas de 1 sucesso (200)
    mock_get.side_effect = [mock_resp_500, mock_resp_429, mock_resp_200]

    status_code, payload = obter_discursos_senador_api(150, "2023-01-01", "2023-12-31")

    assert mock_get.call_count == 3
    assert status_code == 200
    assert payload == {"sucesso": True}


@patch("etl.extrator_discursos_senado.httpx.get")
def test_html_retry_sucesso(mock_get):
    """
    Garante que o Scraping N+1 do HTML do Senado respeite o Rate Limit
    (usando o Tenacity) e retorne a string HTML bruta com sucesso.
    """
    mock_resp_429 = MagicMock()
    mock_resp_429.status_code = 429
    mock_resp_429.raise_for_status.side_effect = httpx.HTTPStatusError(
        "429 Rate Limit", request=MagicMock(), response=mock_resp_429
    )

    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.text = "<html><body>Texto do discurso</body></html>"

    # Simula 1 falha (429 bloqueio do WAF) e 1 sucesso
    mock_get.side_effect = [mock_resp_429, mock_resp_200]

    html = obter_html_discurso_senado("http://legis.senado.leg.br/texto/12345")

    assert mock_get.call_count == 2
    assert "Texto do discurso" in html


@patch("etl.extrator_discursos_senado.httpx.get")
def test_html_falha_rede_critica(mock_get):
    """
    Fase RED - BUG 2: Se a instabilidade da rede for tão forte que esgote o
    Tenacity, o sistema não pode mascarar o erro como "[FALHA NO PARSER HTML]"
    (que é exclusivo para quando o layout muda). Deve acusar erro de rede.
    """
    # Esgota todas as tentativas com falha de conexão crítica
    mock_get.side_effect = httpx.ConnectTimeout("Sem internet")

    mock_supabase = MagicMock()

    with patch("etl.extrator_discursos_senado.obter_discursos_senador_api") as mock_api:
        mock_api.return_value = (
            200,
            {
                "PesquisaPronunciamentos": {
                    "Pronunciamentos": {
                        "Pronunciamento": {
                            "CodigoPronunciamento": "123",
                            "DataPronunciamento": "2023-01-01",
                            "TipoUsoPalavra": {"Descricao": "Sessão"},
                            "UrlTexto": "http://legis.senado.leg.br/texto",
                        }
                    }
                }
            },
        )

        executar_extracao_senador(150, "2023-01-01", "2023-12-31", mock_supabase)

        args, _ = mock_supabase.table().upsert.call_args
        lote_enviado = args[0]

        # O erro verdadeiro foi de rede. O texto bruto deve registrar isso, e não erro de parser.
        assert lote_enviado[0]["texto_bruto"] != "[FALHA NO PARSER HTML]"
        assert lote_enviado[0]["texto_bruto"] == "[ERRO DE REDE]"


@patch("etl.extrator_discursos_senado.time.sleep")
@patch("etl.extrator_discursos_senado.obter_html_discurso_senado")
@patch("etl.extrator_discursos_senado.obter_discursos_senador_api")
def test_orquestracao_extracao_senador(mock_api, mock_html, mock_sleep):
    """
    Garante a orquestração completa: busca discursos na API, raspa o HTML de cada um,
    transforma os dados respeitando o Data Contract e envia em lote pro Supabase.
    """
    # 1. Mock da API retornando HTTP 200 e 1 discurso válido
    mock_api.return_value = (
        200,
        {
            "PesquisaPronunciamentos": {
                "Pronunciamentos": {
                    "Pronunciamento": {
                        "CodigoPronunciamento": "999",
                        "DataPronunciamento": "2023-01-01",
                        "TipoUsoPalavra": {"Descricao": "Sessão"},
                        "UrlTexto": "http://legis.senado.leg.br/texto",
                    }
                }
            }
        },
    )

    # 2. Mock do Scraping retornando um HTML válido do Senado (O SR. TESTE será decepado)
    mock_html.return_value = "<html><body><div class='texto-pronunciamento'>O SR. TESTE (PL - SP) - Olá. Este é um discurso simulado longo o suficiente para passar pela trava de segurança.</div></body></html>"

    # 3. Mock do Supabase
    mock_supabase = MagicMock()

    linhas = executar_extracao_senador(150, "2023-01-01", "2023-12-31", mock_supabase)

    # Verifica orquestração (chamadas e rate limit)
    mock_api.assert_called_once_with(150, "2023-01-01", "2023-12-31")
    mock_html.assert_called_once_with("http://legis.senado.leg.br/texto")
    mock_sleep.assert_called()

    # Verifica o Upsert e a conformidade final
    assert linhas == 1
    mock_supabase.table.assert_called_with("senado_discursos")
    mock_supabase.table().upsert.assert_called_once()

    args, _ = mock_supabase.table().upsert.call_args
    lote_enviado = args[0]
    assert len(lote_enviado) == 1
    assert (
        lote_enviado[0]["texto_bruto"]
        == "Olá. Este é um discurso simulado longo o suficiente para passar pela trava de segurança."
    )
    assert lote_enviado[0]["fase_evento"] == "Sessão"


@patch("etl.extrator_discursos_senado.executar_extracao_senador")
def test_orquestracao_pipeline_completo(mock_executar):
    """
    Garante a orquestração global: busca senadores na base, itera chamando
    a extração individual e finaliza registrando o resultado no etl_logs.
    """
    mock_supabase = MagicMock()

    # Mock do retorno da busca de senadores
    mock_response_politicos = MagicMock()
    mock_response_politicos.data = [{"id": 150}, {"id": 151}]

    # Encadeamento do Supabase: table("senado_politicos").select("id").execute()
    mock_supabase.table.return_value.select.return_value.execute.return_value = (
        mock_response_politicos
    )

    # Simulamos que a extração de cada senador rendeu 5 discursos (total 10)
    mock_executar.return_value = 5

    executar_pipeline_completo(mock_supabase, "2023-01-01", "2023-12-31")

    # Verifica se rodou para os 2 senadores
    assert mock_executar.call_count == 2
    mock_executar.assert_any_call(150, "2023-01-01", "2023-12-31", mock_supabase)
    mock_executar.assert_any_call(151, "2023-01-01", "2023-12-31", mock_supabase)

    # Verifica o Watermarker (Registro de Log)
    mock_supabase.table().insert.assert_called_once()
    args, _ = mock_supabase.table().insert.call_args
    log_enviado = args[0]
    assert log_enviado["nome_rotina"] == "extrator_discursos_senado"
    assert log_enviado["status"] == "Concluído"
    assert log_enviado["linhas_afetadas"] == 10
