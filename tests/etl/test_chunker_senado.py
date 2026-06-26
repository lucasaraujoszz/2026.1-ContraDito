import uuid
import pytest
from unittest.mock import MagicMock
from etl.chunker_discursos_senado import (
    gerar_id_deterministico_chunk,
    processar_discurso_senado,
    executar_pipeline_chunking_senado,
)


def test_gerar_id_deterministico_chunk_gera_uuid_v5_repetivel():
    discurso_id = "550e8400-e29b-41d4-a716-446655440000"
    indice = 0

    # Execução
    id_1 = gerar_id_deterministico_chunk(discurso_id, indice)
    id_2 = gerar_id_deterministico_chunk(discurso_id, indice)

    # Valida se não está vazio e se é determinístico (mesmo input = mesmo output)
    assert id_1 != "", "O ID gerado não pode ser vazio"
    assert id_1 == id_2, "O hash deve ser idêntico para os mesmos inputs (idempotência)"

    # Valida se respeita o formato estrutural UUID versão 5
    parsed_uuid = uuid.UUID(id_1)
    assert parsed_uuid.version == 5, "O UUID gerado deve ser estritamente da versão 5"


def test_processar_discurso_senado_payload_tipagem_dupla():
    """
    Ciclo 2: Construção e Tipagem do Payload (Contrato de Dados).
    Valida se a função retorna 2 listas (para Supabase e Qdrant) com as
    chaves e tipagens corretas (data em Unix Timestamp/Int e politico_id em Int).
    """
    discurso_id = "550e8400-e29b-41d4-a716-446655440000"
    politico_id = 150
    data_str = "2023-05-10"  # Data padrão retida da API do Senado
    texto_bruto = "Sr. Presidente, defendo a aprovação da pauta."

    # Mock do modelo de embedding (BAAI/bge-m3)
    modelo_mock = MagicMock()
    modelo_mock.encode.return_value = [0.5, 0.1, -0.2]

    # Execução (Retorna lote Supabase e lote Qdrant)
    lote_supa, lote_qdrant = processar_discurso_senado(
        discurso_id, texto_bruto, politico_id, data_str, modelo_mock
    )

    assert len(lote_supa) == 1, "Deve retornar os dados textuais para o Supabase"
    assert len(lote_qdrant) == 1, "Deve retornar os pontos vetoriais para o Qdrant"

    # Validação Contrato Qdrant (Vetorial)
    point_qdrant = lote_qdrant[0]
    assert set(point_qdrant.keys()) == {"id", "vector", "payload"}

    payload = point_qdrant["payload"]
    assert set(payload.keys()) == {"politico_id", "discurso_id", "data_discurso"}
    assert isinstance(payload["politico_id"], int), "politico_id deve ser Integer"
    assert isinstance(
        payload["data_discurso"], int
    ), "data_discurso deve ser convertida para Unix Timestamp"


def test_executar_pipeline_chunking_senado_dupla_escrita_feliz():
    """
    Ciclo 3: Resiliência Transacional e Dupla Escrita (O Dual-Write Feliz).
    Testa se a orquestração processa o lote e aciona o Upsert em ambas as pontas (Dual-Write).
    """
    supabase_mock = MagicMock()
    qdrant_mock = MagicMock()
    modelo_mock = MagicMock()
    modelo_mock.encode.return_value = [0.1] * 1024

    # Mock DB: 1. Tabela de chunks (Watermarker: retorna nenhum id processado)
    chunks_table_mock = MagicMock()
    chunks_table_mock.select.return_value.range.return_value.execute.return_value.data = (
        []
    )

    # Mock DB: 2. Tabela de discursos (retorna 1 discurso cru)
    discursos_table_mock = MagicMock()
    db_response = MagicMock()
    db_response.data = [
        {
            "id": "12345678-1234-5678-1234-567812345678",
            "texto_bruto": "Discurso de teste para o dual write do senado.",
            "politico_id": 150,
            "data_discurso": "2023-05-10",
        }
    ]
    db_empty = MagicMock(data=[])

    discursos_table_mock.select.return_value.range.return_value.execute.side_effect = [
        db_response,
        db_empty,
    ]

    # Roteador de tabelas (Side effect)
    supabase_mock.table.side_effect = lambda name: (
        chunks_table_mock if name == "senado_discurso_chunks" else discursos_table_mock
    )

    # Execução
    total = executar_pipeline_chunking_senado(
        supabase_client=supabase_mock,
        qdrant_client=qdrant_mock,
        modelo=modelo_mock,
        limite=1,
    )

    assert (
        total > 0
    ), "O pipeline deve processar e retornar a contagem de chunks inseridos"

    # Verifica se o método UPSERT foi invocado no Relacional e no Vetorial
    chunks_table_mock.upsert.assert_called_once()
    qdrant_mock.upsert.assert_called_once()


