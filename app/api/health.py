from fastapi import APIRouter

from app.core.postgres import get_db_connection_context

router = APIRouter()


@router.get("/")
def read_root():
    return {
        "service": "Multi-Table Hybrid Search & Analysis API",
        "version": "3.0 (Refactored)",
        "status": "running"
    }


@router.get("/health")
def health_check():
    try:
        with get_db_connection_context() as conn:
            db_status = "ok" if conn else "error"
        return {"status": "healthy", "database": db_status}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
