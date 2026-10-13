"""패널 필드 카탈로그: 인구통계/Q-Poll 필드 정의와 값 매핑."""


# 인구통계 필드 정의
WELCOME_OBJECTIVE_FIELDS = [
    ("gender", "성별"),
    ("birth_year", "연령대"),
    ("region_major", "거주 지역"),
    ("region_minor", "세부 거주 지역"),
    ("marital_status", "결혼 여부"),
    ("children_count","자녀수"),
    ("family_size", "가족 수"),
    ("education_level", "최종학력"),
    ("job_title_raw", "직업"),
    ("job_duty_raw", "직무"),
    ("income_personal_monthly", "월소득(개인)"),
    ("income_household_monthly", "월소득(가구)"),
    ("phone_brand_raw", "휴대폰 브랜드"),
    ("phone_model_raw", "휴대폰 모델"),
    ("car_ownership", "차량 보유 여부"),
    ("car_manufacturer_raw", "차량 제조사"),
    ("car_model_raw", "차량 모델명"),
    ("smoking_experience", "흡연 여부"),
    ("smoking_brand", "담배 종류"),
    ("smoking_brand_etc_raw", "기타 담배 종류"),
    ("e_cigarette_experience", "전자 담배 이용 경험"),
    ("smoking_brand_other_details_raw", "기타 흡연 세부 사항"),
    ("drinking_experience", "음주 경험"),
    ("drinking_experience_other_details_raw", "음주 세부 사항"),
    ("owned_electronics", "보유 가전")
]


# Q-Poll 필드 정의
QPOLL_FIELDS = [
    ("physical_activity", "체력 관리 활동"),
    ("ott_count", "OTT 이용 개수"),
    ("traditional_market_freq", "전통시장 방문 빈도"),
    ("lunar_new_year_gift_pref", "설 선물 선호 유형"),
    ("elementary_winter_memories", "겨울방학 기억"),
    ("pet_experience", "반려동물 경험"),
    ("moving_stress_factor", "이사 스트레스 요인"),
    ("happiest_self_spending", "가장 기분 좋은 소비"),
    ("most_used_app", "주요 사용 앱"),
    ("stress_situation", "스트레스 상황"),
    ("stress_relief_method", "스트레스 해소법"),
    ("skin_satisfaction", "피부 만족도"),
    ("skincare_spending", "스킨케어 월 소비"),
    ("skincare_purchase_factor", "스킨케어 구매 요소"),
    ("ai_chatbot_used", "AI 챗봇 사용 경험"),
    ("ai_chatbot_main", "주요 AI 챗봇"),
    ("ai_chatbot_purpose", "AI 챗봇 활용 용도"),
    ("ai_chatbot_sentiment", "AI 챗봇 호감도"),
    ("overseas_travel_pref", "해외여행 선호지"),
    ("fast_delivery_usage", "빠른 배송 이용 제품"),
    ("summer_worry", "여름철 주요 걱정"),
    ("unused_item_disposal", "버리기 아까운 물건 처리"),
    ("alarm_setting_style", "기상 알람 방식"),
    ("eating_alone_frequency", "혼밥 빈도"),
    ("happy_old_age_condition", "행복한 노년 조건"),
    ("sweat_discomfort", "여름철 땀 불편함"),
    ("most_effective_diet", "가장 효과적인 다이어트"),
    ("late_night_snack_method", "야식 섭취 방법"),
    ("favorite_summer_snack", "여름철 최애 간식"),
    ("recent_major_spending", "최근 주요 지출처"),
    ("ai_service_usage_area", "AI 서비스 활용 분야"),
    ("minimalist_maximalist", "미니멀/맥시멀 성향"),
    ("travel_planning_style", "여행 스타일"),
    ("plastic_bag_reduction_effort", "비닐봉투 줄이기 노력"),
    ("point_benefit_attention", "포인트 혜택 관심도"),
    ("chocolate_consumption_time", "초콜릿 섭취 시점"),
    ("personal_info_protection_habit", "개인정보보호 습관"),
    ("summer_fashion_must_have", "여름 패션 필수템"),
    ("no_umbrella_reaction", "우산 없을 때 대처"),
    ("most_saved_photo_type", "갤러리 최다 저장 사진"),
    ("favorite_summer_water_spot", "여름 물놀이 선호 장소")
]


