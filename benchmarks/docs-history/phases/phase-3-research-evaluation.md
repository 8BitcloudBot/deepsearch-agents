# Phase 3 — Agent Research Domain and Evaluation Baseline

**Status:** Accepted — P3-1 through P3-7 accepted
**Entry Gate:** `v0.1.1-tutorial-parity` at accepted HEAD `364180d54a4c7b3141147f58b64b8ddd47d1b851`
**Acceptance note:** P3-7 acceptance ran on the current **dirty worktree** of
`364180d` (`git_dirty=true`); a clean checkpoint commit and tag/release require
later explicit authorization.

## Goal

把已验证的教程闭环迁移到 AI Agent 技术研究领域，并建立第一个可复现评测基线。

## Deliverables

- `agent-research` profile，不破坏 `tutorial` profile；
- 版本化 Web 快照、研究目录和知识资料集；
- `seed-10` 与 `dev-40` 样本；
- 统一评测 runner；
- S0 Single Agent 与 S1 Orchestrator-Workers 基线报告。

## Phase 2 Contracts Reused Without Regression

- `tutorial` profile remains the default and continues to use the accepted Phase 2
  API, WebSocket, artifact and React workbench contract.
- `agent-research` is additive; enabling it must not change tutorial defaults or
  remove `/api/upload`, `/api/task`, `/api/files`, `/api/download`, or `/ws/{thread_id}`.
- Existing event types and exactly-one-terminal semantics remain valid; Phase 3 may
  add profile/strategy metadata only through additive JSON fields.
- Mock/offline results and real Provider results are separate execution modes and are
  never combined into one quality claim.
- Every evaluation number is bound to dataset/version hash, model identity, Prompt
  identity, configuration fingerprint, strategy, and Git commit.

## Planned Packages

The execution order and bounded Reasonix briefs are defined in
[`docs/superpowers/plans/2026-08-07-phase-3-research-evaluation.md`](../superpowers/plans/2026-08-07-phase-3-research-evaluation.md).
The user confirmed the plan decisions on 2026-08-08. P3-1 through P3-7 are
accepted; the integrated acceptance evidence (fresh gates, reproducibility
reruns, real-smoke skips, report hygiene scan and the frozen Phase 4 input
boundary) is in
[`docs/verification/phase-3-evidence.md`](../verification/phase-3-evidence.md).
Phase 4 is not started; it consumes the frozen contracts listed there.

## Minimum Acceptance

离线评测可重复运行，结果绑定数据、模型、Prompt 和 commit；报告同时记录成功、失败
与限制，不以 mock 结果冒充真实服务结果。

## Non-goals

不在本阶段实现完整引用验证、S2-S4、生产 trace、持久化或审批。

## Later-Phase Dependency Boundary

- Phase 4 只消费 Phase 3 冻结的 corpus、dataset、case result 和 report 契约，再增加声明/证据/引用验证。
- Phase 5 以 S0/S1 为已测基线，才引入 S2-S4 与消融对照。
- Phase 6 消费稳定的 run/case/strategy 标识，再增加生产 trace 和可观测性。
- Phase 7-8 负责持久化、恢复、审批和成本治理；Phase 3 不预建这些框架。
