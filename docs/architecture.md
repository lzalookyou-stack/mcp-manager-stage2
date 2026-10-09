# 阶段 1 — 系统架构设计

> 目标：一个**本地优先**的「MCP / Agent 插件管理器」：发现 → 审查 → 评分 → 确认 → 安装 → 回滚，并把同一套能力通过 MCP 暴露给 AI Agent。
> 设计约束：Android / proot Ubuntu 24.04 aarch64；无 systemd、无 GPU；内存紧张（可用约 2.4 GB，测试需串行）；默认仅监听 `127.0.0.1`。

---

## 1. 分层架构

```
┌─────────────────────────────────────────────────────────────┐
│  受信任前端（原生 HTML/CSS/JS，无框架）                        │
│  总览 · 发现 · 详情 · 已安装 · 任务/历史 · 安装确认            │
│  只经 fetch 调用同源 /api/*，SSE 订阅 /api/events              │
└───────────────▲───────────────────────────┬─────────────────┘
                │ HTTP(S) 同源 + CSRF + 会话  │ SSE(进度/日志)
┌───────────────┴───────────────────────────▼─────────────────┐
│  FastAPI 应用层 (app/main.py)                                 │
│  ├─ 安全中间件：Host/Origin 校验、CSRF、会话校验、回环绑定     │
│  ├─ routers/：search · plugins · operations · events · pages  │
│  └─ 依赖注入：settings / db / services                        │
└───────────────┬─────────────────────────────────────────────┘
                │ 仅调用 service 层（不直接碰 DB/网络）
┌───────────────▼─────────────────────────────────────────────┐
│  业务服务层 (app/services/)                                    │
│  github.py   搜索/元数据（GitHub API，带令牌、限流处理）       │
│  registry.py MCP Registry API 发现（不稳定依赖，可降级）       │
│  scoring.py  可解释质量评分（权重固定、可追溯证据）            │
│  security_review.py  安装脚本/调用链静态审查                   │
│  installer.py 受管安装事务状态机（计划→确认→快照→执行→回滚）   │
│  snapshot.py  文件快照与恢复                                   │
│  operations.py 操作记录与历史                                  │
└───────────────┬───────────────────────┬─────────────────────┘
                │                       │
┌───────────────▼──────────┐  ┌─────────▼─────────────────────┐
│  适配器层 (app/adapters/) │  │  存储层 (SQLite, app/db.py)    │
│  base.py（接口）          │  │  plugins / operations /        │
│  skill.py / rules.py      │  │  confirmations / snapshots /   │
│  mcp_server.py            │  │  operation_logs / settings     │
│  agent_plugin.py          │  └────────────────────────────────┘
│  新增类型无需改核心逻辑    │
└──────────────────────────┘
                ▲
                │ 复用同一 service 层（禁止两套逻辑）
┌───────────────┴─────────────────────────────────────────────┐
│  MCP 接口 (app/mcp_server.py，官方 mcp Python SDK)            │
│  search_projects · inspect_project · compare_projects        │
│  get_install_plan · list_installed · inspect_plugin          │
│  request_operation · get_operation_status · list_history     │
│  ⚠ Agent 只能「申请操作」，授权必须来自受信任网页的确认         │
└─────────────────────────────────────────────────────────────┘
```

**关键原则**：网页与 MCP 工具**共用同一 service 层**，绝不允许出现「网页一套逻辑、MCP 另一套」。

---

## 2. 统一插件数据模型

单一模型覆盖：`mcp_server` / `agent_plugin` / `skill` / `command` / `hook` / `rules_instructions` / `adapter_extension`。

| 字段 | 说明 |
|---|---|
| `id` | 稳定插件 ID（来源+类型+规范化名称派生，跨版本稳定） |
| `plugin_type` | 上列枚举之一 |
| `name` / `display_name` | 名称 |
| `source_repo` / `source_url` | 来源仓库与 URL |
| `pinned_ref` | **固定 commit SHA 或可验证版本标识**（禁止只用浮动 tag） |
| `version` / `license` / `license_source` | 版本与许可证，**记录来源**（API / LICENSE 文件 / 未知） |
| `supported_clients` / `supported_platforms` | 支持客户端与平台 |
| `dependencies` / `runtime_requirements` | 依赖与运行时要求 |
| `install_path` / `config_path` | 实际安装路径与配置位置（**受管**） |
| `permissions` | 所需权限（文件/网络/进程/密钥） |
| `risk_level` / `risk_findings` | 风险级别与证据列表 |
| `review_status` | `unreviewed` / `reviewed` / `blocked` |
| `install_status` | 见第 4 节状态机 |
| `last_operation_id` | 最近操作 |
| `snapshot_path` | 快照位置 |
| `rollback_state` | 可回滚状态（可回滚版本列表） |
| `evidence` | 每条结论的证据（已验证/推断/未检查/无法确定） |

> **证据分级贯穿全模型**：任何字段值都必须能回答「这是实测的、推断的，还是未知的」。

---

## 3. 质量评分（可解释）

