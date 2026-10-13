import json
import logging
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple, Union

from langchain_core.messages import HumanMessage, SystemMessage

from app.core import llm_client
from app.panels.fields import FIELD_NAME_MAP, QPOLL_FIELD_TO_TEXT, VALID_REGIONS


KEYWORD_MAPPINGS: List[Tuple[Union[re.Pattern, str], Dict[str, str]]] = [
    (re.compile(r'\b(여|여자|여성)\b', re.IGNORECASE), {"field": "gender", "description": "성별", "type": "filter"}),
    (re.compile(r'\b(남|남자|남성)\b', re.IGNORECASE), {"field": "gender", "description": "성별", "type": "filter"}),
    
    (re.compile(r'미혼|싱글'), {"field": "marital_status", "description": "결혼 여부", "type": "filter"}),
    (re.compile(r'기혼|결혼'), {"field": "marital_status", "description": "결혼 여부", "type": "filter"}),
    (re.compile(r'이혼|돌싱'), {"field": "marital_status", "description": "결혼 여부", "type": "filter"}),
    (re.compile(r'신혼\s*부부|신혼'), {"field": "birth_year", "description": "연령대 (신혼)", "type": "filter", "value_override": "20대, 30대"}),
    
    (re.compile(r'(\d+인|가족\s*\d+명|\d+인\s*가구)'), {"field": "family_size", "description": "가족 수", "type": "filter"}),
    
    (re.compile(r'자녀\s*수|아이\s*수|자녀\s*유무'), {"field": "children_count", "description": "자녀 수", "type": "filter"}),
    
    ("대졸", {"field": "education_level", "description": "최종학력", "type": "filter"}),
    ("대학원", {"field": "education_level", "description": "최종학력", "type": "filter"}),
    ("고학력", {"field": "education_level", "description": "최종학력", "type": "filter"}),
    ("저학력", {"field": "education_level", "description": "최종학력", "type": "filter"}),
    ("대학교 졸업", {"field": "education_level", "description": "최종학력", "type": "filter"}),
    ("대학원 재학 이상", {"field": "education_level", "description": "최종학력", "type": "filter"}),
    ("고등학교 졸업 이하", {"field": "education_level", "description": "최종학력", "type": "filter"}),
    ("중학교 졸업 이하", {"field": "education_level", "description": "최종학력", "type": "filter"}),

    (re.compile(r'(\d{2}대(\s*(초반|중반|후반|이상))?)|젊은층|청년|MZ세대|엠지세대|중장년층|X세대|엑스세대|장년층|베이비부머|베이비붐|노년층|시니어|실버|청소년|10대', re.IGNORECASE), {"field": "birth_year", "description": "연령대", "type": "filter"}),
    
    # --- 지역 ---
    (re.compile(r'(\w+시|\w+군|\w+구)(\s*거주|\s*사는)?'), {"field": "region_minor", "description": "거주 지역(시군구)", "type": "filter"}),
    (re.compile(r'시군구|상세\s*지역'), {"field": "region_minor", "description": "거주 지역(시군구)", "type": "filter"}),
    (re.compile(r'|'.join(VALID_REGIONS) + r'(\s*에\s*사는|\s*거주자)?'), {"field": "region_major", "description": "거주 지역", "type": "filter"}),

    # --- 직업/직무 ---
    (re.compile(r'직장인|사무직|전문직|경영관리직|생산노무직|서비스직|판매직|기술직|마케팅|마케터|it|개발|개발자', re.IGNORECASE), {"field": "job_duty_raw", "description": "직무", "type": "filter"}),
    (re.compile(r'학생|대학생|대학원생|주부|무직|실업자|프리랜서|자영업자'), {"field": "job_title_raw", "description": "직업", "type": "filter"}),

    # --- 소득 ---
    (re.compile(r'(월|월소득)\s*(\d+(?:만)?\s*~\s*)?(\d+)\s*만?원?(\s*이상|\s*이하)?'), {"field": "income_personal_monthly", "description": "월소득(개인)", "type": "filter"}),
    (re.compile(r'(연봉|연 소득)\s*(\d+(?:만)?\s*~\s*)?(\d+)\s*만?원?(\s*이상|\s*이하)?'), {"field": "income_personal_monthly", "description": "월소득(개인)", "type": "filter"}),
    (re.compile(r'월소득|월\s*소득|개인소득|본인\s*소득|고소득|저소득|중산층|돈을\s*많이\s*버는|돈을\s*적게\s*버는|부자|서민|상위\s*소득|중위\s*소득|고액\s*연봉'), {"field": "income_personal_monthly", "description": "월소득(개인)", "type": "filter"}), # 키워드 추가됨
    (re.compile(r'가구소득|가족\s*소득|가정\s*소득'), {"field": "income_household_monthly", "description": "월소득(가구)", "type": "filter"}),

    # --- 휴대폰 ---
    (re.compile(r'핸드폰|휴대폰|스마트폰|모바일\s*기기|폰\s*기종|휴대전화', re.IGNORECASE), {"field": "phone_brand_raw", "description": "휴대폰 브랜드", "type": "filter"}),
    (re.compile(r'아이폰|애플|apple', re.IGNORECASE), {"field": "phone_brand_raw", "description": "휴대폰 브랜드", "type": "filter"}),
    (re.compile(r'갤럭시|삼성', re.IGNORECASE), {"field": "phone_brand_raw", "description": "휴대폰 브랜드", "type": "filter"}),
    (re.compile(r'lg', re.IGNORECASE), {"field": "phone_brand_raw", "description": "휴대폰 브랜드", "type": "filter"}),
    (re.compile(r'가전|전자제품'), {"field": "owned_electronics", "description": "보유 가전", "type": "filter"}),

    (re.compile(r'(아이폰|iphone)\s*(15|14|13|12|11|x|se)', re.IGNORECASE), {"field": "phone_model_raw", "description": "휴대폰 모델", "type": "filter"}),
    (re.compile(r'갤럭시\s*(s|z|a|m|노트)\s*\d*', re.IGNORECASE), {"field": "phone_model_raw", "description": "휴대폰 모델", "type": "filter"}),

    # --- 차량 소유/모델 ---
    (re.compile(r'차량\s*보유|차\s*있음|자가용|차종|자동차\s*모델|차량\s*종류|차량\s*타입'), {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    (re.compile(r'차\s*없음|무소유|차량\s*없음'), {"field": "car_ownership", "description": "차량 보유 여부", "type": "filter"}),
    
    (re.compile(r'기아(차)?'), {"field": "car_manufacturer_raw", "description": "차량 제조사", "type": "filter"}),
    (re.compile(r'르노|르노삼성|쌍용(차)?|kg\s*모빌리티|쉐보레|한국gm|현대(차)?|제네시스', re.IGNORECASE), {"field": "car_manufacturer_raw", "description": "차량 제조사", "type": "filter"}),

    ("아우디", {"field": "car_manufacturer_raw", "description": "차량 제조사", "type": "filter"}),
    ("벤틀리", {"field": "car_manufacturer_raw", "description": "차량 제조사", "type": "filter"}),
    (re.compile(r'bmw', re.IGNORECASE), {"field": "car_manufacturer_raw", "description": "차량 제조사", "type": "filter"}),
    ("포드", {"field": "car_manufacturer_raw", "description": "차량 제조사", "type": "filter"}),
    ("혼다", {"field": "car_manufacturer_raw", "description": "차량 제조사", "type": "filter"}),
    ("인피니티", {"field": "car_manufacturer_raw", "description": "차량 제조사", "type": "filter"}),
    ("재규어", {"field": "car_manufacturer_raw", "description": "차량 제조사", "type": "filter"}),
    (re.compile(r'지프|jeep', re.IGNORECASE), {"field": "car_manufacturer_raw", "description": "차량 제조사", "type": "filter"}),
    ("랜드로버", {"field": "car_manufacturer_raw", "description": "차량 제조사", "type": "filter"}),
    ("렉서스", {"field": "car_manufacturer_raw", "description": "차량 제조사", "type": "filter"}),
    ("링컨", {"field": "car_manufacturer_raw", "description": "차량 제조사", "type": "filter"}),
    (re.compile(r'벤츠|메르세데스-벤츠'), {"field": "car_manufacturer_raw", "description": "차량 제조사", "type": "filter"}),
    (re.compile(r'미니|bmw\s*미니', re.IGNORECASE), {"field": "car_manufacturer_raw", "description": "차량 제조사", "type": "filter"}),
    (re.compile(r'닛산|포르쉐|롤스로이스|테슬라', re.IGNORECASE), {"field": "car_manufacturer_raw", "description": "차량 제조사", "type": "filter"}),
    (re.compile(r'도요타|토요타'), {"field": "car_manufacturer_raw", "description": "차량 제조사", "type": "filter"}),
    (re.compile(r'볼보|폭스바겐', re.IGNORECASE), {"field": "car_manufacturer_raw", "description": "차량 제조사", "type": "filter"}),
    (re.compile(r'만|man', re.IGNORECASE), {"field": "car_manufacturer_raw", "description": "차량 제조사", "type": "filter"}),
    ("스카니아", {"field": "car_manufacturer_raw", "description": "차량 제조사", "type": "filter"}),
    ("포톤", {"field": "car_manufacturer_raw", "description": "차량 제조사", "type": "filter"}),
    ("이스트", {"field": "car_manufacturer_raw", "description": "차량 제조사", "type": "filter"}),
    ("이베코", {"field": "car_manufacturer_raw", "description": "차량 제조사", "type": "filter"}),
    
    # 모델명 (현대)
    (re.compile(r'그랜저|그랜져', re.IGNORECASE), {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    (re.compile(r'소나타|쏘나타'), {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    (re.compile(r'아반떼|아반테', re.IGNORECASE), {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    ("캐스퍼", {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    ("코나", {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    ("투싼", {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    (re.compile(r'싼타페|산타페'), {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    ("팰리세이드", {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    (re.compile(r'아이오닉\s*5', re.IGNORECASE), {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    (re.compile(r'아이오닉\s*6', re.IGNORECASE), {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    ("넥쏘", {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    (re.compile(r'포터\s*2?', re.IGNORECASE), {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    (re.compile(r'봉고\s*3?', re.IGNORECASE), {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    
    # 모델명 (기아)
    ("레이", {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    ("모닝", {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    (re.compile(r'k3', re.IGNORECASE), {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    (re.compile(r'k5', re.IGNORECASE), {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    (re.compile(r'k8', re.IGNORECASE), {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    ("스팅어", {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    ("셀토스", {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    ("스포티지", {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    ("쏘렌토", {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    ("카니발", {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    ("모하비", {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    (re.compile(r'ev6', re.IGNORECASE), {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    ("니로", {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    
    # 모델명 (제네시스)
    (re.compile(r'제네시스\s*g70', re.IGNORECASE), {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    (re.compile(r'제네시스\s*g80', re.IGNORECASE), {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    (re.compile(r'제네시스\s*g90', re.IGNORECASE), {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    (re.compile(r'제네시스\s*gv70', re.IGNORECASE), {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    (re.compile(r'제네시스\s*gv80', re.IGNORECASE), {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),

    # 모델명 (르노, KG, 쉐보레)
    (re.compile(r'xm3', re.IGNORECASE), {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    (re.compile(r'sm6', re.IGNORECASE), {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    ("토레스", {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    ("티볼리", {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    ("코란도", {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    ("렉스턴", {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    ("트레일블레이저", {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    ("트랙스", {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    ("말리부", {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    ("트래버스", {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    ("타호", {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),

    # 모델명 (수입차)
    (re.compile(r'bmw\s*3\s*시리즈', re.IGNORECASE), {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    (re.compile(r'bmw\s*5\s*시리즈', re.IGNORECASE), {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    (re.compile(r'bmw\s*x3', re.IGNORECASE), {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    (re.compile(r'bmw\s*x5', re.IGNORECASE), {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    (re.compile(r'벤츠\s*c\s*클래스', re.IGNORECASE), {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    (re.compile(r'벤츠\s*e\s*클래스', re.IGNORECASE), {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    (re.compile(r'아우디\s*a4', re.IGNORECASE), {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    (re.compile(r'아우디\s*a6', re.IGNORECASE), {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    (re.compile(r'테슬라\s*모델\s*3', re.IGNORECASE), {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    (re.compile(r'테슬라\s*모델\s*y', re.IGNORECASE), {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),

    ("기타 국산차", {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    ("기타 수입차", {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    (re.compile(r'suv|세단|트럭|승합|경차|소형차|준중형차|중형차|준대형차|대형차', re.IGNORECASE), {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    (re.compile(r'전기차|ev|하이브리드|수소차', re.IGNORECASE), {"field": "car_model_raw", "description": "차량 모델명", "type": "filter"}),
    
    # --- 흡연/음주 ---
    (re.compile(r'흡연'), {"field": "smoking_experience", "description": "흡연 여부", "type": "filter"}),
    (re.compile(r'비흡연|금연'), {"field": "smoking_experience", "description": "흡연 여부", "type": "filter"}),

    ("레종", {"field": "smoking_brand", "description": "담배 종류", "type": "filter"}),
    ("에쎄", {"field": "smoking_brand", "description": "담배 종류", "type": "filter"}),
    ("보헴", {"field": "smoking_brand", "description": "담배 종류", "type": "filter"}),
    ("아프리카", {"field": "smoking_brand", "description": "담배 종류", "type": "filter"}),
    (re.compile(r'더원|시즌|아이스볼트 gt', re.IGNORECASE), {"field": "smoking_brand", "description": "담배 종류", "type": "filter"}),
    (re.compile(r'디스플러스|디스'), {"field": "smoking_brand", "description": "담배 종류", "type": "filter"}),
    (re.compile(r'한라산|라일락|심플|타임|88리턴즈'), {"field": "smoking_brand", "description": "담배 종류", "type": "filter"}),
    (re.compile(r'말보로|팔리아멘트|메비우스|던힐|라크|카멜|다비도프|하모니|럭키스트라이크|버지니아 s|블랙데빌|켄트|클라우드 나인|토니노 람보르기니|하비스트', re.IGNORECASE), {"field": "smoking_brand", "description": "담배 종류", "type": "filter"}),

    (re.compile(r'아이코스|iqos', re.IGNORECASE), {"field": "e_cigarette_experience", "description": "전자 담배 이용 경험", "type": "filter"}),
    (re.compile(r'릴|lil', re.IGNORECASE), {"field": "e_cigarette_experience", "description": "전자 담배 이용 경험", "type": "filter"}),
    (re.compile(r'글로|glo', re.IGNORECASE), {"field": "e_cigarette_experience", "description": "전자 담배 이용 경험", "type": "filter"}),
    (re.compile(r'차이코스|cqs', re.IGNORECASE), {"field": "e_cigarette_experience", "description": "전자 담배 이용 경험", "type": "filter"}),
    (re.compile(r'전자담배|궐련형', re.IGNORECASE), {"field": "e_cigarette_experience", "description": "전자 담배 이용 경험", "type": "filter"}),
    
    (re.compile(r'음주|술'), {"field": "drinking_experience", "description": "음주 경험", "type": "filter"}),
    (re.compile(r'금주|비음주|소주|맥주|저도주|막걸리|와인'), {"field": "drinking_experience", "description": "음주 경험", "type": "filter"}),
    (re.compile(r'양주|위스키|보드카|데킬라|진'), {"field": "drinking_experience", "description": "음주 경험", "type": "filter"}),
    
    (re.compile(r'카스|테라|하이트|오비|클라우드|아사히|하이네켄', re.IGNORECASE), {"field": "drinking_experience", "description": "음주 경험", "type": "filter"}),
    (re.compile(r'참이슬|진로|처음처럼|새로|좋은데이', re.IGNORECASE), {"field": "drinking_experience", "description": "음주 경험", "type": "filter"}),

    ("과일칵테일주", {"field": "drinking_experience", "description": "음주 경험", "type": "filter"}),
    (re.compile(r'일본청주|사케'), {"field": "drinking_experience", "description": "음주 경험", "type": "filter"}),
    ("최근 1년 이내 술을 마시지 않음", {"field": "drinking_experience", "description": "음주 경험", "type": "filter"}),

    # --- Q-Poll 키워드 ---
    (re.compile(r'체력\s*관리|운동|헬스|피트니스|체육|요가|필라테스|수영'), {"field": "physical_activity", "description": QPOLL_FIELD_TO_TEXT["physical_activity"], "type": "qpoll"}),
    (re.compile(r'ott|스트리밍|넷플릭스|디즈니|웨이브|티빙|쿠팡플레이|왓챠|온라인\s*영상|동영상\s*플랫폼', re.IGNORECASE), {"field": "ott_count", "description": QPOLL_FIELD_TO_TEXT["ott_count"], "type": "qpoll"}),
    ("전통시장", {"field": "traditional_market_freq", "description": QPOLL_FIELD_TO_TEXT["traditional_market_freq"], "type": "qpoll"}),
    (re.compile(r'설\s*선물|선물\s*선호'), {"field": "lunar_new_year_gift_pref", "description": QPOLL_FIELD_TO_TEXT["lunar_new_year_gift_pref"], "type": "qpoll"}),
    ("겨울방학", {"field": "elementary_winter_memories", "description": QPOLL_FIELD_TO_TEXT["elementary_winter_memories"], "type": "qpoll"}),
    ("반려동물", {"field": "pet_experience", "description": QPOLL_FIELD_TO_TEXT["pet_experience"], "type": "qpoll"}),
    (re.compile(r'이사\s*스트레스'), {"field": "moving_stress_factor", "description": QPOLL_FIELD_TO_TEXT["moving_stress_factor"], "type": "qpoll"}),
    (re.compile(r'기분\s*좋아지는\s*소비|나를\s*위한\s*소비'), {"field": "happiest_self_spending", "description": QPOLL_FIELD_TO_TEXT["happiest_self_spending"], "type": "qpoll"}),
    (re.compile(r'사용하는\s*앱|주요\s*앱'), {"field": "most_used_app", "description": QPOLL_FIELD_TO_TEXT["most_used_app"], "type": "qpoll"}),
    (re.compile(r'스트레스\s*상황'), {"field": "stress_situation", "description": QPOLL_FIELD_TO_TEXT["stress_situation"], "type": "qpoll"}),
    (re.compile(r'스트레스\s*해소'), {"field": "stress_relief_method", "description": QPOLL_FIELD_TO_TEXT["stress_relief_method"], "type": "qpoll"}),
    (re.compile(r'피부\s*만족도'), {"field": "skin_satisfaction", "description": QPOLL_FIELD_TO_TEXT["skin_satisfaction"], "type": "qpoll"}),
    (re.compile(r'스킨케어\s*소비|스킨케어\s*지출'), {"field": "skincare_spending", "description": QPOLL_FIELD_TO_TEXT["skincare_spending"], "type": "qpoll"}),
    (re.compile(r'스킨케어\s*구매\s*요소'), {"field": "skincare_purchase_factor", "description": QPOLL_FIELD_TO_TEXT["skincare_purchase_factor"], "type": "qpoll"}),
    (re.compile(r'ai\s*챗봇\s*사용|챗봇\s*경험', re.IGNORECASE), {"field": "ai_chatbot_used", "description": QPOLL_FIELD_TO_TEXT["ai_chatbot_used"], "type": "qpoll"}),
    (re.compile(r'주로\s*사용하는\s*ai\s*챗봇', re.IGNORECASE), {"field": "ai_chatbot_main", "description": QPOLL_FIELD_TO_TEXT["ai_chatbot_main"], "type": "qpoll"}),
    (re.compile(r'ai\s*챗봇\s*활용|챗봇\s*용도', re.IGNORECASE), {"field": "ai_chatbot_purpose", "description": QPOLL_FIELD_TO_TEXT["ai_chatbot_purpose"], "type": "qpoll"}),
    (re.compile(r'ai\s*챗봇\s*호감도', re.IGNORECASE), {"field": "ai_chatbot_sentiment", "description": QPOLL_FIELD_TO_TEXT["ai_chatbot_sentiment"], "type": "qpoll"}),
    (re.compile(r'해외여행|여행\s*선호'), {"field": "overseas_travel_pref", "description": QPOLL_FIELD_TO_TEXT["overseas_travel_pref"], "type": "qpoll"}),
    (re.compile(r'빠른\s*배송|새벽\s*배송'), {"field": "fast_delivery_usage", "description": QPOLL_FIELD_TO_TEXT["fast_delivery_usage"], "type": "qpoll"}),
    (re.compile(r'여름철\s*걱정'), {"field": "summer_worry", "description": QPOLL_FIELD_TO_TEXT["summer_worry"], "type": "qpoll"}),
    (re.compile(r'물건\s*처리|업사이클링'), {"field": "unused_item_disposal", "description": QPOLL_FIELD_TO_TEXT["unused_item_disposal"], "type": "qpoll"}),
    (re.compile(r'기상\s*알람'), {"field": "alarm_setting_style", "description": QPOLL_FIELD_TO_TEXT["alarm_setting_style"], "type": "qpoll"}),
    ("혼밥", {"field": "eating_alone_frequency", "description": QPOLL_FIELD_TO_TEXT["eating_alone_frequency"], "type": "qpoll"}),
    (re.compile(r'행복한\s*노년'), {"field": "happy_old_age_condition", "description": QPOLL_FIELD_TO_TEXT["happy_old_age_condition"], "type": "qpoll"}),
    (re.compile(r'여름\s*땀\s*불편함'), {"field": "sweat_discomfort", "description": QPOLL_FIELD_TO_TEXT["sweat_discomfort"], "type": "qpoll"}),
    (re.compile(r'다이어트\s*방법'), {"field": "most_effective_diet", "description": QPOLL_FIELD_TO_TEXT["most_effective_diet"], "type": "qpoll"}),
    ("야식", {"field": "late_night_snack_method", "description": QPOLL_FIELD_TO_TEXT["late_night_snack_method"], "type": "qpoll"}),
    (re.compile(r'여름철\s*간식'), {"field": "favorite_summer_snack", "description": QPOLL_FIELD_TO_TEXT["favorite_summer_snack"], "type": "qpoll"}),
    (re.compile(r'최근\s*지출'), {"field": "recent_major_spending", "description": QPOLL_FIELD_TO_TEXT["recent_major_spending"], "type": "qpoll"}),
    (re.compile(r'ai\s*서비스\s*활용', re.IGNORECASE), {"field": "ai_service_usage_area", "description": QPOLL_FIELD_TO_TEXT["ai_service_usage_area"], "type": "qpoll"}),
    (re.compile(r'미니멀리스트|맥시멀리스트'), {"field": "minimalist_maximalist", "description": QPOLL_FIELD_TO_TEXT["minimalist_maximalist"], "type": "qpoll"}),
    (re.compile(r'여행\s*스타일'), {"field": "travel_planning_style", "description": QPOLL_FIELD_TO_TEXT["travel_planning_style"], "type": "qpoll"}),
    (re.compile(r'비닐봉투\s*줄이기'), {"field": "plastic_bag_reduction_effort", "description": QPOLL_FIELD_TO_TEXT["plastic_bag_reduction_effort"], "type": "qpoll"}),
    (re.compile(r'포인트\s*적립'), {"field": "point_benefit_attention", "description": QPOLL_FIELD_TO_TEXT["point_benefit_attention"], "type": "qpoll"}),
    ("초콜릿", {"field": "chocolate_consumption_time", "description": QPOLL_FIELD_TO_TEXT["chocolate_consumption_time"], "type": "qpoll"}),
    ("개인정보보호", {"field": "personal_info_protection_habit", "description": QPOLL_FIELD_TO_TEXT["personal_info_protection_habit"], "type": "qpoll"}),
    (re.compile(r'여름\s*패션'), {"field": "summer_fashion_must_have", "description": QPOLL_FIELD_TO_TEXT["summer_fashion_must_have"], "type": "qpoll"}),
    (re.compile(r'우산\s*없을\s*때'), {"field": "no_umbrella_reaction", "description": QPOLL_FIELD_TO_TEXT["no_umbrella_reaction"], "type": "qpoll"}),
    (re.compile(r'갤러리\s*사진'), {"field": "most_saved_photo_type", "description": QPOLL_FIELD_TO_TEXT["most_saved_photo_type"], "type": "qpoll"}),
    (re.compile(r'물놀이\s*장소'), {"field": "favorite_summer_water_spot", "description": QPOLL_FIELD_TO_TEXT["favorite_summer_water_spot"], "type": "qpoll"}),

]


@lru_cache(maxsize=512)
def get_field_mapping(keyword: str) -> Optional[Dict[str, Any]]:
    search_keyword = keyword.lower().strip()
    for pattern, mapping_info in KEYWORD_MAPPINGS:
        result_info = mapping_info.copy()
        if isinstance(pattern, re.Pattern):
            if pattern.search(search_keyword):
                return result_info
        elif isinstance(pattern, str):
            if pattern.lower() in search_keyword:
                return result_info
    return {
        "field": "unknown", 
        "description": keyword, 
        "type": "unknown"
    }


def find_related_fields(query: str) -> List[str]:
    """
    검색 쿼리에 포함된 단어를 기반으로, 연관된 필드(Q-Poll 등)를 동적으로 찾습니다.
    하드코딩된 매핑 대신, 필드 설명(Description)을 검색하여 매칭합니다.
    """
    related_fields = set()
    
    # 1. 필드 설명(FIELD_NAME_MAP) 전체 스캔
    for field_key, field_desc in FIELD_NAME_MAP.items():
        # 필드 설명이 쿼리의 일부 단어를 포함하는지 확인 (간단한 키워드 매칭)
        # 쿼리를 단어 단위로 쪼개서 확인
        query_words = query.split()
        for word in query_words:
            if len(word) >= 2 and word in field_desc: # 2글자 이상만 매칭
                related_fields.add(field_key)
    
    # 2. 비즈니스 로직상 강제 연결이 필요한 경우만 최소한으로 정의
    IMPLICIT_RELATIONS = {
        '여행': ['income_household_monthly'],
        '차': ['car_model_raw', 'car_manufacturer_raw'],
        '자동차': ['car_model_raw', 'car_manufacturer_raw'],
        '자녀': ['children_count', 'family_size'],
        '결혼': ['marital_status'],
        '소득': ['job_title_raw', 'education_level']
    }
    
    for keyword, fields in IMPLICIT_RELATIONS.items():
        if keyword in query:
            related_fields.update(fields)
            
    return list(related_fields)


def find_target_columns_dynamic(question: str) -> List[str]:
    """
    질문 의도를 파악해 분석할 타겟 컬럼들을 LLM을 통해 동적으로 선정합니다.
    """
    # 1. LLM에게 제공할 컬럼 메타데이터 생성 (필드명: 한글설명)
    # 속도 최적화를 위해 문자열로 미리 포맷팅
    all_fields_str = ""
    valid_columns = []
    
    # 기본 인구통계 + Q-Poll 필드 병합
    for eng, kor in FIELD_NAME_MAP.items():
        all_fields_str += f"- {eng}: {kor}\n"
        valid_columns.append(eng)
        
    # Q-Poll 질문 텍스트도 매핑 정보로 활용
    for eng, text in QPOLL_FIELD_TO_TEXT.items():
        if eng not in FIELD_NAME_MAP: # 중복 제외
            all_fields_str += f"- {eng}: {text}\n"
            valid_columns.append(eng)

    # 2. LLM 호출
    logging.info(f"🔍 동적 컬럼 탐색 시작: '{question}'")
    found_columns = extract_relevant_columns_via_llm(question, all_fields_str)
    
    # 3. 유효성 검사 (실제 존재하는 컬럼만 필터링)
    final_columns = [col for col in found_columns if col in valid_columns]
    
    # 4. 보정 로직 (예: 질문에 '소득'이 있으면 관련 필드 강제 추가 등 - 필요시 작성)
    if '소득' in question and 'income_personal_monthly' not in final_columns:
        final_columns.append('income_personal_monthly')

    logging.info(f"✅ 매핑 완료: {final_columns}")
    return final_columns


def extract_relevant_columns_via_llm(question: str, all_columns_info: str) -> List[str]:
    """
    질문을 분석하여 통계 분석에 필요한 DB 컬럼명들을 추출합니다.
    """
    if not llm_client.CLAUDE_CLIENT: 
        logging.error("Claude Client is not initialized.")
        return []

    system_prompt = f"""
    You are a Data Analyst. Select the most relevant database columns from the [Column List] to answer the user's [Question].
    
    [Column List]
    {all_columns_info}
    
    [Rules]
    1. Return ONLY a JSON object with a key "columns" containing a list of strings.
    2. If no column is relevant, return "columns": [].
    3. Select strictly from the provided list.
    """
    
    user_prompt = f"Question: {question}"

    try:
        response = llm_client.CLAUDE_CLIENT.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ])
        
        # JSON 파싱 
        content = response.content.strip()
        if "```" in content:
            content = content.split("```")[1].replace("json", "").strip()
            
        data = json.loads(content)
        return data.get("columns", [])
    except Exception as e:
        logging.error(f"컬럼 추출 실패: {e}")
        return []
