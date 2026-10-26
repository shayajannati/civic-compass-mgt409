"""Read-only access to the local SQLite directory (data/civic.db)."""

from __future__ import annotations

import sqlite3
import threading

from .config import DB_PATH

_local = threading.local()


def connection() -> sqlite3.Connection:
    con = getattr(_local, "con", None)
    if con is None:
        if not DB_PATH.exists():
            raise RuntimeError(f"Directory database missing at {DB_PATH}. Run: python scripts/build_db.py")
        con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, check_same_thread=False)
        con.row_factory = sqlite3.Row
        _local.con = con
    return con


def query(sql: str, params: tuple = ()) -> list[dict]:
    return [dict(r) for r in connection().execute(sql, params).fetchall()]
