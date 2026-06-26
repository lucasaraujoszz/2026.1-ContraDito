import asyncio
import logging

from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

_MODEL = "gemini-2.5-flash-lite"

_SYSTEM = (
    "Você responde APENAS com o texto puro do resumo, em português, sem títulos, "
    "sem markdown, sem negrito, sem listas, sem numeração, sem qualquer formatação. "
    "Somente parágrafos em texto corrido."
)

_PROMPT = """\
Você é um assistente especializado em resumir proposições legislativas brasileiras.

Crie um RESUMO EXECUTIVO em no máximo 400 tokens contendo:
1. O que a proposição propõe (objetivo principal)
2. Principais obrigações criadas
3. Argumentos centrais da justificativa

Regras:
• Linguagem objetiva, sem opiniões pessoais, preservar o núcleo temático.
• Escreva o resumo APENAS em parágrafos de texto corrido (prosa).
• É ESTRITAMENTE PROIBIDO o uso de tópicos, marcadores (bullet points), negrito, asteriscos ou cabeçalhos com cerquilha.

PROPOSIÇÃO:
{texto}

RESUMO EXECUTIVO:"""

_CONFIG = types.GenerateContentConfig(
    system_instruction=_SYSTEM,
    temperature=0.3,
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
    ],
)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)
def _chamar_gemini(gemini_client: genai.Client, prompt: str) -> str:
    response = gemini_client.models.generate_content(
        model=_MODEL,
        contents=prompt,
        config=_CONFIG,
    )
    return response.text.strip()


async def gerar_resumo_executivo(texto: str, gemini_client: genai.Client) -> str:
    """
    Gera um resumo executivo via Gemini Flash.
    Envia o texto completo truncado em 100.000 caracteres para chamada única ao Gemini.
    Retorna string vazia se o texto de entrada for vazio.
    """
    if not texto or not texto.strip():
        return ""

    texto_truncado = texto[:100_000]
    return await asyncio.to_thread(
        _chamar_gemini, gemini_client, _PROMPT.format(texto=texto_truncado)
    )


def criar_cliente_gemini(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key)
