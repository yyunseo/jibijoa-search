from typing import Dict, List

from app.panels.fields import FIELD_NAME_MAP, QPOLL_FIELD_TO_TEXT, VECTOR_CATEGORY_TO_FIELD
from app.query.field_matching import find_related_fields


# --- Core Logic Functions (핵심 로직) ---
def prepare_display_fields(classification: Dict, query_text: str = "") -> List[Dict]:
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
