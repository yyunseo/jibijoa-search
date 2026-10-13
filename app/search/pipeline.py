import logging
import re
from typing import Dict, Optional

from qdrant_client.http.models import FieldCondition, Filter, MatchText

from app.core.embeddings import embed_keywords, initialize_embeddings
from app.core.qdrant import get_qdrant_client
from app.panels.fields import QPOLL_FIELD_TO_TEXT, VALUE_TRANSLATION_MAP, WELCOME_OBJECTIVE_FIELDS
from app.query.parser import parse_query_intelligent
from app.query.router import get_router
from app.search.negative import filter_negative_conditions, get_negative_patterns
from app.search.rerank import rerank_candidates
from app.search.sql_filter import search_welcome_objective


def hybrid_search(query: str, limit: Optional[int] = None) -> Dict:
    """
    Semantic Search V3 (Refactored): 
    SQL 필터 결과 유무에 따라 Reranking(전수조사)과 일반 검색을 분기하여 수행
    """
    try:
        logging.info(f"🚀 Semantic Search V3 (Optimized): {query}")
        
        # 1. LLM 파싱
        parsed_query = parse_query_intelligent(query) 
        
        all_conditions = parsed_query.get("semantic_conditions", [])
        positive_conditions = [c for c in all_conditions if not c.get('is_negative', False)]
        negative_conditions = [c for c in all_conditions if c.get('is_negative', False)]

        structured_filters = parsed_query.get("demographic_filters", {})
        user_limit = limit or parsed_query.get("limit", 100)

        intent = ""
        if positive_conditions:
            intent = positive_conditions[0].get("original_keyword", "")
        
        # 2. 라우팅
        target_field_info = get_router().find_closest_field(intent)
        target_field = None
        target_desc = None
        if target_field_info:
            target_field = target_field_info['field']
            target_desc = target_field_info['description']

        objective_field_names = [f[0] for f in WELCOME_OBJECTIVE_FIELDS]
        
        # 라우팅 보정
        if target_field in objective_field_names:
            for cond in all_conditions:
                kw = cond.get('original_keyword', '')
                if kw == intent: continue 
                
                alt_info = get_router().find_closest_field(kw)
                if alt_info and alt_info['field'] in QPOLL_FIELD_TO_TEXT:
                    logging.info(f"🔄 타겟 재설정: {target_field}(인구통계) -> {alt_info['field']}(설문)로 변경")
                    target_field = alt_info['field']
                    target_desc = alt_info['description']
                    intent = kw 
                    break

        # 3. 1차 필터링 (SQL - 인구통계)
        filtered_panel_ids = set()
        
        if structured_filters or target_field:
            filters_for_sql = []
            
            # Structured Filters 처리
            for key, value in structured_filters.items():
                if key == "age_range":
                    filters_for_sql.append({"field": "age", "operator": "between", "value": value})
                # 소득 등 범위 필터 처리
                elif isinstance(value, dict) and ("min" in value or "max" in value or "gte" in value or "lte" in value):
                    min_val = value.get("min") or value.get("gte")
                    max_val = value.get("max") or value.get("lte")

                    if min_val is not None and max_val is not None:
                        filters_for_sql.append({"field": key, "operator": "between", "value": [min_val, max_val]})
                    elif min_val is not None:
                        filters_for_sql.append({"field": key, "operator": "gte", "value": min_val})
                    elif max_val is not None:
                        filters_for_sql.append({"field": key, "operator": "lte", "value": max_val})
                else:
                    filters_for_sql.append({"field": key, "operator": "in", "value": value})

            # Target Field 처리
            if target_field and target_field not in QPOLL_FIELD_TO_TEXT:
                is_specific_value_filter = False
                if target_field in VALUE_TRANSLATION_MAP:
                    for key in VALUE_TRANSLATION_MAP[target_field].keys():
                        if key == intent or (len(intent) < 10 and key in intent):
                            logging.info(f"🎯 타겟 필드 '{target_field}'를 값 필터 '{key}'로 변환 (Intent: {intent})")
                            filters_for_sql.append({"field": target_field, "operator": "eq", "value": key})
                            is_specific_value_filter = True
                            break
                
                if not is_specific_value_filter:
                    filters_for_sql.append({"field": target_field, "operator": "not_null", "value": "check"})
            
            if filters_for_sql:
                panel_ids, _ = search_welcome_objective(filters_for_sql, attempt_name="V3_Filter_Optimized")
                filtered_panel_ids = panel_ids
        
        # 검색 범위 설정
        if filtered_panel_ids:
            vector_search_k = max(len(filtered_panel_ids), user_limit * 5)
            vector_search_k = min(vector_search_k, 3000) 
        else:
            vector_search_k = max(user_limit * 5, 500)

        final_panel_ids = filtered_panel_ids
        vector_matched_ids = set() 

        is_structured_target = target_field and target_field not in QPOLL_FIELD_TO_TEXT
        
        # [Case A] 정형 데이터 타겟 + SQL 필터 존재
        if is_structured_target and filtered_panel_ids:
            logging.info(f"🎯 정형 데이터 타겟({target_field}) 감지 -> 벡터 검색 없이 SQL 결과({len(filtered_panel_ids)}명) 사용")
            final_panel_ids = filtered_panel_ids
            
        # [Case B] 벡터 검색 필요
        elif intent and target_field:
            qdrant_client = get_qdrant_client()
            embeddings = initialize_embeddings()
            query_vector = embeddings.embed_query(intent)
            
            is_welcome_collection = False
            target_question_text = None 

            if target_field in QPOLL_FIELD_TO_TEXT:
                collection_name = "qpoll_vectors_v2"
                id_key_path = "panel_id"
                target_question_text = QPOLL_FIELD_TO_TEXT[target_field]
            else:
                collection_name = "welcome_subjective_vectors"
                id_key_path = "metadata.panel_id"
                is_welcome_collection = True

            negative_patterns = get_negative_patterns(target_field)

            # ------------------------------------------------------------------
            # [분기 1] SQL 필터 결과가 있음 -> Reranking (전수 조사)
            # ------------------------------------------------------------------
            if filtered_panel_ids:
                logging.info(f"🚀 Reranking 모드 진입: {len(filtered_panel_ids)}명 대상 정밀 검사")
                
                reranked_ids = rerank_candidates(
                    candidate_ids=list(filtered_panel_ids),
                    query_vector=query_vector,
                    qdrant_client=qdrant_client,
                    collection_name=collection_name,
                    id_key_path=id_key_path,
                    negative_patterns=negative_patterns,
                    target_question=target_question_text 
                )
                
                vector_matched_ids = set(reranked_ids)
                logging.info(f"✅ Reranking 완료: {len(filtered_panel_ids)}명 -> {len(vector_matched_ids)}명 (부정 답변 제외됨)")

            # ------------------------------------------------------------------
            # [분기 2] SQL 필터 결과가 없음 -> 일반 벡터 검색 (기존 로직)
            # ------------------------------------------------------------------
            else:
                logging.info("🔍 일반 벡터 검색 모드 진입 (SQL 필터 없음)")
                must_conditions = []
                
                # 일반 검색에서도 특수문자 이슈가 있을 수 있으나, 
                # 대량 검색이므로 속도를 위해 DB 필터를 유지하되, 검색이 안 되면 필터 없이 시도하는 로직 추가 가능
                # (여기서는 기존 로직 유지)
                if target_question_text:
                     must_conditions.append(FieldCondition(key="question", match=MatchText(text=target_question_text)))

                qdrant_filter = Filter(must=must_conditions)

                search_results = []
                try:
                    search_results = qdrant_client.search(
                        collection_name=collection_name, 
                        query_vector=query_vector,
                        query_filter=qdrant_filter,
                        limit=vector_search_k,
                        with_payload=True 
                    )
                except Exception as e:
                    logging.error(f"❌ Qdrant 검색 실패: {e}")
                    search_results = []

                valid_hits_count = 0
                
                for hit in search_results:
                    if not hit.payload: continue
                    
                    answer_text = hit.payload.get('page_content') or hit.payload.get('sentence') or ""

                    is_negative = False
                    for pattern in negative_patterns:
                        if re.search(pattern, answer_text):
                            is_negative = True
                            break 
                    
                    if is_negative: continue

                    pid = None
                    if is_welcome_collection:
                        meta = hit.payload.get('metadata', {})
                        pid = meta.get('panel_id')
                    else:
                        pid = hit.payload.get('panel_id')
                    
                    if pid:
                        vector_matched_ids.add(pid)
                        valid_hits_count += 1
                
                logging.info(f"   ✂️ 텍스트 필터링 결과: 검색 {len(search_results)}명 -> 유효 {valid_hits_count}명")
                
                # [검증 2] 벡터 기반 부정 조건 필터링
                if negative_conditions and vector_matched_ids:
                     neg_keywords = []
                     for nc in negative_conditions:
                         neg_keywords.extend(nc.get('expanded_queries', []))
                     
                     if neg_keywords:
                         logging.info(f"🚫 부정 조건 필터링 적용 (벡터): {neg_keywords}")
                         neg_vectors = embed_keywords(neg_keywords)
                         vector_matched_ids = filter_negative_conditions(
                             panel_ids=vector_matched_ids,
                             negative_keywords=neg_keywords,
                             query_vectors=neg_vectors,
                             qdrant_client=qdrant_client,
                             collection_name=collection_name,
                             threshold=0.55 
                         )
                         logging.info(f"   ✂️ 벡터 부정 필터링 후 남은 인원: {len(vector_matched_ids)}명")

            final_panel_ids = vector_matched_ids

        else:
            logging.debug("  - 의도/타겟 없음. 1차 필터 결과 사용.")
            final_panel_ids = filtered_panel_ids

        final_panel_ids_list = list(final_panel_ids)
        logging.info(f"✅ 검색 완료: {len(final_panel_ids_list)}명")

        return {
            "final_panel_ids": final_panel_ids_list,
            "total_count": len(final_panel_ids_list),
            "search_intent": intent,
            "target_field": target_field,
            "target_field_desc": target_desc
        }

    except Exception as e:
        logging.error(f"❌ hybrid_search 오류: {e}", exc_info=True)
        return {
            "final_panel_ids": [],
            "total_count": 0,
            "search_intent": "",
            "target_field": None,
            "target_field_desc": None
        }
