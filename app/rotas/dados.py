import math
from fastapi import APIRouter, Query, HTTPException, Path
from typing import Optional
from app.bancos.supabase import supabase
from fastapi_cache.decorator import cache
from app.modelos.schemas import (
    PaginaPoliticosDB,
    PoliticoDetalhadoDB,
    PaginaDiscursosDB,
    DiscursoChunkDB,
    PaginaProposicoesDB,
    ProposicaoDB,
    PaginaVotosDB,
    VotoTimelineSchema,
    ComparacaoResponse,
    AfinidadesResponse,
    FidelidadeResponse,
    PolarizacaoResponse,
    CoesaoGeralResponse,
    DiscursoDB,
)

router = APIRouter(prefix="/api", tags=["Dados Gerais"])

VALID_CASES = ["camara", "senado"]


def validar_casa(casa: str) -> str:
    casa_clean = casa.strip().lower()
    if casa_clean not in VALID_CASES:
        raise HTTPException(
            status_code=400, detail="Casa inválida. Deve ser 'camara' ou 'senado'."
        )
    return casa_clean


@router.get(
    "/{casa}/politicos",
    response_model=PaginaPoliticosDB,
    summary="Listar e Filtrar Políticos por Casa",
    description="Retorna a listagem paginada de parlamentares (Câmara ou Senado) com filtros por nome, partido e estado.",
)
@cache(expire=3600)
def listar_politicos(
    casa: str = Path(..., description="Casa legislativa ('camara' ou 'senado')"),
    busca: Optional[str] = Query(None, description="Busca por nome de urna"),
    partido: Optional[str] = Query(None, description="Filtro por partido"),
    estado: Optional[str] = Query(
        None, min_length=2, max_length=2, description="Filtro por Estado/UF"
    ),
    pagina: int = Query(1, ge=1, description="Número da página"),
    tamanho: int = Query(
        20, ge=1, le=100, description="Quantidade de itens por página"
    ),
):
    casa_clean = validar_casa(casa)
    tabela = f"{casa_clean}_politicos"

    try:
        query = supabase.table(tabela).select("*", count="exact")

        if busca:
            query = query.ilike("nome_urna", f"%{busca}%")
        if partido:
            query = query.eq("partido", partido.upper())
        if estado:
            query = query.eq("estado", estado.upper())

        # Ordenação padrão
        query = query.order("nome_urna", desc=False)

        inicio = (pagina - 1) * tamanho
        fim = inicio + tamanho - 1
        query = query.range(inicio, fim)

        resultado = query.execute()

        total_registros = resultado.count if resultado.count is not None else 0
        total_paginas = (
            math.ceil(total_registros / tamanho) if total_registros > 0 else 0
        )

        return {
            "total_registros": total_registros,
            "pagina_atual": pagina,
            "tamanho_pagina": tamanho,
            "total_paginas": total_paginas,
            "itens": resultado.data,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro interno ao buscar políticos: {str(e)}"
        )


@router.get(
    "/{casa}/politicos/{id_parlamentar}",
    response_model=PoliticoDetalhadoDB,
    summary="Obter Perfil Detalhado por Casa",
    description="Retorna os dados cadastrais de um político específico junto com o seu resumo de votos consolidado.",
    responses={
        404: {"description": "Político não encontrado na base de dados."},
    },
)
def obter_politico_detalhado(
    casa: str = Path(..., description="Casa legislativa ('camara' ou 'senado')"),
    id_parlamentar: int = Path(..., description="ID interno do político"),
):
    casa_clean = validar_casa(casa)
    tabela_politico = f"{casa_clean}_politicos"

    try:
        # 1. Busca os dados cadastrais do político
        res_politico = (
            supabase.table(tabela_politico)
            .select("*")
            .eq("id", id_parlamentar)
            .execute()
        )

        if not res_politico.data:
            raise HTTPException(status_code=404, detail="Político não encontrado")

        politico_data = res_politico.data[0]

        # 2. Busca o resumo de votos na tabela consolidada
        res_resumo = (
            supabase.table("politico_resumo_votos")
            .select("*")
            .eq("politico_id", id_parlamentar)
            .eq("casa", casa_clean.upper())
            .execute()
        )

        resumo_data = res_resumo.data[0] if res_resumo.data else None

        return {"politico": politico_data, "resumo_votos": resumo_data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro interno ao buscar perfil detalhado: {str(e)}"
        )