def test_executar_pipeline_chunking_senado_falha_qdrant_aborta_execucao():
    """
    Ciclo 4: Prevenção de Sujeira Transacional (Simulação de Falha).
    Garante que se o Upsert no Qdrant falhar (ex: Timeout), a exceção é propagada
    imediatamente, interrompendo o loop para que os próximos itens não sejam processados.
    """
    supabase_mock = MagicMock()
    qdrant_mock = MagicMock()
    modelo_mock = MagicMock()
    modelo_mock.encode.return_value = [0.1] * 1024

    chunks_table_mock = MagicMock()
    chunks_table_mock.select.return_value.range.return_value.execute.return_value.data = (
        []
    )

    discursos_table_mock = MagicMock()
    db_response = MagicMock()
    db_response.data = [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "texto_bruto": "Discurso 1",
            "politico_id": 1,
            "data_discurso": "2023-01-01",
        },
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "texto_bruto": "Discurso 2",
            "politico_id": 2,
            "data_discurso": "2023-01-02",
        },
    ]
    db_empty = MagicMock(data=[])

    discursos_table_mock.select.return_value.range.return_value.execute.side_effect = [
        db_response,
        db_empty,
    ]
    supabase_mock.table.side_effect = lambda name: (
        chunks_table_mock if name == "senado_discurso_chunks" else discursos_table_mock
    )

    # Força a falha no Qdrant
    qdrant_mock.upsert.side_effect = TimeoutError("Conexão com Qdrant perdida")

    # Execução e Validação
    with pytest.raises(TimeoutError):
        executar_pipeline_chunking_senado(
            supabase_client=supabase_mock, qdrant_client=qdrant_mock, modelo=modelo_mock
        )

    # Deve ter chamado Supabase upsert apenas 1 vez (pro primeiro discurso) e interrompido antes do 2º
    chunks_table_mock.upsert.assert_called_once()
    qdrant_mock.upsert.assert_called_once()


def test_executar_pipeline_chunking_senado_watermarker_filtra_processados():
    """
    Ciclo 2: Filtro em Memória e Paginação de Discursos.
    Testa se o filtro de processados ocorre na memória (evitando erro de URL gigante no banco)
    e se a busca de discursos usa paginação (.range()), aplicando o limite APENAS aos inéditos.
    """
    supabase_mock = MagicMock()
    qdrant_mock = MagicMock()
    modelo_mock = MagicMock()
    modelo_mock.encode.return_value = [0.1] * 1024

    # 1. Mock do Watermarker paginado (Tabela filha)
    chunks_table_mock = MagicMock()
    chunks_page_1 = MagicMock(data=[{"discurso_id": "uuid-processado-1"}])
    chunks_page_2 = MagicMock(data=[])
    chunks_table_mock.select.return_value.range.return_value.execute.side_effect = [
        chunks_page_1,
        chunks_page_2,
    ]

    # 2. Mock da Tabela pai de discursos paginada
    discursos_table_mock = MagicMock()
    # Página 1 tem um já processado e um inédito
    disc_page_1 = MagicMock(
        data=[
            {
                "id": "uuid-processado-1",
                "texto_bruto": "Velho",
                "politico_id": 1,
                "data_discurso": "2023-01-01",
            },
            {
                "id": "uuid-inedito-1",
                "texto_bruto": "Novo 1",
                "politico_id": 2,
                "data_discurso": "2023-01-02",
            },
        ]
    )
    # Página 2 tem mais um inédito
    disc_page_2 = MagicMock(
        data=[
            {
                "id": "uuid-inedito-2",
                "texto_bruto": "Novo 2",
                "politico_id": 3,
                "data_discurso": "2023-01-03",
            }
        ]
    )
    disc_page_3 = MagicMock(data=[])  # Fim da paginação
    discursos_table_mock.select.return_value.range.return_value.execute.side_effect = [
        disc_page_1,
        disc_page_2,
        disc_page_3,
    ]

    supabase_mock.table.side_effect = lambda name: (
        chunks_table_mock if name == "senado_discurso_chunks" else discursos_table_mock
    )

    # Com limite=1 e 2 inéditos no banco, ele deve processar estritamente o uuid-inedito-1
    executar_pipeline_chunking_senado(supabase_mock, qdrant_mock, modelo_mock, limite=1)

    # 1. Garante que .not_.in_ NÃO foi chamado em nenhum momento
    discursos_table_mock.select.return_value.not_.in_.assert_not_called()

    # 2. Garante que o Supabase recebeu o upsert do chunk APENAS para o uuid-inedito-1
    lote_upsertado = chunks_table_mock.upsert.call_args[0][0]
    assert len(lote_upsertado) == 1
    assert lote_upsertado[0]["discurso_id"] == "uuid-inedito-1"


