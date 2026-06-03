import pytest
from unittest.mock import patch

# Importação da função que ainda será implementada (esperado falhar com ImportError)
from etl.transformadores_discursos_camara import gerar_hash_discurso, limpar_transcricao, transformar_discurso

def test_hash_deterministico():
    """
    Testa o Cenário de UUID: Garante que a geração de hash usando UUID v5
    é estritamente determinística se passarmos a mesma trinca de entradas.
    """
    id_deputado = 74646
    data_hora_inicio = "2023-10-05T11:32"
    fase_evento = "Homenagem"

    hash1 = gerar_hash_discurso(id_deputado, data_hora_inicio, fase_evento)
    hash2 = gerar_hash_discurso(id_deputado, data_hora_inicio, fase_evento)

    assert hash1 == hash2
    assert isinstance(hash1, str)
    assert len(hash1) == 36  # O comprimento padrão de uma string UUID

def test_limpeza_cenario_ideal():
    """
    Testa o Cenário Ideal de higienização agressiva (Estágios 1, 2 e 3).
    Remove HTML, decodifica entidades, extirpa o cabeçalho protocolar e normaliza os espaços.
    """
    texto_sujo = (
        "<p>O SR. AÉCIO NEVES (Bloco/PSDB - MG. Para discursar. Sem revisão do orador.) - "
        "Sr. Presidente, senhoras e senhores, &#x97; testando HTML e <b>negrito</b>. \n\n  Fim.</p>"
    )
    
    # Note que o '&#x97;' deve virar um travessão '—' e os espaços extras devem sumir
    texto_esperado = "Sr. Presidente, senhoras e senhores, — testando HTML e negrito. Fim."
    
    texto_limpo = limpar_transcricao(texto_sujo)
    
    assert texto_limpo == texto_esperado


def test_limpeza_cabecalho_integra():
    """
    Testa a remoção do cabeçalho alternativo sem travessão, comum em discursos lidos.
    Ex: 'DISCURSO NA ÍNTEGRA ENCAMINHADO PELO SR. DEPUTADO NETO CARLETTO. '
    """
    texto_sujo = "DISCURSO NA ÍNTEGRA ENCAMINHADO PELO SR. DEPUTADO NETO CARLETTO. Sr. Presidente, este é o meu discurso."
    
    # O cabeçalho inútil deve sumir, restando apenas o discurso real
    texto_esperado = "Sr. Presidente, este é o meu discurso."
    
    texto_limpo = limpar_transcricao(texto_sujo)
    
    assert texto_limpo == texto_esperado


def test_limpeza_cabecalho_pronuncia():
    """
    Testa a remoção do cabeçalho alternativo onde o orador apenas insere o texto nos anais.
    Ex: 'O SR. DEPUTADO FULANO DE TAL pronuncia o seguinte discurso: '
    """
    texto_sujo = "O SR. DEPUTADO JOÃO DA SILVA (Bloco/PSDB - SP) pronuncia o seguinte discurso: Sr. Presidente, começo aqui minha fala."
    
    # O cabeçalho deve sumir, restando apenas o discurso útil
    texto_esperado = "Sr. Presidente, começo aqui minha fala."
    
    texto_limpo = limpar_transcricao(texto_sujo)
    
    assert texto_limpo == texto_esperado


def test_limpeza_sem_travessao():
    """
    Testa a remoção do cabeçalho quando não há travessão/hífen após o bloco do partido.
    Ex: 'A SRA. ADRIANA VENTURA (NOVO - SP. Pela ordem. Sem revisão da oradora.) Presidente, ...'
    """
    texto_sujo = "A SRA. ADRIANA VENTURA (NOVO - SP. Pela ordem. Sem revisão da oradora.) Presidente, o NOVO está em oposição."
    
    # O cabeçalho deve sumir inteiramente, sobrando apenas a fala limpa.
    texto_esperado = "Presidente, o NOVO está em oposição."
    
    texto_limpo = limpar_transcricao(texto_sujo)
    
    assert texto_limpo == texto_esperado