# 통합 필드 맵
FIELD_NAME_MAP = dict(WELCOME_OBJECTIVE_FIELDS + QPOLL_FIELDS)


CATEGORY_MAPPING = {
    '직장인': ['사무직', '전문직', '경영관리직', '생산노무직', '서비스직', '판매직', '기술직'],
    'office worker': ['사무직', '전문직', '경영관리직', '생산노무직', '서비스직', '판매직', '기술직'],
    'worker': ['사무직', '전문직', '경영관리직', '생산노무직', '서비스직', '판매직', '기술직'],
    'student': ['학생', '대학생', '대학원생'],
    'homemaker': ['주부', '전업주부'],
    'housewife': ['주부', '전업주부'],
    'freelancer': ['프리랜서'],
    'jobless': ['무직'],
    'unemployed': ['무직'],

    '상위 10%': ['월 700만원 이상'],
    '상위 20%': ['월 500~599만원', '월 600~699만원', '월 700만원 이상'],
    '상위권': ['월 600~699만원', '월 700만원 이상'],
    'top tier': ['월 700만원 이상'],
    'top': ['월 700만원 이상'],

    '돈을 많이 버는': ['월 500~599만원', '월 600~699만원', '월 700만원 이상'],
    '고소득': ['월 500~599만원', '월 600~699만원', '월 700만원 이상'],
    'high': ['월 500~599만원', '월 600~699만원', '월 700만원 이상'],
    'high income': ['월 500~599만원', '월 600~699만원', '월 700만원 이상'],
    'rich': ['월 500~599만원', '월 600~699만원', '월 700만원 이상'],
    
    '돈을 적게 버는': ['월 100~199만원', '월 200~299만원', '월 100만원 미만'],
    '저소득': ['월 100~199만원', '월 200~299만원', '월 100만원 미만'],
    'low': ['월 100~199만원', '월 200~299만원', '월 100만원 미만'],
    'low income': ['월 100~199만원', '월 200~299만원', '월 100만원 미만'],
    'poor': ['월 100~199만원', '월 200~299만원', '월 100만원 미만'],
    
    
    '중산층': ['월 300~399만원', '월 400~499만원'],
    '중위 소득': ['월 300~399만원', '월 400~499만원'],
    'middle': ['월 300~399만원', '월 400~499만원'],
    'middle class': ['월 300~399만원', '월 400~499만원'],

    '고학력': ['대학교 졸업', '대학원 재학 이상'],
    'highly educated': ['대학교 졸업', '대학원 재학 이상'],
    'university': ['대학교 졸업', '대학원 재학 이상'],
    'college': ['대학교 졸업', '대학원 재학 이상'],
    'master': ['대학원 재학 이상'],
    'phd': ['대학원 재학 이상'],
    
    '저학력': ['고등학교 졸업 이하', '중학교 졸업 이하'],
    'high school': ['고등학교 졸업 이하'],
    'middle school': ['중학교 졸업 이하'],

    'single': ['미혼', '싱글'],
    'unmarried': ['미혼', '싱글'],
    'married': ['기혼', '결혼'],
    'divorced': ['이혼', '돌싱'],

    '젊은층': ['20대', '30대'],
    'young': ['20대', '30대'],
    'youth': ['20대', '30대'],
    '청년': ['20대', '30대'],
    'MZ세대': ['20대', '30대'],
    'mz': ['20대', '30대'],
    
    '중장년층': ['40대', '50대'],
    'middle aged': ['40대', '50대'],
    'X세대': ['40대', '50대'],
    
    '장년층': ['50대', '60대'],
    'senior': ['60대 이상'],
    'old': ['60대 이상'],
    'elderly': ['60대 이상'],
    '베이비부머': ['50대', '60대 이상'],
    '노년층': ['60대 이상'],
    '청소년': ['10대'],
    'teenager': ['10대'],

    '고소득자': ['월 500~599만원', '월 600~699만원', '월 700만원 이상'],
    '저소득자': ['월 100~199만원', '월 200~299만원', '월 100만원 미만'],
    '아이폰 사용자': ['Apple'],
    'iphone user': ['Apple'],
    'galaxy user': ['Samsung']
}


