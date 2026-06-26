import os
import sys
import logging
import time
import argparse
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer
from etl.chunker_discursos_camara import executar_pipeline_chunking
from etl.chunker_discursos_senado import executar_pipeline_chunking_senado

logging.Formatter.converter = time.gmtime
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_KEY = os.getenv("QDRANT_KEY")

for var, nome in [
    (SUPABASE_URL, "SUPABASE_URL"),
    (SUPABASE_KEY, "SUPABASE_KEY"),
    (QDRANT_URL, "QDRANT_URL"),
    (QDRANT_KEY, "QDRANT_KEY"),
]:
    if not var:
        logging.error(f"{nome} precisa estar definida no .env")
        sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_KEY, timeout=60)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Chunking e vetorização de discursos (Câmara e Senado)."
    )
    parser.add_argument(
        "--casa",
        type=str,
        choices=["camara", "senado", "ambas"],
        default="ambas",
        help="Qual casa processar.",
    )
    parser.add_argument(
        "--chunk_size",
        type=int,
        default=1000,
        help="Tamanho máximo de cada chunk em caracteres.",
    )
    parser.add_argument(
        "--overlap",
        type=int,
        default=200,
        help="Sobreposição entre chunks consecutivos em caracteres.",
    )
    parser.add_argument(
        "--limite", type=int, default=None, help="Processar no máximo N discursos."
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    logging.info(
        f"Carregando modelo BAAI/bge-m3 (chunk_size={args.chunk_size}, overlap={args.overlap})..."
    )
    modelo = SentenceTransformer("BAAI/bge-m3")
    logging.info("Iniciando pipeline de chunking incremental...")

    inicio = time.time()
    total_camara = 0
    total_senado = 0

    if args.casa in ["camara", "ambas"]:
        logging.info("--- Processando discursos da Câmara ---")
        total_camara = executar_pipeline_chunking(
            supabase=supabase,
            modelo=modelo,
            qdrant_client=qdrant_client,
            chunk_size=args.chunk_size,
            chunk_overlap=args.overlap,
            limite=args.limite,
        )

    if args.casa in ["senado", "ambas"]:
        logging.info("--- Processando discursos do Senado (Dual-Write) ---")
        total_senado = executar_pipeline_chunking_senado(
            supabase_client=supabase,
            qdrant_client=qdrant_client,
            modelo=modelo,
            chunk_size=args.chunk_size,
            chunk_overlap=args.overlap,
            limite=args.limite,
        )

    fim = time.time()
    total = total_camara + total_senado
    logging.info(
        f"Pipeline geral finalizado: {total} chunk(s) processado(s) em {fim - inicio:.1f}s."
    )
