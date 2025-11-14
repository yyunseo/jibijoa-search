import logging
from qdrant_client import QdrantClient
from qdrant_client.http.models import PayloadSchemaType

# Qdrant 서버 주소
QDRANT_URL = "http://<REDACTED_IP>:6333"

# 생성할 컬렉션 이름
WELCOME_COLLECTION = "welcome_subjective_vectors"
QPOLL_COLLECTION = "qpoll_vectors_v2"

def create_indexes():
    try:
        client = QdrantClient(url=QDRANT_URL)
        print(f"✅ {QDRANT_URL} 연결 성공. 인덱스 생성을 시도합니다...\n")

        # 1. QPoll v2 컬렉션 (이미 되어 있지만, 확인 차 실행)
        try:
            client.create_payload_index(
                collection_name=QPOLL_COLLECTION,
                field_name="panel_id",
                field_schema=PayloadSchemaType.KEYWORD
            )
            print(f"👍 [성공] {QPOLL_COLLECTION} 컬렉션에 'panel_id' 인덱스 생성 완료")
        except Exception as e:
            print(f"⚠️  [참고] {QPOLL_COLLECTION} 인덱스 생성 실패 (이미 존재할 수 있음): {e}")

        # 2. Welcome 컬렉션 (‼️ 이것이 진짜 목적)
        try:
            client.create_payload_index(
                collection_name=WELCOME_COLLECTION,
                field_name="metadata.panel_id",
                field_schema=PayloadSchemaType.KEYWORD
            )
            print(f"👍 [성공] {WELCOME_COLLECTION} 컬렉션에 'metadata.panel_id' 인덱스 생성 완료")
        except Exception as e:
            print(f"⚠️  [참고] {WELCOME_COLLECTION} 인덱스 생성 실패 (이미 존재할 수 있음): {e}")

    except Exception as e:
        print(f"❌ Qdrant 연결 실패: {e}")

if __name__ == "__main__":
    create_indexes()