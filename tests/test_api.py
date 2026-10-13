import json

import pytest
from fastapi.testclient import TestClient

from tests.fixtures.llm_responses import S1, S2, S5
from tests.golden import assert_golden
from tests.targets import sym


def _sorted(items):
    return sorted(items, key=lambda x: json.dumps(x, ensure_ascii=False, sort_keys=True, default=str))


@pytest.fixture
def client(env):
    # with 없이 생성해서 startup/lifespan을 실행하지 않는다 (기동은 test_startup.py에서 따로 검증)
    return TestClient(sym("app"))


def test_root_and_health(env, client):
    assert_golden("api_root_health", {"root": client.get("/").json(), "health": client.get("/health").json()})


def test_search_lite(env, client):
    env.pool.sql_filter_result = ["p01", "p02", "p03", "p06", "p08"]
    r = client.post("/api/search", json={"query": S2})
    assert r.status_code == 200
    assert_golden("api_search_lite_s2", {"body": r.json(), "sql": env.pool.queries, "qdrant": env.qdrant.calls})


@pytest.mark.parametrize("name,query,sql_ids", [
    ("s1", S1, ["p01", "p05"]),
    ("s2", S2, ["p01", "p02", "p03", "p06", "p08"]),
])
def test_search_and_analyze_pro(env, client, name, query, sql_ids):
    env.pool.sql_filter_result = sql_ids
    r = client.post("/api/search-and-analyze", json={"query": query})
    assert r.status_code == 200
    body = r.json()
    # 우선순위가 같은 차트는 as_completed 순서에 따라 달라지는 기존 동작이 있어서 정렬해서 비교한다
    body["charts"] = _sorted(body["charts"])
    assert_golden(f"api_pro_{name}", {
        "body": body,
        "sql": _sorted(env.pool.queries),
        "qdrant": _sorted(env.qdrant.calls),
        "prompts": sorted(env.llm.prompt_hashes),
    })


def test_insight_summary(env, client):
    r = client.post("/api/insight/summary", json={"question": "이 사람들의 소득 분포는?", "panel_ids": ["p01", "p02", "p03"]})
    assert r.status_code == 200
    assert_golden("api_insight_summary", {"body": r.json(), "prompts": env.llm.prompt_hashes})


@pytest.mark.parametrize("payload", [
    {"question": "질문", "panel_ids": []},
    {"question": "", "panel_ids": ["p01"]},
])
def test_insight_summary_validation(env, client, payload):
    r = client.post("/api/insight/summary", json=payload)
    assert r.status_code == 400


def test_panel_detail(env, client):
    ok = client.get("/api/panels/p01")
    missing = client.get("/api/panels/nope")
    assert ok.status_code == 200 and missing.status_code == 404
    assert_golden("api_panel_detail", {"ok": ok.json(), "missing": missing.json()})


def test_debug_classify(env, client):
    r = client.post("/api/debug/classify", json={"query": S1})
    assert_golden("api_debug_classify", {"status": r.status_code, "body": r.json()})


def test_search_llm_failure_is_500(env, client):
    r = client.post("/api/search", json={"query": S5})
    assert_golden("api_search_llm_failure", {"status": r.status_code, "body": r.json()})
