import os
import logging
import re 
import pandas as pd
from typing import List, Dict, Any, Tuple
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
from sklearn.cluster import DBSCAN

# --- LLM 관련 ---
from llm import generate_stats_summary, generate_demographic_summary

# --- Repository & Helpers ---
from app.panels.repository import PanelRepository, VectorRepository
from app.core.embeddings import initialize_embeddings 
from utils import calculate_distribution, find_top_category
from app.panels.age import get_age_group
from app.panels.fields import WELCOME_OBJECTIVE_FIELDS

# --- Mappings & Rules ---
from app.query.field_matching import get_field_mapping, find_target_columns_dynamic
from app.panels.fields import (
    QPOLL_FIELD_TO_TEXT,
    QPOLL_ANSWER_TEMPLATES,
    VALUE_TRANSLATION_MAP,
    FIELD_NAME_MAP,
    FIELD_ALIAS_MAP,
)
from app.query.router import get_router

def _clean_label(text: Any, max_length: int = 25) -> str:
    """라벨 정제 함수"""
    if not text: return ""
    text_str = str(text)
    cleaned = re.sub(r'\([^)]*\)', '', text_str).strip()
    cleaned = " ".join(cleaned.split())
    if len(cleaned) > max_length:
        return cleaned[:max_length] + ".."
    return cleaned

def _extract_core_value(field_name: str, sentence: str) -> str:
    """문장형 데이터에서 핵심 답변만 추출"""
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
                return _clean_label(match.group(1))
        except: pass

    return _clean_label(sentence)

def _limit_distribution_top_k(distribution: Dict[str, float], k: int = 10) -> Dict[str, float]:
    """[막대 차트용] 상위 K개만 남기고 나머지는 '기타'로 합칩니다."""
    if not distribution or len(distribution) <= k:
        return distribution
    sorted_items = sorted(distribution.items(), key=lambda x: x[1], reverse=True)
    top_items = dict(sorted_items[:k])
    other_sum = sum(v for _, v in sorted_items[k:])
    if other_sum > 0:
        top_items['기타'] = round(other_sum, 1)
    return top_items

def _sort_distribution(distribution: Dict[str, float]) -> Dict[str, float]:
    """[원형 차트용] '기타'로 묶지 않고 전체를 내림차순 정렬하여 반환합니다."""
    if not distribution: return {}
    return dict(sorted(distribution.items(), key=lambda x: x[1], reverse=True))

def get_field_distribution_from_db(field_name: str, limit: int = 50) -> Dict[str, float]:
    """PostgreSQL 집계 (Repository 위임)"""
    
    if field_name == "birth_year":
        query = f"""
            WITH age_groups AS (
                SELECT 
                    CASE 
                        WHEN (date_part('year', CURRENT_DATE) - (structured_data->>'birth_year')::int) < 20 THEN '10대'
                        WHEN (date_part('year', CURRENT_DATE) - (structured_data->>'birth_year')::int) < 30 THEN '20대'
                        WHEN (date_part('year', CURRENT_DATE) - (structured_data->>'birth_year')::int) < 40 THEN '30대'
                        WHEN (date_part('year', CURRENT_DATE) - (structured_data->>'birth_year')::int) < 50 THEN '40대'
                        WHEN (date_part('year', CURRENT_DATE) - (structured_data->>'birth_year')::int) < 60 THEN '50대'
                        ELSE '60대 이상'
                    END as age_group
                FROM welcome_meta2
                WHERE structured_data->>'birth_year' IS NOT NULL
            )
            SELECT age_group, COUNT(*), ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1)
            FROM age_groups GROUP BY age_group ORDER BY 3 DESC LIMIT {limit}
        """
    elif field_name == "children_count":
        query = f"""
            SELECT 
                CONCAT((structured_data->>'{field_name}')::numeric::int, '명') as val, 
                COUNT(*) as count,
                ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) as percentage
            FROM welcome_meta2
            WHERE structured_data->>'{field_name}' IS NOT NULL
            GROUP BY val ORDER BY percentage DESC LIMIT {limit}
        """
    else:
        query = f"""
            SELECT structured_data->>'{field_name}', COUNT(*), ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1)
            FROM welcome_meta2 WHERE structured_data->>'{field_name}' IS NOT NULL
            GROUP BY 1 ORDER BY 3 DESC LIMIT {limit}
        """
    
    return PanelRepository.aggregate_field(query)
    
