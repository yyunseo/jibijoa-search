# main.py
import logging
import os
import time
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from dotenv import load_dotenv

from schemas import (
    InsightRequest, 
    SearchQuery, 
    AnalysisRequest
)
from services import (
    custom_key_builder,
    preload_models,
    _perform_common_search,
    _prepare_display_fields,
)
from app.panels.detail import get_welcome_data, get_qpoll_data
from app.panels.table import get_ordered_welcome_data, get_qpoll_responses_for_table

from insights import (
    get_ai_summary, 
    analyze_search_results_optimized as analyze_search_results,
    get_search_result_overview
)
from app.query.parser import parse_query_intelligent
from app.panels.fields import QPOLL_FIELD_TO_TEXT
from app.core.postgres import init_db, cleanup_db, get_db_connection_context

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:     %(message)s'
)

load_dotenv()

app = FastAPI(title="Multi-Table Hybrid Search API v3 (Refactored)")

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

# --- Lifecycle Events ---
@app.on_event("startup")
async def startup_event():
    logging.info("🚀 FastAPI 시작...")
    FastAPICache.init(InMemoryBackend(), prefix="fastapi-cache", key_builder=custom_key_builder)
    init_db()
    preload_models()

@app.on_event("shutdown")
async def shutdown_event():
    logging.info("🧹 FastAPI 종료... Connection Pool 정리")
    cleanup_db()

# --- API Endpoints ---

