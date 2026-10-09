"""FastAPI 应用装配。

阶段 2 范围：**只读** API + 静态控制台页面 + 基础安全中间件。
- 不提供任何写接口（写操作在阶段 4/5 引入，届时必须带 CSRF 与会话）；
- 所有请求先过 Host / Origin / 体积检查。
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.runtime import Runtime
from app.security import SecurityError, sanitize_for_log
from app.services import PluginNotFound, ValidationError, dump_plugin

# 不需要 Origin 校验的"安全方法"
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# 统一安全响应头。前端不使用内联脚本 / 内联样式，因此 CSP 可以收紧到 'self'。
_SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "base-uri 'none'; "
        "form-action 'none'; "
        "frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}


def _json_response(status: int, payload: dict[str, Any]) -> JSONResponse:
    """构造带统一安全头的 JSON 响应。"""
    resp = JSONResponse(status_code=status, content=payload)
    for key, value in _SECURITY_HEADERS.items():
        resp.headers[key] = value
    return resp


def create_app(runtime: Runtime | None = None) -> FastAPI:
    rt = runtime or Runtime.create()

    app = FastAPI(
        title="mcp-manager",
        version=__version__,
        docs_url=None,       # 关闭交互式文档，减少攻击面
        redoc_url=None,
        openapi_url=None,
    )
    app.state.runtime = rt

    # ------------------------------------------------------------------ #
    # 安全中间件
    # ------------------------------------------------------------------ #
    @app.middleware("http")
    async def _security_guard(request: Request, call_next):  # type: ignore[no-untyped-def]
        settings = rt.settings

        # 1) Host 头校验：防止 DNS rebinding 指向本机服务
        host_header = request.headers.get("host", "")
        hostname = host_header.rsplit(":", 1)[0].strip("[]").lower()
        if hostname and hostname not in {
            h.lower() for h in settings.allowed_hosts
        }:
            return _json_response(
                400, {"error": "invalid_host", "detail": "Host 头不在允许列表内"}
            )

        # 2) 体积限制
        raw_len = request.headers.get("content-length")
        if raw_len is not None:
            try:
                if int(raw_len) > settings.max_request_bytes:
                    return _json_response(413, {"error": "payload_too_large"})
            except ValueError:
                return _json_response(400, {"error": "invalid_content_length"})

        # 3) 非安全方法必须携带允许的 Origin（CSRF 基线）
        if request.method not in _SAFE_METHODS:
            origin = request.headers.get("origin")
            if origin is None or origin not in settings.allowed_origins:
                return _json_response(403, {"error": "csrf_origin_rejected"})

        response = await call_next(request)
        for key, value in _SECURITY_HEADERS.items():
            response.headers[key] = value
        return response

    # ------------------------------------------------------------------ #
    # 异常映射（不泄露内部细节）
    # ------------------------------------------------------------------ #
    @app.exception_handler(PluginNotFound)
    async def _not_found(_: Request, exc: PluginNotFound) -> JSONResponse:
        return _json_response(
            404, {"error": "plugin_not_found", "detail": str(exc)}
        )

    @app.exception_handler(ValidationError)
    @app.exception_handler(SecurityError)
    async def _bad_request(_: Request, exc: Exception) -> JSONResponse:
        return _json_response(
            400, {"error": "invalid_request", "detail": sanitize_for_log(exc)}
        )

    # ------------------------------------------------------------------ #
    # API
    # ------------------------------------------------------------------ #
    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "version": __version__,
            "loopback_only": rt.settings.is_loopback,
            "plugins": rt.plugins.count(),
        }

    @app.get("/api/stats")
    async def stats() -> dict[str, Any]:
        return rt.plugins.stats()

    @app.get("/api/plugins")
    async def list_plugins(
        kind: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        from app.models import PluginKind

        parsed_kind = None
        if kind:
            try:
                parsed_kind = PluginKind(kind)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"未知 kind：{kind}")
        items = rt.plugins.list(kind=parsed_kind, limit=limit, offset=offset)
        return {"count": len(items), "items": [dump_plugin(p) for p in items]}

    @app.get("/api/plugins/{plugin_id}")
    async def get_plugin(plugin_id: str) -> dict[str, Any]:
        return dump_plugin(rt.plugins.get(plugin_id))

    @app.get("/api/audit")
    async def audit(limit: int = 50) -> dict[str, Any]:
        rows = rt.plugins.list_audit(limit=limit)
        return {"count": len(rows), "items": [r.__dict__ for r in rows]}

    # ------------------------------------------------------------------ #
    # 静态页面
    # ------------------------------------------------------------------ #
    web_dir = rt.settings.web_dir

    @app.get("/")
    async def index() -> FileResponse:
        index_path = web_dir / "index.html"
        if not index_path.is_file():
            raise HTTPException(status_code=500, detail="web/index.html 缺失")
        return FileResponse(index_path, media_type="text/html; charset=utf-8")

    if (web_dir / "assets").is_dir():
        app.mount(
            "/assets", StaticFiles(directory=str(web_dir / "assets")), name="assets"
        )

    return app