@router.get(
    "/{casa}/discursos",
    response_model=PaginaDiscursosDB,
    summary="Listar Discursos",
    description="Retorna a listagem paginada dos discursos (Câmara ou Senado) com filtro opcional por parlamentar.",
)
@cache(expire=3600)
def listar_discursos(
    casa: str = Path(..., description="Casa legislativa ('camara' ou 'senado')"),
    politico_id: Optional[int] = Query(
        None, description="ID do político para filtrar discursos"
    ),
    pagina: int = Query(1, ge=1, description="Número da página"),
    tamanho: int = Query(
        20, ge=1, le=100, description="Quantidade de itens por página"
    ),
):
    casa_clean = validar_casa(casa)
    tabela = f"{casa_clean}_discursos"

    try:
        query = supabase.table(tabela).select("*", count="exact")

        if politico_id:
            query = query.eq("politico_id", politico_id)

        query = query.order("data_discurso", desc=True)

        inicio = (pagina - 1) * tamanho
        fim = inicio + tamanho - 1
        query = query.range(inicio, fim)

        resultado = query.execute()

        total_registros = resultado.count if resultado.count is not None else 0
        total_paginas = (
            math.ceil(total_registros / tamanho) if total_registros > 0 else 0
        )

        return {
            "total_registros": total_registros,
            "pagina_atual": pagina,
            "tamanho_pagina": tamanho,
            "total_paginas": total_paginas,
            "itens": resultado.data,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro ao buscar discursos: {str(e)}"
        )


@router.get(
    "/{casa}/politicos/{id_parlamentar}/discursos",
    response_model=PaginaDiscursosDB,
    summary="Listar Discursos de um Político",
    description="Retorna a listagem paginada dos discursos salvos de um parlamentar específico.",
)
@cache(expire=3600)
def listar_discursos_politico(
    casa: str = Path(..., description="Casa legislativa ('camara' ou 'senado')"),
    id_parlamentar: int = Path(..., description="ID interno do político"),
    pagina: int = Query(1, ge=1, description="Número da página"),
    tamanho: int = Query(
        20, ge=1, le=100, description="Quantidade de itens por página"
    ),
):
    casa_clean = validar_casa(casa)
    tabela_politico = f"{casa_clean}_politicos"

    try:
        res_politico = (
            supabase.table(tabela_politico)
            .select("id")
            .eq("id", id_parlamentar)
            .execute()
        )
        if not res_politico.data:
            raise HTTPException(status_code=404, detail="Político não encontrado")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao verificar existência do político: {str(e)}",
        )

    tabela = f"{casa_clean}_discursos"
    try:
        query = (
            supabase.table(tabela)
            .select("*", count="exact")
            .eq("politico_id", id_parlamentar)
        )
        query = query.order("data_discurso", desc=True)

        inicio = (pagina - 1) * tamanho
        fim = inicio + tamanho - 1
        query = query.range(inicio, fim)

        resultado = query.execute()

        total_registros = resultado.count if resultado.count is not None else 0
        total_paginas = (
            math.ceil(total_registros / tamanho) if total_registros > 0 else 0
        )

        return {
            "total_registros": total_registros,
            "pagina_atual": pagina,
            "tamanho_pagina": tamanho,
            "total_paginas": total_paginas,
            "itens": resultado.data,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro ao buscar discursos do político: {str(e)}"
        )


