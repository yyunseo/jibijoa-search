import logging

from fastapi import APIRouter, HTTPException

from app.api.schemas import InsightRequest
from app.insights.summary import get_ai_summary

router = APIRouter()


@router.post("/api/insight/summary")
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