| 维度 | 权重 | 主要证据来源 |
|---|---|---|
| 维护状态 | 20% | 最近提交/Release 时间、活跃度 |
| 代码质量与测试 | 25% | 是否有 tests/、CI、语言构成、规模 |
| **安全风险** | **30%** | 安装脚本/调用链审查结果（**一票否决能力**） |
| 兼容性 | 15% | 支持的客户端/平台/运行时 |
| 社区与许可证 | 10% | Star/Fork/Issue、**API 可解析的许可证** |

**硬性规则**：
- 每个维度的分数必须能追溯到具体证据，`evidence` 字段留痕；
- **Star 数仅作辅助信号**，不单独决定结论；
- **严重安全风险不得被其他高分抵消**：出现高危发现时，`review_status=blocked` 或强制更严格人工审查；
- 许可证未知（如 `NOASSERTION` / `null`）不得默认给满分，须标记不确定性。

---

## 4. 安装事务状态机

```
pending → awaiting_confirmation → approved → running
                                              ├→ succeeded
                                              ├→ failed → rolling_back → rolled_back
                                              └→ interrupted（进程崩溃后检测）
```

10 步安装流程：
1. 生成并保存安装计划（含固定版本、命令、文件变更清单、目标路径、权限、回滚方案）
2. 等待用户**通过受信任网页**确认
3. 验证确认与计划一致（操作 ID / 插件 / 来源 / 版本 / 路径 / 命令 / 变更摘要 / 权限 / 过期时间）
4. 创建快照
5. 暂存目录准备
6. 验证来源、路径、配置
7. 执行安装
8. **原子应用**受管变更
9. 验证结果
10. 记录版本、结果与回滚信息

**不变式**：
- 计划一旦变化，确认立即失效，必须重新确认；
- 进程崩溃后，未完成事务必须被识别为 `interrupted`，**绝不标记为成功**；
- 卸载只处理**有明确归属记录**的文件；
- 回滚只撤销**本系统记录并拥有**的变更。

---

## 5. 安全边界（威胁模型摘要）

详见 `docs/security.md`（阶段 5-6 完整化），此处为边界基线：

| 威胁 | 控制 |
|---|---|
| 局域网/公网访问管理接口 | 默认仅绑 `127.0.0.1`；校验 `Host` 与 `Origin` |
| CSRF | 会话令牌 + CSRF 校验；状态变更仅接受同源请求 |
| Agent 越权安装 | Agent 只能提交操作申请；授权必须来自网页端用户确认；确认令牌绑定操作摘要与有效期 |
| 命令注入 | 结构化参数；**禁止 `shell=True` 与字符串拼接**；限制工作目录/环境变量/超时/输出大小 |
| 路径遍历 / 符号链接逃逸 | 路径规范化 + 越界检查 + 真实路径校验 |
| 安装脚本自动执行 | 默认**禁止**任意安装脚本自动执行；高风险代码优先隔离 |
| 供应链 | 固定 commit SHA；校验和；来源可追溯；审查记录留痕 |
| 前端 XSS | 原生 JS **只用 `textContent`**，禁止 `innerHTML` |
| 凭据泄漏 | 令牌不进前端/日志/MCP 结果 |

> **不以正则或提示词作为安全控制手段**——正则只用于「发现可疑」，最终判定必须基于结构与证据。

---

## 6. 技术选型结论

| 组件 | 选择 | 理由 |
|---|---|---|
| Web 框架 | **FastAPI + uvicorn** | 任务书候选方案；异步、SSE 友好；依赖规模可接受 |
| MCP | **官方 `mcp` Python SDK** | 官方、MIT、活跃（`modelcontextprotocol/python-sdk`） |
| 存储 | **SQLite（stdlib `sqlite3`）** | 零额外依赖、单文件、事务 |
| 前端 | **原生 HTML/CSS/JS** | 无构建步骤、低内存、易审计 |
| 实时 | **SSE（`text/event-stream`）** | 单向进度/日志，比 WebSocket 简单 |
| 并发 | **asyncio** | 与 FastAPI/SSE 天然契合 |

**明确排除**：React/Vue、Redis、Docker 编排、微服务、向量数据库、ORM（用轻量 SQL 封装即可）。

> 选型风险评估：本机内存约 2.4 GB 可用，FastAPI+uvicorn+MCP SDK 常驻预计 80–150 MB，可接受；但**测试必须串行执行**以避免 OOM（参考既有经验：`pytest -p no:cacheprovider`）。

---

## 7. 目录结构（目标）

```
mcp-manager/
├── app/                  # FastAPI 后端
│   ├── main.py           # 应用装配
│   ├── config.py         # 设置（含回环绑定、路径根）
│   ├── security.py       # Host/Origin/CSRF/会话/确认令牌
│   ├── db.py             # SQLite 连接与迁移
│   ├── models.py         # 统一插件模型
│   ├── events.py         # SSE 事件总线
│   ├── services/         # 业务服务（网页与 MCP 共用）
│   ├── adapters/         # 插件类型适配器
│   ├── routers/          # HTTP 路由
│   └── mcp_server.py     # MCP 工具面
├── web/                  # 原生前端
├── scripts/              # 调研与探针脚本
├── tests/                # 单元与端到端测试
├── docs/                 # 本目录文档
├── requirements.txt
└── README.md
```