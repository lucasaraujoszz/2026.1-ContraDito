import os
import sys
import asyncio
import logging
import time

from dotenv import load_dotenv
from groq import Groq
from supabase import create_client, Client

from etl.pipeline_inferencia import executar_pipeline_inferencia

logging.Formatter.converter = time.gmtime
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    logging.error("SUPABASE_URL e SUPABASE_KEY precisam estar definidas.")
    sys.exit(1)

if not GROQ_API_KEY:
    logging.error("GROQ_API_KEY precisa estar definida.")
    sys.exit(1)

if __name__ == "__main__":
    limite = int(sys.argv[1]) if len(sys.argv) > 1 else None

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    groq_client = Groq(api_key=GROQ_API_KEY)

    logging.info(f"Iniciando pipeline de inferência de postura (limite={limite})...")
    total = asyncio.run(
        executar_pipeline_inferencia(supabase, groq_client, limite=limite)
    )
    logging.info(f"Pipeline finalizado. {total} voto(s) processado(s).")