# LLM 필드명 -> 실제 DB 필드명 매핑
FIELD_ALIAS_MAP = {
    "household_size": "family_size",  
    "age": "birth_year",              
    "job": "job_title_raw",  
    "job_duty": "job_duty_raw",         
    "region": "region_major",  
    "income_personal": "income_personal_monthly",   
    "income_household": "income_household_monthly"         
}


# 실제 데이터(명사형)를 포함하도록 매핑 키워드 확장
VALUE_TRANSLATION_MAP = {
    'gender': {
        '남성': 'M', '여성': 'F', '남자': 'M', '여자': 'F', 
        'male': 'M', 'female': 'F', 'man': 'M', 'woman': 'F', 'men': 'M', 'women': 'F'
    },
    'marital_status': {
        '미혼': '미혼', '싱글': '미혼', '기혼': '기혼', '결혼': '기혼', '이혼': '이혼', '돌싱': '이혼',
        'single': '미혼', 'married': '기혼', 'divorced': '이혼'
    },
    'car_ownership': {
        '있음': '있음', '차량 보유': '있음', '보유': '있음', 
        'have car': '있음', 'yes': '있음', 'true': '있음',
        '있다': '있음',  
        '없음': '없음', '미보유': '없음', '차량 미보유': '없음', '뚜벅이': '없음',
        'no car': '없음', 'no': '없음', 'false': '없음',
        '없다': '없음'  
    },
    'education_level': {
        '고졸': ['고등학교 졸업 이하', '고등학교 졸업', '고졸'],
        '고등학교 졸업': ['고등학교 졸업 이하', '고등학교 졸업'],
        '중졸 이하': ['고등학교 졸업 이하', '중학교 졸업 이하', '중학교 졸업', '초등학교 졸업 이하', '무학'],
        '중학교 졸업': ['고등학교 졸업 이하', '중학교 졸업 이하', '중학교 졸업'],
        '대졸': ['대학교 졸업', '대학원 재학 이상', '학사', '석사', '박사'],
        '대학교 졸업': ['대학교 졸업', '대학원 재학 이상'],
        '대학원': ['대학원 재학 이상'],
        '저학력': ['고등학교 졸업 이하', '중학교 졸업 이하', '고등학교 졸업', '중학교 졸업', '초등학교 졸업 이하'],
        '고학력': ['대학교 졸업', '대학원 재학 이상']
    },
    'smoking_experience': {
        'have_smoked': ['일반', '전자', '기타', '피우고', '피웠', '흡연', '연초', '궐련'],
        'smoker': ['일반', '전자', '기타', '피우고', '피웠', '흡연', '연초', '궐련'],
        '있음': ['일반', '전자', '기타', '피우고', '피웠', '흡연', '연초', '궐련'], 
        '흡연': ['일반', '전자', '기타', '피우고', '피웠', '흡연', '연초', '궐련'],
        'no': ['피워본 적이', '비흡연'],
        'none': ['피워본 적이', '비흡연'],
        'non_smoker': ['피워본 적이', '비흡연'],
        '없음': ['피워본 적이', '비흡연'],
        '비흡연': ['피워본 적이', '비흡연'],
    },
    'drinking_experience': {
        'have_drink': ['소주', '맥주', '와인', '막걸리', '위스키', '양주', '사케', '과일칵테일주', '저도주', '즐겨', '마신다'],
        'drinker': ['소주', '맥주', '와인', '막걸리', '위스키', '양주', '사케', '과일칵테일주', '저도주', '즐겨', '마신다'],
        '있음': ['소주', '맥주', '와인', '막걸리', '위스키', '양주', '사케', '과일칵테일주', '저도주', '즐겨', '마신다'],
        'no': ['최근 1년 이내 술을 마시지 않음', '마시지', '비음주', '금주', '않음'],
        '없음': ['최근 1년 이내 술을 마시지 않음', '마시지', '비음주', '금주', '않음'],
    }
}


