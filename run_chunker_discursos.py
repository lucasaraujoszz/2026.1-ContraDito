import os
import sys
import logging
import time
import argparse
from dotenv import load_dotenv
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer

from etl.chunker_discursos_camara import executar_pipeline_chunking

logging.Formatter.converter = time.gmtime
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    raise ValueError("Variáveis SUPABASE_URL e SUPABASE_KEY não encontradas no ambiente.")

supabase: Client = create_client(url, key)


def parse_args():
    parser = argparse.ArgumentParser(description="Chunking e vetorização de discursos da Câmara.")
    parser.add_argument("--chunk_size", type=int, default=1000, help="Tamanho máximo de cada chunk em caracteres.")
    parser.add_argument("--overlap", type=int, default=200, help="Sobreposição entre chunks consecutivos em caracteres.")
    parser.add_argument("--limite", type=int, default=None, help="Processar no máximo N discursos (útil para testes).")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    logging.info(f"Carregando modelo BAAI/bge-m3 (chunk_size={args.chunk_size}, overlap={args.overlap})...")
    modelo = SentenceTransformer("BAAI/bge-m3")

    logging.info("Iniciando pipeline de chunking incremental...")
    inicio = time.time()

    total = executar_pipeline_chunking(
        supabase=supabase,
        modelo=modelo,
        chunk_size=args.chunk_size,
        chunk_overlap=args.overlap,
        limite=args.limite,
    )

    fim = time.time()
    logging.info(f"Pipeline finalizado: {total} chunk(s) inserido(s) em {fim - inicio:.1f}s.")
