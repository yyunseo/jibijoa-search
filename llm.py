import json
import re
import os
import logging
from typing import Dict, List, Optional, Any
from functools import lru_cache
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv
from app.core import llm_client

load_dotenv()









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