import os
import sys
import types

# 앱 모듈을 import하기 전에 설정해야 한다 (settings는 import 시점에 비밀 값을 읽는다)
os.environ.setdefault("DB_PASSWORD", "test-password")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tests.fakes.embeddings import FakeHuggingFaceEmbeddings  # noqa: E402

_hf = types.ModuleType("langchain_huggingface")
_hf.HuggingFaceEmbeddings = FakeHuggingFaceEmbeddings
sys.modules["langchain_huggingface"] = _hf

from types import SimpleNamespace  # noqa: E402

import pytest  # noqa: E402
from freezegun import freeze_time  # noqa: E402

from tests.fakes.llm import FakeLLM  # noqa: E402
from tests.fakes.postgres import FakePool  # noqa: E402
from tests.fakes.qdrant import FakeQdrantClient  # noqa: E402
from tests.fixtures.dataset import build_dataset  # noqa: E402
from tests.fixtures.llm_responses import PARSE_RESPONSES  # noqa: E402
from tests.targets import CACHE_CLEAR, patch_target, sym  # noqa: E402


def pytest_configure(config):
    if os.environ.get("PYTHONHASHSEED") != "0":
        pytest.exit("PYTHONHASHSEED=0 으로 실행하세요 (make test)", returncode=2)
    # freeze_time이 켜진 상태에서 처음 import하면 pydantic.v1이 가짜 date를 상속하다 깨진다.
    # 시간을 고정하기 전에 앱 전체를 한 번 import해 둔다.
    sym("app")


@pytest.fixture(autouse=True)
def _frozen_time():
    with freeze_time("2026-10-13 12:00:00"):
        yield


@pytest.fixture
def env(monkeypatch):
    ds = build_dataset()
    qdrant = FakeQdrantClient(ds.collections)
    pool = FakePool(ds)
    llm = FakeLLM(PARSE_RESPONSES)

    module, attr = patch_target("qdrant_client_cls")
    monkeypatch.setattr(module, attr, lambda *a, **k: qdrant)
    module, attr = patch_target("pg_pool")
    monkeypatch.setattr(module, attr, pool)
    module, attr = patch_target("llm_client")
    monkeypatch.setattr(module, attr, llm)

    for name in CACHE_CLEAR:
        sym(name).cache_clear()
    yield SimpleNamespace(ds=ds, qdrant=qdrant, pool=pool, llm=llm)
    for name in CACHE_CLEAR:
        sym(name).cache_clear()
