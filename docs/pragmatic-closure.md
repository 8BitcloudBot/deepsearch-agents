# Deepsearch 务实封版执行入口

本文件是当前阶段的唯一执行入口，把项目收敛为“多 Agent 调研 + WebSocket 实时过程 + Markdown/PDF 报告 + React 工作台”的可演示闭环。旧 plans、specs、handoffs 只用于审计，不得直接作为新任务指令。

每次协作从全新 Reasonix session 开始，不使用 `--resume`、`--continue` 或旧 handoff；保留工作树中已有修改。一个工作树同时只允许一个写入节点，不提交、不 push、不创建 tag，除非当前任务得到用户明确授权。

## 目标链路

```text
用户提交问题和约束文件
 -> WebSocket 创建任务
 -> 主 Agent 调度 Web/Catalog/Knowledge 专家
 -> 汇总工具事件
 -> 生成 Markdown/PDF 报告
 -> React 预览和下载
```

## 任务顺序

1. **B1 CI gate**：确认本地提交 `1d1c577` 文件范围，获得 push 授权后运行 Ubuntu Node 22 + pnpm 10 的 frozen install、Vitest、lint、build 和 Playwright；本地 Node 22 + pnpm 11 只能作为兼容性证据。
2. **B2 正常演示**：使用 mock provider，从问题/约束文件创建任务，验证 Web/Catalog/Knowledge 事件、报告生成、React 预览和下载。
3. **B3 失败/取消演示**：验证 provider failure、user cancel、duplicate cancel 和 failure 后 rerun，确保终态事件唯一且 React 可以再次 Run。
4. **B4 证据封版**：统一 README、phase-status、phase-2-evidence 和 changelog，明确 mock、opt-in provider 和 deferred capabilities。

## 本轮明确不做

Phase 3-9 的研究固定数据集、引用支持关系、复杂编排对比、完整 trace/成本指标、跨重启恢复、人工审批和硬预算不属于本轮封版。后续能力必须有独立阶段、数据、测试和验收门禁。

## 完成标准

新人按 README 可以启动默认 mock 模式；一条正常任务能从输入到 Markdown/PDF 下载；failure、cancel、rerun 路径可复现；真实 Tavily/RAGFlow/模型是否运行及其凭据要求都有明确说明；Phase 3-9 不被写成已完成。
