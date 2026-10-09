# 阶段 1 — GitHub 候选项目调研报告

> 采集时间：2026-10-09T14:00Z
> 采集方式：GitHub REST API（已认证，账号 `lzalookyou-stack`，scope=`repo`），只读 GET。
> 原始数据：`scripts/research_result.json`（由 `scripts/research_github.py` 生成，可复现）。
> 证据分级：**【已验证】**=本次实测 API/文件内容；**【推断】**=基于证据的合理推论；**【未检查】**=本轮未获取；**【无法确定】**=现有证据不足。

---

## 0. 调研目标

本阶段要回答的问题是：**构建一个「MCP / Agent 插件管理器」时，应当复用什么、自研什么？**

具体需求（来自任务书）：
1. 从 GitHub（及其他来源）搜索 MCP Server / Agent 插件 / Skill；
2. 分析项目质量并给出可解释评分；
3. 对安装脚本与调用链做安全审查；
4. 在用户明确确认后安全安装，支持快照、回滚、事务；
5. 通过 MCP 接口把同一套能力暴露给 AI Agent；
6. 技术栈候选：FastAPI + 官方 Python MCP SDK + 原生 HTML/CSS/JS + SQLite + asyncio + SSE。

---

## 1. 候选仓库实测结果

### 1.1 总览表

| 仓库 | 语言 | 许可证(API) | Stars | 最近提交 | 最近 Release | 活跃度 | 与本题相关性 |
|---|---|---|---|---|---|---|---|
| `xjeway/mcp-manager` | Rust+TS | MIT | 8 | 2026-10-09 | v0.2.0 (2026-09-30) | 高 | 高（多客户端配置 + 风险写入复核 + 备份回滚） |
| `tamb/simple-mcp-manager` | JavaScript | **null（无元数据）** | 0 | 2026-06-25 | 无 | 低（停滞≈3.5月） | 中（配置定位表 + 进程匹配） |
| `Bigsy/mcpmu` | Go | MIT | 19 | 2026-09-24 | v0.1.35 (2026-09-25) | 中 | 中（网关/命名空间/权限/Web UI） |
| `agentbridgehq/agentbridge` | Go | Apache-2.0 | 0 | 2026-09-10 | v0.2.0 (2026-08-31) | 低（新建 2026-08-25） | **极高**（供应链/锁文件/扫描器/安装器验证） |
| `modelcontextprotocol/registry` | Go | **NOASSERTION** | 7331 | 2026-10-08 | v1.8.1 (2026-08-06) | 高 | 高（可作为发现来源：官方注册表 API） |
| `modelcontextprotocol/python-sdk` | Python | MIT | 24522 | 2026-10-05 | v2.3.0 (2026-10-02) | 高 | 高（本项目的 MCP 依赖） |

**【已验证】** 上表全部字段来自本次 GitHub API 实测（见 `scripts/research_result.json`）。6 个候选地址全部有效，无 404/归档/禁用。

---

### 1.2 `xjeway/mcp-manager`（深入）

**【已验证】** 事实：
- 技术栈：Rust（464,687 B）+ TypeScript（356,862 B）+ JavaScript/CSS，`src-tauri/` 表明是 **Tauri 2 + React 19 桌面应用**；平台为 macOS/Windows/Linux。
- 许可证 MIT（API `spdx_id=MIT`）。
- 根目录含 `package.json`、`Cargo.toml`、`Makefile`（属安全相关文件）。
- README 明确列出的能力（原文）：统一 MCP 工作区；从本地客户端配置导入；**从 GitHub MCP Registry、官方 MCP Registry 或任何实现 MCP Registry API 的注册表查找服务器**；表单/原始 JSON 双模式编辑；把配置应用到多个客户端；**"Review risky writes before files change"**；**"Keep backups and rollback support during apply"**；明暗主题；中英双语。

**【推断】** 该项目与我们的「发现→审查→应用到多客户端→备份回滚」闭环高度同构，其**产品能力清单可直接作为我们的需求对照表**。

**【无法确定】** 其「风险写入复核」的具体判定规则（未读取源码）。

**可复用**：多客户端配置适配的**概念模型**、风险写入复核的产品形态、备份/回滚的用户流程。
**不适合采用**：Tauri/Rust/React 桌面栈——与本项目「本地 Web 控制台 + Android/proot 环境」不匹配。

---

### 1.3 `agentbridgehq/agentbridge`（深入，安全设计最重要的参考）

