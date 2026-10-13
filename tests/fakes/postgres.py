from tests.golden import norm, norm_sql


class FakeCursor:
    def __init__(self, pool):
        self.pool = pool
        self._rows = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        s = norm_sql(sql)
        self.pool.queries.append({"sql": s, "params": norm(params)})
        self._rows = self.pool.respond(s, params)

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def close(self):
        pass


class FakeConn:
    def __init__(self, pool):
        self.pool = pool

    def cursor(self):
        return FakeCursor(self.pool)

    def commit(self):
        pass

    def rollback(self):
        pass


class FakePool:
    """psycopg2 ThreadedConnectionPool 대역. SQL은 실행하지 않고 기록한 뒤 미리 정한 행을 돌려준다."""

    def __init__(self, ds):
        self.ds = ds
        self.queries = []
        self.sql_filter_result = sorted(ds.panels)

    def getconn(self):
        return FakeConn(self)

    def putconn(self, conn):
        pass

    def closeall(self):
        pass

    def respond(self, s: str, params):
        panels = self.ds.panels
        if s.startswith("SELECT panel_id FROM welcome_meta2"):
            return [(pid,) for pid in self.sql_filter_result]
        if s.startswith("WITH id_order"):
            return [(pid, panels[pid]) for pid in params[0] if pid in panels]
        if s.startswith("SELECT structured_data FROM welcome_meta2 WHERE panel_id = ANY"):
            return [(panels[pid],) for pid in params[0] if pid in panels]
        if s.startswith("SELECT panel_id, structured_data FROM welcome_meta2 WHERE panel_id = %s"):
            pid = params[0]
            return [(pid, panels[pid])] if pid in panels else []
        if "COUNT(*)" in s:
            return [("값A", 3, 60.0), ("값B", 2, 40.0)]
        raise AssertionError(f"예상하지 못한 SQL: {s[:120]}")
