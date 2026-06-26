import os
import sys
import asyncio
import logging
import time

from dotenv import load_dotenv
from google import genai
from qdrant_client import QdrantClient
from supabase import create_client, Client

from etl.pipeline_inferencia import executar_pipeline_inferencia

logging.Formatter.converter = time.gmtime
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

for var, nome in [
    (SUPABASE_URL, "SUPABASE_URL"),
    (SUPABASE_KEY, "SUPABASE_KEY"),
    (GEMINI_API_KEY, "GEMINI_API_KEY"),
    (QDRANT_URL, "QDRANT_URL"),
    (QDRANT_API_KEY, "QDRANT_API_KEY"),
]:
    if not var:
        logging.error(f"{nome} precisa estar definida no .env")
        sys.exit(1)

if __name__ == "__main__":
    limite = int(sys.argv[1]) if len(sys.argv) > 1 else None

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=60)

    logging.info(f"Iniciando pipeline de inferência de postura (limite={limite})...")
    total = asyncio.run(
        executar_pipeline_inferencia(
            supabase, gemini_client, qdrant_client, limite=limite
        )
    )
    logging.info(f"Pipeline finalizado. {total} voto(s) processado(s).")
