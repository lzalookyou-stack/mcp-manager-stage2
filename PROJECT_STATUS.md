# PROJECT_STATUS — mcp-manager

> 跨对话 / 跨阶段的权威状态快照。**所有「已完成/未实现」的判断以本文件为准。**
> 最后更新：2026-10-09（阶段 1 收口）

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
| 2 最小可运行骨架 | ⬜ 未开始 | — | — |
| 3 搜索/分析/评分/安全审查 | ⬜ 未开始 | — | — |
| 4 网页控制台交互 | ⬜ 未开始 | — | — |
| 5 安全安装闭环 | ⬜ 未开始 | — | — |
| 6 插件适配器 | ⬜ 未开始 | — | — |
| 7 MCP 集成 | ⬜ 未开始 | — | — |
| 8 完整测试与交付 | ⬜ 未开始 | — | — |

### 阶段仓库

| 阶段 | 仓库地址 | 提交哈希 | 推送状态 |
|---|---|---|---|
| 1 | https://github.com/lzalookyou-stack/mcp-manager-stage1 | `ec27ff3eddf3458302746caefe1a5334ba78928e` | ✅ 已推送（远端 HEAD 已回读核对） |
| 2 | （推送后回填） | （推送后回填） | — |
| 3 | （推送后回填） | （推送后回填） | — |
| 4 | （推送后回填） | （推送后回填） | — |
| 5 | （推送后回填） | （推送后回填） | — |
| 6 | （推送后回填） | （推送后回填） | — |
| 7 | （推送后回填） | （推送后回填） | — |
| 8 | （推送后回填） | （推送后回填） | — |

---

## 阶段 1 交付物（已完成）

- `docs/research.md`：6 个候选仓库的实测调研，结论按【已验证】/【推断】/【未检查】/【无法确定】分级。
- `docs/architecture.md`：分层架构、统一插件数据模型、可解释评分规则、安装事务状态机、威胁模型摘要、技术选型结论。
- `docs/plan.md`：阶段 1–8 实施计划与贯穿纪律。
- `scripts/research_github.py`：可复现的 GitHub 调研脚本（仅用标准库，不打印令牌，失败即记录不伪造）。
- `scripts/research_result.json`：本次调研的原始数据（2026-10-09 采集）。

---

## 未实现（**严禁声称已实现**）

- 无任何应用代码：`app/`、`web/`、`tests/` 目录尚未创建。
- 无 Web 服务、无 MCP Server、无数据库、无前端页面。
- `requirements.txt` 中声明的依赖**尚未安装、尚未验证可用**（阶段 2 安装后核实）。
- `mcp` SDK 的具体 API 形态**尚未实测**（阶段 2 编码前必须核对，勿套用旧写法）。
- 本项目自身**尚无 LICENSE**（阶段 8 前确认）。

---

## 已知缺口 / 风险

见 `docs/research.md` 第 3 节。摘要：
- agentbridge 的 scanner 实现与检出率：**未检查**。
- MCP Registry API 的破坏性变更时间表：**无法确定**（官方声明 preview + v0.1 freeze）。
- `tamb/simple-mcp-manager` 的真实许可证：**无法确定**（README 称 MIT，API 为 null）。

---

## 验证基线

阶段 1 的验证方式（可复跑）：

```bash
cd mcp-manager
python3 scripts/research_github.py --out scripts/research_result.json   # 应输出 6 个仓库的真实字段
```

阶段 2 起将补充：`pytest -q -p no:cacheprovider`（串行，避免 OOM）。

---

## 纪律（不可违反）

1. **不伪造**仓库数据、测试结果、执行状态、安全结论。
2. 所有结论标注证据等级。
3. **不以正则或提示词作为安全控制**；不为通过测试而删除安全检查或降低断言。
4. 每阶段成果提交并推送到**新的独立 Git 仓库**。
5. 测试串行执行，避免 OOM。