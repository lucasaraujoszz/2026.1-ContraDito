import pytest
from unittest.mock import patch

# Importamos a função que ainda será implementada (Fase RED)
from etl.transformadores_discursos_senado import (
    normalizar_payload_senado, 
    gerar_id_discurso_senado, 
    mapear_discurso_senado,
    limpar_transcricao_senado
)


def test_normalizar_dict_unico():
    """
    Garante que um único discurso retornado como Dict (anomalia do XML do Senado)
    seja encapsulado em uma Lista para manter o comportamento iterável padrão.
    """
    payload_anomalo = {
        "PesquisaPronunciamentos": {
            "Pronunciamentos": {
                "Pronunciamento": {"CodigoPronunciamento": "12345", "TipoPronunciamento": "Homenagem"}
            }
        }
    }
    
    resultado = normalizar_payload_senado(status_code=200, dados_json=payload_anomalo)
    
    assert isinstance(resultado, list)
    assert len(resultado) == 1
    assert resultado[0]["CodigoPronunciamento"] == "12345"


def test_normalizar_payload_vazio():
    """
    Garante que HTTP 404, 204 ou JSONs vazios não quebrem o script e retornem
    uma lista vazia. O status HTTP deve ser avaliado prioritariamente.
    """
    # 1. Se o status for 404/204, deve ignorar o JSON (mesmo que venha preenchido)
    payload_enganoso = {
        "PesquisaPronunciamentos": {
            "Pronunciamentos": {
                "Pronunciamento": {"CodigoPronunciamento": "999"}
            }
        }
    }
    assert normalizar_payload_senado(status_code=404, dados_json=payload_enganoso) == []
    assert normalizar_payload_senado(status_code=204, dados_json=None) == []
    
    # 2. Se o status for 200, mas for uma "casca vazia" do Senado
    casca_vazia = {"PesquisaPronunciamentos": {"Pronunciamentos": None}}
    assert normalizar_payload_senado(status_code=200, dados_json=casca_vazia) == []


def test_id_deterministico():
    """
    O Hash precisa ser consistente sempre que rodar com os mesmos parâmetros
    para evitar duplicação no Bulk Upsert (idempotência garantida via UUID v5).
    """
    id_senador = 1000150
    codigo_pronunciamento = "999888"
    
    hash_1 = gerar_id_discurso_senado(id_senador, codigo_pronunciamento)
    hash_2 = gerar_id_discurso_senado(id_senador, codigo_pronunciamento)
    
    assert hash_1 == hash_2
    assert isinstance(hash_1, str)
    assert len(hash_1) == 36  # Tamanho padrão de um UUID formatado em string


@patch("etl.transformadores_discursos_senado.logger")
def test_mapear_fallback_parser(mock_logger):
    """
    Se o BeautifulSoup não achar o texto (ex: layout do Senado mudou),
    os metadados devem ser salvos e o erro logado na engenharia (Completude Soberana).
    """
    raw_api = {
        "CodigoPronunciamento": "123",
        "DataPronunciamento": "2023-01-01",
        "TipoUsoPalavra": {"Sigla": "DIS", "Descricao": "Debate"},
        "TextoResumo": "Sumário teste",
        "UrlTexto": "http://legis.senado.leg.br/texto"
    }
    html_invalido = "<html><body><div class='layout-mudou'>Nada aqui</div></body></html>"
    
    resultado = mapear_discurso_senado(id_senador=1000150, discurso_raw=raw_api, html_bruto=html_invalido)
    
    # Asserts do Fallback
    assert resultado["texto_bruto"] == "[FALHA NO PARSER HTML]"
    assert mock_logger.error.called
    
    # Asserts do Data Contract Estrito (7 chaves e mapeamento perfeito)
    chaves_exigidas = {"id", "politico_id", "data_discurso", "fase_evento", "sumario", "texto_bruto", "url_video"}
    assert set(resultado.keys()) == chaves_exigidas
    assert resultado["fase_evento"] == "Debate"
    assert resultado["sumario"] == "Sumário teste"
    assert resultado["url_video"] is None


def test_mapear_sucesso_higienizacao():
    """
    Garante a extração bem-sucedida da div correta via BeautifulSoup e a
    aplicação da Limpeza Taquigráfica (Regex) no texto extraído, extirpando
    o cabeçalho típico do Senado.
    """
    raw_api = {
        "CodigoPronunciamento": "777",
        "DataPronunciamento": "2023-05-10"
    }
    # Simulando o HTML real do Senado com a classe alvo e texto sujo com cabeçalho
    html_valido = """
    <html>
        <body>
            <div class='layout-inutil'>Lixo do Portal</div>
            <div class='texto-pronunciamento'>O SR. MAGNO MALTA (Bloco/PL - ES. Para discursar. Sem revisão do orador.) - Sr. Presidente, defendo a aprovação da pauta de hoje. Muito obrigado.</div>
        </body>
    </html>
    """
    
    resultado = mapear_discurso_senado(id_senador=1000150, discurso_raw=raw_api, html_bruto=html_valido)
    
    texto_esperado = "Sr. Presidente, defendo a aprovação da pauta de hoje. Muito obrigado."
    assert resultado["texto_bruto"] == texto_esperado