def get_qpoll_distribution_from_db(qpoll_field: str, limit: int = 50) -> Dict[str, float]:
    """Qdrant 집계 (Repository 위임)"""
    question_text = QPOLL_FIELD_TO_TEXT.get(qpoll_field)
    if not question_text: return {}
    
    all_points = VectorRepository.fetch_qpoll_by_question(question_text)
    
    if not all_points: return {}
    extracted_values = []
    
    for p in all_points:
        if p.payload and p.payload.get("sentence"):
            raw_sentence = p.payload.get("sentence")
            core_val = _extract_core_value(qpoll_field, raw_sentence)
            if core_val: extracted_values.append(core_val)
    
    if not extracted_values: return {}
    
    val_counts = Counter(extracted_values)
    total = len(extracted_values)
    return {k: round((v / total) * 100, 1) for k, v in val_counts.most_common(limit)}

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

def calculate_column_stats(df: pd.DataFrame, columns: List[str]) -> str:
    """
    DataFrame에서 특정 컬럼들의 분포를 계산하여 텍스트로 반환합니다.
    """
    stats_report = []
    
    for col in columns:
        if col not in df.columns:
            continue
            
        korean_name = FIELD_NAME_MAP.get(col, QPOLL_FIELD_TO_TEXT.get(col, col))
        
        try:
            # 결측치 제외
            valid_series = df[col].dropna()
            total_count = len(valid_series)
            if total_count == 0:
                continue

            # 리스트형 데이터 처리
            if valid_series.apply(lambda x: isinstance(x, list)).any():
                exploded = valid_series.explode()
                counts = exploded.value_counts().head(5)
            else:
                counts = valid_series.value_counts().head(5)

            report_lines = [f"\n📌 [{korean_name}] ({col}) 분포 (상위 5개):"]
            for val, count in counts.items():
                percent = (count / len(df)) * 100 # 전체 모수 대비 비율
                report_lines.append(f"  - {val}: {count}명 ({percent:.1f}%)")
            
            stats_report.append("\n".join(report_lines))
            
        except Exception as e:
            logging.error(f"통계 계산 중 에러 ({col}): {e}")
            
    return "\n".join(stats_report)

async def get_ai_summary(panel_ids: List[str], question: str):
    """
    1. Repository에서 데이터 로드
    2. 동적 매핑 (질문 -> 컬럼)
    3. 통계 계산 (Python)
    4. LLM 요약 생성
    """
    target_ids = panel_ids[:1000]
    
    panels_data = PanelRepository.fetch_panels_data(target_ids)
    
    if not panels_data:
        return {"summary": "분석할 데이터가 없습니다.", "used_fields": []}

    df = pd.DataFrame(panels_data)
    target_columns = find_target_columns_dynamic(question)
    
    if not target_columns:
        stats_context = calculate_column_stats(df, ['gender', 'birth_year', 'region_major'])
        target_columns = ['기본 인구통계']
    else:
        stats_context = calculate_column_stats(df, target_columns)

    summary_text = generate_stats_summary(question, stats_context)

    return {
        "summary": summary_text,
        "used_fields": target_columns
    }