**【已验证】** 事实：
- 定位原文："**The supply chain for agent extensions.**"（Agent 扩展的供应链）。Apache-2.0，Go 为主，v0.2.0，创建于 2026-08-25，0 star。
- 基于 **Agent Plugins 1.0.0** 规范：插件含两类内容——**Skill**（`SKILL.md`，纯文本指令，直接载入模型上下文）与 **MCP server**（真实程序，以你的权限在本机运行）。
- README 直接点出本项目的核心威胁（原文）：
  - "There is no version control … Which commit? Whatever the tag pointed at when you ran the command."
  - "**A Markdown file is executable — and nothing inspects it.**"
  - "a conformant client [may] support neither skills nor MCP servers, so the install 'succeeds', nothing happens, and nothing tells you why."
- 提供：**lockfile**、**secrets off disk**、**scanner**（读取插件让 agent 执行什么）。
- `install.sh`（7,248 B，**已下载全文核验**）：**强制** SHA-256 校验和验证（"Checksum verification is mandatory and cannot be turned off"）；cosign 存在时验证签名，且**把签名身份固定到本仓库 release 工作流**（`--certificate-identity-regexp .../release.yml@.*` + OIDC issuer）；`AGENTBRIDGE_REQUIRE_SIGNATURE=1` 时缺失签名即失败；`--ignore-missing` **被刻意不用**（防止 checksums 文件漏列产物而静默通过）。

**【推断】** 该项目的威胁模型与本项目需求 3/4（安全审查 + 安全安装）几乎重合，是**最值得借鉴的设计参考**。

**【无法确定】** 其 scanner 的具体实现与检出率（未读取 Go 源码，且项目极新）。

**可复用**：威胁模型表述、lockfile（固定 commit/校验和）概念、安装器「强制校验 + 签名固定身份」的验证模式、Skill 作为提示注入面的认知。
**不适合采用**：直接依赖该项目（过新、0 采用度、Go 栈、与本地 Web 控制台形态不同）。

---

### 1.4 `Bigsy/mcpmu`（深入）

**【已验证】** 事实：Go，MIT，19★，v0.1.35；TUI + Web UI；MCP 多路复用 + 工具压缩；按 namespace 暴露；**在网关层对工具做 allowlist、全局阻断危险操作**；支持本地 stdio 与远程 Streamable HTTP/SSE；保留 tool annotations/output schemas。
**【推断】** 「命名空间 + 权限 allowlist + 网关统一管控」是插件管理的成熟交互范式。
**可复用**：命名空间/权限的产品概念、Web UI 信息架构。
**不适合采用**：其核心是「运行时网关」，而本项目核心是「发现—审查—安装—回滚」，二者目标不同。

---

### 1.5 `tamb/simple-mcp-manager`

**【已验证】** 事实：JavaScript，npm 包，TUI + 可选 Web UI（默认 `localhost:3000`）；扫描多客户端 MCP 配置、显示运行/停止状态、支持 restart/kill；**明确说明 HTTP/HTTPS/SSE 端点仅列出、不可管理**。
**【已验证】** **许可证元数据缺失**：README 徽章标注 MIT，但 GitHub API 的 `license` 字段为 `null`。
**【推断】** 「徽章声称的许可证 ≠ API 可解析的许可证元数据」——本项目的许可证评分**必须以 API/文件为准，并标记不确定性**，不能只信 README 徽章。
**【已验证】** 活跃度低：最近提交 2026-06-25（距采集日约 3.5 个月）。
**可复用**：各客户端配置路径表（作为适配器的参考输入）。
**不适合采用**：整体代码（停滞 + 许可证元数据缺失 + 功能面（仅监控重启）与需求不符）。

---

### 1.6 `modelcontextprotocol/registry`

**【已验证】** 事实：Go，7,331★，v1.8.1；「MCP 服务器的应用商店」；提供 REST API；README 声明 **Registry API 已进入 v0.1 API freeze（2025-10-24）**，并曾于 2025-09-08 进入 preview，**可能发生破坏性变更或数据重置**；开发需 Docker + Go + ko + PostgreSQL。
**【已验证】** 许可证 API 值为 **NOASSERTION**（存在 `LICENSE` 文件但未能自动识别为 SPDX 标准许可证）。
**【推断】** 该注册表 API 是本项目**优于爬取 GitHub 的发现来源**，但处于 preview/freeze 阶段，需按「不稳定外部依赖」处理：缓存、降级、显式标注数据来源与时间。
**可复用**：作为「发现」层的首选结构化来源（MCP Registry API）。
**风险**：preview 阶段可能破坏性变更；许可证需人工核对。

