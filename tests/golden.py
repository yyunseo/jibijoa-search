import json
import os
import pathlib
import re

GOLDEN_DIR = pathlib.Path(__file__).parent / "golden"


def norm(obj):
    if isinstance(obj, dict):
        return {str(k): norm(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [norm(v) for v in obj]
    if isinstance(obj, (set, frozenset)):
        return sorted((norm(v) for v in obj), key=lambda x: json.dumps(x, ensure_ascii=False, sort_keys=True, default=str))
    if isinstance(obj, float):
        return round(obj, 6)
    if hasattr(obj, "item") and callable(obj.item):  # numpy 스칼라
        return norm(obj.item())
    return obj


def norm_sql(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def assert_golden(name: str, obj) -> None:
    path = GOLDEN_DIR / f"{name}.json"
    text = json.dumps(norm(obj), ensure_ascii=False, indent=2, sort_keys=True, default=str)
    if os.environ.get("UPDATE_GOLDEN") == "1":
        GOLDEN_DIR.mkdir(exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
        return
    assert path.exists(), f"golden 없음: {path.name} (make golden으로 생성)"
    assert json.loads(path.read_text(encoding="utf-8")) == json.loads(text), f"golden 불일치: {path.name}"
