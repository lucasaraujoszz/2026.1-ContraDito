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
        yield mock


def test_listar_politicos_camara_sucesso(client, mock_supabase):
    # Mock do retorno do Supabase para Câmara
    mock_result = MagicMock()
    mock_result.data = [
        {
            "id": 12345,
            "nome_civil": "Deputado de Teste da Silva",
            "nome_urna": "TESTE SILVA",
            "partido": "PTD",
            "cargo": "Deputado Federal",
            "estado": "DF",
            "status_mandato": "Em Exercício",
            "url_foto": "http://foto.jpg",
            "data_ultima_atualizacao": "2026-06-22T00:00:00Z",
        }
    ]
    mock_result.count = 1

    # Configura o mock do builder de query do Supabase
    mock_query = MagicMock()
    mock_query.ilike.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.order.return_value = mock_query
    mock_query.range.return_value = mock_query
    mock_query.execute.return_value = mock_result

    mock_supabase.table.return_value.select.return_value = mock_query

    resposta = client.get("/api/camara/politicos?busca=TESTE&partido=PTD&estado=DF")

    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["total_registros"] == 1
    assert dados["pagina_atual"] == 1
    assert dados["itens"][0]["nome_urna"] == "TESTE SILVA"
    assert dados["itens"][0]["estado"] == "DF"


def test_listar_politicos_senado_sucesso(client, mock_supabase):
    # Mock do retorno do Supabase para Senado
    mock_result = MagicMock()
    mock_result.data = [
        {
            "id": 67890,
            "nome_civil": "Senador de Teste de Souza",
            "nome_urna": "TESTE SOUZA",
            "partido": "PSD",
            "cargo": "Senador",
            "estado": "SP",
            "status_mandato": "Em Exercício",
            "url_foto": "http://foto.jpg",
            "data_ultima_atualizacao": "2026-06-22T00:00:00Z",
        }
    ]
    mock_result.count = 1

    mock_query = MagicMock()
    mock_query.ilike.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.order.return_value = mock_query
    mock_query.range.return_value = mock_query
    mock_query.execute.return_value = mock_result

    mock_supabase.table.return_value.select.return_value = mock_query

    resposta = client.get("/api/senado/politicos?busca=TESTE&partido=PSD&estado=SP")

    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["total_registros"] == 1
    assert dados["itens"][0]["nome_urna"] == "TESTE SOUZA"
    assert dados["itens"][0]["estado"] == "SP"


def test_listar_politicos_casa_invalida(client):
    resposta = client.get("/api/congresso/politicos")
    assert resposta.status_code == 400
    assert "Casa inválida" in resposta.json()["detail"]


def test_obter_politico_detalhado_sucesso(client, mock_supabase):
    # Mock do retorno do Supabase para político
    mock_politico_result = MagicMock()
    mock_politico_result.data = [
        {
            "id": 12345,
            "nome_civil": "Deputado de Teste da Silva",
            "nome_urna": "TESTE SILVA",
            "partido": "PTD",
            "cargo": "Deputado Federal",
            "estado": "DF",
            "status_mandato": "Em Exercício",
            "url_foto": "http://foto.jpg",
            "data_ultima_atualizacao": "2026-06-22T00:00:00Z",
        }
    ]

    # Mock do retorno do Supabase para resumo de votos
    mock_resumo_result = MagicMock()
    mock_resumo_result.data = [
        {
            "politico_id": 12345,
            "casa": "CAMARA",
            "total_votos": 100,
            "qtd_sim": 60,
            "qtd_nao": 30,
            "qtd_ausencia": 0,
            "qtd_abstencao": 5,
            "qtd_obstrucao": 3,
            "qtd_outros": 2,
        }
    ]

    # Configuração de múltiplos comportamentos para o mock_supabase
    # O primeiro table("camara_politicos") retorna o politico
    # O segundo table("politico_resumo_votos") retorna o resumo
    mock_query_politico = MagicMock()
    mock_query_politico.select.return_value.eq.return_value.execute.return_value = (
        mock_politico_result
    )

    mock_query_resumo = MagicMock()
    mock_query_resumo.select.return_value.eq.return_value.eq.return_value.execute.return_value = (
        mock_resumo_result
    )

    def mock_table_routing(tabela):
        if tabela == "camara_politicos":
            return mock_query_politico
        elif tabela == "politico_resumo_votos":
            return mock_query_resumo
        return MagicMock()

    mock_supabase.table.side_effect = mock_table_routing

    resposta = client.get("/api/camara/politicos/12345")

    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["politico"]["id"] == 12345
    assert dados["resumo_votos"]["total_votos"] == 100
    assert dados["resumo_votos"]["qtd_sim"] == 60


def test_obter_politico_detalhado_nao_encontrado(client, mock_supabase):
    # Mock do retorno vazio
    mock_politico_result = MagicMock()
    mock_politico_result.data = []

    mock_query_politico = MagicMock()
    mock_query_politico.select.return_value.eq.return_value.execute.return_value = (
        mock_politico_result
    )
    mock_supabase.table.return_value = mock_query_politico

    resposta = client.get("/api/camara/politicos/999")
    assert resposta.status_code == 404
    assert "Político não encontrado" in resposta.json()["detail"]


