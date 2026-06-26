import uuid
from typing import List, Dict, Any, Optional


def gerar_id_proposicao(chave_negocio: str) -> str:
    """
    Gera um Hash Determinístico (UUID v5) baseado na chave de negócio da proposição.
    Garante que chaves idênticas gerem o mesmo UUID para evitar duplicatas no banco.
    """
    chave_limpa = chave_negocio.strip()
    # Utilizamos o namespace OID padrão do Python como semente
    return str(uuid.uuid5(uuid.NAMESPACE_OID, chave_limpa))


def obter_data_votacao_merito(tramitacoes: List[Dict[str, Any]]) -> Optional[str]:
    """
    Varre o histórico de tramitações e retorna a dataHora do primeiro evento
    que corresponda à votação de mérito (whitelist: 231, 232, 233, 1231).
    Retorna None se a proposição nunca teve votação de mérito.
    """
    whitelist = {"231", "232", "233", "1231"}
    tramitacoes_ordenadas = sorted(tramitacoes, key=lambda x: x.get("dataHora", ""))
    for tramitacao in tramitacoes_ordenadas:
        if str(tramitacao.get("codTipoTramitacao")) in whitelist:
            return tramitacao.get("dataHora")
    return None


def validar_corte_temporal(data_votacao: Optional[str]) -> bool:
    """
    Valida se a data da votação de mérito atende ao corte do escopo (>= 01/01/2023).
    Retorna False para datas anteriores ou nulas.
    """
    if not data_votacao:
        return False

    # A comparação lexicográfica dos primeiros 10 caracteres é segura para o formato ISO 8601
    return data_votacao[:10] >= "2023-01-01"


def formatar_chave_negocio(sigla_tipo: Any, numero: Any, ano: Any) -> str:
    """
    Formata a chave de negócio da proposição no padrão snake_case (ex: pec_45_2019).
    """
    sigla = str(sigla_tipo).strip().lower()
    num = str(numero).strip()
    ano_str = str(ano).strip()
    return f"{sigla}_{num}_{ano_str}"


def transformar_proposicao(
    payload: Dict[str, Any], tramitacoes: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """
    Filtro principal que transforma o payload bruto da API e suas tramitações
    no dicionário rigoroso do Data Contract. Descarta silenciosamente se não
    houver votação de mérito válida no escopo de tempo.
    """
    data_votacao = obter_data_votacao_merito(tramitacoes)

    if not validar_corte_temporal(data_votacao):
        return None

    chave_negocio = formatar_chave_negocio(
        payload.get("siglaTipo"), payload.get("numero"), payload.get("ano")
    )

    # Busca o ID do evento de tramitação que validou a votação
    id_votacao = None
    whitelist = {"231", "232", "233", "1231"}
    tramitacoes_ordenadas = sorted(tramitacoes, key=lambda x: x.get("dataHora", ""))
    for tramitacao in tramitacoes_ordenadas:
        if str(tramitacao.get("codTipoTramitacao")) in whitelist:
            id_votacao = tramitacao.get("id")
            break

    return {
        "id": gerar_id_proposicao(chave_negocio),
        "proposicao_id": chave_negocio,
        "id_camara": payload.get("id"),
        "id_votacao_camara": str(id_votacao) if id_votacao else None,
        "tipo": payload.get("siglaTipo"),
        "numero": payload.get("numero"),
        "ano": payload.get("ano"),
        "ementa": payload.get("ementa"),
        "data_votacao": data_votacao,
        "url_texto_inteiro": payload.get("urlInteiroTeor"),
        "resumo_executivo": None,
        "embedding_resumo_executivo": None,
    }
