"""테스트가 참조하는 모든 모듈 경로. 리팩토링 각 단계에서는 이 파일만 고친다."""
import importlib

SYMBOLS = {
    "app": "main:app",
    "QPOLL_FIELD_TO_TEXT": "app.panels.fields:QPOLL_FIELD_TO_TEXT",
    "build_sql": "search_helpers:build_sql_from_structured_filters",
    "extract_answer_from_template": "app.panels.table:extract_answer_from_template",
    "prepare_display_fields": "services:_prepare_display_fields",
    "get_negative_patterns": "mapping_rules:get_negative_patterns",
    "get_field_mapping": "mapping_rules:get_field_mapping",
    "find_related_fields": "mapping_rules:find_related_fields",
    "get_age_group": "app.panels.age:get_age_group",
    "calculate_distribution": "utils:calculate_distribution",
    "find_top_category": "utils:find_top_category",
    "parse_query": "llm:parse_query_intelligent",
    "hybrid_search": "search:hybrid_search",
    "rerank_candidates": "search:rerank_candidates",
}

PATCH_POINTS = {
    "qdrant_client_cls": "app.core.qdrant:QdrantClient",
    "pg_pool": "app.core.postgres:_connection_pool",
    "llm_client": "app.core.llm_client:CLAUDE_CLIENT",
}

CACHE_CLEAR = ["parse_query"]


def sym(name: str):
    module, attr = SYMBOLS[name].split(":")
    obj = importlib.import_module(module)
    for part in attr.split("."):
        obj = getattr(obj, part)
    return obj


def patch_target(name: str):
    module, attr = PATCH_POINTS[name].split(":")
    return importlib.import_module(module), attr