@router.get(
    "/{casa}/discursos/{discurso_id}/chunks",
    response_model=list[DiscursoChunkDB],
    summary="Obter Chunks do Discurso",
    description="Retorna a listagem completa dos fragmentos (chunks) de um discurso específico.",
)
def obter_chunks_discurso(
    casa: str = Path(..., description="Casa legislativa ('camara' ou 'senado')"),
    discurso_id: str = Path(..., description="ID do discurso (UUID)"),
):
    casa_clean = validar_casa(casa)
    tabela = f"{casa_clean}_discurso_chunks"

    try:
        resultado = (
            supabase.table(tabela).select("*").eq("discurso_id", discurso_id).execute()
        )
        return resultado.data
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro ao buscar chunks do discurso: {str(e)}"
        )


@router.get(
    "/{casa}/proposicoes",
    response_model=PaginaProposicoesDB,
    summary="Listar Proposições",
    description="Retorna a listagem paginada das proposições (Câmara ou Senado) com filtros por ano e tipo.",
)
@cache(expire=3600)
def listar_proposicoes(
    casa: str = Path(..., description="Casa legislativa ('camara' ou 'senado')"),
    ano: Optional[int] = Query(None, description="Filtro por ano da proposição"),
    tipo: Optional[str] = Query(
        None, description="Filtro por tipo de proposição (ex: PL, PEC)"
    ),
    pagina: int = Query(1, ge=1, description="Número da página"),
    tamanho: int = Query(
        20, ge=1, le=100, description="Quantidade de itens por página"
    ),
):
    casa_clean = validar_casa(casa)
    tabela = f"{casa_clean}_proposicoes"

    try:
        query = supabase.table(tabela).select("*", count="exact")

        if ano:
            query = query.eq("ano", ano)
        if tipo:
            query = query.eq("tipo", tipo.upper())

        query = query.order("data_votacao", desc=True)

        inicio = (pagina - 1) * tamanho
        fim = inicio + tamanho - 1
        query = query.range(inicio, fim)

        resultado = query.execute()

        total_registros = resultado.count if resultado.count is not None else 0
        total_paginas = (
            math.ceil(total_registros / tamanho) if total_registros > 0 else 0
        )

        return {
            "total_registros": total_registros,
            "pagina_atual": pagina,
            "tamanho_pagina": tamanho,
            "total_paginas": total_paginas,
            "itens": resultado.data,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro ao buscar proposições: {str(e)}"
        )


@router.get(
    "/{casa}/proposicoes/{id_proposicao}",
    response_model=ProposicaoDB,
    summary="Obter Detalhes da Proposição",
    description="Retorna os detalhes de uma proposição específica pelo seu ID (UUID).",
    responses={
        404: {"description": "Proposição não encontrada."},
    },
)
def obter_proposicao_detalhada(
    casa: str = Path(..., description="Casa legislativa ('camara' ou 'senado')"),
    id_proposicao: str = Path(..., description="ID interno da proposição (UUID)"),
):
    casa_clean = validar_casa(casa)
    tabela = f"{casa_clean}_proposicoes"

    try:
        resultado = supabase.table(tabela).select("*").eq("id", id_proposicao).execute()

        if not resultado.data:
            raise HTTPException(status_code=404, detail="Proposição não encontrada")

        return resultado.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro ao buscar proposição: {str(e)}"
        )


