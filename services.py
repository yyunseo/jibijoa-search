# services.py
import logging
import re
import asyncio
import time
from typing import List, Dict, Any, Tuple, Optional
from fastapi import Request, Response, HTTPException

from app.panels.repository import PanelRepository, VectorRepository
from insights import (
    get_ai_summary, 
    analyze_search_results_optimized as analyze_search_results,
    get_search_result_overview
)
from llm import parse_query_intelligent
from app.core.embeddings import initialize_embeddings
from search import hybrid_search
from mapping_rules import find_related_fields
from app.panels.fields import QPOLL_FIELD_TO_TEXT, QPOLL_ANSWER_TEMPLATES, VECTOR_CATEGORY_TO_FIELD
from app.core.postgres import get_db_connection_context
from app.core.qdrant import get_qdrant_client
from qdrant_client.http.models import Filter, FieldCondition, MatchValue, MatchAny
from app.panels.fields import FIELD_NAME_MAP



def custom_key_builder(func, namespace: str = "", *, request: Request = None, response: Response = None, **kwargs):
    if request:
        sorted_query_params = sorted(request.query_params.items())
        return ":".join([namespace, request.method.lower(), request.url.path, repr(sorted_query_params), func.__module__ + func.__name__])
    return ":".join([namespace, func.__module__ + func.__name__, repr(sorted(kwargs.items()))])

def preload_models():
    from semantic_router import router
    logging.info("="*70)
    logging.info("🔄 모든 AI 모델을 미리 로드합니다...")
    start = time.time()
    initialize_embeddings()
    try: router.find_closest_field("테스트 쿼리")
    except: pass
    logging.info(f"✅ 모델 로드 완료 ({time.time() - start:.2f}초)")

# --- Core Logic Functions (핵심 로직) ---
def _prepare_display_fields(classification: Dict, query_text: str = "") -> List[Dict]:
    relevant_fields = {"gender", "birth_year", "region_major"} 
    target_field = classification.get('target_field')
    
    is_qpoll_search = target_field and target_field in QPOLL_FIELD_TO_TEXT
    if is_qpoll_search:
        relevant_fields.update(["job_title_raw", "education_level", "income_household_monthly"])
    
    if target_field and target_field != 'unknown':
        relevant_fields.add(target_field)
        for category, fields in VECTOR_CATEGORY_TO_FIELD.items():
            if target_field in fields:
                relevant_fields.update(fields)
                break

    structured_filters = classification.get('structured_filters', {}) or classification.get('demographic_filters', {})
    filter_keys = []
    if isinstance(structured_filters, dict): filter_keys = structured_filters.keys()
    elif isinstance(structured_filters, list): filter_keys = [f.get('field') for f in structured_filters if f.get('field')]
    relevant_fields.update(filter_keys)

    if query_text:
        dynamic_fields = find_related_fields(query_text)
        relevant_fields.update(dynamic_fields)

    final_list = []
    if target_field and target_field != 'unknown':
        label = FIELD_NAME_MAP.get(target_field, target_field)
        if target_field in QPOLL_FIELD_TO_TEXT: label = QPOLL_FIELD_TO_TEXT[target_field]
        final_list.append({'field': target_field, 'label': label})
        relevant_fields.discard(target_field)

    for field in relevant_fields:
        if field in FIELD_NAME_MAP:
            final_list.append({'field': field, 'label': FIELD_NAME_MAP[field]})
            
    return final_list[:12]

async def _perform_common_search(query_text: str, search_mode: str, mode: str) -> Tuple[Dict, List[str], Dict]:
    logging.info(f"🔍 공통 검색 시작: {query_text} (모드: {search_mode}, 실행: {mode})")
    classification = parse_query_intelligent(query_text)
    user_limit = classification.get('limit', 100)
    
    search_results = await asyncio.to_thread(hybrid_search, query=query_text, limit=user_limit)
    
    panel_id_list = search_results.get('final_panel_ids', [])
    total_count = len(panel_id_list)
    classification['target_field'] = search_results.get('target_field')
    
    if mode == "lite":
        lite_response = {
            "query": query_text,
            "classification": classification,
            "total_count": total_count,
            "final_panel_ids": panel_id_list[:500],
            "effective_search_mode": "quota",
        }
        return lite_response, panel_id_list, classification

    pro_mode_info = {
        "query": query_text,
        "classification": classification,
        "search_results": search_results,
        "effective_search_mode": "quota",
        "final_panel_ids": panel_id_list
    }
    return pro_mode_info, panel_id_list, classification



