import asyncio
import logging

from groq import Groq
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

_PROMPT = """\
Você é um assistente especializado em resumir proposições legislativas brasileiras.

Crie um RESUMO EXECUTIVO em no máximo 400 tokens contendo:
1. O que a proposição propõe (objetivo principal)
2. Principais obrigações criadas
3. Argumentos centrais da justificativa

Regras: linguagem objetiva, sem opiniões pessoais, preservar o núcleo temático.

PROPOSIÇÃO:
{texto}

RESUMO EXECUTIVO:"""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _chamar_groq(groq_client: Groq, texto: str) -> str:
    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": _PROMPT.format(texto=texto)}],
        temperature=0.3,
        max_tokens=500,
    )
    return response.choices[0].message.content.strip()


async def gerar_resumo_executivo(texto: str, groq_client: Groq) -> str:
    """
    Gera um resumo executivo do texto via Groq (llama-3.1-8b-instant).
    Retorna string vazia se o texto de entrada for vazio.
    """
    if not texto or not texto.strip():
        return ""
    return await asyncio.to_thread(_chamar_groq, groq_client, texto)
