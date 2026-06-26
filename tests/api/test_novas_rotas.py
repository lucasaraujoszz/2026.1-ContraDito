import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def mock_supabase():
    with patch("app.rotas.dados.supabase") as mock:
        # We need to make sure the same mock is returned for all calls to table()
        mock.table.return_value = mock
        yield mock


def test_timeline_casa_invalida(client):
    resposta = client.get("/api/invalid_house/politicos/123/timeline")
    assert resposta.status_code == 400
    assert "Casa inválida" in resposta.json()["detail"]


def test_timeline_sucesso_ordenacao(client, mock_supabase):
    # Mock data with newer date first to test sorting
    mock_result = MagicMock()
    mock_result.data = [
        {
            "voto_oficial": "SIM",
            "proposicao_id": "PL-123-2026",
            "camara_proposicoes": {
                "data_votacao": "2026-06-20",
                "tipo": "PL",
                "numero": 123,
                "ano": 2026,
                "ementa": "Ementa A",
            },
        },
        {
            "voto_oficial": "NÃO",
            "proposicao_id": "PEC-1-2026",
            "camara_proposicoes": {
                "data_votacao": "2026-06-15",
                "tipo": "PEC",
                "numero": 1,
                "ano": 2026,
                "ementa": "Ementa B",
            },
        },
    ]

    mock_query = MagicMock()
    mock_query.eq.return_value = mock_query
    mock_query.execute.return_value = mock_result
    mock_supabase.table.return_value.select.return_value = mock_query

    resposta = client.get("/api/camara/politicos/123/timeline")
    assert resposta.status_code == 200

    dados = resposta.json()
    assert len(dados) == 2
    assert dados[0]["proposicao_id"] == "PEC-1-2026"
    assert dados[0]["voto_oficial"] == "NÃO"
    assert dados[0]["data_votacao"] == "2026-06-15"

    assert dados[1]["proposicao_id"] == "PL-123-2026"
    assert dados[1]["voto_oficial"] == "SIM"
    assert dados[1]["data_votacao"] == "2026-06-20"


def test_comparar_casa_invalida(client):
    resposta = client.get("/api/comparar?politico_id_1=1&politico_id_2=2&casa=invalid")
    assert resposta.status_code == 400


def test_comparar_sucesso(client, mock_supabase):
    # Mock votes for politician 1
    mock_votes_1 = MagicMock()
    mock_votes_1.data = [
        {
            "voto_oficial": "SIM",
            "proposicao_id": "PL-123-2026",
            "camara_proposicoes": {"ementa": "Ementa A"},
        },
        {
            "voto_oficial": "SIM",
            "proposicao_id": "PL-124-2026",
            "camara_proposicoes": {"ementa": "Ementa B"},
        },
    ]

    # Mock votes for politician 2
    mock_votes_2 = MagicMock()
    mock_votes_2.data = [
        {
            "voto_oficial": "SIM",
            "proposicao_id": "PL-123-2026",
            "camara_proposicoes": {"ementa": "Ementa A"},
        },
        {
            "voto_oficial": "NÃO",
            "proposicao_id": "PL-124-2026",
            "camara_proposicoes": {"ementa": "Ementa B"},
        },
    ]

    # Builder sequential routing
    mock_query_1 = MagicMock()
    mock_query_1.execute.return_value = mock_votes_1

    mock_query_2 = MagicMock()
    mock_query_2.execute.return_value = mock_votes_2

    mock_query_table = MagicMock()
    # eq for politician 1 returns query_1, eq for politician 2 returns query_2
    mock_query_table.select.return_value.eq.side_effect = [mock_query_1, mock_query_2]
    mock_supabase.table.return_value = mock_query_table

    resposta = client.get("/api/comparar?politico_id_1=1&politico_id_2=2&casa=camara")
    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["proposicoes_em_comum"] == 2
    assert dados["concordancia_percentual"] == 50.0
    assert len(dados["divergencias"]) == 1
    assert dados["divergencias"][0]["proposicao_id"] == "PL-124-2026"
    assert dados["divergencias"][0]["voto_politico_1"] == "SIM"
    assert dados["divergencias"][0]["voto_politico_2"] == "NÃO"


def test_afinidades_politico_inexistente(client, mock_supabase):
    mock_politico_result = MagicMock()
    mock_politico_result.data = []

    mock_query_politico = MagicMock()
    mock_query_politico.select.return_value.eq.return_value.execute.return_value = (
        mock_politico_result
    )
    mock_supabase.table.return_value = mock_query_politico

    resposta = client.get("/api/camara/politicos/999/afinidades")
    assert resposta.status_code == 404


