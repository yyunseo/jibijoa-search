from tests.golden import assert_golden
from tests.targets import sym

SQL_CASES = [
    [{"field": "drinking_experience", "operator": "not_null", "value": "check"}],
    [{"field": "smoking_experience", "operator": "not_null", "value": "check"}],
    [{"field": "ott_count", "operator": "not_null", "value": "check"}],
    [{"field": "children_count", "operator": "not_null", "value": "check"}],
    [{"field": "car_ownership", "operator": "not_null", "value": "check"}],
    [{"field": "age", "operator": "between", "value": [20, 29]}],
    [{"field": "gender", "operator": "in", "value": ["남성"]}],
    [{"field": "region_major", "operator": "in", "value": ["서울", "경기"]}],
    [{"field": "job_title_raw", "operator": "in", "value": ["직장인"]}],
    [{"field": "smoking_experience", "operator": "in", "value": ["흡연"]}],
    [{"field": "drinking_experience", "operator": "in", "value": ["있음"]}],
    [{"field": "income_household_monthly", "operator": "gte", "value": 5000000}],
    [{"field": "income_personal_monthly", "operator": "between", "value": [2000000, 3500000]}],
    [{"field": "income_personal_monthly", "operator": "lte", "value": 50}],
    [{"field": "children_count", "operator": "gte", "value": 1}],
    [{"field": "family_size", "operator": "in", "value": ["1", "2"]}],
    [{"field": "family_size", "operator": "eq", "value": "3"}],
    [{"field": "marital_status", "operator": "eq", "value": "미혼"}],
    [{"field": "education_level", "operator": "like", "value": "대학"}],
    [{"field": "gender", "operator": "in", "value": ["여성"]}, {"field": "age", "operator": "between", "value": [30, 39]}],
    [],
    [{"field": None, "operator": "eq", "value": "x"}],
]


def _safe(fn, *args, **kwargs):
    try:
        return {"ok": fn(*args, **kwargs)}
    except Exception as e:  # 예외도 기존 동작의 일부로 기록한다
        return {"error": type(e).__name__}


def test_build_sql(env):
    build = sym("build_sql")
    assert_golden("pure_build_sql", [{"filters": c, "result": _safe(build, c)} for c in SQL_CASES])


TEMPLATE_CASES = [
    ("ott_count", "현재 OTT서비스를 2개 이용 중이다."),
    ("ott_count", "현재 OTT서비스를 이용 안 함 이용 중이다."),
    ("skincare_spending", "한 달 기준으로 스킨케어 제품에 평균 3만 원만큼 소비한다."),
    ("stress_relief_method", "스트레스를 해소하는데 주로 사용하는 방법은 운동(헬스 포함)이다."),
    ("moving_stress_factor", "이사할 때 짐 정리로 가장 스트레스 받는다."),
    ("pet_experience", "반려동물을 키우고 있다."),
    ("unknown_field", "아주아주아주아주 긴 문장이라서 서른 글자를 넘어가면 잘려야 하는 문장입니다"),
    ("ott_count", ""),
]


def test_extract_answer_from_template(env):
    fn = sym("extract_answer_from_template")
    assert_golden("pure_extract_answer", [{"case": c, "out": fn(*c)} for c in TEMPLATE_CASES])


DISPLAY_CASES = [
    ({"target_field": "ott_count", "demographic_filters": {"region_major": ["서울"]}}, "서울 OTT 이용자"),
    ({"target_field": "smoking_experience", "demographic_filters": {"gender": ["남성"]}}, "남성 흡연자"),
    ({"target_field": "unknown"}, "자동차 있는 사람"),
    ({"target_field": None, "structured_filters": [{"field": "income_household_monthly"}]}, "소득 높은 여행 좋아하는 사람"),
    ({}, ""),
]


def test_prepare_display_fields(env):
    fn = sym("prepare_display_fields")
    assert_golden("pure_display_fields", [{"cls": c, "q": q, "out": fn(dict(c), query_text=q)} for c, q in DISPLAY_CASES])


def test_field_mapping_and_patterns(env):
    keywords = ["흡연", "OTT", "남성", "여자", "반려동물", "스트레스", "자동차", "소득", "없는키워드"]
    assert_golden("pure_field_mapping", {
        "mapping": {k: sym("get_field_mapping")(k) for k in keywords},
        "negative": {f: sym("get_negative_patterns")(f) for f in ["ott_count", "smoking_experience", "pet_experience", "unknown"]},
        "related": {q: sorted(sym("find_related_fields")(q)) for q in ["여행 좋아하는 사람", "자동차 소득", "OTT 이용 개수", "자녀 있는 결혼"]},
    })


def test_age_and_distribution(env):
    assert_golden("pure_age_distribution", {
        "age": {str(y): sym("get_age_group")(y) for y in [2010, 2007, 2006, 1997, 1987, 1977, 1967, 1950, "abc", None]},
        "dist": sym("calculate_distribution")(["a", "b", "a", "c", "a"]),
        "dist_empty": sym("calculate_distribution")([]),
        "top": sym("find_top_category")({"x": 10.0, "y": 70.0}),
        "top_empty": sym("find_top_category")({}),
    })
