from tests.targets import sym


def test_app_imports_with_fakes(env):
    app = sym("app")
    paths = sorted(r.path for r in app.routes if hasattr(r, "path"))
    for p in ["/", "/health", "/api/search", "/api/search-and-analyze",
              "/api/insight/summary", "/api/debug/classify", "/api/panels/{panel_id}"]:
        assert p in paths


def test_parse_query_uses_fake_llm(env):
    from tests.fixtures.llm_responses import S1
    parsed = sym("parse_query")(S1)
    assert parsed["limit"] == 30
    assert parsed["demographic_filters"]["gender"] == ["남성"]
