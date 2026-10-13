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
from app.query.parser import parse_query_intelligent
from app.core.embeddings import initialize_embeddings
from app.search.pipeline import hybrid_search
from app.query.field_matching import find_related_fields
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
    from app.query.router import get_router
    logging.info("="*70)
    logging.info("🔄 모든 AI 모델을 미리 로드합니다...")
    start = time.time()
    initialize_embeddings()
    try: get_router().find_closest_field("테스트 쿼리")
    except: pass
    logging.info(f"✅ 모델 로드 완료 ({time.time() - start:.2f}초)")