@patch("logging.warning")
def test_limpeza_fallback_aviso(mock_warning):
    """
    Testa o Cenário de Fallback (Completude Soberana): O discurso tem um formato 
    inesperado (sem o travessão clássico). O sistema deve limpar o HTML, manter o 
    texto original inteiro e disparar um log de warning, sem perdas.
    """
    texto_atipico = "<u>Apenas uma fala irregular sem o travessao da camara.</u> Sr. Presidente."
    
    texto_limpo = limpar_transcricao(texto_atipico)
    
    # Garante a retenção de 100% dos dados (mantendo o cabeçalho atípico) + remoção de HTML
    assert texto_limpo == "Apenas uma fala irregular sem o travessao da camara. Sr. Presidente."
    
    # Assert de que o plano B alertou os engenheiros via warning
    mock_warning.assert_called_once()

def test_limpeza_falsos_cabecalhos():
    """
    Garante que falsos cabeçalhos espúrios inseridos por taquígrafos e iniciados 
    com ponto final (ex: '. O SR. STEFANO -') sejam decepados corretamente.
    """
    texto_sujo_1 = ". O SR. STEFANO (Partido) - Sr. Presidente, meu discurso começa aqui."
    texto_sujo_2 = ". DISCURSO SOBRE A VOLTA. Sr. Presidente, falo sobre o tema."
    
    assert limpar_transcricao(texto_sujo_1) == "Sr. Presidente, meu discurso começa aqui."
    assert limpar_transcricao(texto_sujo_2) == "Sr. Presidente, falo sobre o tema."

def test_limpeza_chaves_minusculas():
    """
    Testa a remoção de cabeçalhos que fogem do padrão de maiúsculas e parênteses,
    usando chaves {} e letras minúsculas (comum em ofícios anexados).
    """
    texto_sujo_1 = ". A Sra. LAURA CARNEIRO {PSD-RJ} pronuncia o seguinte discurso: Senhor Presidente, começo aqui."
    texto_sujo_2 = ". O Sr. STEFANO AGUIAR { PSD - MG } pronuncia o seguinte discurso: Falarei sobre o projeto."
    
    assert limpar_transcricao(texto_sujo_1) == "Senhor Presidente, começo aqui."
    assert limpar_transcricao(texto_sujo_2) == "Falarei sobre o projeto."

def test_limpeza_oficios_longos():
    """
    Testa a remoção de cabeçalhos longos inseridos por gabinetes em sessões de encerramento.
    """
    texto_sujo = ". Discurso feito pelo Senhor Deputado Rubens Pereira Júnior {PT/MA} Na Sessão de 12/9/2023 Sr. Presidente, este é o texto."
    assert limpar_transcricao(texto_sujo) == "Sr. Presidente, este é o texto."

def test_limpeza_pontos_soltos():
    """
    Garante que pontos iniciais perdidos sejam limpos mesmo quando o texto não tem cabeçalho a ser removido.
    """
    texto_sujo = ". Excelentíssimo Senhor Presidente, meu discurso."
    assert limpar_transcricao(texto_sujo) == "Excelentíssimo Senhor Presidente, meu discurso."

def test_limpeza_notas_taquigraficas():
    """
    Garante que reações da plateia ou notas taquigráficas curtas entre parênteses,
    colchetes ou chaves sejam normalizadas para chaves (ex: {Palmas}, {Risos}).
    """
    texto_sujo = "Eu afirmo que o projeto é bom (Palmas). Alguns discordam [Risos]. Porém, continuaremos firmes {Muito bem!}."
    texto_esperado = "Eu afirmo que o projeto é bom {Palmas}. Alguns discordam {Risos}. Porém, continuaremos firmes {Muito bem!}."
    
    assert limpar_transcricao(texto_sujo) == texto_esperado

@patch("logging.warning")
def test_limpeza_vazamento_binario(mock_warning):
    """
    Testa a detecção de lixo binário (arquivos DOCX crus vazados no payload).
    Deve disparar um warning e substituir o conteúdo inútil por uma string indicativa.
    """
    # Assinatura típica de um arquivo .docx (ZIP archive) lido como string
    texto_vazado = "PK!?J~3?? [Content_Types].xml... word/theme/theme1.xml... bytes inúteis"
    
    texto_limpo = limpar_transcricao(texto_vazado)
    
    assert texto_limpo == "[ARQUIVO CORROMPIDO NA ORIGEM]"
    mock_warning.assert_called_once()

