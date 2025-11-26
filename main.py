import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend

# Core & Config
from dotenv import load_dotenv
from app.database.connection import init_db, cleanup_db
from app.api.router import api_router
from search_helpers import initialize_embeddings 

load_dotenv()

# 로깅 설정 (기존 log_config.json 활용 가정, 필요시 app/core/logging.py로 이동)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Multi-Table Hybrid Search API v3 (Refactored)")

# --- CORS Middleware ---
origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "https://<AMPLIFY_DOMAIN>"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- LifeSpan Events ---
@app.on_event("startup")
async def startup_event():
    logging.info("🚀 FastAPI 시작... (Refactored Structure)")
    
    # 캐시 초기화
    FastAPICache.init(InMemoryBackend(), prefix="fastapi-cache")
    
    # DB 초기화
    init_db()
    
    # 모델 프리로딩 (선택사항)
    logging.info("🔄 AI 모델 로드 중...")
    try:
        initialize_embeddings()
    except Exception as e:
        logging.warning(f"모델 로드 중 경고: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    logging.info("🧹 FastAPI 종료... 리소스 정리")
    cleanup_db()

# --- Router 등록 ---
app.include_router(api_router, prefix="/api")

@app.get("/")
def read_root():
    return {
        "service": "Multi-Table Hybrid Search API",
        "version": "3.1 (Layered Architecture)",
        "status": "running"
    }

@app.get("/health")
def health_check():
    from app.database.connection import get_db_connection
    conn = get_db_connection()
    status = "healthy" if conn else "unhealthy"
    if conn: conn.close() # 단순 체크용 연결 닫기
    return {"status": status}