import uuid
import re
from typing import Optional, List, Dict, Any


def gerar_id_voto_senado(proposicao_id: str, politico_id: int) -> str:
    """
    Gera um Hash Determinístico (UUID v5) baseado na combinação da chave
    de negócio da proposição e do ID do parlamentar.
    """
    proposicao_limpa = str(proposicao_id).strip()
    chave_base = f"{proposicao_limpa}_{politico_id}"
    return str(uuid.uuid5(uuid.NAMESPACE_OID, chave_base))


def validar_corte_temporal_votacao(data_votacao: Optional[str]) -> bool:
    """
    Valida se a data atende ao corte da Legislatura 57 (>= 01/01/2023).
    """
    if not data_votacao:
        return False
    return data_votacao[:10] >= "2023-01-01"


def contem_manobra_regimental_senado(descricao: str) -> bool:
    """
    Filtro Blocklist (Regex).
    Retorna True se a descrição contiver manobras regimentais.
    """
    if not descricao:
        return False
    padrao = (
        r"(?i)(requerimento|urgência|adiamento|destaque|questão\sde\sordem|preferência)"
    )
    return bool(re.search(padrao, descricao))


def contem_termo_merito_senado(descricao: str) -> bool:
    """
    Filtro Allowlist (Regex).
    Retorna True se a descrição contiver termos de mérito explícitos.
    """
    if not descricao:
        return False

    padrao = r"(?i)(texto[- ]base|substitutivo|parecer|1º\sturno|primeiro\sturno|turno\súnico|2º\sturno|segundo\sturno)"
    return bool(re.search(padrao, descricao))


def encontrar_sessao_merito_senado(
    sessoes: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Recebe lista de sessões, ordena cronologicamente (ASC) e retorna a primeira
    que atende ao corte temporal (>= 2023), passa pela Blocklist e é aprovada pela Allowlist.
    """
    if not sessoes:
        return None

    sessoes_ordenadas = sorted(sessoes, key=lambda x: x.get("dataSessao", ""))

    for sessao in sessoes_ordenadas:
        data_votacao = sessao.get("dataSessao")
        descricao = sessao.get("descricaoVotacao", "")

        if not validar_corte_temporal_votacao(data_votacao):
            continue

        if contem_manobra_regimental_senado(descricao):
            continue

        if contem_termo_merito_senado(descricao):
            return sessao

    return None


def filtrar_votos_validos_senado(
    votos_brutos: List[Dict[str, Any]], ids_validos_banco: set
) -> List[Dict[str, Any]]:
    """
    Filtra a lista de votos extraída para remover parlamentares cujos IDs
    não estejam no conjunto de políticos válidos. Protege contra erro de FK.
    """
    votos_validos = []
    for voto in votos_brutos:
        codigo = voto.get("codigoParlamentar")
        if codigo is not None:
            try:
                if int(codigo) in ids_validos_banco:
                    votos_validos.append(voto)
            except ValueError:
                continue

    return votos_validos


def transformar_voto_senado(
    voto_bruto: Dict[str, Any], proposicao_id: str
) -> Dict[str, Any]:
    """
    Converte o dicionário bruto da API do Senado para o dicionário da nossa
    tabela senado_votos, gerando o UUID v5 correspondente.
    """
    politico_id = int(voto_bruto.get("codigoParlamentar"))

    return {
        "id": gerar_id_voto_senado(proposicao_id, politico_id),
        "proposicao_id": proposicao_id,
        "politico_id": politico_id,
        "partido_na_epoca": voto_bruto.get("siglaPartidoParlamentar", "S/P"),
        "voto_oficial": voto_bruto.get("siglaVotoParlamentar"),
    }
