"""运行期容器。

把 ``Settings`` / SQLite 连接 / ``PluginService`` 组装成单一对象，
供网页与 MCP 两侧共用（**同一个 service 实例语义**）。
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.config import Settings, load_settings
from app.db import open_database
from app.services import PluginService


@dataclass
class Runtime:
    settings: Settings
    conn: sqlite3.Connection
    plugins: PluginService

    @classmethod
    def create(cls, settings: Settings | None = None) -> "Runtime":
        settings = settings or load_settings()
        conn = open_database(settings.db_path)
        return cls(settings=settings, conn=conn, plugins=PluginService(conn))

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:  # pragma: no cover - 关闭失败不影响退出
            pass
