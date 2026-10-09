# mcp-manager

本地优先的 **MCP / Agent 插件管理器**：发现 → 审查 → 评分 → 确认 → 安装 → 回滚，并把同一套能力通过 MCP 暴露给 AI Agent。

> 当前状态：**阶段 1 已完成**（调研 + 技术选型 + 架构设计）。尚未有可运行的应用代码。
> 各阶段进度与「未实现项」以 `PROJECT_STATUS.md` 为准。

---

## 这是什么

AI 编程助手生态正在快速膨胀：每个助手都有自己的「插件」概念（Skill、MCP Server、Rules、Command、Hook），
来源、版本、安装位置、配置格式、权限各不相同。结果是：

- 同一个插件要在多个客户端里用不同格式各装一遍；
- 从 Git 仓库安装时**装的是哪个 commit 说不清**；
- **一个 Markdown 文件（Skill）就是可执行指令**，直接进模型上下文，却几乎没有东西去审查它。

`mcp-manager` 要解决的就是这条「**Agent 扩展的供应链**」：

1. **发现**：从 GitHub 与 MCP Registry 搜索候选项目；
2. **审查**：分析项目质量并给出**可解释评分**，对安装脚本做**静态安全审查**；
3. **确认**：安装前把「将执行什么命令、改哪些文件、要哪些权限、如何回滚」摊开给用户确认；
4. **安装**：固定 commit、快照、原子应用、失败回滚、崩溃可恢复；
5. **暴露**：通过 MCP 把上述能力给到 Agent，但**Agent 不能自行授权**。

---

## 文档

| 文档 | 内容 |
|---|---|
| [`docs/research.md`](docs/research.md) | 阶段 1：6 个候选仓库的实测调研（含证据分级） |
| [`docs/architecture.md`](docs/architecture.md) | 阶段 1：分层架构、统一插件模型、评分规则、事务状态机、威胁模型 |
| [`docs/plan.md`](docs/plan.md) | 阶段 1：分阶段实施计划 |
| `PROJECT_STATUS.md` | 跨阶段进度快照与「未实现项」清单 |

---

## 阶段 1 交付物与复现

```bash
# 复现 GitHub 调研（只需 Python 3.12 标准库，无需安装任何第三方依赖）
python3 scripts/research_github.py --out scripts/research_result.json
```

脚本会从 `/root/.git-credentials`（`credential.helper=store`）或环境变量 `GITHUB_TOKEN` 读取令牌，
**不会把令牌写入任何输出**；任何请求失败都会写入 `error` 字段，**绝不伪造数据**。

---

## 计划中的技术栈

| 组件 | 选择 |
|---|---|
| Web 框架 | FastAPI + uvicorn（默认仅监听 `127.0.0.1`） |
| MCP | 官方 `mcp` Python SDK（`modelcontextprotocol/python-sdk`） |
| 存储 | SQLite（标准库 `sqlite3`） |
| 前端 | 原生 HTML/CSS/JS（无构建步骤） |
| 实时 | SSE（`text/event-stream`） |
| 并发 | asyncio |

依赖锁定见 [`requirements.txt`](requirements.txt)。

---

## 许可与免责

- 本项目自身许可证：待定（阶段 8 交付前确认）。
- **安全审查不提供任何担保**：工具输出的「风险级别」只是基于静态证据的判断，
  **不构成「安全」或「无恶意代码」的结论**。安装第三方插件前请自行核实。