---

### 1.7 `modelcontextprotocol/python-sdk`

**【已验证】** 事实：官方 Python SDK，MIT，24,522★，最近 Release **v2.3.0（2026-10-02）**，最近提交 2026-10-05；含 `pyproject.toml`、`src/`、`tests/`、`uv.lock`、`SECURITY.md`、`DEPENDENCY_POLICY.md`。
**【未检查】** PyPI 上 `mcp` 包的实际可安装版本号与 GitHub tag 的对应关系（**编码前必须实测核对 SDK API 形态，不得套用记忆中的旧写法**）。
**【推断】** 作为官方 SDK，是本项目 MCP 层的**唯一合理选择**。

---

## 2. 结论：复用什么、自研什么

### 2.1 复用（概念 / 协议 / 库）

| 对象 | 复用方式 | 依据 |
|---|---|---|
| `modelcontextprotocol/python-sdk` | **直接依赖**，作为 MCP Server 实现层 | 官方、MIT、活跃 |
| MCP Registry API | **发现来源之一**（结构化，优于爬取） | 官方注册表 |
| agentbridge 的威胁模型与安装器验证模式 | **设计参考**（强制校验、签名固定身份、lockfile） | install.sh 全文核验 |
| xjeway/mcp-manager 的产品能力清单 | **需求对照表**（风险写入复核、备份回滚、多客户端应用） | README |
| mcpmu 的命名空间/权限概念 | **交互与数据模型参考** | README |
| simple-mcp-manager 的客户端配置路径表 | **适配器输入参考**（并接受其许可证元数据缺失的教训） | README + API |

### 2.2 自研（本项目独有价值）

1. **统一插件数据模型**：跨 MCP Server / Skill / Rules / Command / Hook / 适配器扩展 的单一模型（含来源、固定 commit、权限、风险、审查/安装状态、快照、回滚）。
2. **可解释质量评分**：维护性 20% / 代码质量与测试 25% / 安全风险 30% / 兼容性 15% / 社区与许可证 10%，**每项可追溯到证据**，严重安全风险**不可被其他高分抵消**。
3. **安装脚本静态安全审查**：shell/PowerShell 执行、任意文件读写删、可疑外联、敏感信息访问、安装后自动执行、动态下载执行、依赖与供应链风险、Hook/持久化。
4. **受管安装事务**：计划→确认→快照→暂存→校验→执行→原子应用→验证→记录→可回滚的**持久化状态机**，崩溃后可恢复，绝不把中断标记为成功。
5. **MCP 工具面**：让 Agent 只能「申请操作」，**授权必须来自用户在受信任网页的明确确认**，Agent 无法自造确认参数。

### 2.3 明确不采用

- React/Vue 前端框架、Tauri/Rust 桌面栈、Go 重写、Redis、Docker 编排、微服务、向量数据库——均与需求无关且增加复杂度。
- 直接依赖 agentbridge / xjeway/mcp-manager 作为运行时依赖（过新或形态不符）。

---

## 3. 数据缺口与风险登记（如实记录）

| 项 | 状态 | 说明 |
|---|---|---|
| `mcp` SDK 的 PyPI 实际版本与 API 形态 | **未检查** | 阶段 2 编码前必须实测 |
| agentbridge scanner 的实现与检出率 | **未检查** | 未读 Go 源码 |
| xjeway/mcp-manager 风险写入复核规则 | **未检查** | 未读源码 |
| registry API 的破坏性变更时间表 | **无法确定** | 官方仅声明 preview + v0.1 freeze |
| simple-mcp-manager 的真实许可证 | **无法确定** | README 称 MIT，API 为 null，需人工核对 LICENSE 文件 |
| GitHub 匿名 API 限流 | **已验证** | 同一出口 IP 匿名额度易耗尽；本项目所有 GitHub 调用**必须带令牌** |

---

## 4. 复现方式

```bash
cd mcp-manager
python3 scripts/research_github.py --out scripts/research_result.json
```

> 脚本从 `/root/.git-credentials`（credential.helper=store）或 `GITHUB_TOKEN` 读取令牌，**不打印令牌**；所有请求失败都会写入 `error` 字段，绝不伪造数据。