async def get_search_result_overview(query: str, panel_ids: List[str], classification: Dict) -> str:
    """
    Lite 모드 검색 결과에 대한 텍스트 요약을 생성합니다.
    """
    if not panel_ids:
        return "검색된 패널이 없습니다."

    sample_ids = panel_ids[:1000]
    
    panels_data = PanelRepository.fetch_panels_data(sample_ids)
    
    if not panels_data:
        return "데이터를 불러올 수 없습니다."

    df = pd.DataFrame(panels_data)
    
    stats_context = [] 
    
    # 1. 타겟 필드 통계
    target_field = classification.get('target_field')
    if target_field and target_field in df.columns:
        counts = df[target_field].value_counts(normalize=True).head(3)
        if not counts.empty:
            korean_name = FIELD_NAME_MAP.get(target_field, target_field)
            items_str = []
            for val, ratio in counts.items():
                items_str.append(f"{val}({ratio*100:.1f}%)")
            distribution_desc = ", ".join(items_str)
            stats_context.append(f"[{korean_name} 분포]: {distribution_desc}")

    # 2. 인구통계 (성별, 연령, 지역)
    demos = ['gender', 'region_major']
    if 'birth_year' in df.columns:
        df['age_group'] = df['birth_year'].apply(lambda x: get_age_group(x) if x else None)
        age_counts = df['age_group'].value_counts(normalize=True)
        top_ages = age_counts.head(3)
        if not top_ages.empty:
            age_desc = []
            for age, ratio in top_ages.items():
                age_desc.append(f"{age}({ratio*100:.1f}%)")
            stats_context.append(f"[연령대 분포]: {', '.join(age_desc)}")

    for col in demos:
        if col in df.columns:
            top = df[col].value_counts(normalize=True).head(1)
            if not top.empty:
                val, ratio = top.index[0], top.values[0]
                feature = f"{val} ({ratio*100:.1f}%)"
                if ratio >= 0.5: feature += " - 과반수 이상"
                col_name = FIELD_NAME_MAP.get(col, col)
                stats_context.append(f"[{col_name}]: {feature}")

    # 3. 소득 수준
    if 'income_personal_monthly' in df.columns:
        top_income = df['income_personal_monthly'].value_counts(normalize=True).head(1)
        if not top_income.empty and top_income.values[0] > 0.3:
             stats_context.append(f"[주요 소득구간]: {top_income.index[0]} ({top_income.values[0]*100:.1f}%)")

    full_stats_text = "\n".join(stats_context)
    summary = generate_demographic_summary(query, full_stats_text, len(panel_ids))
    
    return summary

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

def _analyze_fields_in_parallel(panels_data: List[Dict], candidate_fields: List[Tuple[str, str]]) -> List[Dict]:
    """병렬 필드 분석"""
    field_values = {fname: [] for fname, _ in candidate_fields}
    field_map = dict(candidate_fields)

    for item in panels_data:
        for fname in field_values.keys():
            val = item.get(fname)
            if val is None: continue

            if fname == "birth_year":
                field_values[fname].append(get_age_group(val))
            elif isinstance(val, list):
                for v in val:
                    cleaned = _clean_label(v)
                    if cleaned: field_values[fname].append(cleaned)
            else:
                cleaned = _clean_label(val)
                if cleaned: field_values[fname].append(cleaned)

    results = []
    for fname, vals in field_values.items():
        if not vals: continue
        try:
            dist = calculate_distribution(vals)
            final_dist = _sort_distribution(dist)
            if not final_dist: continue
            
            results.append({
                "field": fname,
                "korean_name": field_map[fname],
                "distribution": final_dist,
            })
        except: pass
    return results

