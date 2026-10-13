import logging

from qdrant_client import QdrantClient

from app.core.config import settings


def get_qdrant_client():
    """Qdrant 클라이언트를 생성하고 반환합니다."""
    try:
        client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            timeout=20.0
        )
        return client
    except Exception as e:
        logging.error(f"Qdrant 클라이언트 연결 실패: {e}")
        return None
