import respx
import httpx
import pytest
from unittest.mock import patch, MagicMock

# Importaremos as funções que iremos implementar (GREEN)
from etl.extrator_votos_camara import (
    obter_id_votacao_camada_1,
    obter_id_votacao_camada_2_sweep,
    extrair_votos_proposicao,
    executar_pipeline_votos_camara,
)


@pytest.mark.asyncio
@respx.mock
async def test_obter_id_votacao_camada_1_caminho_feliz():
    """
    Garante o funcionamento da Camada 1 (Regex / Caminho Feliz).
    O extrator deve acessar o endpoint de votações da proposição e encontrar
    o ID exato da sessão nominal, ignorando os eventos procedimentais.
    """
    id_camara_proposicao = 2265213
    url = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes/{id_camara_proposicao}/votacoes"

    mock_json = {
        "dados": [
            {
                "id": "voto-falso",
                "descricao": "Rejeitado o Requerimento.",
            },  # Ignorar (Falso Positivo)
            {
                "id": "voto-alvo",
                "descricao": "Aprovada a PEC. Sim: 340; Não: 110; Abstenção: 7; Total: 457.",
                "dataHoraRegistro": "2023-10-05T15:30:00",
            },  # Match perfeito da Regex
        ]
    }
    respx.get(url).respond(status_code=200, json=mock_json)

    async with httpx.AsyncClient() as client:
        resultado = await obter_id_votacao_camada_1(client, id_camara_proposicao)

        assert resultado == (
            "voto-alvo",
            "2023-10-05T15:30:00",
        ), "O extrator deve retornar a tupla com ID e Data."


@pytest.mark.asyncio
@respx.mock
async def test_obter_id_votacao_camada_1_falha_regex():
    """
    Garante que se a Camada 1 não encontrar nenhuma descrição que bata
    com a Regex (apenas eventos procedimentais ou array vazio), ela retorna None,
    abrindo caminho para a Camada 2.
    """
    id_camara_proposicao = 2265213
    url = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes/{id_camara_proposicao}/votacoes"

    mock_json = {
        "dados": [
            {"id": "voto-1", "descricao": "Rejeitado o Requerimento."},
            {"id": "voto-2", "descricao": "Aprovada a preferência."},
        ]
    }
    respx.get(url).respond(status_code=200, json=mock_json)

    async with httpx.AsyncClient() as client:
        resultado = await obter_id_votacao_camada_1(client, id_camara_proposicao)
        assert resultado is None


@pytest.mark.asyncio
@respx.mock
async def test_obter_id_votacao_camada_2_sweep():
    """
    Garante que a Camada 2 (Sweep Fallback) itere sobre os IDs de votação
    e retorne o primeiro ID cujo endpoint de votos nominais não venha vazio.
    """
    id_camara_proposicao = 2265213
    url_votacoes = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes/{id_camara_proposicao}/votacoes"

    respx.get(url_votacoes).respond(
        status_code=200,
        json={
            "dados": [
                {"id": "sessao-1"},
                {"id": "sessao-2", "dataHoraRegistro": "2023-10-05T16:00:00"},
            ]
        },
    )
    respx.get(
        "https://dadosabertos.camara.leg.br/api/v2/votacoes/sessao-1/votos"
    ).respond(status_code=200, json={"dados": []})
    respx.get(
        "https://dadosabertos.camara.leg.br/api/v2/votacoes/sessao-2/votos"
    ).respond(status_code=200, json={"dados": [{"deputado_": {"id": 10}}]})

    async with httpx.AsyncClient() as client:
        resultado = await obter_id_votacao_camada_2_sweep(client, id_camara_proposicao)
        assert resultado == (
            "sessao-2",
            "2023-10-05T16:00:00",
        ), "A Camada 2 deve retornar a tupla com ID e Data."


