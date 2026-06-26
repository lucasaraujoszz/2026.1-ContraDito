import asyncio
import json
import logging
import re

from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

_MODEL = "gemini-2.5-flash-lite"

_VOTOS_INVALIDOS = {"AUSENTE", "ABSTENÇÃO", "NÃO COMPARECEU", "ART. 17", "OBSTRUÇÃO"}

_PROMPT = """\
Você é um analista político especializado em coerência legislativa brasileira.

Com base nos trechos de discursos do parlamentar abaixo, determine qual seria \
a postura ESPERADA dele em relação à proposição legislativa descrita.

PROPOSIÇÃO:
{resumo}

DISCURSOS DO PARLAMENTAR (trechos mais relevantes):
{chunks}

Analise se os discursos indicam que o parlamentar deveria ser FAVORÁVEL ou CONTRÁRIO \
à proposição. Responda APENAS em JSON válido, sem nenhum texto adicional:
{{
  "postura": "FAVORÁVEL" ou "CONTRÁRIO",
  "justificativa": "Explicação objetiva em 2-3 frases baseada nos discursos acima."
}}"""

_CONFIG = types.GenerateContentConfig(temperature=0.1)


def _parsear_json(texto: str) -> dict:
    match = re.search(r"\{.*?\}", texto, re.DOTALL)
    if not match:
        raise ValueError(f"JSON não encontrado na resposta do LLM: {texto[:200]}")
    return json.loads(match.group())


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _chamar_gemini(gemini_client: genai.Client, resumo: str, chunks_texto: str) -> dict:
    prompt = _PROMPT.format(resumo=resumo, chunks=chunks_texto)
    response = gemini_client.models.generate_content(
        model=_MODEL,
        contents=prompt,
        config=_CONFIG,
    )
    return _parsear_json(response.text)


async def inferir_postura(
    resumo_proposicao: str,
    chunks: list[str],
    gemini_client: genai.Client,
) -> dict | None:
    """
    Infere a postura esperada do parlamentar (FAVORÁVEL/CONTRÁRIO) com base
    nos chunks de discursos e no resumo da proposição.
    Retorna None se não houver chunks disponíveis.
    """
    if not chunks:
        return None

    chunks_texto = "\n\n---\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(chunks))
    return await asyncio.to_thread(
        _chamar_gemini, gemini_client, resumo_proposicao, chunks_texto
    )


def calcular_coerencia(voto_oficial: str, postura_inferida: str) -> bool | None:
    """
    Compara o voto real com a postura inferida pelo LLM.
    Retorna None para votos que não entram no denominador (RF27).
    """
    voto = voto_oficial.strip().upper()
    if voto in _VOTOS_INVALIDOS:
        return None

    postura = postura_inferida.strip().upper()
    if voto == "SIM":
        return postura == "FAVORÁVEL"
    if voto == "NÃO":
        return postura == "CONTRÁRIO"
    return None