@router.get(
    "/{casa}/votos",
    response_model=PaginaVotosDB,
    summary="Listar Votos",
    description="Retorna a listagem paginada de votos (Câmara ou Senado) com filtros por político e proposição.",
)
@cache(expire=3600)
def listar_votos(
    casa: str = Path(..., description="Casa legislativa ('camara' ou 'senado')"),
    politico_id: Optional[int] = Query(None, description="Filtro por ID do político"),
    proposicao_id: Optional[str] = Query(
        None, description="Filtro por ID da proposição (código de texto)"
    ),
    pagina: int = Query(1, ge=1, description="Número da página"),
    tamanho: int = Query(
        20, ge=1, le=100, description="Quantidade de itens por página"
    ),
):
    casa_clean = validar_casa(casa)
    tabela = f"{casa_clean}_votos"

    try:
        query = supabase.table(tabela).select("*", count="exact")

        if politico_id:
            query = query.eq("politico_id", politico_id)
        if proposicao_id:
            query = query.eq("proposicao_id", proposicao_id)

        # Ordenação padrão
        query = query.order("id", desc=False)

        inicio = (pagina - 1) * tamanho
        fim = inicio + tamanho - 1
        query = query.range(inicio, fim)

        resultado = query.execute()

        total_registros = resultado.count if resultado.count is not None else 0
        total_paginas = (
            math.ceil(total_registros / tamanho) if total_registros > 0 else 0
        )

        return {
            "total_registros": total_registros,
            "pagina_atual": pagina,
            "tamanho_pagina": tamanho,
            "total_paginas": total_paginas,
            "itens": resultado.data,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar votos: {str(e)}")


@router.get(
    "/{casa}/politicos/{id_parlamentar}/timeline",
    response_model=list[VotoTimelineSchema],
    summary="Obter Linha do Tempo de Votos",
    description="Retorna a lista cronológica de todos os votos nominais proferidos por um parlamentar.",
)
def obter_timeline_votos(
    casa: str = Path(..., description="Casa legislativa ('camara' ou 'senado')"),
    id_parlamentar: int = Path(..., description="ID interno do político"),
):
    casa_clean = validar_casa(casa)
    tabela_votos = f"{casa_clean}_votos"
    tabela_proposicoes = f"{casa_clean}_proposicoes"

    try:
        resultado = (
            supabase.table(tabela_votos)
            .select(
                f"voto_oficial, proposicao_id, {tabela_proposicoes}(data_votacao, tipo, numero, ano, ementa)"
            )
            .eq("politico_id", id_parlamentar)
            .execute()
        )

        votos_raw = resultado.data
        if not votos_raw:
            return []

        timeline = []
        for v in votos_raw:
            prop = v.get(tabela_proposicoes)
            if not prop:
                continue

            timeline.append(
                {
                    "data_votacao": prop.get("data_votacao"),
                    "proposicao_id": v.get("proposicao_id"),
                    "tipo": prop.get("tipo"),
                    "numero": prop.get("numero"),
                    "ano": prop.get("ano"),
                    "ementa": prop.get("ementa"),
                    "voto_oficial": v.get("voto_oficial"),
                }
            )

        timeline.sort(key=lambda x: str(x["data_votacao"]) or "")
        return timeline
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro ao obter timeline de votos: {str(e)}"
        )


