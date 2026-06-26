import pytest
import respx
import httpx
from unittest.mock import patch, MagicMock, AsyncMock

# Funções que serão implementadas/testadas
from etl.extrator_votos_senado import (
    obter_sessao_votacao_senado,
    extrair_votos_proposicao_senado,
    executar_pipeline_votos_senado,
)


@pytest.mark.asyncio
@respx.mock
async def test_obter_sessao_votacao_senado_encontra_merito():
    """
    Ciclo 8: Busca da Sessão de Votação (Mock HTTP).
    Garante que o extrator bate na API do Senado, recebe o payload de votações,
    e utiliza a função encontrar_sessao_merito_senado para retornar a tupla (codigo, data).
    """
    id_senado = 12345
    url = f"https://legis.senado.leg.br/dadosabertos/votacao?codigoMateria={id_senado}&v=1"

    mock_json = [
        {
            "codigoSessao": 1,
            "dataSessao": "2023-01-10",
            "descricaoVotacao": "Votação do Requerimento",
        },  # Bloqueado (Blocklist)
        {
            "codigoSessao": 2,
            "dataSessao": "2023-02-15",
            "descricaoVotacao": "Aprovação do texto-base",
        },  # ALVO (Válido)
        {
            "codigoSessao": 3,
            "dataSessao": "2022-12-01",
            "descricaoVotacao": "Aprovação do substitutivo",
        },  # Bloqueado (Corte Temporal)
    ]
    respx.get(url).respond(status_code=200, json=mock_json)

    async with httpx.AsyncClient() as client:
        resultado = await obter_sessao_votacao_senado(client, id_senado)

        assert resultado is not None
        codigo_sessao, data_sessao = resultado
        assert codigo_sessao == 2
        assert data_sessao == "2023-02-15"


@pytest.mark.asyncio
@respx.mock
async def test_extrair_votos_proposicao_senado_sucesso():
    """
    Ciclo 9: Extração Completa (Caminho Feliz).
    Garante que o extrator orquestra a busca da sessão, encontra o mérito,
    desce até a raiz de votos nominais, aplica o Soft Drop para deputados órfãos
    e converte para o Data Contract.
    """
    id_senado = 999
    proposicao_id = "pec_5_2023"
    ids_validos = {10, 20}

    url = f"https://legis.senado.leg.br/dadosabertos/votacao?codigoMateria={id_senado}&v=1"

    mock_json = [
        {
            "codigoSessao": 2,
            "dataSessao": "2023-02-15",
            "descricaoVotacao": "Aprovação do texto-base",
            "votos": [
                {
                    "codigoParlamentar": 10,
                    "siglaPartidoParlamentar": "PT",
                    "siglaVotoParlamentar": "Sim",
                },
                {
                    "codigoParlamentar": 99,
                    "siglaPartidoParlamentar": "PSDB",
                    "siglaVotoParlamentar": "Não",
                },  # Fantasma (Soft Drop)
                {
                    "codigoParlamentar": 20,
                    "siglaPartidoParlamentar": "PL",
                    "siglaVotoParlamentar": "Abstenção",
                },
            ],
        }
    ]
    respx.get(url).respond(status_code=200, json=mock_json)

    async with httpx.AsyncClient() as client:
        votos, id_votacao, data_votacao = await extrair_votos_proposicao_senado(
            client, proposicao_id, id_senado, ids_validos
        )

        assert id_votacao == 2
        assert data_votacao == "2023-02-15"
        assert len(votos) == 2, "O parlamentar fantasma (99) deve ter sido removido."

        ids_presentes = [v["politico_id"] for v in votos]
        assert 10 in ids_presentes
        assert 20 in ids_presentes
        assert 99 not in ids_presentes
        assert votos[0]["proposicao_id"] == "pec_5_2023"
        assert "id" in votos[0]


@pytest.mark.asyncio
@respx.mock
async def test_extrair_votos_proposicao_senado_simbolica():
    """
    Ciclo 9: Votação Simbólica.
    Garante que matérias puramente simbólicas (sem votos nominais ou API vazia)
    sejam processadas pacificamente e retornem listas vazias.
    """
    id_senado = 888
    proposicao_id = "pl_888_2023"
    ids_validos = {10}

    url = f"https://legis.senado.leg.br/dadosabertos/votacao?codigoMateria={id_senado}&v=1"
    respx.get(url).respond(status_code=200, json=[])  # Simula vazio

    async with httpx.AsyncClient() as client:
        votos, id_votacao, data_votacao = await extrair_votos_proposicao_senado(
            client, proposicao_id, id_senado, ids_validos
        )

        assert votos == []
        assert id_votacao is None
        assert data_votacao is None


