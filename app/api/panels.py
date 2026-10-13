import asyncio
import logging

from fastapi import APIRouter, HTTPException

from app.panels.detail import get_qpoll_data, get_welcome_data

router = APIRouter()


@router.get("/api/panels/{panel_id}")
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