@app.post("/api/insight/summary")
async def api_get_insight_summary(req: InsightRequest):
    if not req.panel_ids:
        raise HTTPException(status_code=400, detail="분석할 패널 데이터가 없습니다.")
    if not req.question:
        raise HTTPException(status_code=400, detail="질문 내용이 없습니다.")
    logging.info(f"📊 Insight 요청: '{req.question}' (대상: {len(req.panel_ids)}명)")
    try:
        result = await get_ai_summary(req.panel_ids, req.question)
        return result
    except Exception as e:
        logging.error(f"Insight 생성 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="요약 생성 중 오류가 발생했습니다.")

@app.post("/api/search")
async def search_panels(search_query: SearchQuery):
    logging.info(f"🚀 [Lite 모드] 빠른 검색 시작: {search_query.query}")
    try:
        start_time = time.time()
        
        lite_response, full_panel_ids, classification = await _perform_common_search(
            search_query.query, 
            search_query.search_mode,
            mode="lite"
        )
        
        search_time = time.time() - start_time
        logging.info(f"⏱️  [Lite 모드] 검색 완료: {search_time:.2f}초")
        
        display_fields = _prepare_display_fields(classification, query_text=search_query.query)
        ids_to_fetch = lite_response.get('final_panel_ids', [])
        
        field_keys = [f['field'] for f in display_fields]
        welcome_fields = [f for f in field_keys if f not in QPOLL_FIELD_TO_TEXT]
        qpoll_fields = [f for f in field_keys if f in QPOLL_FIELD_TO_TEXT]
        
        welcome_table_data, qpoll_responses_map = await asyncio.gather(
            get_ordered_welcome_data(ids_to_fetch, welcome_fields),
            get_qpoll_responses_for_table(ids_to_fetch, qpoll_fields)
        )
        
        table_data = []
        target_field = classification.get('target_field') 

        for welcome_row in welcome_table_data:
            pid = welcome_row.get('panel_id')
            if pid and pid in qpoll_responses_map:
                welcome_row.update(qpoll_responses_map[pid])
            
            is_valid_row = True
            if target_field in qpoll_fields:
                val = welcome_row.get(target_field)
                if not val or str(val).strip().lower() == 'nan': is_valid_row = False
            elif target_field in welcome_fields:
                val = welcome_row.get(target_field)
                if not val or str(val).strip().lower() == 'nan': is_valid_row = False

            for field in (welcome_fields + qpoll_fields):
                if field != target_field:
                    val = welcome_row.get(field)
                    if not val or str(val).strip().lower() == 'nan': welcome_row[field] = "-"

            if is_valid_row:
                table_data.append(welcome_row)
        
        user_limit = classification.get('limit', 100)
        final_limit = user_limit 
        lite_response['tableData'] = table_data[:final_limit] 
        lite_response['display_fields'] = display_fields
        lite_response['mode'] = "lite" 

        if 'final_panel_ids' in lite_response: del lite_response['final_panel_ids']
        return lite_response
    except Exception as e:
        logging.error(f"[Lite 모드] 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/search-and-analyze")
async def search_and_analyze(request: AnalysisRequest):
    logging.info(f"📊 [Pro 모드] 검색 + 분석 시작: {request.query}")
    try:
        pro_info, panel_ids, classification = await _perform_common_search(request.query, request.search_mode, mode="pro")
        user_limit = classification.get('limit', 100)

        results = await asyncio.gather(
            asyncio.to_thread(analyze_search_results, request.query, classification, panel_ids[:5000]),
            get_search_result_overview(query=request.query, panel_ids=panel_ids, classification=classification)
        )

        analysis_result_tuple = results[0] 
        summary_text = results[1]          
        
        if isinstance(analysis_result_tuple, tuple):
            analysis_result = analysis_result_tuple[0] 
        else:
            analysis_result = analysis_result_tuple

        charts = analysis_result.get('charts', []) if analysis_result else []
        display_fields = _prepare_display_fields(classification, query_text=request.query)
        
        field_keys = [f['field'] for f in display_fields]
        welcome_fields = [f for f in field_keys if f not in QPOLL_FIELD_TO_TEXT]
        qpoll_fields = [f for f in field_keys if f in QPOLL_FIELD_TO_TEXT]

        fetch_limit = max(user_limit * 2, 500) 
        ids_to_fetch = panel_ids[:fetch_limit]

        welcome_table_data, qpoll_responses_map = await asyncio.gather(
            get_ordered_welcome_data(ids_to_fetch, fields_to_fetch=welcome_fields),
            get_qpoll_responses_for_table(ids_to_fetch, qpoll_fields)
        )

        table_data = []
        target_field = classification.get('target_field')
        
        for welcome_row in welcome_table_data:
            pid = welcome_row.get('panel_id')
            if pid and pid in qpoll_responses_map:
                welcome_row.update(qpoll_responses_map[pid])
            
            is_valid_row = True
            if target_field in qpoll_fields:
                val = welcome_row.get(target_field)
                if not val or str(val).strip().lower() == 'nan': is_valid_row = False
            elif target_field in welcome_fields:
                val = welcome_row.get(target_field)
                if not val or str(val).strip().lower() == 'nan': is_valid_row = False
            
            for field in (welcome_fields + qpoll_fields):
                if field != target_field:
                    val = welcome_row.get(field)
                    if not val or str(val).strip().lower() == 'nan': welcome_row[field] = "-"

            if is_valid_row:
                table_data.append(welcome_row)
        
        response_data = {
            "query": pro_info["query"],
            "classification": classification,
            "display_fields": display_fields,
            "charts": charts,
            "search_summary": summary_text, 
            "tableData": table_data[:user_limit], 
            "total_count": len(panel_ids), 
            "mode": 'pro'
        }
        return response_data

    except Exception as e:
        logging.error(f"[Pro 모드] 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/debug/classify")
async def debug_classify(search_query: SearchQuery):
    try:
        classification = parse_query_intelligent(search_query.query)
        return {"query": search_query.query, "classification": classification}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/panels/{panel_id}")
async def get_panel_details(panel_id: str):
    try:
        logging.info(f"⚡️ 패널 상세 정보 병렬 조회 시작 (panel_id: {panel_id})")
        results = await asyncio.gather(get_welcome_data(panel_id), get_qpoll_data(panel_id), return_exceptions=True)
        panel_data, qpoll_data = {}, {}
        for result in results:
            if isinstance(result, HTTPException): raise result 
            elif isinstance(result, Exception): raise HTTPException(status_code=500, detail=f"조회 중 내부 오류 발생: {result}")
            if "qpoll_응답_개수" in result: qpoll_data = result
            else: panel_data = result
        panel_data.update(qpoll_data)
        return panel_data
    except HTTPException: raise
    except Exception as e:
        logging.error(f"패널 상세 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"조회 실패: {str(e)}")

@app.get("/")
def read_root():
    return {
        "service": "Multi-Table Hybrid Search & Analysis API",
        "version": "3.0 (Refactored)",
        "status": "running"
    }

@app.get("/health")
def health_check():
    try:
        with get_db_connection_context() as conn:
            db_status = "ok" if conn else "error"
        return {"status": "healthy", "database": db_status}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}