def find_high_ratio_fields_optimized(
    panels_data: List[Dict], 
    exclude_fields: List[str], 
    threshold: float = 50.0,
    max_charts: int = 3
) -> List[Dict]:
    """높은 비율 필드 찾기 (98% 이상 제외)"""
    candidate_fields = []
    for fname, kname in WELCOME_OBJECTIVE_FIELDS:
        if fname not in exclude_fields:
            candidate_fields.append((fname, kname))
    
    if not candidate_fields: return []
    
    analysis_results = _analyze_fields_in_parallel(panels_data, candidate_fields)
    
    high_ratio_results = []
    for result in analysis_results:
        distribution = result['distribution']
        top_category, top_ratio = find_top_category(distribution)
        
        if top_ratio >= threshold:
            if top_ratio >= 98.0:
                continue

            high_ratio_results.append({
                "field": result['field'],
                "korean_name": result['korean_name'],
                "distribution": distribution,
                "top_category": top_category,
                "top_ratio": top_ratio
            })
    
    high_ratio_results.sort(key=lambda x: x["top_ratio"], reverse=True)
    return high_ratio_results[:max_charts]

def analyze_search_results_optimized(
    query: str,
    classified_keywords: dict,
    panel_id_list: List[str]
) -> Tuple[Dict, int]:
    logging.info(f"📊 분석 시작 (최적화) - panel_id 수: {len(panel_id_list)}개")
    
    if not panel_id_list:
        return {"main_summary": "검색 결과가 없습니다.", "charts": []}, 200
    
    try:
        panels_data = PanelRepository.fetch_panels_data(panel_id_list)

        if not panels_data: return {"main_summary": "데이터 없음", "charts": []}, 200
        fixed_filters = set()
        
        # 1. Demographic Filters 확인
        demographic_filters = classified_keywords.get('demographic_filters', {})
        if demographic_filters:
            for k, v in demographic_filters.items():
                if not isinstance(v, list) or len(v) == 1:
                    fixed_filters.add(k)
                    mapped_field = FIELD_ALIAS_MAP.get(k)
                    if mapped_field: fixed_filters.add(mapped_field)

        # 2. Structured Filters 확인
        structured_filters = classified_keywords.get('structured_filters', [])
        for f in structured_filters:
            if f.get('operator') in ['eq', 'like', 'ilike']: 
                 if f.get('field'): fixed_filters.add(f['field'])
    
        target_field = classified_keywords.get('target_field')
        
        if target_field:
            if target_field == 'job_duty_raw':
                logging.info(f"   🔄 대체 필드 적용: job_duty_raw -> job_title_raw")
                target_field = 'job_title_raw'
                classified_keywords['target_field'] = target_field
            elif target_field == 'region_major':
                logging.info(f"   🔄 대체 필드 적용: region_major -> region_minor")
                target_field = 'region_minor'
                classified_keywords['target_field'] = target_field
            elif target_field in ['income_personal_monthly', 'income_household_monthly']:
                logging.info(f"   🔄 대체 필드 적용: {target_field} -> happiest_self_spending")
                target_field = 'happiest_self_spending' 
                classified_keywords['target_field'] = target_field
            elif target_field == 'car_ownership':
                logging.info(f"   🔄 대체 필드 적용: car_ownership -> car_model_raw")
                target_field = 'car_model_raw'
                classified_keywords['target_field'] = target_field
            elif target_field == 'phone_brand_raw':
                logging.info(f"   🔄 대체 필드 적용: phone_brand_raw -> phone_model_raw")
                target_field = 'phone_model_raw'
                classified_keywords['target_field'] = target_field
            elif target_field == 'marital_status':
                logging.info(f"   🔄 대체 필드 적용: marital_status -> children_count")
                target_field = 'children_count'
                classified_keywords['target_field'] = target_field
            else:
                if target_field in fixed_filters:
                    logging.info(f"   🚫 '{target_field}'에 대한 대체 필드 없음 -> 타겟 해제하여 100% 차트 방지")
                    target_field = None 
                    classified_keywords['target_field'] = None

        
        raw_keywords = classified_keywords.get('ranked_keywords_raw', [])
        ranked_keywords = []
        search_used_fields = set()

        charts = []
        used_fields = [] 
        chart_tasks = []
        objective_fields = set([f[0] for f in WELCOME_OBJECTIVE_FIELDS])

        demographic_filters = classified_keywords.get('demographic_filters', {})
        if demographic_filters:
            if 'age_range' in demographic_filters: search_used_fields.add('birth_year')
            for key in demographic_filters: 
                if key != 'age_range': search_used_fields.add(key)

        if 'children_count' in demographic_filters or 'children_count' in search_used_fields:
            used_fields.append('marital_status')

        if 'region_major' in demographic_filters and 'region_minor' not in used_fields:
            logging.info("📍 지역 필터 감지 -> 세부 지역(region_minor) 분석 자동 추가")
            chart_tasks.append({
                "type": "filter",
                "kw_info": {
                    "field": "region_minor",
                    "description": "세부 지역 분포", 
                    "priority": 0 
                }
            })
            used_fields.append("region_minor")

        structured_filters = classified_keywords.get('structured_filters', [])
        for f in structured_filters:
            if f.get('field'): search_used_fields.add(f['field'])

        if raw_keywords:
            for i, kw in enumerate(raw_keywords):
                mapping = get_field_mapping(kw)
                ranked_keywords.append({
                    "keyword": kw, "field": mapping["field"], "description": mapping["description"],
                    "type": mapping.get("type", "unknown"), "priority": i + 10
                })
                if mapping.get("type") == 'filter' and mapping["field"] != 'unknown':
                    search_used_fields.add(mapping["field"])

        # 1. Main Target Field (0순위)
        if target_field and target_field != 'unknown' and target_field not in used_fields:
            if target_field in QPOLL_FIELD_TO_TEXT:
                chart_tasks.append({"type": "qpoll", "kw_info": {"field": target_field, "description": QPOLL_FIELD_TO_TEXT[target_field], "priority": 0}})
                used_fields.append(target_field)
            elif target_field in objective_fields:
                chart_tasks.append({"type": "filter", "kw_info": {"field": target_field, "description": FIELD_NAME_MAP.get(target_field, target_field), "priority": 0}})
                used_fields.append(target_field)

        # Q-Poll 타겟인 경우 기본 인구통계 자동 추가
        if target_field and target_field in QPOLL_FIELD_TO_TEXT:
            basic_demos = [('gender', '성별'), ('birth_year', '연령대'), ('region_major', '거주 지역')]
            for field, label in basic_demos:
                if field not in used_fields and field not in search_used_fields:
                    chart_tasks.append({
                        "type": "filter",
                        "kw_info": {"field": field, "description": label, "priority": 1}
                    })
                    used_fields.append(field)

        # 2. Semantic Conditions
        semantic_conditions = classified_keywords.get('semantic_conditions', [])
        for condition in semantic_conditions:
            original_keyword = condition.get('original_keyword')
            if not original_keyword: continue
            
            field_info = get_router().find_closest_field(original_keyword)
            if field_info:
                found_field = field_info['field']
                if found_field in used_fields: continue
                
                if found_field in fixed_filters:
                     continue

                logging.info(f"   💡 2차 의도 발견: '{original_keyword}' -> '{field_info['description']}' ({found_field})")
                
                if found_field in QPOLL_FIELD_TO_TEXT:
                    chart_tasks.append({"type": "qpoll", "kw_info": {"field": found_field, "description": QPOLL_FIELD_TO_TEXT[found_field], "priority": 1}})
                    used_fields.append(found_field)
                elif found_field in objective_fields:
                    chart_tasks.append({"type": "filter", "kw_info": {"field": found_field, "description": FIELD_NAME_MAP.get(found_field, found_field), "priority": 1}})
                    used_fields.append(found_field)

        # 3. 나머지 키워드
        for kw_info in ranked_keywords:
            if len(chart_tasks) >= 5: break
            field = kw_info.get('field', '')
            if field in used_fields: continue
            
            if field in fixed_filters:
                logging.info(f"🚫 키워드 차트 제외: '{field}'는 이미 필터로 고정됨")
                continue

            if kw_info.get('type') == 'qpoll':
                kw_info['priority'] = 2
                chart_tasks.append({"type": "qpoll", "kw_info": kw_info})
                used_fields.append(field)
            elif kw_info.get('type') == 'filter' and field not in search_used_fields:
                if field in objective_fields and field != 'unknown':
                    kw_info['priority'] = 2
                    chart_tasks.append({"type": "filter", "kw_info": kw_info})
                    used_fields.append(field)

        # 1인 가구 로직
        is_single_household = False
        fam_val = demographic_filters.get('family_size') or demographic_filters.get('household_size')
        if fam_val and (isinstance(fam_val, list) and any(str(v).startswith('1') for v in fam_val) or str(fam_val).startswith('1')): is_single_household = True
        if not is_single_household:
            for f in structured_filters:
                if f.get('field') in ['family_size', 'household_size']:
                    val = f.get('value')
                    if (isinstance(val, list) and any(str(v).startswith('1') for v in val) or str(val).startswith('1')): is_single_household = True
        if is_single_household: used_fields.append('income_household_monthly')

        # 차량 소유 비율 70% 이상 시 차종 차트 추가
        car_ownership_values = [p.get('car_ownership') for p in panels_data if p.get('car_ownership')]
        if car_ownership_values:
            flat_values = []
            car_map = VALUE_TRANSLATION_MAP.get('car_ownership', {}) 
            
            for v in car_ownership_values:
                if isinstance(v, list):
                    for sub_v in v:
                        cleaned = _clean_label(sub_v)
                        normalized = car_map.get(cleaned, cleaned)
                        flat_values.append(normalized)
                else:
                    cleaned = _clean_label(v)
                    normalized = car_map.get(cleaned, cleaned)
                    flat_values.append(normalized)
            
            car_dist = calculate_distribution(flat_values)
            if car_dist.get('있음', 0) >= 70.0:
                if 'car_model_raw' not in used_fields:
                    logging.info("🚗 차량 보유 비율 70% 이상 -> 차종(car_model_raw) 분석 자동 추가")
                    chart_tasks.append({
                        "type": "filter",
                        "kw_info": {
                            "field": "car_model_raw",
                            "description": "보유 차량 모델",
                            "priority": 1 
                        }
                    })
                    used_fields.append("car_model_raw")
                
                if 'car_ownership' not in used_fields:
                    used_fields.append("car_ownership")

        with ThreadPoolExecutor(max_workers=len(chart_tasks) or 1) as executor:
            futures = []
            for task in chart_tasks:
                kw = task['kw_info']
                if task['type'] == 'filter':
                    futures.append(executor.submit(create_chart_data_optimized, kw.get('keyword',''), kw.get('field'), kw.get('description'), panels_data))
                else:
                    futures.append(executor.submit(create_qpoll_chart_data, kw.get('field')))
                
                futures[-1].priority = kw.get('priority', 99)
            
            temp_results = []
            for future in as_completed(futures):
                try:
                    chart = future.result()
                    if chart.get('chart_data'):
                        temp_results.append((future.priority, chart))
                except: pass
            
            temp_results.sort(key=lambda x: x[0])
            charts.extend([res[1] for res in temp_results])

        # 교차 분석
        if len(charts) < 5:
            topic_info = None
            if target_field and target_field in used_fields:
                topic_info = {'field': target_field, 'description': QPOLL_FIELD_TO_TEXT.get(target_field, FIELD_NAME_MAP.get(target_field))}
            if not topic_info:
                for task in chart_tasks:
                    if task['type'] == 'qpoll':
                        topic_info = task['kw_info']
                        break
            
            if topic_info:
                t_field = topic_info['field']
                t_name = topic_info['description']
                axes = []
                standard_axes = [('birth_year','연령대'), ('gender','성별'), ('region_major','지역'), ('job_title_raw','직업')]
                for ax in standard_axes:
                    if ax[0] not in search_used_fields and ax[0] != t_field: axes.append(ax)
                for ax_field, ax_name in axes:
                    if len(charts) >= 5: break
                    crosstab = create_crosstab_chart(panels_data, ax_field, t_field, ax_name, t_name)
                    if crosstab and crosstab.get('chart_data'):
                        charts.append(crosstab)
                        used_fields.extend([ax_field, t_field])

        if len(charts) < 5:
            high_ratio = find_high_ratio_fields_optimized(panels_data, list(set(used_fields)|search_used_fields), max_charts=5-len(charts))
            for info in high_ratio:
                charts.append({"topic": f"{info['korean_name']} 분포", "description": f"{info['top_ratio']}%가 '{info['top_category']}'입니다.", "ratio": f"{info['top_ratio']}%", "chart_data": [{"label": info['korean_name'], "values": info['distribution']}]})

        return {
            "query": query, 
            "total_count": len(panels_data), 
            "main_summary": f"총 {len(panels_data)}명 데이터 분석 완료", 
            "charts": charts
        }, 200

    except Exception as e:
        logging.error(f"분석 중 오류: {e}", exc_info=True)
        return {"main_summary": "오류 발생", "charts": []}, 500

