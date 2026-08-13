# Portfolio Guide

这组材料把已发布的 `v0.2-portfolio-showcase` 整理为可阅读、可复现和可面试说明的
工程作品集。产品主线是多来源 DeepAgents 研究闭环；确定性 fixture、评测 runner 和
验收记录只用于证明契约，不代替真实研究产品。

## Start Here

- [Architecture](architecture.md)：产品链路、引用交付和离线证据分区；
- [Demonstration](demo.md)：不读取凭据、不访问网络的成功、降级和失败演示；
- [Failure Retrospective](failure-retrospective.md)：Phase 4.5 验收期间发现的问题与修复；
- [Interview Evidence](interview-evidence.md)：可回链的 STAR 叙事和面试追问边界；
- [Evidence Map](evidence-map.md)：每项公开声明对应的仓库证据与禁止外推范围。
- [Formal Local Knowledge](knowledge-showcase.md)：官方来源、显式构建、固定问题和
  Showcase 接入边界。

## What Is Demonstrated

```text
Research request
  -> DeepAgents main agent and expert workers
  -> Web / read-only MySQL / local knowledge / uploaded files
  -> validated source locators, claims, and citations
  -> FastAPI + WebSocket progress and artifacts
  -> React workspace + Markdown/PDF reports
```

仓库内的 Phase 9 demo 通过同一 API、事件、引用和报告契约复现这条链路，但用固定的
本地 fixture executor 代替模型和外部来源。真实模型、Tavily、只读 MySQL 和上传文件
曾在一次显式授权的 Phase 4.5 smoke 中通过；随后一次单独授权的 Phase 9 smoke 仅启用
本地 knowledge 与 uploaded-file，并通过 citation/report 合同。三类证据仍须按执行
模式分区，不得混用。

## Current Limits

- 正式知识包只有 6 份冻结官方文档和 140 个语义 chunk，不是通用 ingestion 平台；
- 13 题固定检索检查是 acceptance set，不是检索准确率或真实回答质量；
- 正式知识桌面/移动浏览器截图由用户明确豁免；功能链审阅覆盖实际索引、citation/report
  和 React 合同，不声称该 fixture 的 viewport E2E；
- 没有生产级持久化、恢复、审批、预算治理或完整可观测性声明；
- 离线评测的成功率、topic recall、coverage、零成本和 `latency=n/a` 不是实际模型指标；
- `v1.0-portfolio` 是本阶段的公开发布边界；该版本不包含部署。
