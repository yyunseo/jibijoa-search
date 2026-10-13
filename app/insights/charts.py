import logging
from collections import Counter, defaultdict
from typing import Dict, List


from app.panels.age import get_age_group
from app.panels.fields import (
    QPOLL_ANSWER_TEMPLATES,
    QPOLL_FIELD_TO_TEXT,
)
from app.insights.distributions import (
    _clean_label,
    _limit_distribution_top_k,
    _sort_distribution,
    calculate_distribution,
    find_top_category,
    get_field_distribution_from_db,
    get_qpoll_distribution_from_db,
)


def create_chart_data_optimized(
    keyword: str,
    field_name: str,
    korean_name: str,
    panels_data: List[Dict],
    use_full_db: bool = False,
    max_categories: int = 50
) -> Dict:
    """차트 데이터 생성 (SQL 집계 우선)"""
    
    # 1. DB 전체 집계가 필요한 경우 (나이, 자녀 수 등)
    if use_full_db or field_name == "children_count":
        logging.info(f"       → DB 집계로 '{field_name}' 분석")
        distribution = get_field_distribution_from_db(field_name, max_categories)
        if not distribution: return {"topic": korean_name, "ratio": "0.0%", "chart_data": [], "description": "데이터 없음"}
        
        cleaned_distribution = defaultdict(float)
        for k, v in distribution.items(): cleaned_distribution[_clean_label(k)] += v
        
        final_distribution = _limit_distribution_top_k(dict(cleaned_distribution), k=8)
        top_category, top_ratio = find_top_category(final_distribution)
        
        return {
            "topic": f"{korean_name} 분포",
            "description": f"전체 기준: {top_ratio}%가 '{top_category}'입니다.",
            "ratio": f"{top_ratio}%",
            "chart_data": [{"label": korean_name, "values": final_distribution}],
            "field": field_name 
        }

    # 2. 검색 결과 내 집계 (리스트형 필드 등)
    else:
        values = []
        
        if field_name == 'birth_year':
            values = [get_age_group(item.get(field_name)) for item in panels_data if item.get(field_name)]
        else:
            raw_values = [item.get(field_name) for item in panels_data if item.get(field_name)]
            for val in raw_values:
                if isinstance(val, list):
                    for v in val:
                        cleaned = _clean_label(v)
                        if cleaned: values.append(cleaned)
                elif val is not None:
                    cleaned = _clean_label(val)
                    if cleaned: values.append(cleaned)
        
        if not values: return {"topic": korean_name, "description": "데이터 부족", "ratio": "0.0%", "chart_data": [], "field": field_name}
        
        distribution = calculate_distribution(values)
        final_distribution = _limit_distribution_top_k(distribution, k=12)
        top_category, top_ratio = find_top_category(final_distribution)
        
        return {
            "topic": f"{korean_name} 분포",
            "description": f"검색 결과: {top_ratio}%가 '{top_category}'입니다.",
            "ratio": f"{top_ratio}%",
            "chart_data": [{"label": korean_name, "values": final_distribution}],
            "field": field_name
        }


def create_qpoll_chart_data(qpoll_field: str, max_categories: int = 50) -> Dict:
    """Q-Poll 차트 데이터 생성"""
    question_text = QPOLL_FIELD_TO_TEXT.get(qpoll_field, qpoll_field) 
    distribution = get_qpoll_distribution_from_db(qpoll_field, max_categories)
    
    if not distribution: return {"topic": question_text, "ratio": "0.0%", "chart_data": [], "description": "데이터 없음", "field": qpoll_field}
    
    top_category, top_ratio = find_top_category(distribution)
    
    template = QPOLL_ANSWER_TEMPLATES.get(qpoll_field)
    if template and top_category != "기타":
        try:
            formatted_answer = template.format(answer_str=f"'{top_category}'")
            description = f"가장 많은 응답자는 {formatted_answer} ({top_ratio}%)"
        except: description = f"가장 많은 응답은 '{top_category}'({top_ratio}%)입니다."
    else: description = f"가장 많은 응답은 '{top_category}'({top_ratio}%)입니다."

    return {
        "topic": question_text, 
        "description": description,
        "ratio": f"{top_ratio}%",
        "chart_data": [{"label": question_text, "values": distribution}],
        "field": qpoll_field
    }


def create_crosstab_chart(
    panels_data: List[Dict],
    field1: str,
    field2: str,
    field1_korean: str,
    field2_korean: str,
    max_categories: int = 5
) -> Dict:
    """교차 분석 차트 생성"""
    logging.info(f"       → 교차 분석: '{field1}' vs '{field2}'")
    
    all_values_field2 = []
    for item in panels_data:
        val2 = item.get(field2)
        if not val2: continue
        
        if isinstance(val2, list):
            for v in val2:
                cleaned = _clean_label(v)
                if cleaned: all_values_field2.append(cleaned)
        else:
            cleaned = _clean_label(val2)
            if cleaned: all_values_field2.append(cleaned)
            
    if not all_values_field2:
        return {}

    global_counter = Counter(all_values_field2)
    top_7_keys = [k for k, v in global_counter.most_common(7)]
    top_7_set = set(top_7_keys)

    crosstab_data = {} 

    for item in panels_data:
        val1 = item.get(field1)
        val2 = item.get(field2)
        
        if val1 is None or val2 is None: continue

        raw_key1 = get_age_group(val1) if field1 == 'birth_year' else str(val1)
        key1 = _clean_label(raw_key1)
        
        if key1 not in crosstab_data:
            crosstab_data[key1] = []
            
        values_to_process = val2 if isinstance(val2, list) else [val2]
        
        for v in values_to_process:
            cleaned_v = _clean_label(v)
            if not cleaned_v: continue
            
            if cleaned_v in top_7_set:
                crosstab_data[key1].append(cleaned_v)
            else:
                crosstab_data[key1].append("기타")

    if not crosstab_data:
        return {}

    # Pie Chart
    if len(crosstab_data) <= 1:
        only_group = list(crosstab_data.keys())[0]
        distribution = calculate_distribution(crosstab_data[only_group])
        final_distribution = _sort_distribution(distribution)
        
        return {
            "topic": f"{field1_korean}별 {field2_korean} 분포 ({only_group})",
            "description": f"'{only_group}' 집단의 '{field2_korean}' 분포입니다.",
            "chart_type": "pie", 
            "chart_data": [{"label": field2_korean, "values": final_distribution}],
            "fields": [field1, field2]
        }

    # Bar Chart
    chart_values = {}
    sorted_groups = sorted(crosstab_data.keys(), key=lambda k: len(crosstab_data[k]), reverse=True)
    target_groups = sorted_groups[:max_categories]

    for group in target_groups:
        items = crosstab_data[group]
        distribution = calculate_distribution(items)
        chart_values[group] = _limit_distribution_top_k(distribution, k=7)

    return {
        "topic": f"{field1_korean}별 {field2_korean} 분포",
        "description": f"'{field1_korean}'에 따른 주요 '{field2_korean}' 분포입니다.",
        "chart_type": "crosstab",
        "chart_data": [{"label": f"{field1_korean}별 {field2_korean}", "values": chart_values}],
        "fields": [field1, field2] 
    }
