from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from app.rotas import dados
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Iniciando o Cache em Memória...")
    FastAPICache.init(InMemoryBackend())
    yield
    print("Desligando a API...")


tags_metadata = [
    {
        "name": "Dados Gerais",
        "description": "Operações diretas de listagem das tabelas do Congresso (Câmara e Senado).",
    },
]

app = FastAPI(
    title="API ContraDito - Raio-X do Parlamentar",
    description="""
    Back-end oficial da Squad 9 para análise de discursos parlamentares.
    Esta API gerencia a listagem de políticos, o cálculo de coerência e o pipeline de checagem de fatos via RAG.
    """,
    version="1.0.0",
    openapi_tags=tags_metadata,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(dados.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://*.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
def home():
    return {"status": "Servidor rodando liso na arquitetura limpa!"}
