"""PostgreSQL-backed adapter that mimics the subset of the supabase-py client
used across the pipeline. Swapped in when USE_LOCAL_PG=true.

Supports: client.table(name).select/insert/update/upsert/delete
          filters: eq, neq, in_, is_, gt, gte, lt, lte, ilike, like, or_
          modifiers: order, limit, range, single, maybe_single
          .execute() → returns object with .data (list or dict)
"""
import json
import logging
import os
import threading
from typing import Any, Optional

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)

_pool_lock = threading.Lock()
_conn_pool: list[psycopg.Connection] = []
_max_pool_size = 10


def _get_conn_str() -> str:
    return (
        f"host={os.environ.get('PG_HOST', 'localhost')} "
        f"port={os.environ.get('PG_PORT', '5432')} "
        f"dbname={os.environ.get('PG_DATABASE', 'seo_articles')} "
        f"user={os.environ.get('PG_USER', 'seo_user')} "
        f"password={os.environ.get('PG_PASSWORD', '')}"
    )


def _get_connection() -> psycopg.Connection:
    with _pool_lock:
        while _conn_pool:
            conn = _conn_pool.pop()
            if not conn.closed:
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1")
                    return conn
                except Exception:
                    try:
                        conn.close()
                    except Exception:
                        pass
    return psycopg.connect(_get_conn_str(), autocommit=True, row_factory=dict_row)


def _release_connection(conn: psycopg.Connection):
    with _pool_lock:
        if not conn.closed and len(_conn_pool) < _max_pool_size:
            _conn_pool.append(conn)
        else:
            try:
                conn.close()
            except Exception:
                pass


class _Result:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count


def _quote_ident(name: str) -> str:
    if name == "*":
        return "*"
    if "," in name:
        return ", ".join(_quote_ident(s.strip()) for s in name.split(","))
    # Simple identifier → quote. Otherwise pass through (expressions).
    if all(c.isalnum() or c == "_" for c in name) and name[0].isalpha() or name.startswith("_"):
        return f'"{name}"'
    return name


