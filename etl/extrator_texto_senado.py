import io
import logging
import httpx
import pdfplumber
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

logger = logging.getLogger(__name__)


def _is_transient_error(exception: BaseException) -> bool:
    """Avalia se a exceção é transitória (rede, rate limit, instabilidade do Senado)."""
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in (429, 500, 502, 503, 504)
    if isinstance(exception, httpx.RequestError):
        return True
    return False


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception(_is_transient_error),
    reraise=True,
)
async def extrair_texto_senado(url: str, client: httpx.AsyncClient) -> str:
    """
    Baixa o PDF do Senado e extrai o texto, truncando rigidamente
    em 100.000 caracteres para proteção de memória da LLM.
    """
    response = await client.get(url, timeout=60.0)
    response.raise_for_status()

    texto_extraido = []
    try:
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            for page in pdf.pages:
                texto = page.extract_text()
                if texto:
                    texto_extraido.append(texto)
    except Exception as e:
        logger.warning(
            f"Erro permanente ao tentar parsear o PDF do Senado ({url}): {e}"
        )
        return ""

    texto_final = "\n".join(texto_extraido)
    return texto_final[:100000]