def test_limpar_anomalias_taquigraficas():
    """
    Testa a resiliência da Regex contra as imprevisibilidades dos taquígrafos do Senado
    (erros de digitação, travessões diferentes, espaços duplos, ausência de partido).
    """
    cenarios = [
        # 1. Padrão normal com travessão (em-dash) em vez de hífen
        ("O SR. MAGNO MALTA (PL - ES) — Sr. Presidente...", "Sr. Presidente..."),
        # 2. Variação de maiúsculas/minúsculas
        ("A Sra. Damares Alves (Republicanos/DF) - Eu voto sim.", "Eu voto sim."),
        # 3. Formato de Presidente da Sessão (apenas cargo no parêntese)
        ("O SR. PRESIDENTE (Rodrigo Pacheco) - Declaro aberta a sessão.", "Declaro aberta a sessão."),
        # 4. Ausência total de parênteses (anomalia crítica e comum)
        ("O SR. PRESIDENTE - Passamos à pauta.", "Passamos à pauta."),
        # 5. Caos de espaçamento e traço duplo
        ("O  SR.   FLÁVIO BOLSONARO   ( PL - RJ )   --   Boa tarde.", "Boa tarde.")
    ]
    
    for texto_sujo, texto_esperado in cenarios:
        resultado = limpar_transcricao_senado(texto_sujo)
        assert resultado == texto_esperado, f"Falhou ao limpar: {texto_sujo}. Retornou: {resultado}"


def test_mapear_fallback_estrategias():
    """
    Testa as 3 estratégias de raspagem agressiva (Fallback em cascata) do Senado:
    1. ID/Classes atualizadas (ex: textoIntegral)
    2. Âncora de título "Texto integral"
    3. Varredura taquigráfica buscando O SR. nos parágrafos
    """
    raw_api = {
        "CodigoPronunciamento": "999",
        "TipoUsoPalavra": {"Descricao": "Debate"},
        "TextoResumo": "Resumo",
    }
    
    # 1. Teste da Estratégia 1 (ID textoIntegral)
    html_1 = "<html><body><div id='textoIntegral'>O SR. TESTE (PL - SP) - Este é o primeiro texto de teste longo.</div></body></html>"
    resultado_1 = mapear_discurso_senado(1000150, raw_api, html_1)
    assert resultado_1["texto_bruto"] == "Este é o primeiro texto de teste longo."

    # 2. Teste da Estratégia 2 (Âncora de título)
    html_2 = "<html><body><div><h2>Texto integral</h2><p>O SR. TESTE - Este é o segundo texto longo.</p><p>Continuando.</p></div></body></html>"
    resultado_2 = mapear_discurso_senado(1000150, raw_api, html_2)
    assert resultado_2["texto_bruto"] == "Este é o segundo texto longo. Continuando."
    
    # 3. Teste da Estratégia 3 (Varredura de parágrafos)
    html_3 = "<html><body><p>Menu Inútil</p><p>O SR. TESTE (PL - SP) - Este é o terceiro texto longo para validar.</p><p>Final.</p></body></html>"
    resultado_3 = mapear_discurso_senado(1000150, raw_api, html_3)
    assert resultado_3["texto_bruto"] == "Este é o terceiro texto longo para validar. Final."


def test_limpar_cabecalho_institucional():
    """
    Fase RED - BUG 1: O cabeçalho massivo do Congresso Nacional e a introdução 
    da mesa diretora devem ser removidos, sobrando apenas o discurso real.
    """
    texto_sujo = (
        "CÂMARA DOS DEPUTADOS CN - DEPARTAMENTO DE TAQUIGRAFIA, REVISÃO E REDAÇÃO – "
        "DETAQ CN (5ª Sessão Plenária, Sessão Não Deliberativa Solene (semipresencial)) "
        "08/04/2026 A SRA. PRESIDENTE (Ana Paula Lobato. PSB - MA) - O próximo orador é o Senador."
    )
    
    texto_limpo = limpar_transcricao_senado(texto_sujo)
    
    assert "CÂMARA DOS DEPUTADOS CN" not in texto_limpo
    assert "DETAQ" not in texto_limpo
    assert texto_limpo == "O próximo orador é o Senador."