# 부분 문자열 검색(ILIKE)을 강제할 필드 목록
FUZZY_MATCH_FIELDS = [
    "job_title_raw", "job_duty_raw", 
    "car_model_raw", "car_manufacturer_raw",
    "phone_brand_raw", "phone_model_raw"
]


# 배열형 필드 목록
ARRAY_FIELDS = [
    "drinking_experience",
    "owned_electronics",
    "smoking_experience",
    "smoking_brand",
    "e_cigarette_experience"
]


VALID_REGIONS = [
    '서울', '경기', '인천', '부산', '대구', '대전', '광주', '울산', '세종',
    '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주'
]


QPOLL_FIELD_TO_TEXT = {
    "physical_activity": "여러분은 평소 체력 관리를 위해 어떤 활동을 하고 계신가요? 모두 선택해주세요.",
    "ott_count": "여러분이 현재 이용 중인 OTT 서비스는 몇 개인가요?",
    "traditional_market_freq": "여러분은 전통시장을 얼마나 자주 방문하시나요?",
    "lunar_new_year_gift_pref": "여러분이 가장 선호하는 설 선물 유형은 무엇인가요?",
    "elementary_winter_memories": "초등학생 시절 겨울방학 때 가장 기억에 남는 일은 무엇인가요?",
    "pet_experience": "여러분은 반려동물을 키우는 중이시거나 혹은 키워보신 적이 있으신가요?",
    "moving_stress_factor": "여러분은 이사할 때 가장 스트레스 받는 부분은 어떤걸까요?",
    "happiest_self_spending": "여러분은 본인을 위해 소비하는 것 중 가장 기분 좋아지는 소비는 무엇인가요?",
    "most_used_app": "여러분은 요즘 가장 많이 사용하는 앱은 무엇인가요?",
    "stress_situation": "다음 중 가장 스트레스를 많이 느끼는 상황은 무엇인가요?",
    "stress_relief_method": "스트레스를 해소하는 방법으로 주로 사용하는 것은 무엇인가요?",
    "skin_satisfaction": "현재 본인의 피부 상태에 얼마나 만족하시나요?",
    "skincare_spending": "한 달 기준으로 스킨케어 제품에 평균적으로 얼마나 소비하시나요?",
    "skincare_purchase_factor": "스킨케어 제품을 구매할 때 가장 중요하게 고려하는 요소는 무엇인가요?",
    "ai_chatbot_used": "여러분이 사용해 본 AI 챗봇 서비스는 무엇인가요? 모두 선택해주세요.",
    "ai_chatbot_main": "사용해 본 AI 챗봇 서비스 중 주로 사용하는 것은 무엇인가요?",
    "ai_chatbot_purpose": "AI 챗봇 서비스를 주로 어떤 용도로 활용하셨거나, 앞으로 활용하고 싶으신가요?",
    "ai_chatbot_sentiment": "다음 두 서비스 중, 어느 서비스에 더 호감이 가나요? 현재 사용 여부는 고려하지 않고 응답해 주세요.",
    "overseas_travel_pref": "여러분은 올해 해외여행을 간다면 어디로 가고 싶나요? 모두 선택해주세요",
    "fast_delivery_usage": "빠른 배송(당일·새벽·직진 배송) 서비스를 주로 어떤 제품을 구매할 때 이용하시나요?",
    "summer_worry": "여러분은 다가오는 여름철 가장 걱정되는 점이 무엇인가요?",
    "unused_item_disposal": "여러분은 버리기 아까운 물건이 있을 때, 주로 어떻게 하시나요?",
    "alarm_setting_style": "여러분은 아침에 기상하기 위해 어떤 방식으로 알람을 설정해두시나요?",
    "eating_alone_frequency": "여러분은 외부 식당에서 혼자 식사하는 빈도는 어느 정도인가요?",
    "happy_old_age_condition": "여러분이 가장 중요하다고 생각하는 행복한 노년의 조건은 무엇인가요?",
    "sweat_discomfort": "여름철 땀 때문에 겪는 불편함은 어떤 것이 있는지 모두 선택해주세요.",
    "most_effective_diet": "여러분이 지금까지 해본 다이어트 중 가장 효과 있었던 방법은 무엇인가요?",
    "late_night_snack_method": "여러분은 야식을 먹을 때 보통 어떤 방법으로 드시나요?",
    "favorite_summer_snack": "여러분의 여름철 최애 간식은 무엇인가요?",
    "recent_major_spending": "여러분은 최근 가장 지출을 많이 한 곳은 어디입니까?",
    "ai_service_usage_area": "여러분은 요즘 어떤 분야에서 AI 서비스를 활용하고 계신가요?",
    "minimalist_maximalist": "여러분은 본인을 미니멀리스트와 맥시멀리스트 중 어디에 더 가깝다고 생각하시나요?",
    "travel_planning_style": "어려분은 여행갈 때 어떤 스타일에 더 가까우신가요?",
    "plastic_bag_reduction_effort": "평소 일회용 비닐봉투 사용을 줄이기 위해 어떤 노력을 하고 계신가요?",
    "point_benefit_attention": "여러분은 할인, 캐시백, 멤버십 등 포인트 적립 혜택을 얼마나 신경 쓰시나요?",
    "chocolate_consumption_time": "여러분은 초콜릿을 주로 언제 드시나요?",
    "personal_info_protection_habit": "여러분은 평소 개인정보보호를 위해 어떤 습관이 있으신가요?",
    "summer_fashion_must_have": "여러분이 절대 포기할 수 없는 여름 패션 필수템은 무엇인가요?",
    "no_umbrella_reaction": "갑작스런 비로 우산이 없을 때 여러분은 어떻게 하시나요?",
    "most_saved_photo_type": "여러분의 휴대폰 갤러리에 가장 많이 저장되어져 있는 사진은 무엇인가요?",
    "favorite_summer_water_spot": "여러분이 여름철 물놀이 장소로 가장 선호하는 곳은 어디입니까?",
}