@router.get(
    "/comparar",
    response_model=ComparacaoResponse,
    summary="Comparar Votos de Dois Políticos",
    description="Calcula o alinhamento de voto entre dois parlamentares nas proposições comuns.",
)
def comparar_politicos(
    politico_id_1: int = Query(..., description="ID do primeiro político"),
    politico_id_2: int = Query(..., description="ID do segundo político"),
    casa: str = Query(..., description="Casa legislativa ('camara' ou 'senado')"),
):
    casa_clean = validar_casa(casa)
    tabela_votos = f"{casa_clean}_votos"
    tabela_proposicoes = f"{casa_clean}_proposicoes"

    try:
        res_votos_1 = (
            supabase.table(tabela_votos)
            .select(f"voto_oficial, proposicao_id, {tabela_proposicoes}(ementa)")
            .eq("politico_id", politico_id_1)
            .execute()
        )

        res_votos_2 = (
            supabase.table(tabela_votos)
            .select(f"voto_oficial, proposicao_id, {tabela_proposicoes}(ementa)")
            .eq("politico_id", politico_id_2)
            .execute()
        )

        votos_1 = {
            v["proposicao_id"]: (
                v["voto_oficial"].strip().upper(),
                v.get(tabela_proposicoes, {}).get("ementa", ""),
            )
            for v in res_votos_1.data
            if v.get("voto_oficial")
            and v["voto_oficial"].strip().upper() in ["SIM", "NÃO", "NAO"]
        }

        votos_2 = {
            v["proposicao_id"]: v["voto_oficial"].strip().upper()
            for v in res_votos_2.data
            if v.get("voto_oficial")
            and v["voto_oficial"].strip().upper() in ["SIM", "NÃO", "NAO"]
        }

        comuns = set(votos_1.keys()).intersection(votos_2.keys())
        total_comuns = len(comuns)

        if total_comuns == 0:
            return {
                "concordancia_percentual": 0.0,
                "proposicoes_em_comum": 0,
                "divergencias": [],
            }

        concordancias = 0
        divergencias = []

        for p_id in comuns:
            voto1, ementa = votos_1[p_id]
            voto2 = votos_2[p_id]

            voto1_norm = "NÃO" if voto1 in ["NÃO", "NAO"] else "SIM"
            voto2_norm = "NÃO" if voto2 in ["NÃO", "NAO"] else "SIM"

            if voto1 == voto2:
                concordancias += 1
            else:
                divergencias.append(
                    {
                        "proposicao_id": p_id,
                        "ementa": ementa,
                        "voto_politico_1": voto1_norm,
                        "voto_politico_2": voto2_norm,
                    }
                )

        percentual = (
            round((concordancias / total_comuns) * 100, 1) if total_comuns > 0 else 0.0
        )

        return {
            "concordancia_percentual": percentual,
            "proposicoes_em_comum": total_comuns,
            "divergencias": divergencias,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro ao comparar políticos: {str(e)}"
        )


@router.get(
    "/{casa}/politicos/{id_parlamentar}/afinidades",
    response_model=AfinidadesResponse,
    summary="Obter Afinidades Políticas (Gêmeo e Antípoda)",
    description="Retorna o parlamentar mais parecido (gêmeo) e o mais divergente (antípoda) da mesma casa.",
)
def obter_afinidades_politico(
    casa: str = Path(..., description="Casa legislativa ('camara' ou 'senado')"),
    id_parlamentar: int = Path(..., description="ID interno do político"),
):
    casa_clean = validar_casa(casa)
    tabela_politicos = f"{casa_clean}_politicos"
    tabela_votos = f"{casa_clean}_votos"

    try:
        res_politico = (
            supabase.table(tabela_politicos)
            .select("id")
            .eq("id", id_parlamentar)
            .execute()
        )
        if not res_politico.data:
            raise HTTPException(status_code=404, detail="Político não encontrado")

        res_votos_alvo = (
            supabase.table(tabela_votos)
            .select("proposicao_id, voto_oficial")
            .eq("politico_id", id_parlamentar)
            .execute()
        )

        votos_alvo = {
            v["proposicao_id"]: v["voto_oficial"].strip().upper()
            for v in res_votos_alvo.data
            if v.get("voto_oficial")
            and v["voto_oficial"].strip().upper() in ["SIM", "NÃO", "NAO"]
        }

        if not votos_alvo:
            return {"gemeo": None, "antipoda": None}

        res_todos_politicos = supabase.table(tabela_politicos).select("*").execute()
        politicos_map = {
            p["id"]: p for p in res_todos_politicos.data if p["id"] != id_parlamentar
        }

        if not politicos_map:
            return {"gemeo": None, "antipoda": None}

        res_todos_votos = (
            supabase.table(tabela_votos)
            .select("politico_id, proposicao_id, voto_oficial")
            .execute()
        )

        votos_por_politico = {}
        for v in res_todos_votos.data:
            p_id = v.get("politico_id")
            if not p_id or p_id == id_parlamentar or p_id not in politicos_map:
                continue
            voto_of = v.get("voto_oficial")
            if not voto_of or voto_of.strip().upper() not in ["SIM", "NÃO", "NAO"]:
                continue
            if p_id not in votos_por_politico:
                votos_por_politico[p_id] = {}
            votos_por_politico[p_id][v["proposicao_id"]] = voto_of.strip().upper()

        comparacoes = []
        for p_id, votos_outro in votos_por_politico.items():
            comuns = set(votos_alvo.keys()).intersection(votos_outro.keys())
            total_comuns = len(comuns)

            if total_comuns < 5:
                continue

            concordancias = sum(
                1 for pid in comuns if votos_alvo[pid] == votos_outro[pid]
            )
            percentual = round((concordancias / total_comuns) * 100, 1)

            comparacoes.append(
                {
                    "politico": politicos_map[p_id],
                    "concordancia": percentual,
                    "votos_comuns": total_comuns,
                }
            )

        if not comparacoes:
            return {"gemeo": None, "antipoda": None}

        comparacoes.sort(
            key=lambda x: (x["concordancia"], x["votos_comuns"]), reverse=True
        )
        gemeo = comparacoes[0]

        comparacoes.sort(key=lambda x: (x["concordancia"], -x["votos_comuns"]))
        antipoda = comparacoes[0]

        return {"gemeo": gemeo, "antipoda": antipoda}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro ao obter afinidades políticas: {str(e)}"
        )


