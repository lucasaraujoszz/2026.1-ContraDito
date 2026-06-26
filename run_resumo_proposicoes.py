import os
import sys
import asyncio
import logging
import time
import argparse
from dotenv import load_dotenv
from google import genai
from qdrant_client import QdrantClient
from supabase import create_client, Client
from etl.pipeline_resumo_proposicoes import executar_pipeline_resumo
from etl.pipeline_resumo_senado import executar_pipeline_resumo_senado
from utils.motor_nlp import MotorNLP

logging.Formatter.converter = time.gmtime
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    logging.error("SUPABASE_URL e SUPABASE_KEY precisam estar definidas.")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def obter_qdrant_client() -> QdrantClient:
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_key = os.getenv("QDRANT_KEY")
    if not qdrant_url or not qdrant_key:
        logging.error(
            "QDRANT_URL e QDRANT_KEY precisam estar definidas para processar o Senado."
        )
        sys.exit(1)
    return QdrantClient(url=qdrant_url, api_key=qdrant_key, timeout=60)


async def main():
    parser = argparse.ArgumentParser(
        description="Pipeline de Resumo e Vetorização de Proposições"
    )
    parser.add_argument(
        "--casa",
        type=str,
        choices=["camara", "senado", "ambas"],
        default="ambas",
        help="Qual casa processar.",
    )
    parser.add_argument(
        "--limite",
        type=int,
        default=None,
        help="Limite máximo de proposições a processar por Casa.",
    )
    args = parser.parse_args()

    logging.info("Carregando pesos do Motor SBERT (BAAI/bge-m3)...")
    motor_nlp = MotorNLP()

    total_camara = 0
    total_senado = 0

    if args.casa in ["camara", "ambas"]:
        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key:
            logging.error(
                "GEMINI_API_KEY precisa estar definida para processar a Câmara."
            )
            sys.exit(1)
        gemini_client = genai.Client(api_key=gemini_key)
        qdrant_client = obter_qdrant_client()
        logging.info(f"--- Iniciando pipeline da Câmara (limite={args.limite}) ---")
        total_camara = await executar_pipeline_resumo(
            supabase, motor_nlp, gemini_client, qdrant_client, limite=args.limite
        )

    if args.casa in ["senado", "ambas"]:
        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key:
            logging.error(
                "GEMINI_API_KEY precisa estar definida para processar o Senado."
            )
            sys.exit(1)

        gemini_client = genai.Client(api_key=gemini_key)
        qdrant_client = obter_qdrant_client()
        logging.info(
            f"--- Iniciando pipeline do Senado [Dual-Write] (limite={args.limite}) ---"
        )
        total_senado = await executar_pipeline_resumo_senado(
            supabase_client=supabase,
            qdrant_client=qdrant_client,
            motor_nlp=motor_nlp,
            gemini_client=gemini_client,
            limite=args.limite,
        )

    logging.info(
        f"Pipelines finalizados! Câmara: {total_camara} | Senado: {total_senado} proposições processadas."
    )


if __name__ == "__main__":
    asyncio.run(main())
