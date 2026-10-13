import hashlib
import math

DIM = 64


def _vec(text: str) -> list:
    """문자 3-gram 해시 기반의 결정적 벡터. 비슷한 문자열일수록 코사인 유사도가 높다."""
    v = [0.0] * DIM
    t = f"  {text}  "
    for i in range(len(t) - 2):
        h = int(hashlib.md5(t[i:i + 3].encode("utf-8")).hexdigest(), 16)
        v[h % DIM] += 1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class FakeHuggingFaceEmbeddings:
    def __init__(self, model_name=None, model_kwargs=None, **kwargs):
        self.model_name = model_name

    def embed_query(self, text):
        return _vec(text)

    def embed_documents(self, texts):
        return [_vec(t) for t in texts]