@router.get(
    "/{casa}/politicos/{id_parlamentar}/fidelidade",
    response_model=FidelidadeResponse,
    summary="Obter Fidelidade Partidária",
    description="Calcula o percentual de vezes que o parlamentar votou alinhado com a maioria do seu partido nas votações nominais.",
)
def obter_fidelidade_partidaria(
    casa: str = Path(..., description="Casa legislativa ('camara' ou 'senado')"),
    id_parlamentar: int = Path(..., description="ID interno do político"),
):
    casa_clean = validar_casa(casa)
    tabela_politicos = f"{casa_clean}_politicos"
    tabela_votos = f"{casa_clean}_votos"

    try:
        res_politico = (
            supabase.table(tabela_politicos)
            .select("id, partido")
            .eq("id", id_parlamentar)
            .execute()
        )
        if not res_politico.data:
            raise HTTPException(status_code=404, detail="Político não encontrado")

        politico_cadastro = res_politico.data[0]
        partido_cadastro = politico_cadastro.get("partido")

        res_votos_parlamentar = (
            supabase.table(tabela_votos)
            .select("proposicao_id, voto_oficial, partido_na_epoca")
            .eq("politico_id", id_parlamentar)
            .execute()
        )

        votos_alvo = []
        for v in res_votos_parlamentar.data:
            voto_of = v.get("voto_oficial")
            if voto_of and voto_of.strip().upper() in ["SIM", "NÃO", "NAO"]:
                votos_alvo.append(
                    {
                        "proposicao_id": v["proposicao_id"],
                        "voto_oficial": voto_of.strip().upper(),
                        "partido": v.get("partido_na_epoca") or partido_cadastro,
                    }
                )

        if not votos_alvo:
            return {
                "taxa_fidelidade": 0.0,
                "votos_alinhados": 0,
                "votos_rebeldes": 0,
                "total_votos_com_orientacao": 0,
            }

        res_todos_votos = (
            supabase.table(tabela_votos)
            .select("politico_id, proposicao_id, voto_oficial, partido_na_epoca")
            .execute()
        )

        votos_partidarios = {}
        for v in res_todos_votos.data:
            p_id = v.get("politico_id")
            prop_id = v.get("proposicao_id")
            voto_of = v.get("voto_oficial")

            if not prop_id or not voto_of:
                continue
            voto_of_upper = voto_of.strip().upper()
            if voto_of_upper not in ["SIM", "NÃO", "NAO"]:
                continue

            voto_norm = "NÃO" if voto_of_upper in ["NÃO", "NAO"] else "SIM"

            partido = v.get("partido_na_epoca")
            if p_id == id_parlamentar and not partido:
                partido = partido_cadastro

            if not partido:
                continue

            partido = partido.strip().upper()

            if prop_id not in votos_partidarios:
                votos_partidarios[prop_id] = {}
            if partido not in votos_partidarios[prop_id]:
                votos_partidarios[prop_id][partido] = {"SIM": 0, "NÃO": 0}

            votos_partidarios[prop_id][partido][voto_norm] += 1

        votos_alinhados = 0
        votos_rebeldes = 0
        total_votos_com_orientacao = 0

        for v in votos_alvo:
            prop_id = v["proposicao_id"]
            partido = v["partido"]
            if not partido:
                continue
            partido = partido.strip().upper()

            voto_norm = "NÃO" if v["voto_oficial"] in ["NÃO", "NAO"] else "SIM"

            partido_votos = votos_partidarios.get(prop_id, {}).get(
                partido, {"SIM": 0, "NÃO": 0}
            )
            sim_count = partido_votos["SIM"]
            nao_count = partido_votos["NÃO"]

            if sim_count == 0 and nao_count == 0:
                continue

            if sim_count > nao_count:
                orientacao = "SIM"
            elif nao_count > sim_count:
                orientacao = "NÃO"
            else:
                orientacao = "SIM"

            total_votos_com_orientacao += 1
            if voto_norm == orientacao:
                votos_alinhados += 1
            else:
                votos_rebeldes += 1

        taxa = (
            round((votos_alinhados / total_votos_com_orientacao) * 100, 1)
            if total_votos_com_orientacao > 0
            else 0.0
        )

        return {
            "taxa_fidelidade": taxa,
            "votos_alinhados": votos_alinhados,
            "votos_rebeldes": votos_rebeldes,
            "total_votos_com_orientacao": total_votos_com_orientacao,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro ao obter fidelidade partidária: {str(e)}"
        )


