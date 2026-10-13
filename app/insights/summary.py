import logging
from typing import Dict, List

import pandas as pd
from langchain_core.messages import HumanMessage, SystemMessage

from app.core import llm_client
from app.panels.age import get_age_group
from app.panels.fields import (
    FIELD_NAME_MAP,
    QPOLL_FIELD_TO_TEXT,
)
from app.panels.repository import PanelRepository
from app.query.field_matching import find_target_columns_dynamic



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


def generate_stats_summary(question: str, stats_context: str) -> str:
    """
    계산된 통계 텍스트를 바탕으로 답변을 생성합니다.
    """
    if not llm_client.CLAUDE_CLIENT: return "AI 모델이 연결되지 않아 요약을 생성할 수 없습니다."

    system_prompt = """
    당신은 데이터 인사이트 전문가입니다. 
    제공된 [데이터 통계]를 근거로 [사용자 질문]에 대한 핵심 요약을 작성하세요.
    
    [작성 원칙]
    1. 막연한 표현 대신 **제공된 수치(명, %)**를 반드시 인용하여 근거를 제시하세요. 
    2. 가장 두드러진 특징(최댓값, 과반수 등)을 강조하세요.
    3. 질문과 관련 없는 통계는 언급하지 마세요.
    4. "~하는 것이 특징입니다"와 같은 분석적인 어조를 사용하세요.
    5. 한국어로 간결하게 답변하세요 (3문장 내외).
    """
    
    user_prompt = f"""
    [사용자 질문]
    {question}
    
    [데이터 통계 (Python 계산 결과)]
    {stats_context}
    """
    
    try:
        response = llm_client.CLAUDE_CLIENT.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ])
        return response.content.strip()
    except Exception as e:
        logging.error(f"통계 요약 생성 실패: {e}")
        return "요약 생성 중 오류가 발생했습니다."


def generate_demographic_summary(query: str, stats_text: str, total_count: int) -> str:
    """
    통계 데이터를 바탕으로 '인사이트'가 담긴 요약 문장을 생성합니다.
    """
    if not llm_client.CLAUDE_CLIENT: return ""

    system_prompt = """
    당신은 데이터 인사이트 전문가입니다. 
    제공된 [데이터 통계]를 근거로 [사용자 질문]에 대한 핵심 요약을 작성하세요.
    
    [작성 원칙]
    1. 막연한 표현 대신 **제공된 수치(명, %)**를 반드시 인용하여 근거를 제시하세요. 
    2. 가장 두드러진 특징(최댓값, 과반수 등)을 강조하세요.
    3. 질문과 관련 없는 통계는 언급하지 마세요.
    4. "~하는 것이 특징입니다"와 같은 분석적인 어조를 사용하세요.
    6. 마케팅을 위한 인사이트를 추가로 제안하세요.
    5. 한국어로 간결하게 답변하세요 (5문장 내외).
    """
    
    user_prompt = f"""
    [사용자 질문]
    {query}

    [분석 대상]
    총 {total_count}명의 패널

    [통계 데이터]
    {stats_text}

    위 데이터를 바탕으로 핵심 분석 요약 마케팅 인사이트를 작성해주세요.
    """

    try:
        response = llm_client.CLAUDE_CLIENT.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ])
        return response.content.strip()
    except Exception as e:
        logging.error(f"요약 생성 실패: {e}")
        return "데이터 분석 중 오류가 발생했습니다."
