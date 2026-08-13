# Portfolio Evidence Map

本表是 Phase 9 公开材料的声明边界。README、架构说明、演示文档、失败复盘和面试材料
只能使用下列已验证事实；原始验收记录保留具体命令、环境和历史语境。

| 公开声明 | 可引用证据 | 允许表述 | 不允许外推 |
|---|---|---|---|
| 产品是多来源 DeepAgents 研究系统 | [ADR 0004](../adr/0004-product-direction-and-codex-governance.md)、[Phase 4.5](../phases/phase-4-5-research-showcase.md) | 主 Agent 与专家 worker 从 Web、只读 MySQL、本地知识检索和上传文件收集证据 | 不得描述为独立评测平台或生产 Agent 控制平面 |
| 四类来源共享可验证引用模型 | [Phase 4.5 finalization](../verification/phase-4-5-finalization-evidence.md) | 固定四来源 fixture 可重复产生 4 个来源、4 条 evidence 和 3 个交付产物 | 不得宣称所有真实来源在任意环境都可用 |
| 引用贯通 API、WebSocket、React、Markdown 和 PDF | [Phase 4 evidence](../verification/phase-4-evidence.md)、[Phase 4.5 finalization](../verification/phase-4-5-finalization-evidence.md) | live citation schema `2.0.0`、线程隔离、唯一终态和三类产物经过验收 | 不得宣称完整生产可观测、持久化或恢复能力 |
| 真实 Showcase 曾在授权边界内通过 | [Phase 4.5 finalization](../verification/phase-4-5-finalization-evidence.md)、[formal knowledge evidence](../verification/showcase-knowledge-evidence.md) | Phase 4.5 的四来源 smoke 与 Phase 9 仅启用 knowledge/uploaded-file 的 smoke 均通过其合同 | 不得把任一 smoke 解释为 Provider 质量、知识准确率、SLA 或生产就绪证明 |
| 正式知识检索使用 Qdrant Local + FastEmbed | [Knowledge migration](../verification/knowledge-retrieval-migration-evidence.md)、[formal knowledge evidence](../verification/showcase-knowledge-evidence.md) | 6 份冻结官方文档、140 个语义 chunk、稳定 fingerprint、13 题 acceptance set 和本地 citation/report chain 已验收 | 不得把 `13 passed` 写成检索准确率、真实回答质量，也不得宣称 Qdrant Server/TEI 或通用 ingestion 已实现 |
| 离线研究评测可复现 | [Phase 3 evidence](../verification/phase-3-evidence.md) | `seed-10`、`dev-40` 的 S0/S1 deterministic mock 输出与 fingerprints 可重复 | 不得把 `success_rate=1.0`、topic recall、coverage、零成本或 `latency=n/a` 当作真实模型表现 |
| 离线引用评测可复现 | [Phase 4 evidence](../verification/phase-4-evidence.md) | rule/offline 与 semantic/mock 的固定 fixture 指标和 report fingerprint 可重复 | 不得宣称真实 semantic adapter 已测或引用质量代表生产流量 |
| UI 适配桌面和移动视口 | [Phase 4.5 finalization](../verification/phase-4-5-finalization-evidence.md) | `1440x900` 和 `375x812` 的确定性浏览器流程通过，无水平溢出 | 不得把仓库截图表述为实时 Provider 运行截图 |
| 正式知识标题和完整 locator 可由 React 展示 | [Formal knowledge evidence](../verification/showcase-knowledge-evidence.md) | focused component suite 与实际索引功能链验证官方标题、完整 `collection:document:chunk` locator 和 Markdown/PDF 控件 | 正式知识 fixture 未做 viewport E2E 截图验收；截图已由用户豁免 |
| Phase 9 受限真实 Showcase smoke | [Formal knowledge evidence](../verification/showcase-knowledge-evidence.md) | 一次明确授权的 `knowledge,uploaded-file` run 生成 28 个 sources/evidence，且保留脱敏 limitation | 不得把单次运行的来源数量、工具调用或降级记录解释为质量、成本、延迟或成功率指标 |
| 系统会诚实表达局部不可用 | [Phase 4.5](../phases/phase-4-5-research-showcase.md)、[Phase 4.5 finalization](../verification/phase-4-5-finalization-evidence.md) | knowledge 缺失、来源未启用、配置不完整和执行失败均以结构化 limitation 表达 | 不得隐去失败路径或用空结果伪装成功 |

## Portfolio Language Rules

- 区分 `deterministic offline demo`、`authorized real smoke` 和 `unmeasured`。
- 数字必须与数据集、执行模式、模型类型和证据文件同时出现。
- 使用“已验证契约”“一次授权 smoke”“确定性 fixture”等限定词，不使用“生产级”、
  “高准确率”“低延迟”“低成本”或无证据的比较级。
- `v1.0-portfolio` 是 Phase 9 的公开发布边界；该版本不包含部署，也不授权后续远程
  操作。
