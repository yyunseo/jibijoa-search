import logging
from functools import lru_cache
from typing import List

from langchain_huggingface import HuggingFaceEmbeddings


@lru_cache(maxsize=None)
def initialize_embeddings():
    try:
        return HuggingFaceEmbeddings(model_name="nlpai-lab/KURE-v1", model_kwargs={'device': 'cpu'})
    except Exception as e:
        logging.error(f"임베딩 로드 실패: {e}")
        raise


def embed_keywords(keywords: List[str]) -> List[List[float]]:
    if not keywords: return []
    try:
        return initialize_embeddings().embed_documents(keywords)
    except Exception as e:
        logging.error(f"임베딩 실패: {e}")
        return []
