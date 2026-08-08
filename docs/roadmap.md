# Agent Engineering Research Copilot Roadmap

## 项目目标

构建一个面向 AI Agent 框架选型、工程调研和技术决策的多智能体研究系统，最终形成
可运行、可评测、可追踪、可恢复并能由仓库证据支撑简历表述的个人作品集项目。

项目采用渐进路线：先证明教程闭环，再迁移到真实研究领域；随后用评测验证引用和
编排收益，最后增加生产可靠性与治理能力。后续能力必须复用前一阶段已经证明的垂直
闭环，不为未来需求提前构建抽象。

## 交付原则

1. **可演示闭环优先。** 每个开发包必须产生可运行的用户流程，而不只是内部模块。
2. **关键安全不后置。** 路径隔离、只读 SQL、敏感信息脱敏和任务终态正确性始终是
   发布阻塞项。
3. **生产硬化分层。** 极端竞态、恢复、追踪和治理按所属 Phase 实施，不阻塞更早的
   教程演示。
4. **测试按风险配置。** 一个行为由最接近责任边界的测试证明，再由少量 E2E 证明
   闭环；不在多层重复验证相同内部细节。
5. **证据服务于决策。** 最终门禁记录真实命令和结果；开发过程中不为同步测试数字
   反复修改状态文档。
6. **简历数字可复现。** 质量、成本、延迟和成功率必须绑定数据、模型、Prompt 与
   commit，未实测不得写入简历。

## 发布线

| Release | 覆盖范围 | 目标 |
|---|---|---|
| `v0.0-foundation` | Phase 0 | 可安装、测试和构建的工程基础 |
| `v0.0-deepagents-examples` | Phase 1 | DeepAgents 核心能力示例 |
| `v0.1.1-tutorial-parity` | Phase 2 | 教程后端与 React 工作台闭环（accepted at `364180d`） |
| `v0.2-portfolio-core` | Phase 3-6 | 研究领域、评测、引用、编排和观测 |
| `v0.3-reliable-runtime` | Phase 7-8 | 持久化、恢复、审批和成本治理 |
| `v1.0-portfolio` | Phase 9 | 可公开展示的作品集版本 |

## Phase Map

| Phase | 核心成果 | 当前状态 |
|---|---|---|
| [0 — Foundation](phases/phase-0-foundation.md) | 工程基础与执行纪律 | 已验收 |
| [1 — Capability Examples](phases/phase-1-capability-examples.md) | DeepAgents 最小能力示例 | 已验收 |
| [2 — Tutorial Parity](phases/phase-2-tutorial-parity.md) | Web、数据、知识、文件、API、WS、React 闭环 | 已验收（`v0.1.1-tutorial-parity`） |
| [3 — Research Evaluation](phases/phase-3-research-evaluation.md) | AI Agent 研究领域与评测基线 | 已验收（P3-1–P3-7；dirty worktree HEAD `364180d`，[证据](verification/phase-3-evidence.md)） |
| [4 — Trustworthy Citations](phases/phase-4-trustworthy-citations.md) | 声明、证据和引用可信度 | 未开始（入口边界已冻结：Phase 3 corpus/dataset/runner/report 契约；需显式授权后启动） |
| [5 — Orchestration](phases/phase-5-orchestration.md) | 编排策略对照与消融 | 未开始 |
| [6 — Observability](phases/phase-6-observability.md) | 版本化事件、trace、指标 | 未开始 |
| [7 — Persistence & Recovery](phases/phase-7-persistence-recovery.md) | 持久化、重试和恢复 | 未开始 |
| [8 — Approval & Governance](phases/phase-8-approval-governance.md) | 人工审批和预算治理 | 未开始 |
| [9 — Portfolio Release](phases/phase-9-portfolio-release.md) | 演示、复盘和简历证据 | 未开始 |

当前唯一执行入口见 [phase-status.md](phase-status.md)。
