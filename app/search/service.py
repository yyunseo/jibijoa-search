import asyncio
import logging
from typing import Dict, List, Tuple

from app.query.parser import parse_query_intelligent
from app.search.pipeline import hybrid_search


async def perform_common_search(query_text: str, search_mode: str, mode: str) -> Tuple[Dict, List[str], Dict]:
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
