import os
import httpx
import asyncio
from dotenv import load_dotenv
from supabase import create_client, Client
from tenacity import retry, wait_exponential, stop_after_attempt

load_dotenv()

URL_BANCO = os.environ.get("SUPABASE_URL")
CHAVE_BANCO = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(URL_BANCO, CHAVE_BANCO)


@retry(wait=wait_exponential(multiplier=2, min=2, max=15), stop=stop_after_attempt(5))
async def fetch_dados_governo(url: str):
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()


async def executar_pipeline_etl(ano: int, tipo_lei: str):
    url_base = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes?ano={ano}&siglaTipo={tipo_lei}"

    try:
        dados_leis = await fetch_dados_governo(url_base)

        for lei in dados_leis.get("dados", []):
            id_lei = lei.get("id")
            ementa_lei = lei.get("ementa")

            url_votacoes = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes/{id_lei}/votacoes"
            dados_votacoes = await fetch_dados_governo(url_votacoes)

            if not dados_votacoes.get("dados"):
                continue

            for votacao in dados_votacoes.get("dados", []):
                id_votacao = votacao.get("id")

                raw_data = votacao.get("data") or votacao.get("dataHoraRegistro")
                data_evento = raw_data.split("T")[0] if raw_data else f"{ano}-01-01"

                url_votos = f"https://dadosabertos.camara.leg.br/api/v2/votacoes/{id_votacao}/votos"
                dados_votos = await fetch_dados_governo(url_votos)

                if not dados_votos.get("dados"):
                    continue

                for voto in dados_votos.get("dados", []):
                    parlamentar = voto.get("deputado_", {})

                    registro_voto = {
                        "politico_id": parlamentar.get("id"),
                        "tipo_documento": "Voto",
                        "voto_oficial": voto.get("tipoVoto"),
                        "ementa": ementa_lei,
                        "texto_extraido": ementa_lei,
                        "data_evento": data_evento,
                    }

                    try:
                        supabase.table("provas_contradicao").insert(
                            registro_voto
                        ).execute()
                        print(
                            f"✅ Salvo no banco: ID {registro_voto['politico_id']} | Voto: {registro_voto['voto_oficial']}"
                        )
                    except Exception as erro_banco:
                        print(
                            f"❌ Erro ao salvar o voto no ID {registro_voto['politico_id']}: {erro_banco}"
                        )

    except Exception as erro:
        print(f"Erro na execução do pipeline: {erro}")


async def main():
    tipos = ["PL", "PEC"]
    for tipo in tipos:
        await executar_pipeline_etl(2023, tipo)


if __name__ == "__main__":
    asyncio.run(main())
