import psycopg2.pool
from fastapi.testclient import TestClient

from tests.fakes.postgres import FakePool
from tests.golden import assert_golden
from tests.targets import patch_target, sym


def _reset_pool(monkeypatch):
    module, attr = patch_target("pg_pool")
    monkeypatch.setattr(module, attr, None)


def test_startup_with_db(env, monkeypatch):
    _reset_pool(monkeypatch)
    monkeypatch.setattr(psycopg2.pool, "ThreadedConnectionPool", lambda *a, **k: FakePool(env.ds))
    with TestClient(sym("app")) as c:
        health = c.get("/health").json()
    assert_golden("startup_with_db", health)


def test_startup_without_db_still_serves(env, monkeypatch):
    _reset_pool(monkeypatch)

    def _boom(*a, **k):
        raise psycopg2.OperationalError("db down")

    monkeypatch.setattr(psycopg2.pool, "ThreadedConnectionPool", _boom)
    with TestClient(sym("app")) as c:
        health = c.get("/health").json()
    assert_golden("startup_without_db", health)
