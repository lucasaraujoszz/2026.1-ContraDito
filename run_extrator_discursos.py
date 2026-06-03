import os
import logging
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from supabase import create_client, Client

from etl.extrator_discursos_camara import executar_pipeline_completo as executar_pipeline_camara
from etl.extrator_discursos_senado import executar_pipeline_completo as executar_pipeline_senado

# Força o logger do terminal a exibir o horário em UTC (Internacional)
logging.Formatter.converter = time.gmtime
# Configuração básica de log para vermos o progresso no terminal
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Carrega as variáveis do .env (SUPABASE_URL e SUPABASEKEY)
load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    raise ValueError("Variáveis SUPABASE_URL e SUPABASEKEY não encontradas no ambiente.")

supabase: Client = create_client(url, key)

if __name__ == "__main__":
    data_inicio = "2023-01-01"
    data_fim = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    logging.info(f"Iniciando extração histórica de discursos da Câmara ({data_inicio} a {data_fim})...")
    executar_pipeline_camara(supabase, data_inicio, data_fim)
    
    logging.info(f"Iniciando extração histórica de discursos do Senado ({data_inicio} a {data_fim})...")
    executar_pipeline_senado(supabase, data_inicio, data_fim)
    
    logging.info("Extração do Congresso Nacional finalizada! Verifique as tabelas de discursos e 'etl_logs' no Supabase.")