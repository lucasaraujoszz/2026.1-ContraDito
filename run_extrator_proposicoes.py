import os
import logging
import time
import sys
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from supabase import create_client, Client

from etl.extrator_proposicoes_camara import (
    executar_pipeline_completo as executar_pipeline_camara,
)
from etl.extrator_proposicoes_senado import (
    executar_pipeline_completo as executar_pipeline_senado,
)

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
    data_inicio = sys.argv[1] if len(sys.argv) > 1 else "2023-01-01"
    data_fim = (
        sys.argv[2]
        if len(sys.argv) > 2
        else (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    )

    logging.info(
        f"Iniciando extração histórica de proposições da Câmara ({data_inicio} a {data_fim})..."
    )
    await executar_pipeline_camara(supabase, data_inicio, data_fim)

    logging.info(
        f"Iniciando extração histórica de proposições do Senado ({data_inicio} a {data_fim})..."
    )
    await executar_pipeline_senado(supabase, data_inicio, data_fim)

    logging.info(
        "Extração do Congresso Nacional finalizada! Verifique as tabelas de proposição e 'etl_logs' no Supabase."
    )


if __name__ == "__main__":
    asyncio.run(main())
