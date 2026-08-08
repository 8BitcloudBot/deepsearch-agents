# Phase 4 — Trustworthy Citations

**Status:** Accepted at local clean checkpoint (Phase 5 not started)
**Entry Gate:** the frozen Phase 3 corpus/dataset/runner/report contract
(below), plus the clean Phase 3 checkpoint
`8afa4cd84cdf3da4259b3570011c7d1d923fbd8e`. Activation requires explicit
authorization for each fresh Reasonix node. Implementation is frozen after
P4-6; P4-7 is Codex-only evidence and handoff.

## Frozen Phase 3 Inputs (handoff boundary)

Phase 4 consumes exactly these contracts and adds claim/evidence/citation
implementation; it must not modify them or product code.

- **Corpus:** `agent-research-corpus-v1`
  (`corpus_sha256=3d0e034c0155e4d3190155137a0d312e4c156f80fb2be89215b4b2daaef788d7`).
- **Datasets:** `seed-10-v1` (10 cases `seed-001…seed-010`, `file_sha256=a902aba4…e8cf1055`)
  and `dev-40-v1` (40 cases `dev-001…dev-040`, `file_sha256=2a1aab55…34223f`),
  both bound by the strict `data/phase3/datasets/manifest.json` registry.
- **Runner / report contract:** `EvaluationCase`, `StrategyOutput`,
  `CaseResult`, `RunManifest`, `EvaluationReport`; runner `1.0.0`,
  `execution_mode=offline`, `model_id=mock:deterministic`; 17-field manifest
  with canonical run/input fingerprints and the dirty-worktree marker; report
  files `manifest.json` / `cases.jsonl` / `summary.md` / `comparison.md`.
- **Baselines:** S0 `s0-single-agent` and S1 `s1-orchestrator-workers`
  (prompt/config hashes and aggregates recorded in
  [`verification/phase-3-evidence.md`](../verification/phase-3-evidence.md)).
- **Offline / real separation:** mock results and real Provider results are
  separate execution modes and are never combined into one quality claim.
- **Dirty-worktree caveat:** Phase 3 acceptance evidence was produced on a
  dirty worktree at `364180d` (`git_dirty=true`). Phase 4 starts only after a
  clean checkpoint commit is explicitly authorized and made.

## Goal

让报告中的关键声明能够定位来源、判断支持关系并暴露冲突、过期和不支持状态。

## Deliverables

- `EvidenceItem`、`Claim` 和来源等级模型；
- 规则与语义支持检查；
- 引用定位、冲突和版本状态；
- 前端引用面板；
- Citation Precision、Recall、Entailment 和 Unsupported Claim Rate 报告。

## Minimum Acceptance

在 Phase 3 固定数据上复现指标，失败声明可追溯到具体规则或模型判断。

P4-7 fresh acceptance 已在 Phase 4 implementation checkpoint `e817c79`
独立完成，详见 [Phase 4 验收证据](../verification/phase-4-evidence.md)。实现
文件保持冻结；`acf7c46` closeout 已将 fixtures、计划和 roadmap 状态固定为后续开发
起点。未创建 release tag，Phase 5 仍未启动。

## Planned Package Order

The executable Phase 4 plan is
[`2026-08-08-phase-4-trustworthy-citations.md`](../superpowers/plans/2026-08-08-phase-4-trustworthy-citations.md).
It is intentionally limited to P4-1 through P4-7: citation data contracts,
deterministic rule checks, opt-in semantic checks, citation metrics, additive
API/event delivery, the React citation panel, and integrated acceptance.

## Non-goals

不同时实现所有编排策略、完整观测系统或持久化。