def test_limpeza_texto_vazio():
    """
    Garante que a função retorna uma string vazia imediatamente se receber None ou "".
    """
    assert limpar_transcricao("") == ""
    assert limpar_transcricao(None) == ""

def test_transformacao_fase_evento_string():
    """
    Garante que a transformação lida corretamente com a anomalia onde a API 
    retorna 'faseEvento' como uma String direta em vez de um Objeto/Dict.
    """
    payload_anomalo = {
        "dataHoraInicio": "2023-10-05T11:32",
        "faseEvento": "Sessão Solene",  # Diferente do habitual {"titulo": "Sessão Solene"}
        "transcricao": "Texto de teste."
    }
    
    resultado = transformar_discurso(payload_anomalo, 123)
    assert resultado["fase_evento"] == "Sessão Solene"

def test_transformacao_data_contract():
    """
    Testa a transformação de um item do payload de Discurso,
    garantindo que o dicionário de saída adere ESTRITAMENTE ao Schema Estrito / Data Contract acordado.
    """
    id_deputado = 74646
    payload_camara = {
        "dataHoraInicio": "2023-10-05T11:32",
        "faseEvento": {"titulo": "Breves Comunicações"},
        "sumario": "Resumo do discurso.",
        "transcricao": "O SR. DEPUTADO (Partido) - Texto final validado.",
        "urlVideo": "http://camara.gov/video.mp4"
    }
    
    resultado = transformar_discurso(payload_camara, id_deputado)
    
    chaves_esperadas = {
        "id",
        "politico_id",
        "data_discurso",
        "fase_evento",
        "sumario",
        "texto_bruto",
        "url_video"
    }
    
    assert set(resultado.keys()) == chaves_esperadas
    assert resultado["politico_id"] == id_deputado
    assert resultado["fase_evento"] == "Breves Comunicações"
    assert resultado["texto_bruto"] == "Texto final validado."

def test_limpeza_sem_travessao_chaves():
    """Garante a limpeza quando o partido está em chaves e não há travessão."""
    texto_sujo = "O Sr. FAUSTO SANTOS JÚNIOR {UNIÃO-AM} Senhor Presidente, gostaria..."
    assert limpar_transcricao(texto_sujo) == "Senhor Presidente, gostaria..."

def test_limpeza_parentese_aberto():
    """Garante a limpeza quando o taquígrafo esquece de fechar o parêntese."""
    # A fala emenda direto na saudação após o hífen do estado
    texto_sujo = "O Sr. RICARDO AYRES (REPUBLICANOS-TO Senhor Presidente, inicio..."
    assert limpar_transcricao(texto_sujo) == "Senhor Presidente, inicio..."

def test_limpeza_erro_digitacao_pronunciamento():
    """Garante a remoção de PRONUNCIAMENTO (ou PRONUCIAMENTO com erro de digitação)."""
    texto_sujo_1 = "PRONUNCIAMENTO DO DEPUTADO ACÁCIO FAVACHO - MDB/AP Sr. Presidente..."
    texto_sujo_2 = "PRONUCIAMENTO DO DEPUTADO ACÁCIO FAVACHO - MDB/AP Senhor Presidente..."
    assert limpar_transcricao(texto_sujo_1) == "Sr. Presidente..."
    assert limpar_transcricao(texto_sujo_2) == "Senhor Presidente..."

def test_limpeza_cabecalho_camara():
    """Garante que cabeçalhos puros da CÂMARA DOS DEPUTADOS sejam limpos."""
    texto_sujo_1 = "CÂMARA DOS DEPUTADOS Senhor Presidente, falo hoje..."
    texto_sujo_2 = "CÂMARA DOS DEPUTADOS. O meu estado precisa..."
    # O primeiro cairá no Padrão 5 (com saudação), o segundo cairá no Padrão 6 (sem saudação)
    assert limpar_transcricao(texto_sujo_1) == "Senhor Presidente, falo hoje..."
    assert limpar_transcricao(texto_sujo_2) == "O meu estado precisa..."

def test_limpeza_pronuncia_variacoes():
    """Reforça a verificação da frase 'pronuncia o seguinte discurso' com variações."""
    texto_sujo = "O Sr. STEFANO AGUIAR {PSD-MG} pronunciou o seguinte discurso: Senhor Presidente..."
    assert limpar_transcricao(texto_sujo) == "Senhor Presidente..."