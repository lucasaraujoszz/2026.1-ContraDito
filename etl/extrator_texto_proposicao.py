import io
import logging

import httpx
import pdfplumber
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


def _is_transient_error(exception: BaseException) -> bool:
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in (429, 500, 502, 503, 504)
    if isinstance(exception, httpx.RequestError):
        return True
    return False


def _extrair_texto_de_bytes(pdf_bytes: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            partes = [page.extract_text() for page in pdf.pages if page.extract_text()]
            return "\n\n".join(partes)
    except Exception as e:
        logger.warning(f"Falha ao parsear PDF: {e}")
        return ""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception(_is_transient_error),
    reraise=True,
)
async def extrair_texto_de_url(url: str, client: httpx.AsyncClient) -> str:
    """
    Baixa o PDF apontado pela URL e retorna o texto extraído.
    Retorna string vazia se o PDF não contiver texto selecionável.
    Levanta HTTPStatusError em caso de 404 ou falha permanente.
    """
    response = await client.get(url, timeout=60.0)
    response.raise_for_status()
    return _extrair_texto_de_bytes(response.content)[:100_000]
