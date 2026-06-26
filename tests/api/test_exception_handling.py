import pytest
from unittest.mock import patch
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


def test_routes_exception_handling(client, mock_supabase):
    # Configura o mock para lançar uma exceção genérica do banco de dados
    mock_supabase.table.side_effect = Exception("Erro genérico de banco de dados")

    endpoints = [
        "/api/camara/politicos",
        "/api/camara/politicos/12345",
        "/api/camara/politicos/12345/timeline",
        "/api/camara/politicos/12345/afinidades",
        "/api/camara/politicos/12345/fidelidade",
        "/api/comparar?politico_id_1=1&politico_id_2=2&casa=camara",
        "/api/camara/partidos/coesao",
        "/api/camara/proposicoes",
        "/api/camara/proposicoes/c0c1c2c3-d4d5-e6e7-f8f9-a0a1a2a3a4a5",
        "/api/camara/proposicoes/c0c1c2c3-d4d5-e6e7-f8f9-a0a1a2a3a4a5/polarizacao",
        "/api/camara/discursos",
        "/api/camara/politicos/12345/discursos",
        "/api/camara/discursos/e0e84b6f-7023-4554-949e-f00de7a44f77",
        "/api/camara/discursos/e0e84b6f-7023-4554-949e-f00de7a44f77/chunks",
        "/api/camara/votos",
    ]

    for url in endpoints:
        response = client.get(url)
        assert response.status_code == 500
        assert "detail" in response.json()
        assert (
            "Erro" in response.json()["detail"]
            or "erro" in response.json()["detail"].lower()
        )
