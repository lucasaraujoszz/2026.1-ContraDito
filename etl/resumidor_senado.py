import asyncio
import logging
from tenacity import retry, stop_after_attempt, wait_exponential
from google.genai import types

logger = logging.getLogger(__name__)

_PROMPT = """\
Você é um assistente especializado em resumir proposições legislativas brasileiras.

Crie um RESUMO EXECUTIVO em no máximo 400 tokens contendo:
1. O que a proposição propõe (objetivo principal)
2. Principais obrigações criadas
3. Argumentos centrais da justificativa

Regras:
- Linguagem objetiva, sem opiniões pessoais, preservar o núcleo temático.
- Escreva o resumo APENAS em parágrafos de texto corrido (prosa).
- É ESTRITAMENTE PROIBIDO o uso de tópicos, marcadores (bullet points), negrito, asteriscos ou cabeçalhos com cerquilha.

PROPOSIÇÃO:
{texto}

RESUMO EXECUTIVO:"""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _chamar_gemini(client, texto: str) -> str:
    config = types.GenerateContentConfig(
        safety_settings=[
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
        ]
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=_PROMPT.format(texto=texto),
        config=config,
    )

    return response.text


async def gerar_resumo_executivo_senado(texto: str, client) -> str:
    """
    Gera um resumo executivo do texto via Gemini 2.5 Flash Lite.
    Retorna string vazia se o texto de entrada for vazio.
    """
    if not texto or not texto.strip():
        return ""

    return await asyncio.to_thread(_chamar_gemini, client, texto)
