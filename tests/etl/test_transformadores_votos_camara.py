import uuid
import pytest

# Importaremos a função do módulo de transformação que iremos implementar (GREEN)
from etl.transformadores_votos_camara import (
    eh_votacao_merito_nominal,
    gerar_id_voto_camara,
    filtrar_votos_validos,
    transformar_voto_camara,
)


@pytest.mark.parametrize(
    "descricao, esperado",
    [
        # --- IGNORAR (Falsos Positivos / Votações Procedimentais) ---
        (
            "Rejeitado o Requerimento. Sim: 102; Não: 322; Abstenção: 1; Total: 425.",
            False,
        ),
        ("Aprovada a preferência. Sim: 467; Não: 4; Abstenção: 1; Total: 472.", False),
        (
            "Aprovado o Requerimento nº 4.491/2024, dos Senhores Líderes, que solicita a quebra de interstício de 5 sessões previsto no § 6º do art. 202 do RICD, para apreciação do segundo turno da PEC 5, de 2023.",
            False,
        ),
        (
            "Aprovada a Redação Final assinada pelo relator, Dep. Dr. Fernando Máximo (UNIÃO-RO).",
            False,
        ),
        # --- APROVAR (Votações Nominais de Mérito Verdadeiras) ---
        (
            "Aprovada, em primeiro turno, a Proposta de Emenda à Constituição nº 5, de 2023, na forma da Emenda Aglutinativa Substitutiva nº 3. Sim: 385; Não: 93; Abstenção: 7; Total: 485.",
            True,
        ),
        ("Mantido o texto. Sim: 340; Não: 110; Abstenção: 7; Total: 457.", True),
        (
            "Aprovada, em segundo turno, a Proposta de Emenda à Constituição nº 5, de 2023. Sim: 368; Não: 96; Abstenção: 7; Total: 471.",
            True,
        ),
    ],
)
def test_eh_votacao_merito_nominal_via_regex(descricao, esperado):
    """
    Garante que a função avalia as descrições de votação com uma Regex agressiva,
    rejeitando requerimentos, quebras de interstício, preferências e redação final,
    e aprovando apenas votações de mérito nominais (com contagem explícita de votos).
    """
    assert eh_votacao_merito_nominal(descricao) is esperado


def test_gerar_id_voto_deterministico():
    """
    Garante que a geração de ID do voto é determinística (UUID v5),
    sempre resultando no mesmo hash para a mesma combinação de proposição e parlamentar.
    """
    proposicao_id = "pec_5_2023"
    politico_id = 74646

    id_1 = gerar_id_voto_camara(proposicao_id, politico_id)
    id_2 = gerar_id_voto_camara(proposicao_id, politico_id)

    assert id_1 == id_2, "O UUID gerado deve ser perfeitamente idempotente."
    assert (
        uuid.UUID(id_1).version == 5
    ), "O hash deve ser obrigatoriamente UUID versão 5."


def test_filtrar_votos_validos_soft_drop():
    """
    Garante que os votos de parlamentares inexistentes no nosso banco (suplentes efêmeros)
    sejam silenciosamente descartados, protegendo o banco do Erro 23503 (Violação de FK).
    Garante também resiliência contra payloads malformados sem ID.
    """
    votos_brutos = [
        {"deputado_": {"id": 10, "nome": "Valido 1"}, "tipoVoto": "Sim"},
        {"deputado_": {"id": 99, "nome": "Suplente Fantasma"}, "tipoVoto": "Não"},
        {"deputado_": {"id": 20, "nome": "Valido 2"}, "tipoVoto": "Sim"},
        {"deputado_": {}, "tipoVoto": "Abstenção"},  # Payload malformado / sem ID
    ]

    ids_validos_banco = {10, 20}

    votos_filtrados = filtrar_votos_validos(votos_brutos, ids_validos_banco)

    assert len(votos_filtrados) == 2, "Deve retornar exatamente 2 votos válidos."
    ids_restantes = [v.get("deputado_", {}).get("id") for v in votos_filtrados]
    assert 10 in ids_restantes
    assert 20 in ids_restantes


def test_filtrar_votos_validos_lista_vazia():
    """
    Garante que a função de Soft Drop lida pacificamente com uma lista vazia de votos.
    """
    ids_validos_banco = {10, 20}
    assert filtrar_votos_validos([], ids_validos_banco) == []


def test_transformar_voto_camara_sucesso():
    """
    Garante que o voto bruto vindo da API da Câmara seja perfeitamente
    mapeado para o Data Contract do banco de dados (tabela camara_votos).
    """
    voto_bruto = {"deputado_": {"id": 74646, "siglaPartido": "PSDB"}, "tipoVoto": "Sim"}
    proposicao_id = "pec_5_2023"

    resultado = transformar_voto_camara(voto_bruto, proposicao_id)

    assert resultado["id"] == gerar_id_voto_camara(proposicao_id, 74646)
    assert resultado["proposicao_id"] == "pec_5_2023"
    assert resultado["politico_id"] == 74646
    assert resultado["partido_na_epoca"] == "PSDB"
    assert resultado["voto_oficial"] == "Sim"
