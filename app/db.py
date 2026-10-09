"""SQLite 存储层。

- 仅使用标准库 ``sqlite3``（不引入 ORM，见 docs/architecture.md 技术选型）。
- 连接统一开启 ``PRAGMA foreign_keys=ON`` 与 WAL。
- 所有写操作走显式事务；``check_same_thread=False`` 配合调用方串行化。
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plugins (
    id             TEXT PRIMARY KEY,
    source         TEXT NOT NULL,
    slug           TEXT NOT NULL,
    name           TEXT NOT NULL,
    kind           TEXT NOT NULL,
    risk_level     TEXT NOT NULL DEFAULT 'none',
    review_status  TEXT NOT NULL DEFAULT 'pending',
    install_status TEXT NOT NULL DEFAULT 'not_installed',
    score_total    REAL NOT NULL DEFAULT 0.0,
    pinned_ref     TEXT,
    data           TEXT NOT NULL,          -- 完整 Plugin 的 JSON 序列化
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    UNIQUE (source, slug)
);

CREATE INDEX IF NOT EXISTS idx_plugins_kind   ON plugins(kind);
CREATE INDEX IF NOT EXISTS idx_plugins_risk   ON plugins(risk_level);
CREATE INDEX IF NOT EXISTS idx_plugins_install ON plugins(install_status);

CREATE TABLE IF NOT EXISTS audit_log (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT NOT NULL,
    actor      TEXT NOT NULL,              -- 'user' | 'agent' | 'system'
    action     TEXT NOT NULL,
    target     TEXT,
    outcome    TEXT NOT NULL,              -- 'ok' | 'denied' | 'error'
    detail     TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts);
"""


def connect(db_path: Path | str) -> sqlite3.Connection:
    """建立连接并完成基础 PRAGMA 设置。"""
    path = Path(db_path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if str(path) != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """创建 schema（幂等）。"""
    with transaction(conn):
        conn.executescript(_SCHEMA)
        conn.execute(
            "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )


def get_schema_version(conn: sqlite3.Connection) -> int | None:
    try:
        row = conn.execute(
            "SELECT value FROM schema_meta WHERE key='schema_version'"
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    return int(row["value"]) if row else None


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """显式事务；异常时回滚并重新抛出（**不吞异常**）。"""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def open_database(db_path: Path | str) -> sqlite3.Connection:
    """便捷入口：连接 + 初始化。"""
    conn = connect(db_path)
    init_db(conn)
    return conn