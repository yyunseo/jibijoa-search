import logging
import re

import numpy as np
from qdrant_client.http.models import FieldCondition, Filter, MatchAny, MatchText
from sklearn.metrics.pairwise import cosine_similarity


def normalize_text(text: str) -> str:
    """[New] 텍스트 정규화: 공백, 특수문자 제거 후 비교용 문자열 생성"""
    if not text: return ""
    # 알파벳, 한글, 숫자만 남기고 모두 제거 (특수문자, 공백 무시)
    return re.sub(r'[^a-zA-Z0-9가-힣]', '', text)


def rerank_candidates(
    candidate_ids: list,
    query_vector: list,
    qdrant_client,
    collection_name: str,
    id_key_path: str,
    negative_patterns: list,
    target_question: str = None  
) -> list:
    """
    [핵심 로직] In-Memory Reranking (Hybrid Fetching & Fuzzy Matching)
    - 대상이 적을 때(2000명 이하): 질문 필터 없이 데이터를 가져와 Python에서 정밀/유연하게 매칭 (누락 방지)
    - 대상이 많을 때: DB 필터 사용 (속도 최적화)
    """
    # [Safety Cap] 대상이 너무 많으면 상위 5000명으로 제한
    if len(candidate_ids) > 10000:
        logging.warning(f"⚠️ Reranking 대상이 너무 많음 ({len(candidate_ids)}명). 상위 5000명만 수행합니다.")
        candidate_ids = candidate_ids[:5000]

    # [전략 결정] 대상이 적고 타겟 질문이 있으면 -> Python 유연 필터링 사용 (DB 필터 미사용)
    # 이유: DB의 MatchText는 특수문자(·, ()) 처리가 엄격하여 데이터를 놓칠 수 있음
    use_python_filter = (len(candidate_ids) <= 2000) and (target_question is not None)

    must_conditions = [
        FieldCondition(
            key=id_key_path, 
            match=MatchAny(any=[str(pid) for pid in candidate_ids])
        )
    ]
    
    # DB 레벨 질문 필터는 '대량이거나 질문이 없을 때'만 사용
    if target_question and not use_python_filter:
        must_conditions.append(
            FieldCondition(key="question", match=MatchText(text=target_question))
        )

    search_filter = Filter(must=must_conditions)

    # 1. 데이터 조회 (Batch Scroll)
    batch_size = 2000 
    all_points = []
    offset = None
    
    while True:
        points, next_offset = qdrant_client.scroll(
            collection_name=collection_name,
            scroll_filter=search_filter,
            limit=batch_size,
            with_vectors=True,
            with_payload=True,
            offset=offset
        )
        all_points.extend(points)
        offset = next_offset
        if offset is None:
            break
            
    if not all_points:
        return []

    # 2. [정밀 로직] Python 레벨에서 질문 매칭 (use_python_filter 모드)
    target_points = []
    if use_python_filter:
        norm_target = normalize_text(target_question)
        
        for p in all_points:
            p_question = p.payload.get("question", "")
            # 정규화된 문자열로 포함 여부 확인 (띄어쓰기, 특수문자 무시하고 비교)
            if norm_target in normalize_text(p_question):
                target_points.append(p)
        
        # 만약 매칭된 게 하나도 없다면(데이터 오류 등), 필터 없이 전체 사용 (Fallback)
        if not target_points and all_points:
            logging.warning(f"⚠️ 질문 매칭 실패 (Target: {target_question[:10]}...). 전체 데이터를 사용합니다.")
            target_points = all_points
    else:
        target_points = all_points

    if not target_points:
        return []

    # 3. 유사도 계산 및 부정어 필터링
    vectors = [p.vector for p in target_points]
    query_vec_np = np.array([query_vector])
    
    # 코사인 유사도 계산
    scores = cosine_similarity(query_vec_np, vectors)[0]

    scored_results = []
    for i, point in enumerate(target_points):
        score = scores[i]
        payload = point.payload
        
        # 답변 텍스트 추출
        answer_text = payload.get('page_content') or payload.get('sentence') or ""
        
        # 부정어 필터링 (정규식 검사)
        is_negative = False
        for pattern in negative_patterns:
            if re.search(pattern, answer_text):
                is_negative = True
                break
        
        if is_negative:
            continue  # 부정 답변은 결과에서 제외
            
        # ID 추출
        pid = payload.get('panel_id') or payload.get('metadata', {}).get('panel_id')
        
        if pid:
            scored_results.append((pid, score))

    # 4. 점수 내림차순 정렬
    scored_results.sort(key=lambda x: x[1], reverse=True)
    
    # 중복 제거 (한 사람이 여러 답변을 했을 경우 최고 점수만 유지)
    seen_pids = set()
    unique_results = []
    for pid, score in scored_results:
        if pid not in seen_pids:
            unique_results.append(pid)
            seen_pids.add(pid)

    return unique_results