def _normalize_value(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        # psycopg handles dicts as jsonb via Jsonb adapter; but we JSON-stringify safely
        return json.dumps(v, ensure_ascii=False, default=str)
    return v


class _QueryBuilder:
    def __init__(self, table: str):
        self._table = table
        self._op: Optional[str] = None
        self._select_cols = "*"
        self._select_count = None
        self._select_head = False
        self._insert_rows: Optional[list] = None
        self._update_data: Optional[dict] = None
        self._upsert_data: Optional[list] = None
        self._upsert_on_conflict: str = "id"
        self._filters: list = []
        self._orders: list = []
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None
        self._range: Optional[tuple] = None
        self._single_mode: Optional[str] = None  # 'single'|'maybe'

    # ----- verbs -----
    def select(self, cols: str = "*", count: Optional[str] = None, head: bool = False):
        self._op = "select"
        self._select_cols = cols or "*"
        self._select_count = count
        self._select_head = head
        return self

    def insert(self, rows):
        self._op = "insert"
        self._insert_rows = rows if isinstance(rows, list) else [rows]
        return self

    def upsert(self, rows, on_conflict: str = "id"):
        self._op = "upsert"
        self._upsert_data = rows if isinstance(rows, list) else [rows]
        self._upsert_on_conflict = on_conflict
        return self

    def update(self, data: dict):
        self._op = "update"
        self._update_data = data
        return self

    def delete(self):
        self._op = "delete"
        return self

    # ----- filters -----
    def _add_filter(self, type_, col, val):
        self._filters.append({"type": type_, "col": col, "val": val})
        return self

    def eq(self, col, val): return self._add_filter("eq", col, val)
    def neq(self, col, val): return self._add_filter("neq", col, val)
    def gt(self, col, val): return self._add_filter("gt", col, val)
    def gte(self, col, val): return self._add_filter("gte", col, val)
    def lt(self, col, val): return self._add_filter("lt", col, val)
    def lte(self, col, val): return self._add_filter("lte", col, val)
    def in_(self, col, val): return self._add_filter("in", col, val)
    def is_(self, col, val): return self._add_filter("is", col, val)
    def like(self, col, val): return self._add_filter("like", col, val)
    def ilike(self, col, val): return self._add_filter("ilike", col, val)
    def contains(self, col, val): return self._add_filter("contains", col, val)
    def not_(self, col, op, val): return self._add_filter("not", col, {"op": op, "val": val})

    # ----- modifiers -----
    def order(self, col, desc: bool = False, ascending: Optional[bool] = None):
        # supabase-py uses desc=True, Node-style uses ascending=
        if ascending is not None:
            asc = ascending
        else:
            asc = not desc
        self._orders.append({"col": col, "ascending": asc})
        return self

    def limit(self, n: int):
        self._limit = n
        return self

    def range(self, start: int, end: int):
        self._range = (start, end)
        return self

    def single(self):
        self._single_mode = "single"
        return self

    def maybe_single(self):
        self._single_mode = "maybe"
        return self

    # ----- execute -----
    def execute(self):
        conn = _get_connection()
        try:
            if self._op == "select" or self._op is None:
                return self._execute_select(conn)
            if self._op == "insert":
                return self._execute_insert(conn)
            if self._op == "upsert":
                return self._execute_upsert(conn)
            if self._op == "update":
                return self._execute_update(conn)
            if self._op == "delete":
                return self._execute_delete(conn)
            raise RuntimeError(f"Unknown op: {self._op}")
        finally:
            _release_connection(conn)

    def _build_where(self, start_idx: int = 0):
        params = []
        conds = []
        for f in self._filters:
            col = f'"{f["col"]}"' if f["col"] else None
            t = f["type"]
            v = f["val"]
            if t == "eq":
                if v is None:
                    conds.append(f"{col} IS NULL")
                else:
                    conds.append(f"{col} = %s")
                    params.append(v)
            elif t == "neq":
                if v is None:
                    conds.append(f"{col} IS NOT NULL")
                else:
                    conds.append(f"{col} <> %s")
                    params.append(v)
            elif t == "gt":
                conds.append(f"{col} > %s"); params.append(v)
            elif t == "gte":
                conds.append(f"{col} >= %s"); params.append(v)
            elif t == "lt":
                conds.append(f"{col} < %s"); params.append(v)
            elif t == "lte":
                conds.append(f"{col} <= %s"); params.append(v)
            elif t == "is":
                if v is None:
                    conds.append(f"{col} IS NULL")
                elif v is True:
                    conds.append(f"{col} IS TRUE")
                elif v is False:
                    conds.append(f"{col} IS FALSE")
                else:
                    conds.append(f"{col} = %s"); params.append(v)
            elif t == "in":
                arr = list(v) if not isinstance(v, (list, tuple)) else list(v)
                if not arr:
                    conds.append("FALSE")
                else:
                    placeholders = ",".join(["%s"] * len(arr))
                    conds.append(f"{col} IN ({placeholders})")
                    params.extend(arr)
            elif t == "like":
                conds.append(f"{col} LIKE %s"); params.append(v)
            elif t == "ilike":
                conds.append(f"{col} ILIKE %s"); params.append(v)
            elif t == "contains":
                conds.append(f"{col} @> %s")
                params.append(v if isinstance(v, str) else json.dumps(v))
            elif t == "not":
                inner_op = v["op"]
                inner_val = v["val"]
                if inner_op == "is" and inner_val is None:
                    conds.append(f"{col} IS NOT NULL")
                elif inner_op == "eq":
                    conds.append(f"{col} <> %s"); params.append(inner_val)
                else:
                    raise RuntimeError(f"Unsupported not({inner_op})")
        where = f" WHERE {' AND '.join(conds)}" if conds else ""
        return where, params

    def _build_order_limit(self) -> str:
        sql = ""
        if self._orders:
            parts = []
            for o in self._orders:
                direction = "ASC" if o["ascending"] else "DESC"
                parts.append(f'"{o["col"]}" {direction} NULLS LAST')
            sql += " ORDER BY " + ", ".join(parts)
        if self._range is not None:
            start, end = self._range
            sql += f" LIMIT {end - start + 1} OFFSET {start}"
        else:
            if self._limit is not None:
                sql += f" LIMIT {self._limit}"
            if self._offset is not None:
                sql += f" OFFSET {self._offset}"
        return sql

    def _format_result(self, rows, count=None) -> _Result:
        if self._single_mode == "single":
            if not rows:
                raise RuntimeError(f"PGRST116: no rows found in {self._table}")
            if len(rows) > 1:
                raise RuntimeError(f"Multiple rows returned for single() in {self._table}")
            return _Result(rows[0], count)
        if self._single_mode == "maybe":
            return _Result(rows[0] if rows else None, count)
        return _Result(rows, count)

    def _execute_select(self, conn) -> _Result:
        cols = "*" if self._select_cols == "*" else _quote_ident(self._select_cols)
        where, params = self._build_where()
        order_limit = self._build_order_limit()

        count = None
        if self._select_count == "exact":
            with conn.cursor() as cur:
                cur.execute(f'SELECT COUNT(*)::int AS c FROM "{self._table}"{where}', params)
                count = cur.fetchone()["c"]

        if self._select_head:
            return _Result(None, count)

        sql = f'SELECT {cols} FROM "{self._table}"{where}{order_limit}'
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return self._format_result(rows, count)

    def _execute_insert(self, conn) -> _Result:
        if not self._insert_rows:
            return _Result([])
        cols = list(self._insert_rows[0].keys())
        placeholders_per_row = f"({','.join(['%s'] * len(cols))})"
        params = []
        for row in self._insert_rows:
            for c in cols:
                params.append(_normalize_value(row.get(c)))
        values_sql = ",".join([placeholders_per_row] * len(self._insert_rows))
        cols_sql = ",".join(f'"{c}"' for c in cols)
        sql = f'INSERT INTO "{self._table}" ({cols_sql}) VALUES {values_sql} RETURNING *'
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return _Result(rows)

    def _execute_upsert(self, conn) -> _Result:
        if not self._upsert_data:
            return _Result([])
        cols = list(self._upsert_data[0].keys())
        conflict_cols = [c.strip() for c in self._upsert_on_conflict.split(",")]
        update_cols = [c for c in cols if c not in conflict_cols]

        placeholders_per_row = f"({','.join(['%s'] * len(cols))})"
        params = []
        for row in self._upsert_data:
            for c in cols:
                params.append(_normalize_value(row.get(c)))
        values_sql = ",".join([placeholders_per_row] * len(self._upsert_data))
        cols_sql = ",".join(f'"{c}"' for c in cols)
        conflict_sql = ",".join(f'"{c}"' for c in conflict_cols)

        if update_cols:
            set_sql = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in update_cols)
            conflict_action = f"DO UPDATE SET {set_sql}"
        else:
            conflict_action = "DO NOTHING"

        sql = (
            f'INSERT INTO "{self._table}" ({cols_sql}) VALUES {values_sql} '
            f"ON CONFLICT ({conflict_sql}) {conflict_action} RETURNING *"
        )
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return _Result(rows)

    def _execute_update(self, conn) -> _Result:
        if not self._update_data:
            return _Result([])
        cols = list(self._update_data.keys())
        set_parts = ", ".join(f'"{c}" = %s' for c in cols)
        params = [_normalize_value(self._update_data[c]) for c in cols]
        where, where_params = self._build_where()
        params.extend(where_params)
        sql = f'UPDATE "{self._table}" SET {set_parts}{where} RETURNING *'
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return _Result(rows)

    def _execute_delete(self, conn) -> _Result:
        where, params = self._build_where()
        sql = f'DELETE FROM "{self._table}"{where} RETURNING *'
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return _Result(rows)


class _PgClient:
    """Facade that mimics supabase-py Client."""

    def table(self, name: str) -> _QueryBuilder:
        return _QueryBuilder(name)

    def rpc(self, name, params=None):
        raise NotImplementedError("rpc() not supported — replace with direct SQL")

    @property
    def storage(self):
        raise NotImplementedError("storage not supported in pg adapter")


_client: Optional[_PgClient] = None
_init_lock = threading.Lock()


def get_pg_client() -> _PgClient:
    global _client
    if _client is None:
        with _init_lock:
            if _client is None:
                _client = _PgClient()
                logger.info("Local PostgreSQL client initialized")
    return _client
