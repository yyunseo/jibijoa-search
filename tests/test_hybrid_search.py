import logging

import pytest

from tests.fixtures.llm_responses import S1, S2, S3, S4, S5
from tests.golden import assert_golden
from tests.targets import sym

SCENARIOS = [
    ("s1_structured_target", S1, ["p01", "p05"], "정형 데이터 타겟"),
    ("s2_rerank", S2, ["p01", "p02", "p03", "p06", "p08"], "Reranking 모드 진입"),
    ("s3_vector_only", S3, None, "일반 벡터 검색 모드 진입"),
    ("s4_negative", S4, None, "부정 조건 필터링 적용 (벡터)"),
]


@pytest.mark.parametrize("name,query,sql_ids,branch_log", SCENARIOS)
def test_hybrid_search_branches(env, caplog, name, query, sql_ids, branch_log):
    if sql_ids is not None:
        env.pool.sql_filter_result = sql_ids
    caplog.set_level(logging.DEBUG)
    result = sym("hybrid_search")(query=query, limit=30)
    assert branch_log in caplog.text, f"{name}: 의도한 분기({branch_log})에 들어가지 않음"
    assert_golden(f"search_{name}", {
        "result": result,
        "sql": env.pool.queries,
        "qdrant": env.qdrant.calls,
        "prompts": env.llm.prompt_hashes,
    })


def test_hybrid_search_llm_failure_returns_empty(env):
    result = sym("hybrid_search")(query=S5, limit=30)
    assert_golden("search_s5_llm_failure", result)
