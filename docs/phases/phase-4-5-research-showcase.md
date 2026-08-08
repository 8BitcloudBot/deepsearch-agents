# Phase 4.5 — Research Showcase and Live-Source Parity

**Status:** Planned / ready; no package started
**Entry Gate:** Phase 4 accepted and frozen; implementation checkpoint
`e817c79`, with later closeout documentation commits forming the development
baseline

## Goal

把已验收的研究、评测和可信引用能力重新接回原项目的核心业务链路，形成可直接演示
的多智能体深度研究产品：主 Agent 协调专家 worker，从 Web、结构化数据、知识库和
上传文件取证，产出可回链引用的 Markdown/PDF 报告，并通过 API、WebSocket 与 React
工作台完整呈现。

## Product Flow

```text
Research request
  -> DeepAgents main agent + expert workers
  -> Tavily Web / MySQL / RAGFlow / uploaded files
  -> normalized source locators + claims + citations
  -> WebSocket progress + thread-scoped API
  -> React research workspace + Markdown/PDF report
```

## Deliverables

- 显式 `showcase` profile 和 live-source capability contract；默认离线与 tutorial
  profile 行为不变；
- Tavily、MySQL、RAGFlow、上传文件统一来源身份、版本、定位和安全跳转规则；
- DeepAgents 主 Agent / 专家 worker 复用现有研究 runtime 完成多来源纵向闭环；
- 引用丰富的 Markdown/PDF、artifact API 与 WebSocket 事件交付；
- React 工作台展示来源、引用、研究过程、限制与产物，不建设独立评测首页；
- 一组固定、显式 opt-in 的真实 Provider / 真实数据源 smoke 及脱敏证据。

## Invariants

- 离线评测与真实运行是两个执行和证据分区；不得混合聚合或用 fixture 指标代表真实
  Provider、Tavily、MySQL 或 RAGFlow 的质量。
- 真实调用必须同时满足显式 opt-in、已配置凭据和 capability check；缺一项即明确
  skip/fail closed，默认测试不得触网或读取凭据。
- 引用必须解析到实际来源 locator。Web 使用规范 URL 与抓取时间；MySQL 使用受控
  query/table/row identity；RAGFlow 使用 dataset/document/chunk；上传文件使用
  thread-scoped artifact/page/line 或 span。
- Provider 原始响应、凭据、绝对路径和未脱敏业务数据不得进入事件、fixture、报告或
  Git。远程 URL 和下载路径必须经过服务端校验。
- 保留唯一 terminal event、thread 隔离、只读 SQL、受控文件路径和 Markdown/PDF
  交付等既有安全契约。
- 不重写 DeepAgents，不引入另一套 Agent 框架，不以扩展评测 runner 代替产品闭环。

## Package Order

1. P4.5-1 — Showcase Profile And Live-Source Contracts
2. P4.5-2 — Multi-Source Citation Locators
3. P4.5-3 — DeepAgents Live Research Integration
4. P4.5-4 — Citation-Rich Delivery
5. P4.5-5 — React Showcase Polish
6. P4.5-6 — Real-Provider Showcase Smoke And Acceptance

每个 package 使用一个 fresh、bounded Reasonix 节点；Codex 独立审查 diff、契约和
门禁后才可进入下一 package。Reasonix 不负责 commit、tag、push 或 release。

## Minimum Acceptance

- 默认离线全量门禁保持绿色且零意外网络访问；
- 至少一个固定展示场景从研究请求贯通多来源、引用、WebSocket、React 和
  Markdown/PDF；
- 每类启用来源的引用均可回链并能在来源不可用、locator 失效或权限不满足时诚实降级；
- 显式 opt-in 的真实 smoke 生成独立、脱敏、可审计证据，不产生离线质量结论；
- 桌面和移动视口下研究过程、引用与报告可读，无重叠或核心流程回归。

## Non-goals

不在本阶段实现 S2-S4 编排对照、完整生产观测、持久化恢复、人工审批、预算治理或
广域爬虫。这些分别属于 Phase 5-8，且不得阻塞作品集展示闭环。
