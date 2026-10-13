import re
from collections import Counter
from typing import Any, Dict, List, Tuple


from app.panels.fields import (
    QPOLL_ANSWER_TEMPLATES,
    QPOLL_FIELD_TO_TEXT,
)
from app.panels.repository import PanelRepository, VectorRepository


def calculate_distribution(values: List[Any]) -> Dict[str, float]:
    """값 리스트의 분포를 백분율로 계산"""
    if not values:
        return {}
    counter = Counter(values)
    total = len(values)
    return {k: round((v / total) * 100, 1) for k, v in counter.most_common()}


def find_top_category(distribution: Dict[str, float]) -> Tuple[str, float]:
    """분포에서 가장 높은 비율의 카테고리와 비율 반환"""
    if not distribution:
        return ("없음", 0.0)
    return max(distribution.items(), key=lambda x: x[1])


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
