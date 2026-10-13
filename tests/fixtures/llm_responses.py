import json

S1 = "서울 20대 남성 흡연자 30명"
S2 = "서울 경기 OTT 이용하는 젊은층 30명"
S3 = "스트레스 해소 방법으로 운동하는 사람"
S4 = "반려동물을 키우지 않는 OTT 이용자"
S5 = "응답 형식이 깨지는 질의"

PARSE_RESPONSES = {
    S1: json.dumps({
        "demographic_filters": {"region_major": ["서울"], "age_range": [20, 29], "gender": ["남성"]},
        "semantic_conditions": [{"original_keyword": "흡연", "is_negative": False, "expanded_queries": ["담배를 피운다"]}],
        "limit": 30,
    }, ensure_ascii=False),
    S2: "```json\n" + json.dumps({
        "demographic_filters": {"region_major": ["서울", "경기"], "age_range": [20, 39]},
        "semantic_conditions": [{"original_keyword": "OTT", "is_negative": False, "expanded_queries": ["OTT 서비스를 이용한다"]}],
        "limit": 30,
    }, ensure_ascii=False) + "\n```",
    S3: json.dumps({
        "demographic_filters": {},
        "semantic_conditions": [{"original_keyword": "스트레스 해소", "is_negative": False, "expanded_queries": ["운동으로 스트레스를 푼다"]}],
        "limit": 100,
    }, ensure_ascii=False),
    S4: json.dumps({
        "demographic_filters": {},
        "semantic_conditions": [
            {"original_keyword": "OTT", "is_negative": False, "expanded_queries": ["OTT 서비스를 이용한다"]},
            {"original_keyword": "반려동물", "is_negative": True, "expanded_queries": ["반려동물을 키우고 있다"]},
        ],
        "limit": 100,
    }, ensure_ascii=False),
    S5: "이건 JSON이 아니다",
}