@router.get(
    "/{casa}/proposicoes/{id_proposicao}/polarizacao",
    response_model=PolarizacaoResponse,
    summary="Obter Polarização de Votos da Proposição",
    description="Mede o quão dividida a casa legislativa estava na votação de uma determinada matéria.",
)
def obter_polarizacao_proposicao(
    casa: str = Path(..., description="Casa legislativa ('camara' ou 'senado')"),
    id_proposicao: str = Path(..., description="ID da proposição (UUID)"),
):
    casa_clean = validar_casa(casa)
    tabela_proposicoes = f"{casa_clean}_proposicoes"
    tabela_votos = f"{casa_clean}_votos"

    try:
        res_prop = (
            supabase.table(tabela_proposicoes)
            .select("id, proposicao_id")
            .eq("id", id_proposicao)
            .execute()
        )
        if not res_prop.data:
            raise HTTPException(status_code=404, detail="Proposição não encontrada")

        prop_data = res_prop.data[0]
        codigo_proposicao = prop_data["proposicao_id"]

        res_votos = (
            supabase.table(tabela_votos)
            .select("voto_oficial")
            .eq("proposicao_id", codigo_proposicao)
            .execute()
        )

        qtd_sim = 0
        qtd_nao = 0

        for v in res_votos.data:
            voto_of = v.get("voto_oficial")
            if voto_of:
                voto_upper = voto_of.strip().upper()
                if voto_upper == "SIM":
                    qtd_sim += 1
                elif voto_upper in ["NÃO", "NAO"]:
                    qtd_nao += 1

        total_validos = qtd_sim + qtd_nao
        if total_validos == 0:
            return {
                "proposicao_id": codigo_proposicao,
                "qtd_sim": 0,
                "qtd_nao": 0,
                "pct_sim": 0.0,
                "pct_nao": 0.0,
                "polarizacao": 0.0,
                "classificacao": "Consensual",
            }

        pct_sim = round((qtd_sim / total_validos) * 100, 1)
        pct_nao = round((qtd_nao / total_validos) * 100, 1)

        polarizacao = round(100 - abs(pct_sim - pct_nao), 1)

        if polarizacao < 30.0:
            classificacao = "Consensual"
        elif polarizacao <= 70.0:
            classificacao = "Dividida"
        else:
            classificacao = "Altamente Polarizada"

        return {
            "proposicao_id": codigo_proposicao,
            "qtd_sim": qtd_sim,
            "qtd_nao": qtd_nao,
            "pct_sim": pct_sim,
            "pct_nao": pct_nao,
            "polarizacao": polarizacao,
            "classificacao": classificacao,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro ao obter polarização de proposição: {str(e)}"
        )


