import logging
import numpy as np
import os
from typing import List, Dict
from sklearn.metrics.pairwise import cosine_similarity
from app.panels.fields import QPOLL_FIELDS, WELCOME_OBJECTIVE_FIELDS, FIELD_NAME_MAP
from app.core.embeddings import initialize_embeddings
from mapping_rules import get_field_mapping

# 로거 설정
logger = logging.getLogger(__name__)

class SemanticRouter:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SemanticRouter, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        if self.initialized:
            return
            
        logger.info("🔄 Semantic Router 초기화 중...")
        self.embeddings = initialize_embeddings()
        
        # 2. 질문(Field) 리스트업 (utils.py 활용)
        self.fields = []
        self.descriptions = []
        
        # Q-Poll 뿐만 아니라 Welcome 데이터(가전, 차량 등)도 검색 대상에 포함!
        all_target_fields = QPOLL_FIELDS + WELCOME_OBJECTIVE_FIELDS
        
        for field, desc in all_target_fields:
            self.fields.append(field)
            self.descriptions.append(desc)
            
        # 3. 모든 필드 미리 벡터화 (캐싱)
        self.field_vectors = self.embeddings.embed_documents(self.descriptions)
        self.initialized = True
        logger.info(f"✅ 총 {len(self.fields)}개 필드(Q-Poll + Welcome) 벡터화 완료")

    def find_closest_field(self, user_intent: str, threshold: float = 0.4) -> Dict:
        """
        사용자 의도(user_intent)와 가장 가까운 질문 필드를 찾습니다.
        1차: 키워드 매칭, 2차: 의미(벡터) 매칭
        """
        if not user_intent:
            return None

        logger.debug(f"➡️ Semantic Router: 의도 '{user_intent}'에 대한 필드 탐색 시작")

        # 1. 키워드 기반 우선 검색
        keyword_match = get_field_mapping(user_intent)
        # 타입이 qpoll이든 filter든 매칭되면 반환하도록 조건 완화
        if keyword_match and keyword_match.get("field") != "unknown":
            logger.debug(f"  🎯 Semantic Route: '{user_intent}' -> '{keyword_match['description']}' (Keyword Match)")
            return {
                "field": keyword_match['field'],
                "description": keyword_match['description'],
                "score": 1.0,
                "method": "keyword"
            }

        # 2. 의미 기반 검색 (Fallback)
        logger.debug(f"  (1/2) ⚠️ 키워드 매칭 실패. 의미 기반 검색으로 전환합니다: '{user_intent}'")
        
        # 사용자 의도 벡터화
        query_vec = self.embeddings.embed_query(user_intent)
        
        # 코사인 유사도 계산
        sims = cosine_similarity([query_vec], self.field_vectors)[0]
        
        # 상위 3개 점수 로깅
        top_k_indices = np.argsort(sims)[-3:][::-1]
        top_scores_log = ", ".join([f"'{self.descriptions[i]}'({sims[i]:.3f})" for i in top_k_indices])
        logger.debug(f"  (2/2) 📈 상위 유사도 점수: {top_scores_log}")

        # 가장 높은 유사도 찾기
        best_idx = np.argmax(sims)
        best_score = sims[best_idx]
        
        if best_score < threshold:
            logger.warning(f"  (2/2) ❌ 매칭되는 필드 없음 (임계값: {threshold}, 최고점: {best_score:.2f})")
            return None
            
        matched_field = self.fields[best_idx]
        matched_desc = self.descriptions[best_idx]
        
        logger.info(f"  🎯 Semantic Route: '{user_intent}' -> '{matched_desc}' ({matched_field}) (Score: {best_score:.2f})")
        
        return {
            "field": matched_field,
            "description": matched_desc,
            "score": float(best_score),
            "method": "semantic"
        }

# 싱글톤 인스턴스 생성
router = SemanticRouter()