VECTOR_CATEGORY_TO_FIELD = {
    "DEMO_BASIC": ["gender", "birth_year", "region_major", "region_minor"],
    "FAMILY_STATUS": ["marital_status", "family_size", "children_count"],
    "JOB_EDUCATION": ["job_title_raw", "job_duty_raw", "education_level"],
    "INCOME_LEVEL": ["income_personal_monthly", "income_household_monthly"],
    "TECH_OWNER": ["owned_electronics"], 
    "CAR_OWNER": ["car_ownership", "car_manufacturer_raw", "car_model_raw"],
    "DRINK_HABIT": ["drinking_experience", "drinking_experience_other_details_raw"],
    "SMOKE_HABIT": ["smoking_experience", "smoking_brand", "e_cigarette_experience"],
}


# Q-Poll 답변 템플릿
QPOLL_ANSWER_TEMPLATES = {
    "physical_activity": "체력 관리를 위해 {answer_str} 활동을 하고 있다.",
    "ott_count": "현재 OTT서비스를 {answer_str}이용 중이다.",
    "traditional_market_freq": "전통시장을 {answer_str}방문한다.",
    "lunar_new_year_gift_pref": "가장 선호하는 설 선물 유형은 {answer_str}이다.",
    "elementary_winter_memories": "초등학생 시절 겨울방학 때 가장 기억에 남는 일은 {answer_str}(이)다.",
    "pet_experience": "{answer_str}.",
    "moving_stress_factor": "이사할 때 {answer_str}(으)로 가장 스트레스 받는다.",
    "happiest_self_spending": "본인을 위해 소비하는 것 중 가장 기분 좋아지는 소비는 {answer_str}이 다.",
    "most_used_app": "요즘 가장 많이 사용하는 앱은 {answer_str}이다.",
    "stress_situation": "{answer_str}에서 스트레스를 가장 많이 느낀다.",
    "stress_relief_method": "스트레스를 해소하는데 주로 사용하는 방법은 {answer_str}이다.",
    "skin_satisfaction": "현재 본인의 피부 상태에 {answer_str}.",
    "skincare_spending": "한 달 기준으로 스킨케어 제품에 평균 {answer_str}만큼 소비한다.",
    "skincare_purchase_factor": "스킨케어 제품을 구매할 떄 가장 중요하게 생각하는 요소는 {answer_str}이다.",
    "ai_chatbot_used": "사용해 본 AI 챗봇 서비스는 {answer_str}이다.",
    "ai_chatbot_main": "사용해 본 AI 챗봇 서비스 중 주로 사용하는 것은 {answer_str}이다.",
    "ai_chatbot_purpose": "AI 챗봇 서비스를 주로 {answer_str} 용도로 활용하였거나, 앞으로 활용하고 싶다.",
    "ai_chatbot_sentiment": "ChatGPT와 딥시크 중 {answer_str}에 더 호감이 간다.",
    "overseas_travel_pref": "올해 해외여행을 {answer_str}(으)로 가고 싶다.",
    "fast_delivery_usage": "빠른 배송(당일·새벽·직진 배송) 서비스를 주로 {answer_str}을 구매할 때 이용한다.",
    "summer_worry": "다가오는 여름철 {answer_str}이(가) 가장 걱정된다.",
    "unused_item_disposal": "버리기 아까운 물건이 있을 때, 주로 {answer_str}한다.",
    "alarm_setting_style": "아침에 기상하기 위해 {answer_str}.",
    "eating_alone_frequency": "외부 식당에서 식사를 {answer_str} 한다.",
    "happy_old_age_condition": "가장 중요한 행복한 노년의 조건은 {answer_str}이다.",
    "sweat_discomfort": "여름철 땀 때문에 {answer_str}는 불편함이 있다.",
    "most_effective_diet": "지금까지 해본 다이어트 중 {answer_str}가 가장 효과 있었다.",
    "late_night_snack_method": "야식을 먹을 때 보통 {answer_str}.",
    "favorite_summer_snack": "여름철 최애 간식은 {answer_str}이다.",
    "recent_major_spending": "최근 가장 지출을 많이 한 곳은 {answer_str}이다.",
    "ai_service_usage_area": "요즘 {answer_str} 분야에서 AI 서비스를 활용하고 있다.",
    "minimalist_maximalist": "나는 {answer_str}에 더 가깝다.",
    "travel_planning_style": "여행갈 때 {answer_str} 스타일에 더 가깝다.",
    "plastic_bag_reduction_effort": "평소 일회용 비닐봉투 사용을 줄이기 위해 {answer_str}.",
    "point_benefit_attention": "할인, 캐시백, 멤버십 등 포인트 적립 혜택을 {answer_str}.",
    "chocolate_consumption_time": "초콜릿을 주로 {answer_str} 먹는다.",
    "personal_info_protection_habit": "평소 개인정보보호를 위해 {answer_str}.",
    "summer_fashion_must_have": "절대 포기할 수 없는 여름 패션 필수탬은 {answer_str} 이다.",
    "no_umbrella_reaction": "갑작스런 비로 우산이 없을 때 {answer_str}.",
    "most_saved_photo_type": "휴대폰 갤러리에 가장 많이 저장되어져 있는 사진은 {answer_str}이다.",
    "favorite_summer_water_spot": "여름철 물놀이 장소로 가장 선호하는 곳은 {answer_str}이다.",
}
