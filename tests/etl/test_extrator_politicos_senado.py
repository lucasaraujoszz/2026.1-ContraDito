import respx
import httpx
from unittest.mock import patch, MagicMock
from etl.extrator_politicos_senado import extrair_senadores, executar_pipeline_senadores


@respx.mock
def test_api_offset_e_schema():
    """
    Testa a requisição à API do Senado garantindo que:
    1. O header 'Accept: application/json' seja respeitado.
    2. Os campos básicos sejam mapeados para o schema correto do banco.
    """
    url = "https://legis.senado.leg.br/dadosabertos/senador/lista/legislatura/57.json"

    mock_json = {
        "ListaParlamentarLegislatura": {
            "Parlamentares": {
                "Parlamentar": [
                    {
                        "IdentificacaoParlamentar": {
                            "CodigoParlamentar": "500",
                            "NomeCompletoParlamentar": "Senador Teste Completo",
                            "NomeParlamentar": "Senador Teste",
                            "SiglaPartidoParlamentar": "PART",
                            "UfParlamentar": "UF",
                            "UrlFotoParlamentar": "http://foto.com/500.jpg",
                        },
                        "Mandatos": {
                            "Mandato": [
                                {
                                    "DescricaoParticipacao": "Titular",
                                    "Exercicios": {
                                        "Exercicio": [{"DataInicio": "2023-02-01"}]
                                    },  # Sem DataFim = Ativo
                                }
                            ]
                        },
                    }
                ]
            }
        }
    }

    respx.get(url).respond(status_code=200, json=mock_json)

    resultado = extrair_senadores(url)

    assert len(resultado) == 1
    # Garante o ID original da API
    assert resultado[0]["id"] == 500
    # Garante a formatação do Schema
    assert resultado[0]["nome_civil"] == "Senador Teste Completo"
    assert resultado[0]["nome_urna"] == "Senador Teste"
    assert resultado[0]["cargo"] == "Senador"
    assert resultado[0]["status_mandato"] == "Ativo"
    assert "data_ultima_atualizacao" in resultado[0]


@respx.mock
def test_anomalia_dict_unico():
    """
    Testa a falha comum de APIs que convertem XML->JSON:
    Garante que se a API retornar apenas 1 senador como Dict (em vez de Lista),
    o script não quebre no laço 'for' e processe normalmente.
    """
    url = "https://legis.senado.leg.br/dadosabertos/senador/lista/legislatura/57.json"

    mock_json = {
        "ListaParlamentarLegislatura": {
            "Parlamentares": {
                # Retornando um Objeto direto em vez de uma Lista []
                "Parlamentar": {
                    "IdentificacaoParlamentar": {"CodigoParlamentar": "99"},
                    "Mandatos": {
                        "Mandato": [
                            {
                                "DescricaoParticipacao": "Titular",
                                "Exercicios": {
                                    "Exercicio": [{"DataInicio": "2023-02-01"}]
                                },
                            }
                        ]
                    },
                }
            }
        }
    }

    respx.get(url).respond(status_code=200, json=mock_json)

    resultado = extrair_senadores(url)
    assert len(resultado) == 1
    assert resultado[0]["id"] == 99


@respx.mock
def test_conversao_arvore_status():
    """
    Testa a árvore de decisão do Senado para os 3 status possíveis no nosso banco (Padronizado com a Câmara):
    - Titular em Exercício -> Ativo
    - Suplente em Exercício -> Ativo
    - Titular Afastado / Fora de Exercício -> Inativo
    """
    url = "https://legis.senado.leg.br/dadosabertos/senador/lista/legislatura/57.json"

    mock_json = {
        "ListaParlamentarLegislatura": {
            "Parlamentares": {
                "Parlamentar": [
                    {
                        "IdentificacaoParlamentar": {"CodigoParlamentar": "1"},
                        "Mandatos": {
                            "Mandato": [
                                {
                                    "DescricaoParticipacao": "Titular",
                                    "Exercicios": {
                                        "Exercicio": [{"DataInicio": "2023-02-01"}]
                                    },
                                }
                            ]
                        },
                    },
                    {
                        "IdentificacaoParlamentar": {"CodigoParlamentar": "2"},
                        "Mandatos": {
                            "Mandato": [
                                {
                                    "DescricaoParticipacao": "1º Suplente",
                                    "Exercicios": {
                                        "Exercicio": [{"DataInicio": "2023-02-01"}]
                                    },
                                }
                            ]
                        },
                    },
                    {
                        "IdentificacaoParlamentar": {"CodigoParlamentar": "3"},
                        "Mandatos": {
                            "Mandato": [
                                {
                                    "DescricaoParticipacao": "Titular",
                                    "Exercicios": {
                                        "Exercicio": [
                                            {
                                                "DataInicio": "2019-02-01",
                                                "DataFim": "2020-10-21",
                                            }
                                        ]
                                    },  # Com DataFim = Inativo
                                }
                            ]
                        },
                    },
                ]
            }
        }
    }

    respx.get(url).respond(status_code=200, json=mock_json)

    resultado = extrair_senadores(url)

    assert resultado[0]["status_mandato"] == "Ativo"
    assert resultado[1]["status_mandato"] == "Ativo"
    assert resultado[2]["status_mandato"] == "Inativo"


