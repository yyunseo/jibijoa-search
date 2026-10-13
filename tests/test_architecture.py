import ast
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP = ROOT / "app"

# 화살표 방향으로만 import 허용 (spec §5.1)
ALLOWED = {
    "core": set(),
    "panels": {"core"},
    "query": {"panels", "core"},
    "search": {"query", "panels", "core"},
    "insights": {"query", "panels", "core"},
    "api": {"search", "insights", "query", "panels", "core"},
}


def _imports(path: pathlib.Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app."):
            yield node.module.split(".")[1]
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith("app."):
                    yield a.name.split(".")[1]


def test_layer_dependencies():
    violations = []
    for layer, allowed in ALLOWED.items():
        for py in (APP / layer).rglob("*.py"):
            for target in _imports(py):
                if target != layer and target not in allowed:
                    violations.append(f"{py.relative_to(ROOT)} -> app.{target}")
    assert not violations, violations


def test_no_flat_modules_left():
    assert sorted(p.name for p in ROOT.glob("*.py")) == []


def test_dead_code_removed():
    # spec §6.1: 호출하는 곳이 없어서 삭제하기로 한 코드
    from app.core import postgres
    from app.panels.repository import VectorRepository
    assert not hasattr(postgres, "log_search_query")
    assert not hasattr(postgres, "get_panels_data_from_db")
    assert not hasattr(VectorRepository, "hybrid_search")
    # 유일한 호출부(generate_dynamic_insight)가 삭제되면서 함께 도달 불가능해진 모듈
    assert not (APP / "insights" / "clustering.py").exists()


def test_no_panel_data_tracked():
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    banned = [f for f in files if f.endswith((".xlsx", "welcome_data.json", "merged_qpoll_data.json"))]
    big = [f for f in files if (ROOT / f).is_file() and (ROOT / f).stat().st_size > 500_000]
    assert not banned and not big, banned + big
    # 히스토리 전체에도 패널 데이터가 없어야 한다 (Task 1의 정리 결과 보호)
    in_history = subprocess.run(["git", "log", "--all", "--oneline", "--", "welcome_data.json"],
                                cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    assert in_history == "", in_history


def test_deploy_script_forwards_cors_origins():
    # 운영 origin은 CORS_ORIGINS로만 들어오므로 CodeDeploy 경로(start.sh)도 컨테이너에 전달해야 한다
    start = (ROOT / "scripts" / "start.sh").read_text(encoding="utf-8")
    assert '-e CORS_ORIGINS="${CORS_ORIGINS}"' in start
    assert "${CORS_ORIGINS:?" in start
