import logging

from langchain_anthropic import ChatAnthropic

from app.core.config import settings

# 1. Claude 클라이언트 설정
try:
    # API Key는 환경변수(.env)에서 자동으로 로드됩니다.
    CLAUDE_CLIENT = ChatAnthropic(model="claude-sonnet-4-5", temperature=0.1, api_key=settings.ANTHROPIC_API_KEY)
except Exception as e:
    CLAUDE_CLIENT = None
    logging.error(f"Anthropic 클라이언트 생성 실패: {e}")