@pytest.mark.asyncio
@respx.mock
async def test_obter_id_votacao_camada_2_sweep_ignora_falsos_positivos():
    """
    Garante que a Camada 2 aplica a Regex/Blocklist na descrição.
    Se a primeira sessão com votos nominais for um 'Requerimento' ou 'Redação Final',
    ela deve ser ignorada, e o Sweep deve continuar até achar a sessão de mérito.
    """
    id_camara_proposicao = 2265213
    url_votacoes = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes/{id_camara_proposicao}/votacoes"

    respx.get(url_votacoes).respond(
        status_code=200,
        json={
            "dados": [
                {"id": "sessao-requerimento", "descricao": "Rejeitado o Requerimento."},
                {
                    "id": "sessao-merito",
                    "descricao": "Aprovada a PEC.",
                    "dataHoraRegistro": "2023-10-05T17:00:00",
                },
            ]
        },
    )
    respx.get(
        "https://dadosabertos.camara.leg.br/api/v2/votacoes/sessao-requerimento/votos"
    ).respond(status_code=200, json={"dados": [{"deputado_": {"id": 10}}]})
    respx.get(
        "https://dadosabertos.camara.leg.br/api/v2/votacoes/sessao-merito/votos"
    ).respond(status_code=200, json={"dados": [{"deputado_": {"id": 20}}]})

    async with httpx.AsyncClient() as client:
        resultado = await obter_id_votacao_camada_2_sweep(client, id_camara_proposicao)
        assert resultado == (
            "sessao-merito",
            "2023-10-05T17:00:00",
        ), "A Camada 2 deve pular o requerimento e retornar a votação de mérito."


@pytest.mark.asyncio
@respx.mock
async def test_obter_id_votacao_camada_1_resiliencia_retry():
    """
    Garante que a Camada 1 possui resiliência de rede (Tenacity) e
    tenta novamente em caso de erro transiente (500/503) da API da Câmara,
    conseguindo recuperar o ID se uma tentativa subsequente funcionar.
    """
    id_camara_proposicao = 12345
    url = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes/{id_camara_proposicao}/votacoes"

    mock_json = {
        "dados": [
            {
                "id": "voto-alvo",
                "descricao": "Aprovada a PEC. Sim: 100; Não: 10",
                "data": "2023-10-05",
            }
        ]
    }

    route = respx.get(url)
    # Simula a Câmara caindo nas 2 primeiras requisições e voltando na 3ª
    route.side_effect = [
        httpx.Response(500),
        httpx.Response(503),
        httpx.Response(200, json=mock_json),
    ]

    async with httpx.AsyncClient() as client:
        resultado = await obter_id_votacao_camada_1(client, id_camara_proposicao)

        assert route.call_count == 3
        assert resultado == ("voto-alvo", "2023-10-05")


@pytest.mark.asyncio
@respx.mock
async def test_extrair_votos_proposicao_poison_pill():
    """
    Garante o Isolamento de Falha (Skip-and-Continue). Se uma proposição for
    uma 'Poison Pill' e retornar Erro 500 cronicamente (esgotando o Tenacity),
    o orquestrador deve capturar a exceção, logar o erro e retornar graciosamente
    para não capotar o pipeline inteiro.
    """
    id_camara = 999
    proposicao_id = "pl_999_2023"
    ids_validos = {10}

    url = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes/{id_camara}/votacoes"
    # Simula erro 500 permanente
    respx.get(url).mock(return_value=httpx.Response(500))

    async with httpx.AsyncClient() as client:
        votos, id_votacao, data_votacao = await extrair_votos_proposicao(
            client, proposicao_id, id_camara, ids_validos
        )

        assert (
            votos == []
        ), "Deve retornar lista vazia de votos em caso de falha crítica."
        assert id_votacao is None, "Não deve haver ID de votação."
        assert data_votacao is None


@pytest.mark.asyncio
@respx.mock
async def test_extrair_votos_proposicao_estado_vazio():
    """
    Garante que, em votações simbólicas (onde Camada 1 e 2 não encontram votos),
    o orquestrador retorna pacificamente sem falhas.
    """
    id_camara = 888
    proposicao_id = "pl_888_2023"
    ids_validos = {10}

    url = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes/{id_camara}/votacoes"
    respx.get(url).respond(status_code=200, json={"dados": []})

    async with httpx.AsyncClient() as client:
        votos, id_votacao, data_votacao = await extrair_votos_proposicao(
            client, proposicao_id, id_camara, ids_validos
        )

        assert votos == []
        assert id_votacao is None
        assert data_votacao is None


