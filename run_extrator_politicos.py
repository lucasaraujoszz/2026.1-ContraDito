import os
from dotenv import load_dotenv
from supabase import create_client, Client
from etl.extrator_politicos_camara import executar_pipeline_completo
from etl.extrator_politicos_senado import executar_pipeline_senadores

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError(
        "As variáveis SUPABASE_URL e SUPABASE_KEY precisam estar definidas no .env"
    )

# Inicializa o cliente do Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

if __name__ == "__main__":
    print("Iniciando extração de deputados...")
    executar_pipeline_completo(supabase)

    print("Extração de deputados finalizada!\n")

    print("Iniciando extração de senadores...")
    executar_pipeline_senadores(supabase)
    print("Extração de senadores finalizada!\n")

    print("Pipeline completo finalizado! Verifique a tabela etl_logs.")
