# Phase 2 — Tutorial Parity

**Status:** Accepted
**Target Release:** `v0.1-tutorial-parity`

The accepted Phase 2A implementation boundary is recorded in
[`phase-2a-implementation-addendum.md`](phase-2a-implementation-addendum.md).

## Goal and Portfolio Value

实现一个可离线复现、可切换真实 Provider 的教程级研究 Copilot：用户上传约束，系统
通过 Web、MySQL Catalog 和 Knowledge Provider 协作研究，实时展示事件并交付
Markdown/PDF 报告。该阶段证明端到端 Agent 工程能力，而不是生产级恢复与治理。

## 2A — Demo Closure

当前最高优先级。完成一个可展示的垂直用户流程：

1. React 工作台创建 thread 并连接 WebSocket；
2. 用户上传支持的约束/资料文件；
3. 用户提交研究问题，可观察任务、Agent 和工具事件；
4. Web、Catalog、Knowledge 三类 Provider 都参与运行；
5. 任务生成 `tutorial-report.md` 和 `tutorial-report.pdf`；
6. 页面展示 Markdown，列出并下载两种报告；
7. 完成、失败和取消状态清晰可见。

### 2A Required Safety

- 上传和输出目录按 thread 隔离；
- 拒绝路径穿越、危险文件类型、超限文件和伪造内容；
- Catalog 仅执行受控只读 SQL；
- 终态不泄露密钥、绝对路径或 Provider 原始响应；
- 每次任务只有一个 terminal event；
- mock 模式无需模型 Key 或网络。

### 2A Minimum Gate

- 一个真实后端闭环测试证明上传、三类 Provider、终态和两个报告；
- 前端 Vitest 覆盖提交、上传、事件、终态、预览和下载；
- 前端构建、lint 通过；
- 一个桌面与移动宽度的浏览器 smoke；
- 本地 mock quick start 可按文档运行。

同一内部事件规则不在 unit、integration 和 E2E 多层重复精确断言；责任边界测试证明
规则，E2E 只证明用户闭环。

## 2B — Safety Hardening

在 2A Demo 可运行后集中处理高风险边界：

- cancellation-before-entry 与 active cancellation；
- WebSocket disconnect 不取消任务；
- 慢订阅者 overflow 与关闭策略；
- 成功、失败、取消恰好一个 terminal；
- HTTP 负向契约、跨 thread 隔离和下载 containment；
- Provider、文件解析和报告失败的脱敏与清理；
- 清理重复、脆弱或依赖私有实现的测试。

影响安全、数据隔离或错误终态的失败阻塞发布；只影响内部精确顺序且用户闭环正常的
低风险边界可以记录为 backlog，但必须在 Phase 2C 前明确处置结论。

**2B 验收状态（2026-08-07 B8 节点）：** B1–B7 全部 claims 已由 B8 全量门禁复核
通过（E2E 1 passed；integration/unit 355 passed / 9 skipped；前端 60 tests /
eslint / build 与 2A bundle 一致；ruff 与 `git diff --check` 干净），2A 浏览器
证据仍有效。唯一未决项：`pre-commit` 中 detect-secrets 要求刷新
`.secrets.baseline` 行号（B6 测试文件行号漂移，无新 secret，修复为一次性运行
pre-commit 并提交更新）。Codex 已独立重跑门禁且结果一致，baseline 已刷新并提交；
Phase 2B accepted，下一节点为 Phase 2C Release Evidence。

## 2C — Release Evidence

- 更新 README 与教程 runbook；
- 记录 mock、MySQL integration 和可选真实 Provider smoke；
- 后端、前端、CI、Compose 和 secrets gate 全部通过；
- 记录已知限制和未运行的外部 smoke；
- 用户独立验收后才创建 `v0.1-tutorial-parity`。

**2C 状态（2026-08-07，HEAD `fb17a39`）：** README 已更新，本地 mock 复现
runbook 已产出：[`docs/runbooks/phase-2-tutorial-parity.md`](../runbooks/phase-2-tutorial-parity.md)，
覆盖前置条件、mock quick start、上传/任务/WebSocket/产物下载工作流、可选
MySQL 与真实 Provider smoke 前置条件、精确验证命令与安全限制。C2 节点已在
当前工作树独立重跑全部 11 项门禁并全部 GREEN，结果与
[Phase 2 验收证据](../verification/phase-2-evidence.md) B8 记录逐项一致；
未创建或移动 tag，`v0.1-tutorial-parity` 待用户独立验收后才创建/移动。

**C4 fresh environment evidence（2026-08-07）：** locked dependency sync、mock
health/upload/task/WebSocket/artifact/download quick start 已实测通过；MySQL
integration `6 skipped`（Docker 不可用），真实 Web/Knowledge/model smoke `3
skipped`（凭据缺失）。这些 skip 均已明确记录，未被计为成功。

**Final delegated acceptance（2026-08-07）：** 用户将独立验收委托给 Codex。
最新全量门禁再次通过：E2E 1 passed、integration/unit 355 passed / 9 skipped、
frontend 60 passed、eslint/build、ruff/format、pre-commit、Compose、offline doctor
与 `git diff --check` 全部 GREEN。Phase 2C accepted；tag 尚未获得重指向授权。

## Non-goals

以下内容属于后续 Phase，不在 Phase 2 实现：

- AI Agent 研究数据集和评测 runner；
- Claim/Evidence 引用验证；
- 多编排策略消融；
- trace、成本和指标系统；
- 持久化、断线续传和服务重启恢复；
- 审批与预算治理。