def test_listar_discursos_sucesso(client, mock_supabase):
    mock_result = MagicMock()
    mock_result.data = [
        {
            "id": "e0e84b6f-7023-4554-949e-f00de7a44f77",
            "politico_id": 12345,
            "data_discurso": "2026-06-22T10:00:00Z",
            "texto_bruto": "Discurso de Teste sobre educação",
            "url_video": "http://youtube.com/v",
            "sumario": "Fala sobre educação.",
            "fase_evento": "Pequeno Expediente",
        }
    ]
    mock_result.count = 1

    mock_query = MagicMock()
    mock_query.eq.return_value = mock_query
    mock_query.order.return_value = mock_query
    mock_query.range.return_value = mock_query
    mock_query.execute.return_value = mock_result
    mock_supabase.table.return_value.select.return_value = mock_query

    resposta = client.get("/api/camara/discursos?politico_id=12345")
    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["total_registros"] == 1
    assert dados["itens"][0]["id"] == "e0e84b6f-7023-4554-949e-f00de7a44f77"


def test_obter_chunks_discurso_sucesso(client, mock_supabase):
    mock_result = MagicMock()
    mock_result.data = [
        {
            "id": "a0a1a2a3-b4b5-c6c7-d8d9-e0e1e2e3e4e5",
            "discurso_id": "e0e84b6f-7023-4554-949e-f00de7a44f77",
            "texto_chunk": "educação é muito importante",
        }
    ]

    mock_query = MagicMock()
    mock_query.select.return_value.eq.return_value.execute.return_value = mock_result
    mock_supabase.table.return_value = mock_query

    resposta = client.get(
        "/api/camara/discursos/e0e84b6f-7023-4554-949e-f00de7a44f77/chunks"
    )
    assert resposta.status_code == 200
    chunks = resposta.json()
    assert len(chunks) == 1
    assert chunks[0]["texto_chunk"] == "educação é muito importante"


def test_listar_proposicoes_sucesso(client, mock_supabase):
    mock_result = MagicMock()
    mock_result.data = [
        {
            "id": "c0c1c2c3-d4d5-e6e7-f8f9-a0a1a2a3a4a5",
            "proposicao_id": "PL 123/2026",
            "id_camara": 10001,
            "tipo": "PL",
            "numero": 123,
            "ano": 2026,
            "ementa": "Matéria educacional",
            "data_votacao": "2026-06-22",
            "url_texto_inteiro": "http://inteiro.pdf",
            "resumo_executivo": "Resumo executivo da matéria.",
            "erro_resumo": None,
        }
    ]
    mock_result.count = 1

    mock_query = MagicMock()
    mock_query.eq.return_value = mock_query
    mock_query.order.return_value = mock_query
    mock_query.range.return_value = mock_query
    mock_query.execute.return_value = mock_result
    mock_supabase.table.return_value.select.return_value = mock_query

    resposta = client.get("/api/camara/proposicoes?ano=2026&tipo=PL")
    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["total_registros"] == 1
    assert dados["itens"][0]["id"] == "c0c1c2c3-d4d5-e6e7-f8f9-a0a1a2a3a4a5"


def test_obter_proposicao_detalhada_sucesso(client, mock_supabase):
    mock_result = MagicMock()
    mock_result.data = [
        {
            "id": "c0c1c2c3-d4d5-e6e7-f8f9-a0a1a2a3a4a5",
            "proposicao_id": "PL 123/2026",
            "id_camara": 10001,
            "tipo": "PL",
            "numero": 123,
            "ano": 2026,
            "ementa": "Matéria educacional",
            "data_votacao": "2026-06-22",
            "url_texto_inteiro": "http://inteiro.pdf",
            "resumo_executivo": "Resumo executivo da matéria.",
            "erro_resumo": None,
        }
    ]

    mock_query = MagicMock()
    mock_query.select.return_value.eq.return_value.execute.return_value = mock_result
    mock_supabase.table.return_value = mock_query

    resposta = client.get(
        "/api/camara/proposicoes/c0c1c2c3-d4d5-e6e7-f8f9-a0a1a2a3a4a5"
    )
    assert resposta.status_code == 200
    proposicao = resposta.json()
    assert proposicao["id"] == "c0c1c2c3-d4d5-e6e7-f8f9-a0a1a2a3a4a5"
    assert proposicao["proposicao_id"] == "PL 123/2026"


def test_obter_proposicao_detalhada_nao_encontrado(client, mock_supabase):
    mock_result = MagicMock()
    mock_result.data = []

    mock_query = MagicMock()
    mock_query.select.return_value.eq.return_value.execute.return_value = mock_result
    mock_supabase.table.return_value = mock_query

    resposta = client.get("/api/camara/proposicoes/uuid-nao-existente")
    assert resposta.status_code == 404
    assert "Proposição não encontrada" in resposta.json()["detail"]


def test_listar_votos_sucesso(client, mock_supabase):
    mock_result = MagicMock()
    mock_result.data = [
        {
            "id": "d0d1d2d3-e4e5-f6f7-a8a9-b0b1b2b3b4b5",
            "proposicao_id": "PL 123/2026",
            "politico_id": 12345,
            "partido_na_epoca": "PTD",
            "voto_oficial": "Sim",
            "chunks_proximos": [
                {
                    "chunk_id": "uuid-chunk-1",
                    "texto_chunk": "educação é prioridade",
                    "distancia": 0.15,
                }
            ],
        }
    ]
    mock_result.count = 1

    mock_query = MagicMock()
    mock_query.eq.return_value = mock_query
    mock_query.order.return_value = mock_query
    mock_query.range.return_value = mock_query
    mock_query.execute.return_value = mock_result
    mock_supabase.table.return_value.select.return_value = mock_query

    resposta = client.get(
        "/api/camara/votos?politico_id=12345&proposicao_id=PL 123/2026"
    )
    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["total_registros"] == 1
    assert dados["itens"][0]["id"] == "d0d1d2d3-e4e5-f6f7-a8a9-b0b1b2b3b4b5"
    assert dados["itens"][0]["voto_oficial"] == "Sim"
    assert (
        dados["itens"][0]["chunks_proximos"][0]["texto_chunk"]
        == "educação é prioridade"
    )