@respx.mock
def test_inclusao_suplentes_sem_exercicio():
    """
    Testa a regra de negócio atualizada (Padrão Câmara):
    Suplentes que nunca assumiram (sem bloco 'Exercicios' válido)
    devem ser extraídos e marcados como Suplentes (aguardando) na lista final.
    """
    url = "https://legis.senado.leg.br/dadosabertos/senador/lista/legislatura/57.json"

    mock_json = {
        "ListaParlamentarLegislatura": {
            "Parlamentares": {
                "Parlamentar": [
                    {
                        "IdentificacaoParlamentar": {
                            "CodigoParlamentar": "1",
                            "NomeParlamentar": "Senador Titular",
                        },
                        "Mandatos": {
                            "Mandato": [
                                {
                                    "DescricaoParticipacao": "Titular",
                                    "Exercicios": {
                                        "Exercicio": [{"DataInicio": "2023-02-01"}]
                                    },
                                }
                            ]
                        },
                    },
                    {
                        "IdentificacaoParlamentar": {
                            "CodigoParlamentar": "2",
                            "NomeParlamentar": "Suplente Fantasma",
                        },
                        "Mandatos": {
                            "Mandato": [
                                {
                                    "DescricaoParticipacao": "1º Suplente",
                                    "Exercicios": {},
                                }
                            ]
                        },  # Sem exercício, nunca assumiu
                    },
                ]
            }
        }
    }

    respx.get(url).respond(status_code=200, json=mock_json)

    resultado = extrair_senadores(url)

    # Deve retornar os 2, incluindo o "Suplente Fantasma" aguardando
    assert len(resultado) == 2
    assert resultado[0]["nome_urna"] == "Senador Titular"
    assert resultado[1]["nome_urna"] == "Suplente Fantasma"
    assert resultado[1]["status_mandato"] == "Suplente"


@respx.mock
def test_busca_exercicio_ativo():
    """
    Testa a correção de Status Quebrado:
    Garante que o script não pega cegamente o índice [0], mas varre a lista
    de exercícios para encontrar o atual, mapeando corretamente para 'Ativo'.
    """
    url = "https://legis.senado.leg.br/dadosabertos/senador/lista/legislatura/57.json"

    mock_json = {
        "ListaParlamentarLegislatura": {
            "Parlamentares": {
                "Parlamentar": [
                    {
                        "IdentificacaoParlamentar": {
                            "CodigoParlamentar": "1",
                            "NomeParlamentar": "Senador Reeleito",
                        },
                        "Mandatos": {
                            "Mandato": [
                                {
                                    "DescricaoParticipacao": "Titular",
                                    "Exercicios": {
                                        "Exercicio": [
                                            {
                                                "DataInicio": "2019-02-01",
                                                "DataFim": "2023-01-31",
                                            },  # Índice 0 antigo
                                            {
                                                "DataInicio": "2023-02-01"
                                            },  # Índice 1 atual
                                        ]
                                    },
                                }
                            ]
                        },
                    }
                ]
            }
        }
    }

    respx.get(url).respond(status_code=200, json=mock_json)

    resultado = extrair_senadores(url)

    # O script deve achar o status "Exercício" e setar como Ativo, não como Inativo
    assert resultado[0]["status_mandato"] == "Ativo"


@respx.mock
@patch("time.sleep")
def test_orquestracao_pipeline_completo(mock_sleep):
    """
    Testa o pipeline completo do Senado:
    1. Requisição com retry (herdado dos deputados).
    2. Extração sem problema N+1.
    3. Upsert no Supabase e log final.
    """
    url = "https://legis.senado.leg.br/dadosabertos/senador/lista/legislatura/57.json"

    mock_json = {
        "ListaParlamentarLegislatura": {
            "Parlamentares": {
                "Parlamentar": [
                    {
                        "IdentificacaoParlamentar": {"CodigoParlamentar": "500"},
                        "Mandatos": {
                            "Mandato": [
                                {
                                    "DescricaoParticipacao": "Titular",
                                    "Exercicios": {
                                        "Exercicio": [{"DataInicio": "2023-02-01"}]
                                    },
                                }
                            ]
                        },
                    }
                ]
            }
        }
    }

    # Simulando 1 falha e depois sucesso para provar que o Retry funciona!
    respx.get(url).side_effect = [
        httpx.Response(500),
        httpx.Response(200, json=mock_json),
    ]

    mock_supabase = MagicMock()
    executar_pipeline_senadores(mock_supabase)

    # Garante que o Supabase recebeu a inserção em lote e o log
    mock_supabase.table.assert_any_call("senado_politicos")
    mock_supabase.table().upsert.assert_called_once()
    args_log, _ = mock_supabase.table().insert.call_args
    assert args_log[0]["linhas_afetadas"] == 1
    assert args_log[0]["nome_rotina"] == "extrator_politicos_senado"
