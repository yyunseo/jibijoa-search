import json
import logging
import re
from functools import lru_cache
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage

from app.core import llm_client

load_dotenv()


# 2. DB 스키마 정보
DB_SCHEMA_INFO = """
## PostgreSQL (인구통계)
- gender, birth_year, region_major, marital_status, education_level
- job_title_raw (e.g. 학생, 주부, 회사원), job_duty_raw (e.g. 전문직, 사무직, 기술직)
- income_personal_monthly: ["월 100만원 미만", "월 100~199만원", "월 200~299만원", "월 300~399만원", "월 400~499만원", "월 500~599만원", "월 600~699만원", "월 700만원 이상"]
- car_ownership, smoking_experience, drinking_experience
"""


# 3. 시스템 프롬프트 
SYSTEM_PROMPT_V2 = """
You are a Search Query Analyzer. Parse the query into "Demographic Filters (SQL)" and "Semantic Conditions (Vector)".

## 📋 DB Schema
{schema}

## 🛠️ Extraction Rules

### 1. Demographic Filters (Strict SQL)
Extract ONLY explicit matches. **ALL VALUES MUST BE TRANSLATED TO KOREAN.**
Extract ONLY explicit matches for these fields:
- **Basic**: `age` (convert to range), `gender`, `region` (e.g., 서울, 경기).
- **Social**: `marital_status`, `family_size`, `children_count`.
- **Status**: `job`, `education_level`, `income_personal`, `income_household`.
- **Asset**: `car_ownership` (Only 'have car' or 'no car').
**[IMPORTANT RULE for INCOME]**
- If the query mentions **"earning", "salary", "making money" (e.g., 돈을 많이 버는, 연봉, 월급)** combined with a **Job/Profession**, map it to **`income_personal_monthly`**.
- Map to `income_household_monthly` ONLY when "household", "family income", or "house" (e.g., 가구 소득, 집안 형편) is explicitly mentioned.
*Note: Do NOT infer missing data. Exclude smoking/drinking/appliances here.*

### 2. Semantic Conditions (Vector Search)
Extract all other subjective intents, hobbies, habits, and specific item ownerships (e.g., specific car model, phone type).
- **Negative Handling**: Mark "don't", "no", "hate" (e.g., "안 하는", "없는") as **`is_negative: true`**.
- **Expansion**: Generate 3 positive synonyms in `expanded_queries` even for negative conditions.
- **Importance**: 0.9 (Core), 0.7 (Important), 0.5 (Optional).

## 💡 Few-Shot Examples

**Query**: "서울 경기 사는 20대 남성 중 OTT 즐겨 보고 주말에 배달음식 시켜먹는 사람 30명"
**Output**:
{
  "demographic_filters": { "region_major": ["서울", "경기"], "age_range": [20, 29], "gender": ["남성"] },
  "semantic_conditions": [
    { "original_keyword": "OTT를 즐겨 보고", "is_negative": false, "importance": 0.9, "expanded_queries": ["넷플릭스나 유튜브를 자주 본다", "동영상 스트리밍 구독 중이다", "주말에 드라마 정주행한다"] },
    { "original_keyword": "주말에 배달음식 시켜먹는", "importance": 0.7, "expanded_queries": ["배달 앱을 자주 쓴다", "요기요나 배민을 이용한다", "배달 음식을 선호한다"] }
  ],
  "limit": 30
}

**Query**: "경기도 사는 30대 중 고양이를 안 키우는 사람"
**Output**:
{
  "demographic_filters": { "region_major": ["경기"], "age_range": [30, 39] },
  "semantic_conditions": [
    { 
      "original_keyword": "고양이를 안 키우는", 
      "is_negative": true, 
      "importance": 0.9, 
      "expanded_queries": ["고양이를 키운다", "반려묘가 있다", "고양이 집사다"],
      "note": "Filter out people similar to expanded_queries"
    }
  ],
  "limit": 100
}

## 📤 Output Format (JSON Only)
Return ONLY the raw JSON.
{
  "demographic_filters": { ... },
  "semantic_conditions": [ ... ],
  "limit": <number>
}

*** Target Query ***
<query>
{{QUERY}}
</query> 
"""


