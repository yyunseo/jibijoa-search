import asyncio
import logging
import time

from fastapi import APIRouter, HTTPException

from app.api.schemas import AnalysisRequest, SearchQuery
from app.insights.analysis import analyze_search_results_optimized as analyze_search_results
from app.insights.summary import get_search_result_overview
from app.panels.fields import QPOLL_FIELD_TO_TEXT
from app.panels.table import build_table_rows, get_ordered_welcome_data, get_qpoll_responses_for_table
from app.query.parser import parse_query_intelligent
from app.search.display import prepare_display_fields
from app.search.service import perform_common_search

router = APIRouter()


@router.post("/api/search")
async def search_panels(search_query: SearchQuery):
    logging.info(f"🚀 [Lite 모드] 빠른 검색 시작: {search_query.query}")
    try:
        start_time = time.time()
        
        lite_response, full_panel_ids, classification = await perform_common_search(
            search_query.query, 
            search_query.search_mode,
            mode="lite"
        )
        
        search_time = time.time() - start_time
        logging.info(f"⏱️  [Lite 모드] 검색 완료: {search_time:.2f}초")
        
        display_fields = prepare_display_fields(classification, query_text=search_query.query)
        ids_to_fetch = lite_response.get('final_panel_ids', [])
        
        field_keys = [f['field'] for f in display_fields]
        welcome_fields = [f for f in field_keys if f not in QPOLL_FIELD_TO_TEXT]
        qpoll_fields = [f for f in field_keys if f in QPOLL_FIELD_TO_TEXT]
        
        welcome_table_data, qpoll_responses_map = await asyncio.gather(
            get_ordered_welcome_data(ids_to_fetch, welcome_fields),
            get_qpoll_responses_for_table(ids_to_fetch, qpoll_fields)
        )
        
        target_field = classification.get('target_field')
        table_data = build_table_rows(welcome_table_data, qpoll_responses_map, welcome_fields, qpoll_fields, target_field)
        
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


@router.post("/api/search-and-analyze")
async def search_and_analyze(request: AnalysisRequest):
    logging.info(f"📊 [Pro 모드] 검색 + 분석 시작: {request.query}")
    try:
        pro_info, panel_ids, classification = await perform_common_search(request.query, request.search_mode, mode="pro")
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
        display_fields = prepare_display_fields(classification, query_text=request.query)
        
        field_keys = [f['field'] for f in display_fields]
        welcome_fields = [f for f in field_keys if f not in QPOLL_FIELD_TO_TEXT]
        qpoll_fields = [f for f in field_keys if f in QPOLL_FIELD_TO_TEXT]

        fetch_limit = max(user_limit * 2, 500) 
        ids_to_fetch = panel_ids[:fetch_limit]

        welcome_table_data, qpoll_responses_map = await asyncio.gather(
            get_ordered_welcome_data(ids_to_fetch, fields_to_fetch=welcome_fields),
            get_qpoll_responses_for_table(ids_to_fetch, qpoll_fields)
        )

        target_field = classification.get('target_field')
        table_data = build_table_rows(welcome_table_data, qpoll_responses_map, welcome_fields, qpoll_fields, target_field)
        
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


@router.post("/api/debug/classify")
async def debug_classify(search_query: SearchQuery):
    try:
        classification = parse_query_intelligent(search_query.query)
        return {"query": search_query.query, "classification": classification}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