def test_afinidades_sucesso(client, mock_supabase):
    def mock_table_routing_afinidades(tabela):
        mock_query = MagicMock()
        if tabela == "camara_politicos":
            mock_builder = MagicMock()
            # eq("id", 1) call
            mock_builder.eq.return_value.execute.return_value.data = [
                {
                    "id": 1,
                    "nome_civil": "P1",
                    "nome_urna": "P1",
                    "partido": "PT",
                    "cargo": "Deputado Federal",
                    "estado": "DF",
                    "status_mandato": "Ativo",
                    "url_foto": "http://foto.jpg",
                }
            ]
            # execute for all politicos call
            mock_builder.execute.return_value.data = [
                {
                    "id": 1,
                    "nome_civil": "P1",
                    "nome_urna": "P1",
                    "partido": "PT",
                    "cargo": "Deputado Federal",
                    "estado": "DF",
                    "status_mandato": "Ativo",
                    "url_foto": "http://foto.jpg",
                },
                {
                    "id": 2,
                    "nome_civil": "P2",
                    "nome_urna": "P2",
                    "partido": "PT",
                    "cargo": "Deputado Federal",
                    "estado": "DF",
                    "status_mandato": "Ativo",
                    "url_foto": "http://foto.jpg",
                },
                {
                    "id": 3,
                    "nome_civil": "P3",
                    "nome_urna": "P3",
                    "partido": "PT",
                    "cargo": "Deputado Federal",
                    "estado": "DF",
                    "status_mandato": "Ativo",
                    "url_foto": "http://foto.jpg",
                },
            ]
            mock_query.select.return_value = mock_builder
        elif tabela == "camara_votos":
            mock_builder_votos = MagicMock()
            # target votes query
            mock_target_result = MagicMock()
            mock_target_result.data = [
                {"proposicao_id": f"P-{i}", "voto_oficial": "SIM"} for i in range(5)
            ]

            # all votes query
            mock_all_result = MagicMock()
            mock_all_result.data = [
                {"proposicao_id": f"P-{i}", "voto_oficial": "SIM", "politico_id": 2}
                for i in range(5)
            ] + [
                {"proposicao_id": f"P-{i}", "voto_oficial": "NÃO", "politico_id": 3}
                for i in range(5)
            ]

            mock_builder_votos.eq.return_value.execute.return_value = mock_target_result
            mock_builder_votos.execute.return_value = mock_all_result
            mock_query.select.return_value = mock_builder_votos
        return mock_query

    mock_supabase.table.side_effect = mock_table_routing_afinidades

    resposta = client.get("/api/camara/politicos/1/afinidades")
    assert resposta.status_code == 200
    dados = resposta.json()

    # Politico 2 has 100% agreement (SIM vs SIM)
    assert dados["gemeo"]["politico"]["id"] == 2
    assert dados["gemeo"]["concordancia"] == 100.0
    assert dados["gemeo"]["votos_comuns"] == 5

    # Politico 3 has 0% agreement (SIM vs NAO)
    assert dados["antipoda"]["politico"]["id"] == 3
    assert dados["antipoda"]["concordancia"] == 0.0
    assert dados["antipoda"]["votos_comuns"] == 5


def test_fidelidade_politico_inexistente(client, mock_supabase):
    mock_politico_result = MagicMock()
    mock_politico_result.data = []

    mock_query_politico = MagicMock()
    mock_query_politico.select.return_value.eq.return_value.execute.return_value = (
        mock_politico_result
    )
    mock_supabase.table.return_value = mock_query_politico

    resposta = client.get("/api/camara/politicos/999/fidelidade")
    assert resposta.status_code == 404