@lru_cache(maxsize=256)
def parse_query_intelligent(query: str) -> Dict[str, Any]:
   """ 쿼리를 지능적으로 파싱하여 구조화된 검색 조건 생성 """ 
   if llm_client.CLAUDE_CLIENT is None:
       raise RuntimeError("Claude 클라이언트가 초기화되지 않았습니다.")
   
   logging.info(f"🔄 LLM Parser v2 호출 중: {query}")

   # 프롬프트 생성 (schema는 단순 문자열 치환, QUERY는 사용자 입력 치환)
   prompt = SYSTEM_PROMPT_V2.replace("{{QUERY}}", query).replace("{schema}", DB_SCHEMA_INFO)

   try:
       messages = [
           SystemMessage(content=prompt),
           HumanMessage(content="Analyze the query and provide structured search conditions in JSON.")
       ]
       
       response = llm_client.CLAUDE_CLIENT.invoke(messages)
       text_output = response.content.strip()
       logging.info(f"🤖 Claude LLM 원본 응답:\n---\n{text_output}\n---")
       
       # JSON 추출 (마크다운 코드 블록 제거)
       json_match = re.search(r'```(?:json)?\s*({.*?})\s*```', text_output, re.DOTALL)
       if json_match:
           json_str = json_match.group(1)
       else:
           json_match = re.search(r'({.*})', text_output, re.DOTALL)
           if json_match:
               json_str = json_match.group(1)
           else:
               json_str = text_output
       
       parsed = json.loads(json_str)
       
       # 기본값 설정 및 반환 구조 생성
       result = {
           'demographic_filters': parsed.get('demographic_filters', {}),
           'semantic_conditions': parsed.get('semantic_conditions', []),
           'logic_structure': parsed.get('logic_structure', {'operator': 'AND', 'children': []}),
           'exclude_conditions': parsed.get('exclude_conditions', []),
           'search_strategy_recommendation': parsed.get('search_strategy_recommendation', {
               'strategy': 'balanced',
               'use_collections': ['welcome_subjective_vectors', 'qpoll_vectors_v2']
           }),
           'limit': parsed.get('limit', 100),
           'query_intent': parsed.get('query_intent', {})
       }
       
       logging.debug(f"✅ LLM Parser v2 완료")
       logging.info(f"  - Demographic filters: {result['demographic_filters']}")
       intent_keywords = [c.get('original_keyword', '') for c in result['semantic_conditions']]
       logging.info(f"  - Semantic conditions: {intent_keywords}")

       # 🔍 디버깅: Semantic Conditions 상세 정보 출력 (DEBUG 레벨)
       if result['semantic_conditions']:
           logging.debug("="*60)
           logging.debug("🔍 [디버깅] Semantic Conditions 상세 정보:")
           for idx, cond in enumerate(result['semantic_conditions'], 1):
               logging.debug(f"  [{idx}] original_keyword: {cond.get('original_keyword')}")
               logging.debug(f"      importance: {cond.get('importance')}")
               logging.debug(f"      search_strategy: {cond.get('search_strategy')}")
               expanded = cond.get('expanded_queries', [])
               if expanded:
                   logging.debug(f"      expanded_queries:")
                   for exp_idx, exp_q in enumerate(expanded, 1):
                       logging.debug(f"        {exp_idx}. {exp_q}")
           logging.debug("="*60)
       
       return result
       
   except json.JSONDecodeError as je:
       logging.error(f"❌ JSON 파싱 실패: {je.msg}. 원본: {text_output}")
       raise RuntimeError(f"Claude 응답 파싱 실패: {je.msg}")
   except Exception as e:
       logging.error(f"❌ Claude 호출 실패: {e}", exc_info=True)
       raise RuntimeError(f"Claude 호출 실패: {e}")


def extract_limit_from_query(query: str) -> Optional[int]:
    """쿼리에서 인원 수 추출"""
    all_limit_matches = re.findall(r'(\d+)\s*명', query)
    if all_limit_matches:
        try:
            return int(all_limit_matches[-1])
        except ValueError:
            pass
    return None
