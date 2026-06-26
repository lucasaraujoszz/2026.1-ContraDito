import os
import sys
import logging
import time

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from supabase import create_client, Client

from etl.vinculador_discursos_votos_senado import executar_pipeline_vinculo_senado
from etl.vinculador_discursos_votos_camara import executar_pipeline_vinculo_camara

logging.Formatter.converter = time.gmtime
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_KEY = os.getenv("QDRANT_KEY")

for var, name in [
    (SUPABASE_URL, "SUPABASE_URL"),
    (SUPABASE_KEY, "SUPABASE_KEY"),
    (QDRANT_URL, "QDRANT_URL"),
    (QDRANT_KEY, "QDRANT_KEY"),
]:
    if not var:
        logging.error(f"{name} precisa estar definida no .env")
        sys.exit(1)

if __name__ == "__main__":
    # Tratamento flexível de argumentos posicionais:
    # python run_vinculo_chunks_votos.py [camara|senado|ambas] [limite] [threshold]
    # Ou mantendo retrocompatibilidade com o formato anterior:
    # python run_vinculo_chunks_votos.py [limite] [threshold]
    casa = "ambas"
    limite = None
    threshold = None

    if len(sys.argv) > 1:
        arg1 = sys.argv[1].lower()
        if arg1 in ["camara", "senado", "ambas"]:
            casa = arg1
            if len(sys.argv) > 2 and sys.argv[2].isdigit():
                limite = int(sys.argv[2])
            if len(sys.argv) > 3:
                try:
                    threshold = float(sys.argv[3])
                except ValueError:
                    pass
        elif arg1.isdigit():
            limite = int(arg1)
            if len(sys.argv) > 2:
                try:
                    threshold = float(sys.argv[2])
                except ValueError:
                    pass
        else:
            logging.error(
                "Uso: python run_vinculo_chunks_votos.py [camara|senado|ambas] [limite] [threshold]"
            )
            sys.exit(1)

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_KEY, timeout=60)

    # Threshold padrão conforme PRD de cada casa
    t_camara = threshold if threshold is not None else 0.72
    t_senado = threshold if threshold is not None else 0.75

    if casa in ["camara", "ambas"]:
        logging.info(
            f"Iniciando pipeline de vínculo de chunks aos votos da Câmara (limite={limite}, threshold={t_camara})..."
        )
        total_c = executar_pipeline_vinculo_camara(
            supabase, qdrant_client, threshold=t_camara, limite_votos=limite
        )
        logging.info(f"Pipeline Câmara finalizado. {total_c} voto(s) processado(s).")

    if casa in ["senado", "ambas"]:
        logging.info(
            f"Iniciando pipeline de vínculo de chunks aos votos do Senado (limite={limite}, threshold={t_senado})..."
        )
        total_s = executar_pipeline_vinculo_senado(
            supabase, qdrant_client, threshold=t_senado, limite_votos=limite
        )
        logging.info(f"Pipeline Senado finalizado. {total_s} voto(s) processado(s).")