def test_fidelidade_sucesso_calculo(client, mock_supabase):
    def mock_table_routing_fidelidade(tabela):
        mock_query = MagicMock()
        if tabela == "camara_politicos":
            mock_builder = MagicMock()
            mock_builder.eq.return_value.execute.return_value.data = [
                {
                    "id": 1,
                    "nome_civil": "P1",
                    "nome_urna": "P1",
                    "partido": "PT",
                    "cargo": "Deputado Federal",
                    "estado": "DF",
                    "status_mandato": "Ativo",
                }
            ]
            mock_query.select.return_value = mock_builder
        elif tabela == "camara_votos":
            mock_builder_votos = MagicMock()

            mock_target_result = MagicMock()
            mock_target_result.data = [
                {
                    "proposicao_id": "Prop-1",
                    "voto_oficial": "SIM",
                    "partido_na_epoca": "PT",
                },
                {
                    "proposicao_id": "Prop-2",
                    "voto_oficial": "SIM",
                    "partido_na_epoca": "PT",
                },
                {
                    "proposicao_id": "Prop-3",
                    "voto_oficial": "NÃO",
                    "partido_na_epoca": "PT",
                },
            ]

            mock_all_result = MagicMock()
            mock_all_result.data = [
                {
                    "proposicao_id": "Prop-1",
                    "voto_oficial": "SIM",
                    "partido_na_epoca": "PT",
                    "politico_id": 1,
                },
                {
                    "proposicao_id": "Prop-1",
                    "voto_oficial": "SIM",
                    "partido_na_epoca": "PT",
                    "politico_id": 2,
                },
                {
                    "proposicao_id": "Prop-1",
                    "voto_oficial": "SIM",
                    "partido_na_epoca": "PT",
                    "politico_id": 3,
                },
                {
                    "proposicao_id": "Prop-1",
                    "voto_oficial": "SIM",
                    "partido_na_epoca": "PT",
                    "politico_id": 4,
                },
                {
                    "proposicao_id": "Prop-1",
                    "voto_oficial": "SIM",
                    "partido_na_epoca": "PT",
                    "politico_id": 5,
                },
                {
                    "proposicao_id": "Prop-1",
                    "voto_oficial": "NÃO",
                    "partido_na_epoca": "PT",
                    "politico_id": 6,
                },
                {
                    "proposicao_id": "Prop-2",
                    "voto_oficial": "SIM",
                    "partido_na_epoca": "PT",
                    "politico_id": 1,
                },
                {
                    "proposicao_id": "Prop-2",
                    "voto_oficial": "NÃO",
                    "partido_na_epoca": "PT",
                    "politico_id": 2,
                },
                {
                    "proposicao_id": "Prop-2",
                    "voto_oficial": "NÃO",
                    "partido_na_epoca": "PT",
                    "politico_id": 3,
                },
                {
                    "proposicao_id": "Prop-2",
                    "voto_oficial": "NÃO",
                    "partido_na_epoca": "PT",
                    "politico_id": 4,
                },
                {
                    "proposicao_id": "Prop-2",
                    "voto_oficial": "NÃO",
                    "partido_na_epoca": "PT",
                    "politico_id": 5,
                },
                {
                    "proposicao_id": "Prop-2",
                    "voto_oficial": "NÃO",
                    "partido_na_epoca": "PT",
                    "politico_id": 6,
                },
                {
                    "proposicao_id": "Prop-3",
                    "voto_oficial": "NÃO",
                    "partido_na_epoca": "PT",
                    "politico_id": 1,
                },
                {
                    "proposicao_id": "Prop-3",
                    "voto_oficial": "NÃO",
                    "partido_na_epoca": "PT",
                    "politico_id": 2,
                },
                {
                    "proposicao_id": "Prop-3",
                    "voto_oficial": "NÃO",
                    "partido_na_epoca": "PT",
                    "politico_id": 3,
                },
                {
                    "proposicao_id": "Prop-3",
                    "voto_oficial": "NÃO",
                    "partido_na_epoca": "PT",
                    "politico_id": 4,
                },
                {
                    "proposicao_id": "Prop-3",
                    "voto_oficial": "NÃO",
                    "partido_na_epoca": "PT",
                    "politico_id": 5,
                },
            ]

            mock_builder_votos.eq.return_value.execute.return_value = mock_target_result
            mock_builder_votos.execute.return_value = mock_all_result
            mock_query.select.return_value = mock_builder_votos
        return mock_query

    mock_supabase.table.side_effect = mock_table_routing_fidelidade

    resposta = client.get("/api/camara/politicos/1/fidelidade")
    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["total_votos_com_orientacao"] == 3
    assert dados["votos_alinhados"] == 2
    assert dados["votos_rebeldes"] == 1
    assert dados["taxa_fidelidade"] == 66.7


def test_polarizacao_proposicao_inexistente(client, mock_supabase):
    mock_result_prop = MagicMock()
    mock_result_prop.data = []

    mock_query_prop = MagicMock()
    mock_query_prop.select.return_value.eq.return_value.execute.return_value = (
        mock_result_prop
    )
    mock_supabase.table.return_value = mock_query_prop

    resposta = client.get("/api/camara/proposicoes/999/polarizacao")
    assert resposta.status_code == 404


