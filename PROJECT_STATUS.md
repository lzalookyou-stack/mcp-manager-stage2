# PROJECT_STATUS — mcp-manager

> 跨对话 / 跨阶段的权威状态快照。**所有「已完成/未实现」的判断以本文件为准。**
> 最后更新：2026-10-09（阶段 2 收口）

---

## 基本信息

- 项目名：`mcp-manager`（本地优先的 MCP / Agent 插件管理器）
- 本地路径：`/data/user/0/com.ai.assistance.operit/files/workspace/baa843f1-7d93-466b-93b5-647f4942442b/mcp-manager`
- 技术栈：Python 3.12 + FastAPI + uvicorn + 官方 `mcp` SDK + SQLite + 原生 HTML/CSS/JS + asyncio + SSE
- 环境：Android proot Ubuntu 24.04 aarch64；无 systemd / 无 GPU；可用内存约 2.4 GB
- 目标仓库：**每个阶段一个独立 GitHub 仓库**（见下）

---

## 阶段进度

| 阶段 | 状态 | 仓库 | 备注 |
|---|---|---|---|
| 1 调研与技术选型 | ✅ 已完成 | https://github.com/lzalookyou-stack/mcp-manager-stage1 | 提交 `ec27ff3`，已推送 |
| 2 最小可运行骨架 | ✅ 已完成 | https://github.com/lzalookyou-stack/mcp-manager-stage2 | 77 项测试全绿；MCP stdio 冒烟 9 项通过；Web 实机验证通过 |
| 3 搜索/分析/评分/安全审查 | ⬜ 未开始 | — | — |
| 4 网页控制台交互 | ⬜ 未开始 | — | — |
| 5 安全安装闭环 | ⬜ 未开始 | — | — |
| 6 插件适配器 | ⬜ 未开始 | — | — |
| 7 MCP 集成 | ⬜ 未开始 | — | — |
| 8 完整测试与交付 | ⬜ 未开始 | — | — |

### 阶段仓库

| 阶段 | 仓库地址 | 提交哈希 | 推送状态 |
|---|---|---|---|
| 1 | https://github.com/lzalookyou-stack/mcp-manager-stage1 | 交付提交 `ec27ff3eddf3458302746caefe1a5334ba78928e`；状态回填提交 `806c58c` | ✅ 已推送（远端 `refs/heads/main` 已回读核对） |
| 2 | https://github.com/lzalookyou-stack/mcp-manager-stage2 | 交付提交 `015fdcb521eea18abba32d940ba14fec9cc992ef`；状态回填提交 `b742dcb` | ✅ 已推送（远端 `refs/heads/main` 已回读核对，33 文件树经 API 核验） |
| 3 | （推送后回填） | （推送后回填） | — |
| 4 | （推送后回填） | （推送后回填） | — |
| 5 | （推送后回填） | （推送后回填） | — |
| 6 | （推送后回填） | （推送后回填） | — |
| 7 | （推送后回填） | （推送后回填） | — |
| 8 | （推送后回填） | （推送后回填） | — |

---

## 阶段交付物

### 阶段 1（已完成）

- `docs/research.md`：6 个候选仓库的实测调研，结论按【已验证】/【推断】/【未检查】/【无法确定】分级。
- `docs/architecture.md`：分层架构、统一插件数据模型、可解释评分规则、安装事务状态机、威胁模型摘要、技术选型结论。
- `docs/plan.md`：阶段 1–8 实施计划与贯穿纪律。
- `scripts/research_github.py`：可复现的 GitHub 调研脚本（仅用标准库，不打印令牌，失败即记录不伪造）。
- `scripts/research_result.json`：本次调研的原始数据（2026-10-09 采集）。

### 阶段 2（已完成）

可运行骨架：**只读** Web 控制台 + **只读** MCP Server，共用同一 service 层。

