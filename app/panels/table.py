import asyncio
import re
from typing import Any, Dict, List

from app.panels.fields import QPOLL_ANSWER_TEMPLATES, QPOLL_FIELD_TO_TEXT
from app.panels.repository import PanelRepository, VectorRepository


# --- Helper Functions (유틸리티 함수) ---
def truncate_text(value: Any, max_length: int = 30) -> str:
    if value is None: return ""
    if isinstance(value, list):
        text = ", ".join(map(str, value))
    else:
        text = str(value)
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text


def extract_answer_from_template(field_name: str, sentence: str) -> str:
    if not sentence: return ""
    if field_name == "ott_count":
        match = re.search(r'(\d+개|이용 안 함|없음)', sentence)
        if match: return match.group(1)
    elif field_name == "skincare_spending":
        match = re.search(r'(\d+만\s*원|\d+~\d+만\s*원|\d+원)', sentence)
        if match: return match.group(1)

    template = QPOLL_ANSWER_TEMPLATES.get(field_name)
    if template:
        try:
            pattern_str = re.escape(template)
            pattern_str = pattern_str.replace(re.escape("{answer_str}"), r"(.*?)")
            pattern_str = pattern_str.replace(r"\(이\)다", r"(?:이)?다")
            pattern_str = pattern_str.replace(r"\(으\)로", r"(?:으)?로")
            pattern_str = pattern_str.replace(r"\(가\)", r"(?:가)?")
            pattern_str = pattern_str.replace(r"\ ", r"\s*")

            match = re.search(pattern_str, sentence)
            if match:
                extracted = match.group(1)
                cleaned = re.sub(r'\([^)]*\)', '', extracted).strip()
                return truncate_text(cleaned, 20)
        except: pass

    cleaned = re.sub(r'\([^)]*\)', '', str(sentence)).strip()
    return truncate_text(cleaned, 30)


async def get_ordered_welcome_data(ids_to_fetch: List[str], fields_to_fetch: List[str] = None) -> List[dict]:
    if not ids_to_fetch: return []
    table_data = []
    
    # Repository 호출
    results = await asyncio.to_thread(PanelRepository.fetch_ordered_table_data, ids_to_fetch)

    for row in results:
        panel_id_val, structured_data_val = row
        if not structured_data_val: continue
        
        display_data = {'panel_id': panel_id_val}
        if fields_to_fetch:
            for field in fields_to_fetch:
                if field != 'panel_id':
                    val = structured_data_val.get(field)
                    display_data[field] = truncate_text(val) 
        else:
            for k, v in structured_data_val.items():
                if k != 'panel_id':
                    display_data[k] = truncate_text(v)
        table_data.append(display_data)
        
    return table_data


async def get_qpoll_responses_for_table(ids_to_fetch: List[str], qpoll_fields: List[str]) -> Dict[str, Dict[str, str]]:
    if not ids_to_fetch or not qpoll_fields: return {}
    questions_to_fetch = [QPOLL_FIELD_TO_TEXT[f] for f in qpoll_fields if f in QPOLL_FIELD_TO_TEXT]
    if not questions_to_fetch: return {}

    def process_qpoll():
        qpoll_results = VectorRepository.fetch_qpoll_responses(ids_to_fetch, questions_to_fetch)
        
        result_map = {pid: {} for pid in ids_to_fetch}
        text_to_field_map = {v: k for k, v in QPOLL_FIELD_TO_TEXT.items()}
        
        for point in qpoll_results:
            pid = point.payload.get("panel_id")
            question = point.payload.get("question")
            sentence = point.payload.get("sentence")
            
            if pid and question and sentence:
                field_key = text_to_field_map.get(question)
                if field_key:
                    core_value = extract_answer_from_template(field_key, sentence)
                    result_map[pid][field_key] = core_value
        return result_map
        
    return await asyncio.get_running_loop().run_in_executor(None, process_qpoll)


def build_table_rows(welcome_table_data, qpoll_responses_map, welcome_fields, qpoll_fields, target_field):
    # Lite/Pro 엔드포인트에 똑같이 복사돼 있던 행 조립 루프를 한 곳으로 모았다 (로직 변경 없음)
    table_data = []
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
    return table_data
