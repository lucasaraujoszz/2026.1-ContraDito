import uuid
import logging
import re
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Usamos o mesmo namespace da Câmara para manter o padrão de geração de UUID do projeto, embora agora os dados fiquem isolados.
NAMESPACE_SENADO = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def normalizar_payload_senado(status_code: int, dados_json: dict) -> list:
    """
    Normaliza o payload da API do Senado, garantindo que o retorno seja sempre uma lista iterável.
    """
    if status_code in (404, 204):
        return []

    if not dados_json:
        return []

    raiz = dados_json.get("PesquisaPronunciamentos")
    if not raiz:
        raiz = dados_json.get("DiscursosParlamentar", {}).get("Parlamentar", {})

    pronunciamentos_brutos = raiz.get("Pronunciamentos") or {}

    if not pronunciamentos_brutos:
        return []

    discursos = pronunciamentos_brutos.get("Pronunciamento") or []

    if isinstance(discursos, dict):
        return [discursos]

    return discursos


def gerar_id_discurso_senado(id_senador: int, codigo_pronunciamento: str) -> str:
    """
    Gera um UUID v5 sintético e determinístico baseado no ID do Senador e Código do Pronunciamento.
    """
    return str(uuid.uuid5(NAMESPACE_SENADO, f"{id_senador}_{codigo_pronunciamento}"))


def limpar_transcricao_senado(texto_bruto: str) -> str:
    """
    Aplica regras de higienização exclusivas do Senado, removendo
    cabeçalhos taquigráficos e lixos estruturais.
    """
    if not texto_bruto:
        return ""

    # Remove prefixo "Texto integral" ou indicação de ausência gerados pelo site do Senado
    texto_limpo = re.sub(
        r"^Texto integral\s*(não disponível!?)?\s*",
        "",
        texto_bruto,
        flags=re.IGNORECASE,
    )

    # Remove padrão de orador do Senado: "O SR. NOME (Partido/UF) - "
    # Suporta anomalias como ausência de parênteses, múltiplos espaços e travessões variados.
    padrao = r"^.*?(?:O\s+SR\.?|A\s+SRA\.?|O\s+PRESIDENTE|A\s+PRESIDENTE)\s+[^\(]*?(?:\([^\)]+\))?\s*[-—–]+\s+"
    texto_limpo = re.sub(padrao, "", texto_limpo, flags=re.IGNORECASE | re.DOTALL)

    # Converte reações da plateia/taquigrafia para o padrão de chaves e remove espaços duplos
    texto_limpo = re.sub(
        r"\(([Rr]isos|[Pp]almas|[Vv]ozes|Ininteligível)\)", r"{\1}", texto_limpo
    )
    texto_limpo = re.sub(r"\s+", " ", texto_limpo)

    return texto_limpo.strip()


def mapear_discurso_senado(
    id_senador: int, discurso_raw: dict, html_bruto: str
) -> dict:
    """
    Mapeia os metadados do Senado para o Data Contract e extrai o texto do HTML bruto.
    Caso o parser não encontre a tag alvo, aciona a Completude Soberana (preservando os metadados).
    """
    texto_bruto = ""
    if html_bruto == "[ERRO DE REDE]":
        texto_bruto = "[ERRO DE REDE]"
    else:
        soup = BeautifulSoup(html_bruto, "html.parser")

        # 1. Estratégia: Múltiplas classes e IDs conhecidos do portal do Senado
        texto_tag = (
            soup.find("div", id="textoIntegral")
            or soup.find("div", class_="texto-integral")
            or soup.find("div", id="textoDiscurso")
            or soup.find("div", class_="texto-pronunciamento")
            or soup.find("div", class_="texto")
        )

        if texto_tag:
            texto_bruto = texto_tag.get_text(separator=" ", strip=True)
        else:
            # 2. Estratégia: Título âncora "Texto integral" e captura do conteúdo adjacente
            cabecalho = soup.find(
                lambda tag: tag.name
                in ["h2", "h3", "h4", "h5", "strong", "b", "span", "div"]
                and "Texto integral" in tag.get_text()
                and len(tag.get_text()) < 30
            )
            if cabecalho:
                paragrafos = [
                    sibling.get_text(separator=" ", strip=True)
                    for sibling in cabecalho.find_next_siblings("p")
                ]
                texto_bruto = " ".join(paragrafos)
                if not texto_bruto:
                    container = cabecalho.find_parent("div")
                    if container:
                        texto_bruto = container.get_text(separator=" ", strip=True)

            # 3. Estratégia de Fallback final: A partir do primeiro parágrafo que inicie com o orador
            if not texto_bruto:
                paragrafos = soup.find_all("p")
                for i, p in enumerate(paragrafos):
                    txt = p.get_text(separator=" ", strip=True)
                    if re.match(
                        r"^(?:O\s+SR\.?|A\s+SRA\.?|O\s+PRESIDENTE|A\s+PRESIDENTE)",
                        txt,
                        re.IGNORECASE,
                    ):
                        texto_bruto = " ".join(
                            tag.get_text(separator=" ", strip=True)
                            for tag in paragrafos[i:]
                        )
                        break

        if texto_bruto:
            texto_bruto = limpar_transcricao_senado(texto_bruto)

        if (
            not texto_bruto
            or len(texto_bruto) < 20
            or "não disponível" in texto_bruto.lower()
        ):
            logger.error(
                f"Falha de Scraping. Texto não encontrado. URL: {discurso_raw.get('UrlTexto')}"
            )
            texto_bruto = "[FALHA NO PARSER HTML]"

    return {
        "id": gerar_id_discurso_senado(
            id_senador, discurso_raw.get("CodigoPronunciamento", "")
        ),
        "politico_id": id_senador,
        "data_discurso": discurso_raw.get("DataPronunciamento"),
        "fase_evento": discurso_raw.get("TipoUsoPalavra", {}).get("Descricao"),
        "sumario": discurso_raw.get("TextoResumo"),
        "texto_bruto": texto_bruto,
        "url_video": None,
    }