async def generate_dynamic_insight(panel_ids: List[str], target_field: str, field_desc: str) -> Dict:
    if not panel_ids or not target_field: return {}
    logging.info(f"📊 동적 인사이트 생성 중... (Field: {target_field})")
    
    panels_data = PanelRepository.fetch_panels_data(panel_ids)
    
    cleaned_answers = []
    for p in panels_data:
        val = p.get(target_field)
        if val:
            if isinstance(val, list):
                for v in val:
                    cleaned = _clean_label(v)
                    if cleaned: cleaned_answers.append(cleaned)
            else:
                cleaned = _clean_label(val)
                if cleaned: cleaned_answers.append(cleaned)
    
    if not cleaned_answers: return {"error": "데이터 부족"}

    unique_answers = list(set(cleaned_answers))
    chart_data = {}
    
    if len(unique_answers) <= 15:
        chart_data = calculate_distribution(cleaned_answers)
    else:
        chart_data = _group_answers_with_vectors(cleaned_answers, threshold=0.82)

    final_chart_data = _limit_distribution_top_k(chart_data, k=7)
    if not final_chart_data: return {}

    top_category, top_ratio = find_top_category(final_chart_data)
    
    return {
        "topic": f"{field_desc} 분석",
        "description": f"'{field_desc}'에 대해 '{top_category}'({top_ratio}%) 응답이 가장 많았습니다.",
        "ratio": f"{top_ratio}%",
        "chart_data": [{"label": field_desc, "values": final_chart_data}]
    }

