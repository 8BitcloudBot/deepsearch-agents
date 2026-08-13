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
| `v0.2-portfolio-showcase` | Phase 3-4.5 | 已发布：研究评测、可信引用与真实多源展示 |
| `v0.3-optional-runtime` | Phase 5-8 | 经明确授权的编排、观测、恢复和治理扩展 |
| `v1.0-portfolio` | Release lane | 基于已验收展示闭环的公开作品集版本；不包含部署 |

## Phase Map

| Phase | 核心成果 | 当前状态 |
|---|---|---|
| [0 — Foundation](phases/phase-0-foundation.md) | 工程基础与执行纪律 | 已验收 |
| [1 — Capability Examples](phases/phase-1-capability-examples.md) | DeepAgents 最小能力示例 | 已验收 |
| [2 — Tutorial Parity](phases/phase-2-tutorial-parity.md) | Web、数据、知识、文件、API、WS、React 闭环 | 已验收（`v0.1.1-tutorial-parity`） |
| [3 — Research Evaluation](phases/phase-3-research-evaluation.md) | AI Agent 研究领域与评测基线 | 已验收（P3-1–P3-7；clean checkpoint `8afa4cd`，[证据](verification/phase-3-evidence.md)） |
| [4 — Trustworthy Citations](phases/phase-4-trustworthy-citations.md) | 声明、证据和引用可信度 | 已验收（P4-1–P4-7；checkpoint `acf7c46`，[证据](verification/phase-4-evidence.md)） |
| [4.5 — Research Showcase](phases/phase-4-5-research-showcase.md) | 真实多源研究、引用回链与报告展示 | 已验收（checkpoint `3a84c58`） |
| [5 — Orchestration](phases/phase-5-orchestration.md) | 现有 DeepAgents 编排策略对照 | 可选；需新授权 |
| [6 — Observability](phases/phase-6-observability.md) | 版本化事件、trace、指标 | 可选；需新授权 |
| [7 — Persistence & Recovery](phases/phase-7-persistence-recovery.md) | 持久化、重试和恢复 | 可选生产声明 |
| [8 — Approval & Governance](phases/phase-8-approval-governance.md) | 人工审批和预算治理 | 可选生产声明 |
| [9 — Portfolio Release](phases/phase-9-portfolio-release.md) | README、架构、正式本地知识演示、复盘和面试证据 | 已验收；`v1.0-portfolio` 发布边界 |

## Next Development Boundary

Phase 4.5 已在 checkpoint `3a84c58` 完成验收，并以
`v0.2-portfolio-showcase` 发布；发布 tag 指向 `bab5da4`。Phase 9 的公开 README、
架构说明、确定性演示、仓库截图、失败复盘和面试 STAR 证据已在本地完成验收。正式
本地知识包的 K1-K6、后端引用/报告链和 React 组件边界已经通过；正式知识桌面/移动
浏览器截图已由用户豁免，K5 以功能链审阅为验收边界。`v1.0-portfolio` 是该成果的
公开发布边界；不包含部署。

Phase 5-8 均为可选后续能力，不是本次作品集发布的阻塞项，并且需要新的明确授权。
其中 Phase 5 只能在同一多来源 DeepAgents 研究流程中比较编排策略，不得用无关 Agent
框架或独立评测产品替代业务闭环。Phase 7/8 仅在项目明确声称生产级持久化、恢复、
审批或治理能力时需要。

当前唯一执行入口见 [phase-status.md](phase-status.md)。