def test_processar_discurso_senado_ignora_falhas_extracao():
    """
    Ciclo 6: Prevenção de Vetorização de Lixo (Filtro de Texto Inválido).
    Garante que discursos marcados com erros de extração não gerem chunks
    e não acionem o modelo de embedding.
    """
    modelo_mock = MagicMock()

    textos_invalidos = [
        "[FALHA NO PARSER HTML]",
        "[ERRO DE REDE]",
        "[ARQUIVO CORROMPIDO NA ORIGEM]",
    ]

    for texto_invalido in textos_invalidos:
        lote_supa, lote_qdrant = processar_discurso_senado(
            discurso_id="uuid-qualquer",
            texto_bruto=texto_invalido,
            politico_id=1,
            data_discurso_str="2023-01-01",
            modelo=modelo_mock,
        )

        assert lote_supa == []
        assert lote_qdrant == []

    modelo_mock.encode.assert_not_called()


def test_executar_pipeline_chunking_senado_watermarker_paginado():
    """
    Ciclo 1: Watermarker Paginado.
    Garante que a busca pelos IDs já processados utiliza paginação (.range)
    para burlar o limite de 1000 linhas do Supabase.
    """
    supabase_mock = MagicMock()
    qdrant_mock = MagicMock()
    modelo_mock = MagicMock()

    chunks_table_mock = MagicMock()
    select_mock = chunks_table_mock.select.return_value

    # Simula 3 páginas: 1000 itens, 1000 itens, e 0 itens
    page_1 = MagicMock(data=[{"discurso_id": f"id-{i}"} for i in range(1000)])
    page_2 = MagicMock(data=[{"discurso_id": f"id-{i}"} for i in range(1000, 2000)])
    page_3 = MagicMock(data=[])

    range_mock = select_mock.range.return_value
    range_mock.execute.side_effect = [page_1, page_2, page_3]

    # Mock para a tabela de discursos retornar vazio e encerrar o script rápido
    discursos_table_mock = MagicMock()
    discursos_table_mock.select.return_value.range.return_value.execute.return_value.data = (
        []
    )

    supabase_mock.table.side_effect = lambda name: (
        chunks_table_mock if name == "senado_discurso_chunks" else discursos_table_mock
    )

    executar_pipeline_chunking_senado(supabase_mock, qdrant_mock, modelo_mock)

    # Verifica se .range() foi chamado para paginar os resultados com os offsets corretos
    assert select_mock.range.call_count == 3
    select_mock.range.assert_any_call(0, 999)
    select_mock.range.assert_any_call(1000, 1999)
    select_mock.range.assert_any_call(2000, 2999)


def test_executar_pipeline_chunking_senado_qdrant_sub_lotes():
    """
    Ciclo 1: Sub-lotes Qdrant.
    Garante que a inserção no Qdrant é fatiada em lotes menores (ex: 50 pontos)
    para evitar timeout de rede em discursos muito longos.
    """
    supabase_mock = MagicMock()
    qdrant_mock = MagicMock()
    modelo_mock = MagicMock()
    modelo_mock.encode.return_value = [0.1] * 1024

    chunks_table_mock = MagicMock()
    chunks_table_mock.select.return_value.range.return_value.execute.return_value.data = (
        []
    )

    discursos_table_mock = MagicMock()
    # Texto gigante sem espaços para forçar o splitter a quebrar exatamente a cada 1000 caracteres
    texto_gigante = "A" * 120000

    db_response = MagicMock()
    db_response.data = [
        {
            "id": "12345678-1234-5678-1234-567812345678",
            "texto_bruto": texto_gigante,
            "politico_id": 150,
            "data_discurso": "2023-05-10",
        }
    ]
    db_empty = MagicMock(data=[])
    discursos_table_mock.select.return_value.range.return_value.execute.side_effect = [
        db_response,
        db_empty,
    ]

    supabase_mock.table.side_effect = lambda name: (
        chunks_table_mock if name == "senado_discurso_chunks" else discursos_table_mock
    )

    executar_pipeline_chunking_senado(
        supabase_client=supabase_mock,
        qdrant_client=qdrant_mock,
        modelo=modelo_mock,
        chunk_size=1000,
        chunk_overlap=0,
    )

    # 120 chunks devem gerar 3 chamadas parciais no Qdrant (50, 50, 20)
    assert qdrant_mock.upsert.call_count == 3