def test_polarizacao_sucesso_calculo(client, mock_supabase):
    def mock_table_routing_polarizacao(tabela):
        mock_query = MagicMock()
        if tabela == "camara_proposicoes":
            mock_builder = MagicMock()
            mock_builder.eq.return_value.execute.return_value.data = [
                {
                    "id": "Prop-1",
                    "proposicao_id": "PL-123",
                    "tipo": "PL",
                    "numero": 123,
                    "ano": 2026,
                }
            ]
            mock_query.select.return_value = mock_builder
        elif tabela == "camara_votos":
            mock_builder_votos = MagicMock()
            mock_result_votos = MagicMock()
            mock_result_votos.data = [
                {"voto_oficial": "SIM"},
                {"voto_oficial": "SIM"},
                {"voto_oficial": "SIM"},
                {"voto_oficial": "NÃO"},
                {"voto_oficial": "Ausente"},
            ]
            mock_builder_votos.eq.return_value.execute.return_value = mock_result_votos
            mock_query.select.return_value = mock_builder_votos
        return mock_query

    mock_supabase.table.side_effect = mock_table_routing_polarizacao

    resposta = client.get("/api/camara/proposicoes/Prop-1/polarizacao")
    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["proposicao_id"] == "PL-123"
    assert dados["qtd_sim"] == 3
    assert dados["qtd_nao"] == 1
    assert dados["pct_sim"] == 75.0
    assert dados["pct_nao"] == 25.0
    assert dados["polarizacao"] == 50.0
    assert dados["classificacao"] == "Dividida"


def test_coesao_partidos_casa_invalida(client):
    resposta = client.get("/api/invalid_house/partidos/coesao")
    assert resposta.status_code == 400


def test_coesao_partidos_sucesso(client, mock_supabase):
    mock_result_votos = MagicMock()
    mock_result_votos.data = [
        {
            "proposicao_id": "Prop-1",
            "voto_oficial": "SIM",
            "partido_na_epoca": "PT",
            "politico_id": 1,
        },
        {
            "proposicao_id": "Prop-1",
            "voto_oficial": "SIM",
            "partido_na_epoca": "PT",
            "politico_id": 2,
        },
        {
            "proposicao_id": "Prop-1",
            "voto_oficial": "SIM",
            "partido_na_epoca": "PT",
            "politico_id": 3,
        },
        {
            "proposicao_id": "Prop-1",
            "voto_oficial": "NÃO",
            "partido_na_epoca": "PT",
            "politico_id": 4,
        },
        {
            "proposicao_id": "Prop-1",
            "voto_oficial": "SIM",
            "partido_na_epoca": "PL",
            "politico_id": 5,
        },
        {
            "proposicao_id": "Prop-1",
            "voto_oficial": "SIM",
            "partido_na_epoca": "PL",
            "politico_id": 6,
        },
        {
            "proposicao_id": "Prop-1",
            "voto_oficial": "SIM",
            "partido_na_epoca": "PL",
            "politico_id": 7,
        },
        {
            "proposicao_id": "Prop-1",
            "voto_oficial": "SIM",
            "partido_na_epoca": "PL",
            "politico_id": 8,
        },
        {
            "proposicao_id": "Prop-2",
            "voto_oficial": "SIM",
            "partido_na_epoca": "PT",
            "politico_id": 1,
        },
        {
            "proposicao_id": "Prop-2",
            "voto_oficial": "SIM",
            "partido_na_epoca": "PT",
            "politico_id": 2,
        },
        {
            "proposicao_id": "Prop-2",
            "voto_oficial": "SIM",
            "partido_na_epoca": "PT",
            "politico_id": 3,
        },
        {
            "proposicao_id": "Prop-2",
            "voto_oficial": "SIM",
            "partido_na_epoca": "PT",
            "politico_id": 4,
        },
        {
            "proposicao_id": "Prop-2",
            "voto_oficial": "SIM",
            "partido_na_epoca": "PL",
            "politico_id": 5,
        },
        {
            "proposicao_id": "Prop-2",
            "voto_oficial": "SIM",
            "partido_na_epoca": "PL",
            "politico_id": 6,
        },
        {
            "proposicao_id": "Prop-2",
            "voto_oficial": "NÃO",
            "partido_na_epoca": "PL",
            "politico_id": 7,
        },
        {
            "proposicao_id": "Prop-2",
            "voto_oficial": "NÃO",
            "partido_na_epoca": "PL",
            "politico_id": 8,
        },
    ]

    mock_query = MagicMock()
    mock_query.select.return_value.execute.return_value = mock_result_votos
    mock_supabase.table.return_value = mock_query

    resposta = client.get("/api/camara/partidos/coesao")
    assert resposta.status_code == 200
    dados = resposta.json()
    assert len(dados["itens"]) == 2
    assert dados["itens"][0]["partido"] == "PT"
    assert dados["itens"][0]["indice_coesao"] == 75.0
    assert dados["itens"][1]["partido"] == "PL"
    assert dados["itens"][1]["indice_coesao"] == 50.0


