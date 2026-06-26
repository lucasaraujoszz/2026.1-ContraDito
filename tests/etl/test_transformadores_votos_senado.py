import uuid

from etl.transformadores_votos_senado import (
    gerar_id_voto_senado,
    validar_corte_temporal_votacao,
    contem_manobra_regimental_senado,
    contem_termo_merito_senado,
    encontrar_sessao_merito_senado,
    filtrar_votos_validos_senado,
    transformar_voto_senado,
)


def test_gerar_id_voto_senado_deterministico():
    """
    Ciclo 1: Garante que a geração de ID do voto é determinística (UUID v5),
    sempre resultando no mesmo hash para a mesma combinação de proposição e parlamentar.
    """
    proposicao_id = "pls_67_2015"
    politico_id = 12345

    id_1 = gerar_id_voto_senado(proposicao_id, politico_id)
    id_2 = gerar_id_voto_senado(proposicao_id, politico_id)

    assert id_1 == id_2, "O UUID gerado deve ser perfeitamente idempotente."
    assert (
        uuid.UUID(id_1).version == 5
    ), "O hash deve ser obrigatoriamente UUID versão 5."


def test_validar_corte_temporal_votacao():
    """
    Ciclo 2: Valida se a data da sessão nominal atende ao corte da
    Legislatura 57 (>= 01/01/2023). Retorna False para datas antigas ou nulas.
    """
    assert validar_corte_temporal_votacao("2023-01-01") is True
    assert validar_corte_temporal_votacao("2023-05-15") is True
    assert validar_corte_temporal_votacao("2022-12-31") is False
    assert validar_corte_temporal_votacao(None) is False
    assert validar_corte_temporal_votacao("") is False


def test_contem_manobra_regimental_senado():
    """
    Ciclo 3: Filtro Blocklist (Regex).
    Testa a rejeição de descrições contendo manobras regimentais
    (requerimento, urgência, adiamento, destaque, questão de ordem, preferência).
    """
    assert contem_manobra_regimental_senado("Votação do Requerimento nº 123") is True
    assert contem_manobra_regimental_senado("Votação do pedido de urgência") is True
    assert contem_manobra_regimental_senado("Adiamento da discussão") is True
    assert contem_manobra_regimental_senado("Destaque para a emenda 4") is True
    assert contem_manobra_regimental_senado("Questão de Ordem levantada") is True
    assert contem_manobra_regimental_senado("Votação da preferência") is True

    # Devem ser aprovados pela blocklist (retornam False pois não contêm as palavras proibidas)
    assert contem_manobra_regimental_senado("Aprovação do texto-base") is False
    assert contem_manobra_regimental_senado("Votação em 1º turno") is False


def test_contem_termo_merito_senado():
    """
    Ciclo 4: Filtro Allowlist (Regex).
    Testa a aprovação de descrições contendo termos de mérito
    (texto-base, substitutivo, parecer, 1º turno, segundo turno, turno único).
    """
    assert contem_termo_merito_senado("Aprovação do texto-base") is True
    assert contem_termo_merito_senado("Votação do substitutivo") is True
    assert contem_termo_merito_senado("Votação do parecer") is True
    assert contem_termo_merito_senado("Votação em 1º turno") is True
    assert contem_termo_merito_senado("Votação em segundo turno") is True
    assert contem_termo_merito_senado("Votação em turno único") is True

    # Deve ser rejeitado (False) pois não contém termos explícitos da Allowlist
    assert contem_termo_merito_senado("Votação da emenda 4") is False


def test_encontrar_sessao_merito_senado():
    """
    Ciclo 5: Encontrar Sessão de Mérito.
    Recebe lista de sessões, ordena cronologicamente (ASC) e retorna a primeira
    que atende ao corte temporal (>= 2023), passa pela Blocklist e é aprovada pela Allowlist.
    """
    sessoes_mock = [
        {
            "codigoSessao": 1,
            "dataSessao": "2022-12-01",
            "descricaoVotacao": "Aprovação do texto-base",
        },  # Rejeitado: Corte temporal
        {
            "codigoSessao": 2,
            "dataSessao": "2023-02-01",
            "descricaoVotacao": "Votação do Requerimento",
        },  # Rejeitado: Blocklist
        {
            "codigoSessao": 3,
            "dataSessao": "2023-03-01",
            "descricaoVotacao": "Aprovação do texto-base",
        },  # APROVADO: É a mais antiga válida
        {
            "codigoSessao": 4,
            "dataSessao": "2023-01-15",
            "descricaoVotacao": "Votação da emenda",
        },  # Rejeitado: Não tem Allowlist
        {
            "codigoSessao": 5,
            "dataSessao": "2023-04-01",
            "descricaoVotacao": "Votação do substitutivo",
        },  # Válido, mas mais recente que a 3
    ]

    sessao_valida = encontrar_sessao_merito_senado(sessoes_mock)

    assert sessao_valida is not None
    assert sessao_valida["codigoSessao"] == 3


def test_encontrar_sessao_merito_senado_retorna_none_se_vazio():
    assert encontrar_sessao_merito_senado([]) is None
    assert (
        encontrar_sessao_merito_senado(
            [
                {
                    "codigoSessao": 1,
                    "dataSessao": "2023-02-01",
                    "descricaoVotacao": "Requerimento",
                }
            ]
        )
        is None
    )


def test_filtrar_votos_validos_senado_soft_drop():
    """
    Ciclo 6: Soft Drop de Parlamentares.
    Filtra a lista de votos extraída para remover parlamentares cujos IDs
    não estejam no conjunto de políticos válidos. Protege contra erro de FK.
    Garante também resiliência contra payloads malformados sem ID.
    """
    votos_brutos = [
        {"codigoParlamentar": 10, "nomeParlamentar": "Valido 1", "voto": "Sim"},
        {
            "codigoParlamentar": 99,
            "nomeParlamentar": "Suplente Fantasma",
            "voto": "Não",
        },
        {"codigoParlamentar": 20, "nomeParlamentar": "Valido 2", "voto": "Sim"},
        {"voto": "Abstenção"},  # Payload malformado / sem codigoParlamentar
    ]

    ids_validos_banco = {10, 20}

    votos_filtrados = filtrar_votos_validos_senado(votos_brutos, ids_validos_banco)

    assert len(votos_filtrados) == 2, "Deve retornar exatamente 2 votos válidos."
    ids_restantes = [v.get("codigoParlamentar") for v in votos_filtrados]
    assert 10 in ids_restantes
    assert 20 in ids_restantes


def test_filtrar_votos_validos_senado_lista_vazia():
    ids_validos_banco = {10, 20}
    assert filtrar_votos_validos_senado([], ids_validos_banco) == []


def test_transformar_voto_senado_sucesso():
    """
    Ciclo 7: Data Contract.
    Converte o dicionário bruto da API do Senado para o dicionário da nossa
    tabela senado_votos, gerando o UUID v5 correspondente.
    """
    voto_bruto = {
        "codigoParlamentar": 74646,
        "nomeParlamentar": "Aécio Neves",
        "siglaPartidoParlamentar": "PSDB",
        "siglaVotoParlamentar": "Sim",
    }
    proposicao_id = "pec_5_2023"

    resultado = transformar_voto_senado(voto_bruto, proposicao_id)

    assert resultado["id"] == gerar_id_voto_senado(proposicao_id, 74646)
    assert resultado["proposicao_id"] == "pec_5_2023"
    assert resultado["politico_id"] == 74646
    assert resultado["partido_na_epoca"] == "PSDB"
    assert resultado["voto_oficial"] == "Sim"