应用代码：
- `app/config.py`：不可变 `Settings`；默认仅绑回环，非回环需 `MCPM_ALLOW_NON_LOOPBACK=1` 否则**启动即失败**。
- `app/models.py`：统一插件模型（7 种 kind）、四级证据枚举、五级风险枚举、可解释评分（security 权重 0.30，且安全一票否决时总分归零）、`pinned_ref` 强制为 40/64 位 commit（拒绝浮动引用）。
- `app/security.py`：安全标识符校验、`resolve_within`（防 `..` 穿越 / 绝对路径 / 符号链接逃逸）、常量时间比较、日志清洗。
- `app/db.py`：SQLite（stdlib，无 ORM），WAL、外键、`busy_timeout`、事务上下文管理器。
- `app/services/plugin_service.py`：注册 / 查询 / 列表 / 审计；**搜索、评分、审查、安装、回滚五个方法显式 `raise NotImplementedError`**。
- `app/web/app.py`：只读 API + Host 白名单 + Origin(CSRF) 校验 + 体积上限 + 统一安全响应头（严格 CSP，无 `unsafe-inline`）+ 关闭 docs/openapi。
- `app/mcp_server/server.py`：基于 `mcp.server.mcpserver.MCPServer`（**mcp 2.x 中 FastMCP 已改名**）注册 4 个工具；`request_install` 恒返回 `not_implemented` 并记 `denied` 审计。
- `web/index.html` + `web/assets/{style.css,app.js}`：原生前端，全程只用 `textContent`/`createElement` 写 DOM。
- `run_web.py` / `run_mcp.py`：启动入口。
- `scripts/smoke_mcp_stdio.py`：真实子进程 stdio JSON-RPC 冒烟测试。

测试：`tests/` 共 77 项（模型 / 安全 / 服务 / Web），含「无写接口」负向断言与「未实现能力必须抛异常」断言。

---

## 未实现（**严禁声称已实现**）

以下能力在阶段 2 **确实不存在**，调用会显式失败（`NotImplementedError` 或返回 `not_implemented`）：

- `PluginService.search_remote` / `score` / `review` / `install` / `rollback`：全部 `raise NotImplementedError`（阶段 3/5 实现）。
- Web 层**没有任何写接口**（阶段 4/5 引入，届时必须带会话与 CSRF 令牌）；`tests/test_web.py::test_no_write_endpoints_exist` 为负向断言。
- MCP 工具 `request_install` **不产生任何安装行为**，恒返回 `{"ok": false, "error": "not_implemented"}` 并写 `actor=agent, outcome=denied` 审计。
- 无插件适配器（阶段 6）、无真实远程搜索源接入（阶段 3）。
- 本项目自身**尚无 LICENSE**（阶段 8 前确认）。

---

## 已知缺口 / 风险

见 `docs/research.md` 第 3 节。摘要：
- agentbridge 的 scanner 实现与检出率：**未检查**。
- MCP Registry API 的破坏性变更时间表：**无法确定**（官方声明 preview + v0.1 freeze）。
- `tamb/simple-mcp-manager` 的真实许可证：**无法确定**（README 称 MIT，API 为 null）。

---

## 验证基线

阶段 1（可复跑）：

```bash
cd mcp-manager
python3 scripts/research_github.py --out scripts/research_result.json   # 应输出 6 个仓库的真实字段
```

阶段 2（可复跑，必须先建好 `.venv`）：

```bash
cd mcp-manager
.venv/bin/python -m pytest                                   # 期望 77 passed
.venv/bin/python scripts/smoke_mcp_stdio.py                  # 期望 SMOKE_EXIT=0，9 项 PASS
.venv/bin/python run_web.py &                                # 真实启动
curl -s http://127.0.0.1:8765/api/health                     # {"status":"ok",...}
```

阶段 2 的实测结果（2026-10-09）：

- `pytest`：**77 passed in 2.29s**。
- `smoke_mcp_stdio.py`：**9 项 PASS，退出码 0**；`tools/list` 返回 4 个工具；`request_install` 被拒绝（`not_implemented`）。
- Web 实机：`GET /` 200（含完整安全头与严格 CSP）、`/api/health` 200、`/api/stats` 200、`/api/plugins` 200、`/assets/app.js` 200、无 Origin 的 `POST /api/plugins` **403**、非法 Host **400**、`/docs` **404**。

> 环境说明：系统 Python 受 PEP 668 保护，**必须使用项目内 `.venv`**；依赖走清华镜像安装。
> `mcp 2.3.0` 实测：`FastMCP` 已改名为 `MCPServer`（`from mcp.server.mcpserver import MCPServer`），旧 `mcp.server.fastmcp` 导入会失败。

---

## 纪律（不可违反）

1. **不伪造**仓库数据、测试结果、执行状态、安全结论。
2. 所有结论标注证据等级（`EvidenceLevel`：verified / inferred / unchecked / undetermined）。
3. **不以正则或提示词作为安全控制**；不为通过测试而删除安全检查或降低断言。
4. **Agent 只能提交操作申请，授权必须来自用户通过受信任网页的明确确认**（禁止 Agent 自造授权）。
5. 每阶段成果提交并推送到**新的独立 Git 仓库**。
6. 测试串行执行，避免 OOM（本机可用内存约 2.4 GB）。