"""mcp-manager 应用包。

分层约定（详见 docs/architecture.md）：
- ``app.config``      : 全局配置（唯一来源，默认仅监听回环）
- ``app.models``      : 统一插件数据模型（Pydantic）
- ``app.db``          : SQLite 连接与 schema 初始化
- ``app.security``    : 路径规范化 / 常量时间比较 / 输入校验等安全原语
- ``app.services``    : 业务服务层（**网页与 MCP 工具必须共用同一实现**）
- ``app.web``         : FastAPI 网页控制台
- ``app.mcp_server``  : MCP Server（对 Agent 暴露的工具）
"""

__version__ = "0.2.0"