def _group_answers_with_vectors(answers: List[str], threshold: float = 0.75) -> Dict[str, float]:
    if not answers: return {}
    embeddings_model = initialize_embeddings()
    unique_answers = list(set(answers))
    if len(unique_answers) < 2: return calculate_distribution(answers)

    try:
        vectors = embeddings_model.embed_documents(unique_answers)
        vectors = np.array(vectors)
        clustering = DBSCAN(eps=1-threshold, min_samples=1, metric='cosine').fit(vectors)
        labels = clustering.labels_
        
        cluster_map = {}
        for i, label in enumerate(labels):
            if label not in cluster_map: cluster_map[label] = []
            cluster_map[label].append(unique_answers[i])
            
        total_counts = Counter(answers)
        cluster_to_repr = {}
        for label, group_members in cluster_map.items():
            repr_word = max(group_members, key=lambda x: (total_counts[x], -len(x)))
            cluster_to_repr[label] = repr_word
            
        ans_to_label = {ans: labels[i] for i, ans in enumerate(unique_answers)}
        mapped_answers = [cluster_to_repr[ans_to_label[ans]] for ans in answers]
            
        return calculate_distribution(mapped_answers)
    except Exception as e:
        logging.error(f"벡터 클러스터링 실패: {e}", exc_info=True)
        return calculate_distribution(answers)