def test_obter_discurso_detalhado_inexistente(client, mock_supabase):
    mock_result = MagicMock()
    mock_result.data = []

    mock_query = MagicMock()
    mock_query.select.return_value.eq.return_value.execute.return_value = mock_result
    mock_supabase.table.return_value = mock_query

    resposta = client.get("/api/camara/discursos/e0e84b6f-7023-4554-949e-f00de7a44f77")
    assert resposta.status_code == 404


def test_obter_discurso_detalhado_sucesso(client, mock_supabase):
    mock_result = MagicMock()
    mock_result.data = [
        {
            "id": "e0e84b6f-7023-4554-949e-f00de7a44f77",
            "politico_id": 12345,
            "data_discurso": "2026-06-22T10:00:00Z",
            "texto_bruto": "Discurso de Teste sobre educação completo",
            "url_video": "http://youtube.com/v",
            "sumario": "Fala sobre educação.",
            "fase_evento": "Pequeno Expediente",
        }
    ]

    mock_query = MagicMock()
    mock_query.select.return_value.eq.return_value.execute.return_value = mock_result
    mock_supabase.table.return_value = mock_query

    resposta = client.get("/api/camara/discursos/e0e84b6f-7023-4554-949e-f00de7a44f77")
    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["id"] == "e0e84b6f-7023-4554-949e-f00de7a44f77"
    assert dados["texto_bruto"] == "Discurso de Teste sobre educação completo"


def test_listar_discursos_politico_casa_invalida(client):
    resposta = client.get("/api/invalid/politicos/12345/discursos")
    assert resposta.status_code == 400


def test_listar_discursos_politico_inexistente(client, mock_supabase):
    mock_politico_result = MagicMock()
    mock_politico_result.data = []

    mock_query = MagicMock()
    mock_query.select.return_value.eq.return_value.execute.return_value = (
        mock_politico_result
    )
    mock_supabase.table.return_value = mock_query

    resposta = client.get("/api/camara/politicos/99999/discursos")
    assert resposta.status_code == 404
    assert resposta.json()["detail"] == "Político não encontrado"


def test_listar_discursos_politico_sucesso(client, mock_supabase):
    mock_politico_result = MagicMock()
    mock_politico_result.data = [{"id": 12345}]

    mock_discursos_result = MagicMock()
    mock_discursos_result.count = 1
    mock_discursos_result.data = [
        {
            "id": "e0e84b6f-7023-4554-949e-f00de7a44f77",
            "politico_id": 12345,
            "data_discurso": "2026-06-22T10:00:00Z",
            "texto_bruto": "Texto do discurso",
            "url_video": "http://video.com",
            "sumario": "Sumário do discurso",
            "fase_evento": "Grande Expediente",
        }
    ]

    mock_query_politico = MagicMock()
    mock_query_politico.select.return_value.eq.return_value.execute.return_value = (
        mock_politico_result
    )

    mock_query_discursos = MagicMock()
    mock_query_discursos.select.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value = (
        mock_discursos_result
    )

    def mock_table_routing(tabela):
        if tabela == "camara_politicos":
            return mock_query_politico
        elif tabela == "camara_discursos":
            return mock_query_discursos
        return MagicMock()

    mock_supabase.table.side_effect = mock_table_routing

    resposta = client.get("/api/camara/politicos/12345/discursos")
    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["total_registros"] == 1
    assert dados["pagina_atual"] == 1
    assert len(dados["itens"]) == 1
    assert dados["itens"][0]["id"] == "e0e84b6f-7023-4554-949e-f00de7a44f77"
    assert dados["itens"][0]["texto_bruto"] == "Texto do discurso"
