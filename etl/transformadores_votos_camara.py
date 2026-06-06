import uuid
import re

def contem_manobra_regimental(descricao: str) -> bool:
    """Verifica se a descrição contém termos bloqueados (falsos positivos)."""
    if not descricao:
        return False
    termos_bloqueados = [
        "requerimento", "preferência", "redação final", 
        "adiamento", "interstício", "retirada de pauta"
    ]
    return any(termo in descricao.lower() for termo in termos_bloqueados)

def eh_votacao_merito_nominal(descricao: str) -> bool:
    """
    Avalia a descrição de uma votação e determina se ela é uma Votação Nominal de Mérito.
    Ignora votações procedimentais (requerimentos, quebras de interstício, redação final)
    e exige a presença da contagem explícita de votos no padrão da Câmara.
    """
    if not descricao:
        return False
        
    descricao_lower = descricao.lower()
    
    # 1. Filtro agressivo (Blocklist): Rejeita qualquer votação de manobra regimental
    if contem_manobra_regimental(descricao_lower):
        return False
        
    # 2. Exigência (Allowlist): Precisa ter a string que denota votação nominal e eletrônica
    padrao_votos = r"sim:\s*\d+;\s*não:\s*\d+"
    
    return bool(re.search(padrao_votos, descricao_lower))

def gerar_id_voto_camara(proposicao_id: str, politico_id: int) -> str:
    """
    Gera um Hash Determinístico (UUID v5) baseado na combinação da chave 
    de negócio da proposição e do ID do parlamentar.
    """
    proposicao_limpa = str(proposicao_id).strip()
    chave_base = f"{proposicao_limpa}_{politico_id}"
    return str(uuid.uuid5(uuid.NAMESPACE_OID, chave_base))

def filtrar_votos_validos(votos_brutos: list, ids_validos_banco: set) -> list:
    """
    Filtra a lista de votos vindos da API, mantendo apenas aqueles cujos
    deputados estão cadastrados no nosso banco de dados.
    Ignora votos malformados ou de parlamentares inexistentes (Soft Drop).
    """
    votos_validos = []
    for voto in votos_brutos:
        id_deputado = voto.get("deputado_", {}).get("id")
        if id_deputado and id_deputado in ids_validos_banco:
            votos_validos.append(voto)
            
    return votos_validos

def transformar_voto_camara(voto_bruto: dict, proposicao_id: str) -> dict:
    """
    Transforma o payload bruto de um voto na API da Câmara para o Data Contract
    esperado na tabela camara_votos do banco de dados.
    """
    deputado = voto_bruto.get("deputado_", {})
    politico_id = deputado.get("id")
    
    return {
        "id": gerar_id_voto_camara(proposicao_id, politico_id),
        "proposicao_id": proposicao_id,
        "politico_id": politico_id,
        "partido_na_epoca": deputado.get("siglaPartido", "S/P"),
        "voto_oficial": voto_bruto.get("tipoVoto")
    }