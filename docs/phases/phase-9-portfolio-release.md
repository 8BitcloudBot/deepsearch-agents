# Phase 9 — Portfolio Release

**Status:** Accepted for `v1.0-portfolio`

**Entry Gate:** Phase 4.5 accepted; this is sufficient to enter the portfolio
release lane. Phase 5-8 remain optional and are required only when the
portfolio makes claims about their orchestration, observability, persistence,
recovery, approval, or governance capabilities.

## Goal

把已验证系统整理为可公开演示、可复现、可用于简历和面试说明的作品集版本。

## Deliverables

- 以公开 README 说明已验证的多来源研究流程、证据边界和已知限制；
- 提供架构图、确定性离线演示脚本和仓库安全的桌面/移动截图；
- 整理失败复盘、工程权衡和可回链的 STAR/面试证据；
- 建立公开声明与仓库验收记录之间的证据矩阵；
- 提供小型正式本地知识包的公开来源清单、显式构建、固定问题和引用交付证据；
- 把 `v1.0-portfolio` 定义为公开发布边界；该版本不包含部署。

`portfolio-100`、`hidden-20` 和新的真实 Provider 质量、成本、延迟或成功率测量不属于
当前授权范围。正式知识扩展只允许固定 6 份公开官方文档、140 个语义 chunk 和 13 题
本地 acceptance set；不得把它表述为检索准确率或真实模型质量。其他 Phase 9 声明只能
引用已有的 `seed-10`、`dev-40`、引用评测和 Phase 4.5 验收记录，并必须同时保留其
离线、fixture、真实 smoke 或未测限制。

## Minimum Acceptance

- README、架构、演示、截图、复盘和面试材料相互链接且使用一致的产品叙事；
- 确定性演示在不读取凭据、不访问网络和不调用真实 Provider 的条件下复现正常、
  降级和失败路径；
- 所有公开能力或数字均可回链到仓库证据，且不把离线 fixture 指标外推为真实质量；
- 截图不包含凭据、本地绝对路径、私有文件、原始 Provider 响应或生产数据；
- 正式知识 evidence 贯通本地检索、同一 chunk locator、React、Markdown 和 PDF；正式知识
  fixture 的桌面/移动浏览器截图由用户豁免，功能链审阅作为该 fixture 的验收边界；
- 完整离线后端、前端、静态、安全和可复现门禁通过。

## Non-goals

本阶段不增加通用 ingestion、爬虫、企业知识平台或生产检索准确率评测，不启动
Phase 5-8，不在未授权时调用真实 Provider，也不在未授权时 push、tag、创建 Release
或部署。

## Current Acceptance Boundary

P9-1 through P9-5 与正式知识 K1-K6 已完成本地验收。用户明确豁免正式知识浏览器截图，
因此 K5 以实际索引后端、citation/report、React 合同和功能链审阅为准，不声称该 fixture
的桌面/移动 viewport 证据。一次明确授权的真实 Showcase smoke 仅启用
`knowledge,uploaded-file`，通过了 citation、Markdown、PDF、线程和泄漏合同，并保留
运行期间的脱敏降级 limitation。配置存在本身不构成未来真实 Provider 授权；其他真实
Provider、Phase 5-8 和部署仍不在该发布范围内。后续 push、tag 或 Release 仍需新的
明确授权。
