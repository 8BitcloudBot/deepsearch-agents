# Current Phase Status

**Updated:** 2026-08-08

**Current Phase:** Phase 3 — Research Evaluation（accepted）

**Current Package:** P3-7 — Integrated Acceptance And Phase 4 Handoff（accepted）
**Next Phase:** Phase 4 — Trustworthy Citations（not started / planned；入口边界已冻结）

**Current accepted / release HEAD:** `364180d54a4c7b3141147f58b64b8ddd47d1b851`（Phase 2 release HEAD；Phase 3 acceptance 运行于其 dirty worktree，`git_dirty=true`）
**Current release tag:** `v0.1.1-tutorial-parity`（peeled to `364180d`; pushed；未被本次节点移动）
**Historical tag:** `v0.1-tutorial-parity`（peeled to `e29a80e`; unchanged）

## Accepted Baseline

| Phase | Status | Evidence |
|---|---|---|
| Phase 0 — Foundation | accepted | `v0.0-foundation` |
| Phase 1 — Capability Examples | accepted | `v0.0-deepagents-examples` |
| Phase 2 — Tutorial Parity | accepted | `v0.1.1-tutorial-parity` at `364180d` |

## Current Work

Phase 2A Demo Closure 已在 checkpoint `1d6166c` 验收：后端闭环、React Workbench、
三类 Provider、唯一 terminal、Markdown/PDF、前后端门禁以及 1440px/375px browser
smoke 全部通过。

Phase 2B Safety Hardening 已正式 accepted（B1→B8 独立节点推进，Codex 独立重跑
门禁结果一致；B8 全量门禁：后端 E2E 1 passed、integration/unit 355 passed /
9 skipped、前端 60 passed / eslint / build、ruff 与 `git diff --check` 干净；
`pre-commit` detect-secrets 的 `.secrets.baseline` 行号刷新已按钩子要求提交）。

Phase 2C Release Evidence 以 `fb17a39` 为起始 baseline，并在 `2d8698a` 完成验收：已产出
[本地 mock 复现 runbook](runbooks/phase-2-tutorial-parity.md)，覆盖前置条件、
mock quick start、上传/任务/WebSocket/产物下载工作流、可选 MySQL 与真实
Provider smoke 前置条件，以及精确验证命令；README 已链接该 runbook。C2 节点
已在当前工作树独立重跑全部 11 项门禁并全部 GREEN（结果与 B8 记录逐项一致，
见 [验收证据](verification/phase-2-evidence.md)），门禁未改动任何文件；B8
唯一的 RED（detect-secrets baseline 行号刷新）已随 `fb17a39` 提交而关闭。
C4 fresh mock quick start 已通过；MySQL `6 skipped` 的 pytest 原因为
`PHASE2_MYSQL_INTEGRATION` 未设置，同时当前 Docker daemon 权限不可用；真实
Provider/model `3 skipped` 的直接原因为 smoke opt-in flags 未设置，所需凭据也缺失。
用户已将独立验收委托给 Codex；最新验收
再次确认 E2E 1 passed、后端 355 passed / 9 skipped、前端 60 passed，以及全部
静态、构建、Compose、doctor 和 secret gates 为 GREEN。Phase 2C accepted。
后续文档收口提交形成当前 accepted HEAD `364180d`；annotated release tag
`v0.1.1-tutorial-parity` 已发布并 peel 至该 HEAD。旧 tag
`v0.1-tutorial-parity`（tag object `50680e6c`，peeled commit `e29a80e`）作为历史状态保持不变。

## Package Status

| Package | Status | Exit condition |
|---|---|---|
| Phase 2A — Demo Closure | accepted | 后端闭环、React Workbench 与桌面/移动 browser smoke 通过 |
| Phase 2B — Safety Hardening | accepted | B1–B8 门禁与 baseline 通过 |
| Phase 2C — Release Evidence | accepted | 文档、CI parity、最终门禁与委托用户验收通过 |

