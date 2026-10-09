"""插件服务层（阶段 2：只读骨架）。

本阶段实现：注册 / 查询 / 列表 / 审计日志。
**尚未实现**（后续阶段）：远程搜索、评分、安全审查、安装、回滚。
所有"未实现"的能力都显式抛 ``NotImplementedError``，绝不返回假成功。
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.db import transaction
from app.models import InstallStatus, Plugin, PluginKind, RiskLevel
from app.security import require_safe_identifier


class PluginNotFound(LookupError):
    """请求的插件不存在。"""


class ValidationError(ValueError):
    """输入不合法。"""


@dataclass(frozen=True)
class AuditRecord:
    seq: int
    ts: str
    actor: str
    action: str
    target: str | None
    outcome: str
    detail: str | None


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PluginService:
    """统一业务入口。线程内串行使用（SQLite 单连接）。"""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # ------------------------------------------------------------------ #
    # 审计
    # ------------------------------------------------------------------ #
    def audit(
        self,
        *,
        actor: str,
        action: str,
        target: str | None = None,
        outcome: str = "ok",
        detail: str | None = None,
    ) -> None:
        """记录一条审计日志。``actor`` 只允许 user / agent / system。"""
        if actor not in {"user", "agent", "system"}:
            raise ValidationError(f"actor 非法：{actor!r}")
        if outcome not in {"ok", "denied", "error"}:
            raise ValidationError(f"outcome 非法：{outcome!r}")
        with transaction(self._conn):
            self._conn.execute(
                "INSERT INTO audit_log(ts, actor, action, target, outcome, detail)"
                " VALUES(?,?,?,?,?,?)",
                (_utcnow_iso(), actor, action, target, outcome, detail),
            )

    def list_audit(self, limit: int = 50) -> list[AuditRecord]:
        limit = max(1, min(int(limit), 500))
        rows = self._conn.execute(
            "SELECT seq, ts, actor, action, target, outcome, detail"
            " FROM audit_log ORDER BY seq DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [AuditRecord(**dict(r)) for r in rows]

    # ------------------------------------------------------------------ #
    # 写入
    # ------------------------------------------------------------------ #
    def upsert(self, plugin: Plugin, *, actor: str = "system") -> Plugin:
        """插入或更新插件（按稳定 ID 幂等）。"""
        if not isinstance(plugin, Plugin):
            raise ValidationError("plugin 必须是 Plugin 实例")

        now = _utcnow_iso()
        payload = plugin.model_dump_json()
        with transaction(self._conn):
            self._conn.execute(
                """
                INSERT INTO plugins(id, source, slug, name, kind, risk_level,
                                    review_status, install_status, score_total,
                                    pinned_ref, data, created_at, updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    kind=excluded.kind,
                    risk_level=excluded.risk_level,
                    review_status=excluded.review_status,
                    install_status=excluded.install_status,
                    score_total=excluded.score_total,
                    pinned_ref=excluded.pinned_ref,
                    data=excluded.data,
                    updated_at=excluded.updated_at
                """,
                (
                    plugin.id,
                    plugin.source,
                    plugin.slug,
                    plugin.name,
                    plugin.kind.value,
                    plugin.risk_level.value,
                    plugin.review_status.value,
                    plugin.install_status.value,
                    plugin.score.total(),
                    plugin.pinned_ref,
                    payload,
                    plugin.created_at.isoformat(),
                    now,
                ),
            )
        self.audit(actor=actor, action="plugin.upsert", target=plugin.id, outcome="ok")
        return plugin

    def register_placeholder(
        self,
        *,
        source: str,
        slug: str,
        name: str,
        kind: PluginKind,
        actor: str = "user",
        **kwargs: Any,
    ) -> Plugin:
        """注册一个尚未经过完整审查的条目。

        **注意**：此类条目的 ``review_status`` 为 pending、``risk_level`` 为 none，
        含义是"尚未评估"，而不是"已确认安全"。调用方不得将其视为已审查。
        """
        require_safe_identifier(source.split(":")[-1].replace("/", "-"), what="source")
        require_safe_identifier(slug, what="slug")
        plugin = Plugin.new(source=source, slug=slug, name=name, kind=kind, **kwargs)
        return self.upsert(plugin, actor=actor)

    # ------------------------------------------------------------------ #
    # 读取
    # ------------------------------------------------------------------ #
    def get(self, plugin_id: str) -> Plugin:
        row = self._conn.execute(
            "SELECT data FROM plugins WHERE id = ?", (plugin_id,)
        ).fetchone()
        if row is None:
            raise PluginNotFound(plugin_id)
        return Plugin.model_validate_json(row["data"])

    def list(
        self,
        *,
        kind: PluginKind | None = None,
        risk_level: RiskLevel | None = None,
        install_status: InstallStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Plugin]:
        clauses: list[str] = []
        params: list[Any] = []
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind.value)
        if risk_level is not None:
            clauses.append("risk_level = ?")
            params.append(risk_level.value)
        if install_status is not None:
            clauses.append("install_status = ?")
            params.append(install_status.value)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        limit = max(1, min(int(limit), 500))
        offset = max(0, int(offset))
        params.extend([limit, offset])

        rows = self._conn.execute(
            f"SELECT data FROM plugins {where}"
            " ORDER BY score_total DESC, name ASC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        return [Plugin.model_validate_json(r["data"]) for r in rows]

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) AS c FROM plugins").fetchone()["c"])

    def stats(self) -> dict[str, Any]:
        by_kind = {
            r["kind"]: r["c"]
            for r in self._conn.execute(
                "SELECT kind, COUNT(*) AS c FROM plugins GROUP BY kind"
            )
        }
        by_install = {
            r["install_status"]: r["c"]
            for r in self._conn.execute(
                "SELECT install_status, COUNT(*) AS c FROM plugins GROUP BY install_status"
            )
        }
        return {
            "total": self.count(),
            "by_kind": by_kind,
            "by_install_status": by_install,
        }

    # ------------------------------------------------------------------ #
    # 尚未实现（显式失败，禁止伪成功）
    # ------------------------------------------------------------------ #
    def search_remote(self, query: str) -> list[Plugin]:
        raise NotImplementedError("远程搜索将在阶段 3 实现")

    def score(self, plugin_id: str) -> Plugin:
        raise NotImplementedError("评分将在阶段 3 实现")

    def review(self, plugin_id: str) -> Plugin:
        raise NotImplementedError("安全审查将在阶段 3 实现")

    def install(self, plugin_id: str, *, actor: str) -> Plugin:
        raise NotImplementedError("安装闭环将在阶段 5 实现")

    def rollback(self, plugin_id: str, *, actor: str) -> Plugin:
        raise NotImplementedError("回滚将在阶段 5 实现")


def dump_plugin(plugin: Plugin) -> dict[str, Any]:
    """稳定的 JSON 视图（供 API / MCP 复用）。"""
    return json.loads(plugin.model_dump_json())