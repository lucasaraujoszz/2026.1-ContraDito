# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**ContraDito** is a political transparency platform that cross-references Brazilian federal legislators' speeches against their voting records, computing a **Score de Coerência** (Coherence Score) using AI. It is an academic project for the MDS discipline at UnB (Universidade de Brasília).

## Running the Project

All services run via Docker Compose. Requires a `.env` file at the root:

```env
SUPABASE_URL=...
SUPABASE_KEY=...
LLM_PROVIDER=groq   # "groq" or "colab"
GROQ_API_KEY=...
REDIS_URL=redis://redis:6379
NEXT_PUBLIC_API_URL=http://localhost:8001
```

```bash
docker compose up --build
```

- API docs (FastAPI Swagger): http://localhost:8001/docs
- PostgreSQL: localhost:5432

> On Apple Silicon (ARM64): ensure `platform: linux/arm64` is set in `docker-compose.yml`. The first build downloads the HuggingFace model (~2.3GB) and caches it in a Docker volume.

## Linting (CI enforced on PRs to `develop` and `main`)

```bash
# Format check
black --check app/

# Lint (critical errors only)
flake8 app/ --count --select=E9,F63,F7,F82 --show-source --statistics

## Architecture

The system is a strict **CQRS** pattern split into two isolated Python services:

### Read Side — `app/` (FastAPI, port 8000)
- Entry point: `app/main.py`
- Routes: `app/rotas/politicos.py` and `app/rotas/logs.py`
- Pydantic schemas: `app/modelos/schemas.py`
- Supabase client: `app/bancos/supabase.py`
- Uses `fastapi-cache2` with `InMemoryBackend` (1h TTL on list endpoints)
- Rate-limited via `slowapi` (5/min on semantic search)
- CORS is locked to `http://localhost:3000`

Key internal routes (hidden from Swagger):
- `POST /api/politicos/interno/recalcular-scores` — recalculates all coherence scores from `provas_contradicao` table
- `POST /api/politicos/interno/limpar-cache` — invalidates the in-memory cache (called by the ETL worker after writes)

### Write Side — `worker_api.py` (FastAPI, port 8001, internal only)
- Entry point: `worker_api.py`
- Exposes a single route: `POST /gerar-embedding`
- NLP engine: `utils/motor_nlp.py` — wraps `sentence-transformers` model `paraphrase-multilingual-mpnet-base-v2` (768-dimension vectors)
- Port 8001 is **not exposed externally** (Docker-internal only); the API calls it via `http://worker:8001`

### Database — Supabase (PostgreSQL + pgvector)
Core tables:
- `politicos` — legislators with `score_coerencia` field
- `provas_contradicao` — AI-generated contradiction evidence, one row per speech/vote pair, with `status_coerencia` (bool)
- `logs_pipeline_ia` — ETL error log
- Vector similarity search uses a Supabase RPC `buscar_discursos_similares` (stored procedure using `pgvector`)

In local Docker, the DB is `pgvector/pgvector:pg15` on port 5432 (exposed for DBeaver/pgAdmin inspection).

### Frontend — `frontend/` (Next.js 16 + React 19 + Tailwind CSS 4)
- App Router under `frontend/app/`
- Pages: `/` (listing), `/politico/[id]` (profile), `/comparacao` (comparison)
- Communicates with the API at `NEXT_PUBLIC_API_URL`

## Score de Coerência Logic

Defined in `app/rotas/politicos.py:recalcular_todos_scores`:
- Abstentions/absences (`AUSENTE`, `ABSTENÇÃO`, `NÃO COMPARECEU`, etc.) are excluded from the denominator (RF27)
- Minimum of **3 valid votes** required to produce a non-null score (RF15)
- Score = `(votos_coerentes / total_validos) * 100`, rounded to 1 decimal
