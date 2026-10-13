import logging

from tests.fakes.embeddings import _vec
from tests.golden import assert_golden
from tests.targets import sym


def _run(env, candidates, target_question, query="운동"):
    out = sym("rerank_candidates")(
        candidate_ids=candidates,
        query_vector=_vec(query),
        qdrant_client=env.qdrant,
        collection_name="qpoll_vectors_v2",
        id_key_path="panel_id",
        negative_patterns=sym("get_negative_patterns")("stress_relief_method"),
        target_question=target_question,
    )
    return {"out": out, "qdrant": env.qdrant.calls}


def test_rerank_python_question_filter(env):
    q = sym("QPOLL_FIELD_TO_TEXT")["stress_relief_method"]
    assert_golden("rerank_python_filter", _run(env, ["p01", "p02", "p04", "p06", "p08"], q))


def test_rerank_question_mismatch_falls_back(env, caplog):
    caplog.set_level(logging.WARNING)
    result = _run(env, ["p01", "p02"], "존재하지 않는 질문 텍스트")
    assert "질문 매칭 실패" in caplog.text
    assert_golden("rerank_fallback", result)


def test_rerank_large_candidate_uses_db_filter(env):
    q = sym("QPOLL_FIELD_TO_TEXT")["stress_relief_method"]
    candidates = [f"x{i:05d}" for i in range(2001)] + ["p01", "p08"]
    result = _run(env, candidates, q)
    assert result["qdrant"][0]["filter"][-1]["match"] == "MatchText"
    assert_golden("rerank_db_filter", result)


def test_rerank_no_question(env):
    assert_golden("rerank_no_question", _run(env, ["p01", "p03", "p05"], None, query="키워본 적이 없다"))