@router.get(
    "/{casa}/partidos/coesao",
    response_model=CoesaoGeralResponse,
    summary="Obter Índice de Coesão dos Partidos",
    description="Retorna o índice médio de disciplina e coesão de votos de todos os partidos políticos na casa legislativa.",
)
def obter_coesao_partidos(
    casa: str = Path(..., description="Casa legislativa ('camara' ou 'senado')"),
):
    casa_clean = validar_casa(casa)
    tabela_votos = f"{casa_clean}_votos"

    try:
        res_votos = (
            supabase.table(tabela_votos)
            .select("proposicao_id, voto_oficial, partido_na_epoca")
            .execute()
        )

        partidos_votos = {}

        for v in res_votos.data:
            prop_id = v.get("proposicao_id")
            voto_of = v.get("voto_oficial")
            partido = v.get("partido_na_epoca")

            if not prop_id or not voto_of or not partido:
                continue

            voto_upper = voto_of.strip().upper()
            if voto_upper not in ["SIM", "NÃO", "NAO"]:
                continue

            voto_norm = "NÃO" if voto_upper in ["NÃO", "NAO"] else "SIM"
            partido_upper = partido.strip().upper()

            if partido_upper not in partidos_votos:
                partidos_votos[partido_upper] = {}

            if prop_id not in partidos_votos[partido_upper]:
                partidos_votos[partido_upper][prop_id] = {"SIM": 0, "NÃO": 0}

            partidos_votos[partido_upper][prop_id][voto_norm] += 1

        itens = []
        for partido, proposicoes in partidos_votos.items():
            soma_coesao = 0.0
            total_proposicoes_validas = 0

            for prop_id, counts in proposicoes.items():
                sims = counts["SIM"]
                naos = counts["NÃO"]
                total_votos_prop = sims + naos

                if total_votos_prop == 0:
                    continue

                coesao_prop = abs(sims - naos) / total_votos_prop
                soma_coesao += coesao_prop
                total_proposicoes_validas += 1

            if total_proposicoes_validas > 0:
                coesao_media = round((soma_coesao / total_proposicoes_validas) * 100, 1)
                itens.append({"partido": partido, "indice_coesao": coesao_media})

        itens.sort(key=lambda x: x["indice_coesao"], reverse=True)
        return {"itens": itens}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao obter índice de coesão dos partidos: {str(e)}",
        )


@router.get(
    "/{casa}/discursos/{discurso_id}",
    response_model=DiscursoDB,
    summary="Obter Detalhes do Discurso",
    description="Retorna as informações completas e o texto bruto de um discurso específico pelo seu ID (UUID).",
    responses={
        404: {"description": "Discurso não encontrado."},
    },
)
def obter_discurso_detalhado(
    casa: str = Path(..., description="Casa legislativa ('camara' ou 'senado')"),
    discurso_id: str = Path(..., description="ID do discurso (UUID)"),
):
    casa_clean = validar_casa(casa)
    tabela = f"{casa_clean}_discursos"

    try:
        resultado = supabase.table(tabela).select("*").eq("id", discurso_id).execute()

        if not resultado.data:
            raise HTTPException(status_code=404, detail="Discurso não encontrado")

        return resultado.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro ao buscar discurso: {str(e)}"
        )
