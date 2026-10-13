import logging
from collections import Counter
from typing import List, Dict, Any, Tuple
import datetime

from app.panels.fields import WELCOME_OBJECTIVE_FIELDS, QPOLL_FIELDS, FIELD_NAME_MAP
from app.panels.age import get_age_group



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

def extract_field_values(data: List[Dict], field_name: str) -> List[Any]:
    """데이터에서 특정 필드의 값들을 추출 (analysis.py에서 사용)"""
    values = []

    if field_name == "birth_year":
        values = [get_age_group(item.get(field_name, 0)) for item in data if item.get(field_name)]
    else:
        raw_values = [item.get(field_name) for item in data if item.get(field_name)]
        for val in raw_values:
            if isinstance(val, list):
                values.extend(val)
            elif val is not None:
                values.append(val)

    return [v for v in values if v is not None]
