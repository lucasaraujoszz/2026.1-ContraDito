import os
import logging
import time
import sys
import asyncio
from dotenv import load_dotenv
from supabase import create_client, Client

from etl.extrator_votos_camara import executar_pipeline_votos_camara
from etl.extrator_votos_senado import executar_pipeline_votos_senado

# Força o logger do terminal a exibir o horário em UTC (Internacional)
logging.Formatter.converter = time.gmtime
# Configuração básica de log para vermos o progresso no terminal
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Carrega as variáveis do .env (SUPABASE_URL e SUPABASE_KEY)
load_dotenv()

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")

if not url or not key:
    raise ValueError(
        "Variáveis SUPABASE_URL e SUPABASE_KEY não encontradas no ambiente."
    )

supabase: Client = create_client(url, key)


async def main():
    # Permite passar um limite via linha de comando para testes. Ex: python run_extrator_votos.py 10
    limite = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else None
    msg_limite = f" (Amostra de {limite} registros)" if limite else " (Carga Completa)"

    logging.info(f"Iniciando extração de votos nominais da Câmara{msg_limite}...")
    await executar_pipeline_votos_camara(supabase, limite_amostral=limite)

    logging.info(f"Iniciando extração de votos nominais do Senado{msg_limite}...")
    await executar_pipeline_votos_senado(supabase, limite_amostral=limite)


if __name__ == "__main__":
    asyncio.run(main())
    logging.info(
        "Extração de Votos do Congresso Nacional finalizada! Verifique as tabelas de votos e 'etl_logs' no Supabase."
    )
