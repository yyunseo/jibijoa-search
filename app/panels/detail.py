import asyncio
from typing import Dict

from fastapi import HTTPException

from app.panels.fields import QPOLL_FIELD_TO_TEXT
from app.panels.repository import PanelRepository, VectorRepository


async def get_welcome_data(panel_id: str) -> Dict:
    result = await asyncio.to_thread(PanelRepository.fetch_panel_detail, panel_id)
    if not result:
        raise HTTPException(status_code=404, detail="패널 정보를 찾을 수 없습니다.")
    return result


async def get_qpoll_data(panel_id: str) -> Dict:
    def process():
        q_data = {"qpoll_응답_개수": 0}
        res = VectorRepository.fetch_qpoll_for_panel(panel_id)
        
        if res:
            q_data["qpoll_응답_개수"] = len(res)
            txt_map = {v: k for k, v in QPOLL_FIELD_TO_TEXT.items()}
            for p in res:
                if p.payload:
                    q = p.payload.get("question")
                    s = p.payload.get("sentence")
                    if q and s:
                        k = txt_map.get(q)
                        if k: q_data[k] = s
        return q_data
    return await asyncio.get_running_loop().run_in_executor(None, process)
