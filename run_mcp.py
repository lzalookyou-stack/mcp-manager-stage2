#!/usr/bin/env python3
"""以 stdio 传输启动 MCP Server（供 MCP 客户端拉起）。

用法：
    python run_mcp.py

注意：stdio 模式下 **禁止**向 stdout 打印任何非协议内容，
因此本脚本不使用 print 输出日志。
"""

from __future__ import annotations

import sys

from app.mcp_server import build_server
from app.runtime import Runtime


def main() -> int:
    runtime = Runtime.create()
    try:
        server = build_server(runtime)
        server.run("stdio")
    finally:
        runtime.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())