@pytest.mark.asyncio
@respx.mock
async def test_extrair_votos_proposicao_caminho_feliz():
    """
    Garante o fluxo completo de sucesso do orquestrador de uma proposição.
    Deve encontrar a sessão via Camada 1, baixar os votos, aplicar o Soft Drop
    em parlamentares inválidos e retornar os dados estruturados pelo Data Contract.
    """
    id_camara = 2265213
    proposicao_id = "pec_5_2023"
    ids_validos = {10, 20}

    url_votacoes = (
        f"https://dadosabertos.camara.leg.br/api/v2/proposicoes/{id_camara}/votacoes"
    )
    mock_votacoes = {
        "dados": [
            {
                "id": "voto-feliz",
                "descricao": "Aprovada a PEC. Sim: 340; Não: 110",
                "dataHoraRegistro": "2023-10-05T15:30:00",
            }
        ]
    }
    respx.get(url_votacoes).respond(status_code=200, json=mock_votacoes)

    url_votos = "https://dadosabertos.camara.leg.br/api/v2/votacoes/voto-feliz/votos"
    mock_votos = {
        "dados": [
            {"deputado_": {"id": 10, "siglaPartido": "PT"}, "tipoVoto": "Sim"},
            {
                "deputado_": {"id": 99, "siglaPartido": "PSDB"},
                "tipoVoto": "Não",
            },  # Fantasma (Soft Drop)
            {"deputado_": {"id": 20, "siglaPartido": "PL"}, "tipoVoto": "Abstenção"},
        ]
    }
    respx.get(url_votos).respond(status_code=200, json=mock_votos)

    async with httpx.AsyncClient() as client:
        votos, id_votacao, data_votacao = await extrair_votos_proposicao(
            client, proposicao_id, id_camara, ids_validos
        )

        assert id_votacao == "voto-feliz"
        assert data_votacao == "2023-10-05T15:30:00"
        assert (
            len(votos) == 2
        ), "O suplente fantasma (99) deve ter sido limpo pelo Soft Drop."

        ids_presentes = [v["politico_id"] for v in votos]
        assert 10 in ids_presentes
        assert 20 in ids_presentes
        assert 99 not in ids_presentes
        assert "id" in votos[0]
        assert votos[0]["proposicao_id"] == "pec_5_2023"


@pytest.mark.asyncio
@patch("etl.extrator_votos_camara.extrair_votos_proposicao")
async def test_executar_pipeline_votos_camara_update_duplo(mock_extrair):
    """
    Teste da rotina principal (Pipeline Completo).
    Ele deve buscar a lista de proposições e parlamentares do banco, realizar
    a extração e garantir que o UPDATE na proposição contém tanto o ID da votação
    quanto a data da votação (Rastreabilidade).
    """
    mock_supabase = MagicMock()

    # Mock dos retornos dos SELECTs iniciais
    mock_resp_politicos = MagicMock()
    mock_resp_politicos.data = [{"id": 10}]

    mock_resp_proposicoes = MagicMock()
    mock_resp_proposicoes.data = [{"proposicao_id": "pec_5_2023", "id_camara": 2265213}]

    mock_supabase.table.return_value.select.return_value.execute.side_effect = [
        mock_resp_politicos,
        mock_resp_proposicoes,
    ]

    # Mock da função orquestradora retornando a NOVA tupla (com a data_votacao inclusa)
    mock_extrair.return_value = (
        [{"id": "voto1", "politico_id": 10}],
        "sessao-alvo",
        "2023-10-05T15:30:00",
    )

    await executar_pipeline_votos_camara(mock_supabase)

    # Verifica se a função update foi chamada com o ID E a data_votacao
    mock_update = mock_supabase.table.return_value.update
    mock_update.assert_called_with(
        {"id_votacao_camara": "sessao-alvo", "data_votacao": "2023-10-05T15:30:00"}
    )
    mock_update.return_value.eq.assert_called_with("proposicao_id", "pec_5_2023")
    mock_update.return_value.eq.return_value.execute.assert_called_once()
