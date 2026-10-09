#!/usr/bin/env python3
"""启动网页控制台。

默认仅监听 127.0.0.1。用法：
    python run_web.py                # 127.0.0.1:8765
    MCPM_PORT=9000 python run_web.py
"""

from __future__ import annotations

import sys

import uvicorn

from app.config import load_settings
from app.runtime import Runtime
from app.web import create_app


def main() -> int:
    try:
        settings = load_settings()
    except (RuntimeError, ValueError) as exc:
        print(f"[mcp-manager] 配置错误：{exc}", file=sys.stderr)
        return 2

    runtime = Runtime.create(settings)
    app = create_app(runtime)

    print(f"[mcp-manager] 数据目录：{settings.data_dir}")
    print(f"[mcp-manager] 数据库：{settings.db_path}")
    print(f"[mcp-manager] 监听：http://{settings.host}:{settings.port}/")
    if not settings.is_loopback:
        print("[mcp-manager] 警告：正在监听非回环地址！", file=sys.stderr)

    try:
        uvicorn.run(
            app,
            host=settings.host,
            port=settings.port,
            log_level="info",
            access_log=True,
            # 关闭自动重载（生产式运行；开发时自行加 --reload）
            reload=False,
        )
    finally:
        runtime.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())