@pytest.mark.asyncio
@respx.mock
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_extrair_votos_proposicao_senado_resiliencia_retry(mock_sleep):
    """
    Ciclo 11: Resiliência de Rede (Tenacity).
    Garante que a extração tenta novamente em caso de erro transiente (500/503)
    da API do Senado, conseguindo recuperar os dados se uma tentativa subsequente funcionar.
    """
    id_senado = 12345
    proposicao_id = "pec_5_2023"
    ids_validos = {10}

    url = f"https://legis.senado.leg.br/dadosabertos/votacao?codigoMateria={id_senado}&v=1"

    mock_json = [
        {
            "codigoSessao": 2,
            "dataSessao": "2023-02-15",
            "descricaoVotacao": "Aprovação do texto-base",
            "votos": [{"codigoParlamentar": 10, "siglaVotoParlamentar": "Sim"}],
        }
    ]

    route = respx.get(url)
    # Simula a API do Senado caindo 2 vezes e voltando na 3ª
    route.side_effect = [
        httpx.Response(500),
        httpx.Response(503),
        httpx.Response(200, json=mock_json),
    ]

    async with httpx.AsyncClient() as client:
        votos, id_votacao, data_votacao = await extrair_votos_proposicao_senado(
            client, proposicao_id, id_senado, ids_validos
        )

        assert (
            route.call_count == 3
        ), "Deveria ter tentado 3 vezes antes de retornar com sucesso."
        assert id_votacao == 2
        assert len(votos) == 1


@pytest.mark.asyncio
@respx.mock
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_executar_pipeline_senado_poison_pill(mock_sleep):
    """
    Ciclo 12: Isolamento de Falha (Skip-and-Continue).
    Se uma proposição for uma 'Poison Pill' e retornar Erro 500 cronicamente,
    o orquestrador deve capturar a exceção e retornar graciosamente
    para não capotar o pipeline inteiro.
    """
    mock_supabase = MagicMock()
    mock_resp_politicos = MagicMock()
    mock_resp_politicos.data = [{"id": 10}]
    mock_resp_proposicoes = MagicMock()
    mock_resp_proposicoes.data = [{"proposicao_id": "pec_5_2023", "id_senado": 999}]

    mock_supabase.table.return_value.select.return_value.execute.return_value = (
        mock_resp_politicos
    )
    mock_supabase.table.return_value.select.return_value.is_.return_value.execute.return_value = (
        mock_resp_proposicoes
    )

    url = "https://legis.senado.leg.br/dadosabertos/votacao?codigoMateria=999&v=1"

    # Força a API a dar erro 500 sempre
    respx.get(url).respond(status_code=500)

    # Não deve levantar exceção para fora, o pipeline deve continuar
    await executar_pipeline_votos_senado(mock_supabase)

    # Verifica se o log registrou 0 linhas afetadas, e o status da rotina permaneceu 'Concluído'
    mock_supabase.table.assert_any_call("etl_logs")
    args_log, _ = mock_supabase.table().insert.call_args
    assert args_log[0]["linhas_afetadas"] == 0
    assert args_log[0]["status"] == "Concluído"


@pytest.mark.asyncio
@patch("etl.extrator_votos_senado.extrair_votos_proposicao_senado")
async def test_executar_pipeline_votos_senado_update_duplo(mock_extrair):
    """
    Ciclo 10: Consistência Eventual e Execução (Pipeline E2E).
    Garante que o orquestrador realiza o Upsert dos votos primeiro e,
    apenas em caso de sucesso, faz o UPDATE na proposição com o ID e Data da votação.
    """
    mock_supabase = MagicMock()

    # Mock dos retornos dos SELECTs iniciais
    mock_resp_politicos = MagicMock()
    mock_resp_politicos.data = [{"id": 10}]

    mock_resp_proposicoes = MagicMock()
    mock_resp_proposicoes.data = [{"proposicao_id": "pec_5_2023", "id_senado": 999}]

    # Mock das queries iniciais
    mock_supabase.table.return_value.select.return_value.execute.return_value = (
        mock_resp_politicos
    )
    mock_supabase.table.return_value.select.return_value.is_.return_value.execute.return_value = (
        mock_resp_proposicoes
    )

    # Mock da extração
    mock_extrair.return_value = ([{"id": "voto1", "politico_id": 10}], 2, "2023-02-15")

    await executar_pipeline_votos_senado(mock_supabase)

    # Verifica Upsert dos votos
    mock_supabase.table.assert_any_call("senado_votos")
    mock_supabase.table().upsert.assert_called_once()

    # Verifica Update na proposição (Inversão de ordem para consistência eventual)
    mock_update = mock_supabase.table.return_value.update
    mock_update.assert_called_with(
        {"id_votacao_senado": 2, "data_votacao": "2023-02-15"}
    )
    mock_update.return_value.eq.assert_called_with("proposicao_id", "pec_5_2023")
    mock_update.return_value.eq.return_value.execute.assert_called_once()
