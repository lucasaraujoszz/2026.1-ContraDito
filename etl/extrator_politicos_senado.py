import logging
from datetime import datetime, timezone
from typing import List
from etl.extrator_politicos_camara import _fetch_com_retry

logger = logging.getLogger(__name__)


def extrair_senadores(url: str) -> List[dict]:
    """
    Busca a lista de senadores na API do Senado (forçando JSON), processa os dados
    """
    dados_json = _fetch_com_retry(url, headers={"Accept": "application/json"})
    if not dados_json:
        return []

    lista_parlamentares = (
        dados_json.get("ListaParlamentarLegislatura", {})
        .get("Parlamentares", {})
        .get("Parlamentar", [])
    )

    if isinstance(lista_parlamentares, dict):
        lista_parlamentares = [lista_parlamentares]

    resultados = []
    for senador in lista_parlamentares:
        identificacao = senador.get("IdentificacaoParlamentar", {})
        id_banco = int(identificacao.get("CodigoParlamentar", 0))

        status_mandato = "Inativo"
        eh_suplente = False

        # Navegando pela estrutura de mandatos com segurança contra Dicionários soltos
        mandatos = senador.get("Mandatos", {}).get("Mandato", [])
        if isinstance(mandatos, dict):
            mandatos = [mandatos]

        for mandato in mandatos:
            participacao = mandato.get("DescricaoParticipacao", "")
            if "Suplente" in participacao:
                eh_suplente = True

            exercicios = mandato.get("Exercicios", {}).get("Exercicio", [])
            if isinstance(exercicios, dict):
                exercicios = [exercicios]

            if exercicios:
                for exercicio in exercicios:
                    # A regra de negócio real da API: se não há 'DataFim', o senador está no exercício atual do cargo
                    data_fim = exercicio.get("DataFim")
                    if not data_fim:
                        status_mandato = "Ativo"
                        break  # Achou o atual, interrompe a busca neste mandato

            if status_mandato != "Inativo":
                break  # Se já encontrou um status ativo/suplente, não precisa checar mandatos antigos

        # Se não está em exercício e foi eleito suplente, o status é Suplente (aguardando convocação)
        if status_mandato == "Inativo" and eh_suplente:
            status_mandato = "Suplente"

        resultados.append(
            {
                "id": id_banco,
                "nome_civil": identificacao.get("NomeCompletoParlamentar"),
                "nome_urna": identificacao.get("NomeParlamentar"),
                "partido": identificacao.get("SiglaPartidoParlamentar") or "S/P",
                "estado": identificacao.get("UfParlamentar") or "ND",
                "url_foto": identificacao.get("UrlFotoParlamentar") or "",
                "cargo": "Senador",
                "status_mandato": status_mandato,
                "data_ultima_atualizacao": datetime.now(timezone.utc).isoformat(),
            }
        )

        print(
            f"Senador extraído com sucesso: {identificacao.get('NomeParlamentar')} ({identificacao.get('SiglaPartidoParlamentar')}-{identificacao.get('UfParlamentar')})"
        )

    return resultados


def executar_pipeline_senadores(supabase_client) -> None:
    """
    Orquestra a extração dos senadores, realiza o envio em lote ao Supabase e registra o log.
    """
    data_inicio = datetime.now(timezone.utc).isoformat()
    url = "https://legis.senado.leg.br/dadosabertos/senador/lista/legislatura/57.json"
    total_linhas = 0

    try:
        resultados = extrair_senadores(url)
        if resultados:
            supabase_client.table("senado_politicos").upsert(resultados).execute()
            total_linhas = len(resultados)
            print(f"Lote de {total_linhas} senadores enviado ao Supabase com sucesso.")

        status = "Concluído"
        detalhe_erro = None
    except Exception as e:
        status = "Erro"
        detalhe_erro = str(e)
        logger.error(f"Erro crítico no pipeline do Senado: {e}")

    data_fim = datetime.now(timezone.utc).isoformat()

    supabase_client.table("etl_logs").insert(
        {
            "nome_rotina": "extrator_politicos_senado",
            "data_inicio": data_inicio,
            "data_fim": data_fim,
            "status": status,
            "detalhe_erro": detalhe_erro,
            "linhas_afetadas": total_linhas,
        }
    ).execute()
