import logging
import os
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend

from app.api import health, insights, panels, search
from app.core.embeddings import initialize_embeddings
from app.core.postgres import cleanup_db, init_db

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:     %(message)s'
)

load_dotenv()


def custom_key_builder(func, namespace: str = "", *, request: Request = None, response: Response = None, **kwargs):
    if request:
        sorted_query_params = sorted(request.query_params.items())
        return ":".join([namespace, request.method.lower(), request.url.path, repr(sorted_query_params), func.__module__ + func.__name__])
    return ":".join([namespace, func.__module__ + func.__name__, repr(sorted(kwargs.items()))])

def preload_models():
    from app.query.router import get_router
    logging.info("="*70)
    logging.info("🔄 모든 AI 모델을 미리 로드합니다...")
    start = time.time()
    initialize_embeddings()
    try: get_router().find_closest_field("테스트 쿼리")
    except: pass
    logging.info(f"✅ 모델 로드 완료 ({time.time() - start:.2f}초)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("🚀 FastAPI 시작...")
    FastAPICache.init(InMemoryBackend(), prefix="fastapi-cache", key_builder=custom_key_builder)
    init_db()
    preload_models()
    yield
    logging.info("🧹 FastAPI 종료... Connection Pool 정리")
    cleanup_db()


app = FastAPI(title="Multi-Table Hybrid Search API v3 (Refactored)", lifespan=lifespan)

# --- CORS Middleware ---
origins = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 기존 main.py에서 엔드포인트가 정의돼 있던 순서대로 등록한다
for r in (insights.router, search.router, panels.router, health.router):
    app.include_router(r)