P3-1 Minimal Agent-Research Vertical Slice 已独立验收：`agent-research`
在残留真实 Provider 环境变量下仍为纯离线路径；三类版本化 source、真实
`/ws/{thread_id}` 事件、唯一 terminal、thread 隔离、Markdown/PDF、列表/下载和输入脱敏
全部通过。Codex fresh 验收：Phase 3 定向 `44 passed`，全后端
`484 passed / 11 skipped`，React `60 passed`，Ruff check/format 与 `git diff --check`
全部 GREEN。P3-2 亦已冻结 corpus v1 与 `seed-10-v1`，并经 Codex 独立验收：
全后端 `564 passed / 11 skipped`，React `60 passed`，UTF-8、metadata、hash、schema
与 source 引用边界通过。P3-3 已独立验收：统一离线 runner 与 S0 在只读
`seed-10-v1` 上生成 manifest、JSONL 和 Markdown；每 case 恰有一个 terminal
结果，离线模型/成本固定为 `mock:deterministic`/`0.0`，未测 latency 显式为
`null`/`n/a`。Codex fresh 验收：目标 `73 passed`，完整 Phase 3 `197 passed`，
全后端 `637 passed / 11 skipped`；Ruff check/format 与 `git diff --check` 全部
GREEN。两次 CLI 重跑的 case rows 字节一致，稳定 manifest 字段一致；跨 cwd 的
CLI 绑定当前 HEAD，且拒绝写入（含解析后的 symlink alias）`data/phase3`。P3-4
亦已独立验收：S1 固定为 Web snapshot、catalog、knowledge 三个有界 worker，
worker 拓扑和返回值均 fail-closed；异常或伪造输出成为结构化 limitation，不能
污染 source coverage 或中断其余 worker/case。Codex fresh 验收：P3-4 定向
`41 passed`、P3-3 回归 `73 passed`、完整 Phase 3 `238 passed`、全后端
`678 passed / 11 skipped`，Ruff check/format 与 `git diff --check` 全部 GREEN。
CLI comparison 证明 S0/S1 各有 10 个有序 terminal case，输入指纹一致，离线
latency/cost 为 `null`/`0.0`，且未声明策略胜负。P3-5 亦已独立验收：多数据集 registry
严格验证 `seed-10-v1` 与 `dev-40-v1`，seed fixture 保持字节不变；dev-40
包含 `dev-001` 至 `dev-040` 共 40 个固定 case。Codex fresh 验收：P3-5
定向 `71 passed`、完整 Phase 3 `271 passed`、全后端 `711 passed / 11 skipped`，
Ruff check/format 与 `git diff --check` 全部 GREEN。独立 CLI 的 dev-40 S0、S1
和 comparison 均各生成 40 个有序 terminal case，输入指纹一致，离线 cost 为
`0.0`、latency 为 `null`，没有静默遗漏或胜负宣称。P3-6 亦已独立验收：
canonical JSON SHA-256、dirty-worktree 布尔标记、run/input fingerprints、完整
manifest 字段、redaction 和未知成本 `null`/`n/a` 均通过；真实 Provider/model
smoke 在未设置 opt-in flags 时明确 skipped，未触发网络或读取凭据。Codex fresh
验收：P3-6 定向 `30 passed / 2 skipped`，完整 Phase 3 `301 passed / 2 skipped`，
全后端 `741 passed / 13 skipped`，Ruff check/format 与 `git diff --check` 全部
GREEN。四组 seed-10/dev-40 S0/S1 离线报告均生成完整 terminal rows 和 17 个
manifest 字段；混合已知/未知成本 aggregate 保持 `null`。P3-7 亦已独立验收：
9 项门禁全部 GREEN（Phase 3 E2E `2 passed`、完整 Phase 3 `301 passed / 2
skipped`、全后端 `741 passed / 13 skipped`、React `60 passed`、eslint/build、
ruff check/format 与 `git diff --check`）；seed-10/dev-40 S0/S1 离线报告各重跑
两次，case rows 字节一致、稳定 manifest 字段与 run/input fingerprints 一致；
真实 model/Provider smoke 在无 opt-in flags 下各 `1 skipped` 且未触网/未读凭据；
全部生成报告的凭据/绝对路径/原始 Provider 响应扫描 0 命中。
[Phase 3 验收证据](verification/phase-3-evidence.md) 已记录完整命令、退出码与计数。

Phase 3 验收运行于当前 **dirty worktree**（HEAD `364180d`、`git_dirty=true`），
并非干净 checkpoint。干净 checkpoint 提交、tag/push/release 与 Phase 4 激活均需
后续显式授权；Phase 4 保持 not started（planned），其入口边界已冻结为 Phase 3
corpus/dataset/runner/report 契约，详见 [Phase 4 文档](phases/phase-4-trustworthy-citations.md)。

## Phase 3 Package Status

| Package | Status | Exit condition |
|---|---|---|
| P3-1 — Minimal Agent-Research Vertical Slice | accepted | 离线 API/WS/artifact 纵向闭环与 Phase 2 回归通过 |
| P3-2 — Versioned Corpus And seed-10 | accepted | corpus v1 与 10 个固定 case 通过严格校验 |
| P3-3 — Unified Runner And S0 | accepted | seed-10 S0 生成受指纹绑定的可重复离线报告 |
| P3-4 — S1 Orchestrator-Workers | accepted | 同一 runner 下 seed-10 S0/S1 可比且 worker 边界 fail-closed |
| P3-5 — dev-40 Promotion | accepted | S0/S1 各完成 40 个固定 case |
| P3-6 — Fingerprints And Truthful Reports | accepted | 来源可审计，真实 smoke 显式 opt-in |
| P3-7 — Integrated Acceptance | accepted | Phase 3 门禁/复现/证据已验证；Phase 4 输入边界已冻结 |
| Phase 4 — Trustworthy Citations | not started | 入口边界已冻结；需干净 checkpoint 与显式授权后启动 |

## Active Documents

- [整体路线](roadmap.md)
- [Phase 2 实施文档](phases/phase-2-tutorial-parity.md)
- [Phase 2A 实施补充规范](phases/phase-2a-implementation-addendum.md)
- [Phase 2B 执行计划](superpowers/plans/2026-08-07-phase-2b-safety-hardening.md)
- [Phase 2C 复现 runbook](runbooks/phase-2-tutorial-parity.md)
- [Phase 2 验收证据](verification/phase-2-evidence.md)
- [Phase 3 研究评测计划](superpowers/plans/2026-08-07-phase-3-research-evaluation.md)
- [Phase 3 验收证据](verification/phase-3-evidence.md)

旧 plans、specs 和 handoffs 仅作历史记录，不是当前执行指令。
