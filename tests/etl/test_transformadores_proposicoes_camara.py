import uuid

# Importaremos a função do módulo de transformação que iremos implementar (GREEN)
from etl.transformadores_proposicoes_camara import (
    gerar_id_proposicao,
    obter_data_votacao_merito,
    validar_corte_temporal,
    formatar_chave_negocio,
    transformar_proposicao,
)


def test_gerar_id_proposicao_deve_ser_deterministico():
    """
    Garante que a mesma chave de negócio sempre resulta no mesmo UUID v5.
    """
    chave_negocio = "pec_45_2019"

    id_1 = gerar_id_proposicao(chave_negocio)
    id_2 = gerar_id_proposicao(chave_negocio)

    assert (
        id_1 == id_2
    ), "O hash deve ser perfeitamente idempotente para a mesma entrada."

    # Valida se de fato é uma string UUID v5 bem formatada
    uuid_obj = uuid.UUID(id_1)
    assert (
        uuid_obj.version == 5
    ), "O hash gerado precisa ser obrigatoriamente um UUID versão 5."


def test_gerar_id_proposicao_gera_ids_distintos_para_chaves_diferentes():
    id_pec = gerar_id_proposicao("pec_45_2019")
    id_pl = gerar_id_proposicao("pl_45_2019")

    assert id_pec != id_pl, "Chaves de negócio distintas devem gerar IDs distintos."


def test_gerar_id_proposicao_lida_com_espacos_extras():
    """
    Garante que a função consegue lidar com chaves que contenham espaços antes e depois.
    """
    id_limpo = gerar_id_proposicao("pec_45_2019")
    id_sujo = gerar_id_proposicao("  pec_45_2019   ")

    assert (
        id_limpo == id_sujo
    ), "A função deve limpar os espaços (strip) antes de gerar o hash."


def test_obter_data_votacao_merito_encontra_whitelist():
    """
    Garante que a função itera sobre as tramitações e retorna a data
    do PRIMEIRO evento que possua um dos códigos da whitelist (231, 232, 233, 1231).
    """
    tramitacoes_mock = [
        {
            "codTipoTramitacao": 232,
            "dataHora": "2023-06-20T10:00",
        },  # ALVO 2 (Veio primeiro na API - Decrescente)
        {
            "codTipoTramitacao": 100,
            "dataHora": "2021-01-01T10:00",
        },  # Irrelevante (Mais antigo)
        {
            "codTipoTramitacao": 231,
            "dataHora": "2023-05-15T15:30",
        },  # ALVO 1 (Primeira votação de mérito - Deve ser pego)
    ]

    data = obter_data_votacao_merito(tramitacoes_mock)
    assert (
        data == "2023-05-15T15:30"
    ), "Deve capturar a data do primeiro evento validado da whitelist."


def test_obter_data_votacao_merito_ignora_irrelevantes():
    tramitacoes_mock = [
        {"codTipoTramitacao": 999, "dataHora": "2023-01-01T10:00"},
        {"codTipoTramitacao": 888, "dataHora": "2023-05-15T15:30"},
    ]

    data = obter_data_votacao_merito(tramitacoes_mock)
    assert (
        data is None
    ), "Deve retornar None se a proposição nunca teve votação de mérito."


def test_validar_corte_temporal_aprova_projetos_recentes():
    """
    Projetos com votação de mérito a partir de 01/01/2023 devem retornar True.
    """
    assert validar_corte_temporal("2023-01-01T10:00:00") is True
    assert validar_corte_temporal("2024-05-15T15:30:00") is True
    assert validar_corte_temporal("2023-01-01") is True  # Formato sem a hora


def test_validar_corte_temporal_rejeita_projetos_antigos():
    """
    Projetos com votação de mérito anterior a 2023 devem retornar False.
    """
    assert validar_corte_temporal("2022-12-31T23:59:59") is False
    assert validar_corte_temporal("2019-05-10T10:00:00") is False


def test_validar_corte_temporal_rejeita_nulos():
    """
    Projetos que não possuem data de votação devem ser rejeitados (False).
    """
    assert validar_corte_temporal(None) is False


def test_formatar_chave_negocio_snake_case():
    """
    Garante que a sigla, número e ano sejam formatados rigorosamente no padrão snake_case.
    """
    assert formatar_chave_negocio("PEC", 45, 2019) == "pec_45_2019"
    assert formatar_chave_negocio(" PL  ", "1234", "2023") == "pl_1234_2023"


def test_transformar_proposicao_descarte_sem_votacao():
    payload = {"id": 123, "siglaTipo": "PL", "numero": 1, "ano": 2023}
    tramitacoes = [{"codTipoTramitacao": 100, "dataHora": "2023-05-15T10:00:00"}]

    resultado = transformar_proposicao(payload, tramitacoes)
    assert (
        resultado is None
    ), "Proposições sem votação de mérito devem ser descartadas (None)."


def test_transformar_proposicao_descarte_data_antiga():
    payload = {"id": 123, "siglaTipo": "PL", "numero": 1, "ano": 2022}
    tramitacoes = [{"codTipoTramitacao": 231, "dataHora": "2022-12-31T23:59:59"}]

    resultado = transformar_proposicao(payload, tramitacoes)
    assert (
        resultado is None
    ), "Proposições com votação antes de 2023 devem ser descartadas (None)."


def test_transformar_proposicao_descarte_falso_positivo_cronologico():
    """
    Garante que se a primeira votação ocorreu antes de 2023, o projeto é descartado,
    mesmo que possua uma nova votação após 2023 no seu histórico recente.
    """
    payload = {"id": 123, "siglaTipo": "PL", "numero": 1, "ano": 2020}
    tramitacoes = [
        {
            "codTipoTramitacao": 231,
            "dataHora": "2023-08-10T14:00:00",
        },  # Votação recente (Falso positivo)
        {
            "codTipoTramitacao": 231,
            "dataHora": "2021-05-20T10:00:00",
        },  # Votação original (Texto-Base real)
    ]

    resultado = transformar_proposicao(payload, tramitacoes)
    assert (
        resultado is None
    ), "Deve ordenar, encontrar a de 2021 primeiro, e descartar o projeto."


def test_transformar_proposicao_sucesso_data_contract():
    payload = {
        "id": 2265213,
        "siglaTipo": "PEC",
        "numero": 45,
        "ano": 2019,
        "ementa": "Altera o Sistema Tributário Nacional.",
        "urlInteiroTeor": "http://camara.gov.br/pec45.pdf",
    }
    tramitacoes = [
        {
            "codTipoTramitacao": 231,
            "dataHora": "2023-07-07T18:00:00",
            "id": "12345-tramitacao",
        }
    ]

    resultado = transformar_proposicao(payload, tramitacoes)

    assert resultado is not None

    chaves_exigidas = {
        "id",
        "proposicao_id",
        "id_camara",
        "id_votacao_camara",
        "tipo",
        "numero",
        "ano",
        "ementa",
        "data_votacao",
        "url_texto_inteiro",
        "resumo_executivo",
        "embedding_resumo_executivo",
    }
    assert (
        set(resultado.keys()) == chaves_exigidas
    ), "O dicionário final deve obedecer estritamente ao Data Contract."

    assert resultado["proposicao_id"] == "pec_45_2019"
    assert resultado["id_camara"] == 2265213
