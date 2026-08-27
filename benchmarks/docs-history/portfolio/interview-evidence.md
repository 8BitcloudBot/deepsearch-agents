# Interview Evidence

以下 STAR 叙事用于解释工程决策，不是可以脱离证据使用的营销文案。面试时应主动区分
deterministic offline evidence、authorized real smoke 和 unmeasured boundaries。

## 1. Restoring The Multi-Source Product Flow

**Situation:** Phase 3/4 已加入评测、fingerprint 和可信引用，但仓库容易被误读为独立的
Agent 评测平台，偏离原始 DeepAgents 研究产品。

**Task:** 把 Web、结构化数据、知识检索和上传文件重新接入主 Agent/专家 worker 流程，
并贯通 API、WebSocket、React、Markdown 和 PDF。

**Action:** 固定产品 ADR；新增显式 showcase profile 和 capability contract；为四类来源
设计统一 locator；复用既有 TaskRegistry 和报告边界；让引用 schema `2.0.0` 成为前后端
共同合同。

**Result:** Phase 4.5 在 `3a84c58` 验收，并发布为 `v0.2-portfolio-showcase`。固定离线
场景可重复产生 4 个来源、4 条 evidence 和 3 个产物；一次授权 smoke 贯通模型、Tavily、
只读 MySQL 和上传文件，另一次 Phase 9 授权 smoke 仅启用本地 knowledge 与 uploaded-file，
并保留降级 limitation。

**Evidence:** [ADR 0004](../adr/0004-product-direction-and-codex-governance.md)、
[Phase 4.5 finalization](../verification/phase-4-5-finalization-evidence.md)。

## 2. Making Citations A Cross-Layer Contract

**Situation:** 一个答案即使“看起来有引用”，如果 API、事件、UI 和报告使用不同身份，
也无法稳定回链或安全下载。

**Task:** 建立能够跨 Web、MySQL、knowledge 和 uploaded-file 表达来源身份的引用合同，
同时保持线程隔离、只读 SQL 和安全路径。

**Action:** 将来源标准化为 validated locator；对 quote、answer 和 limitation 统一脱敏；
由 delivery 生成 canonical citation JSON、Markdown 和 PDF；通过事件发布产物，并在 React
中按 source kind 使用受控链接策略。

**Result:** Phase 4/4.5 验收覆盖 citation retrieval、foreign-thread rejection、事件顺序、
唯一终态、报告下载和桌面/移动渲染。Phase 9 又用 credential-free demo 复现相同合同。

**Evidence:** [Phase 4 evidence](../verification/phase-4-evidence.md)、
[Architecture](architecture.md)、[Demonstration](demo.md)。

## 3. Separating Reproducibility From Provider Quality

**Situation:** Agent 系统很容易把 deterministic mock 的稳定数字误写成真实模型效果。

**Task:** 让研究和引用评测可重复，同时阻止离线数字越过其执行语义。

**Action:** 固定 corpus、dataset、prompt/config fingerprints 和 execution mode；重复运行
`seed-10`、`dev-40` 与 citation partitions；在报告中保留 `latency=null`、mock cost 和
“no superiority claim”边界；把 real smoke 与 offline reports 分区。

**Result:** Phase 3 的 S0/S1 cases 和 fingerprints 在两次运行间稳定，Phase 4 citation
partitions 也产生相同 fingerprint。公开材料只把这些结果描述为离线可复现证据。

**Evidence:** [Phase 3 evidence](../verification/phase-3-evidence.md)、
[Phase 4 evidence](../verification/phase-4-evidence.md)、[Evidence map](evidence-map.md)。

## 4. Closing Failures At Their Ownership Boundaries

**Situation:** 最终验收连续暴露 leak matcher 误报、MySQL native crash、上传链接 origin
错误和 wrong-thread fixture。

**Task:** 修复真实原因，同时不放松安全、线程隔离或外部 adapter 边界。

**Action:** 为每个失败先建立聚焦复现；收紧 token matcher；切换 Connector/Python pure
mode；组合 API base URL；修正 fixture thread identity；最后再运行完整离线门禁和授权
smoke。

**Result:** corrected real smoke 以 `2 passed` 完成，桌面/移动浏览器流程无水平溢出，
上传文件下载内容与 fixture 逐字节一致。复盘保留了失败过程而不是只记录绿灯。

**Evidence:** [Failure retrospective](failure-retrospective.md)、
[Phase 4.5 finalization](../verification/phase-4-5-finalization-evidence.md)。

## 5. Turning A Knowledge Adapter Into A Bounded Product Dataset

**Situation:** Phase 4.5 已证明 Qdrant Local + FastEmbed adapter 和引用合同，但没有正式
语料，knowledge 在授权 smoke 中只能诚实降级。

**Task:** 用少量公开、许可清晰、可冻结版本的官方文档证明真实本地检索参与研究，同时
避免发展成爬虫、企业知识平台或虚假的“高准确率”声明。

**Action:** 冻结 6 份官方来源及 commit/license/hash；以显式 catalog 做语义 Markdown
分块；建立 140-chunk path-backed index；设置读时 score threshold；设计 13 题固定
acceptance set；贯通正式标题、locator、citation `2.0.0`、Markdown/PDF 和 React 组件。

**Result:** 索引首次写入 140、第二次全部跳过，13 题满足声明的 Top-K/no-evidence 预期，
正式 knowledge 后端 smoke 通过。桌面/移动浏览器访问被环境安全审查阻断，随后用户明确
豁免该 fixture 的截图验收，因此 K5 以实际索引功能链、citation/report 和 React 合同为
边界，不把组件测试包装成 E2E。

**Evidence:** [Formal local knowledge](knowledge-showcase.md)、
[formal knowledge evidence](../verification/showcase-knowledge-evidence.md)。

## Questions To Answer Carefully

- **系统是否生产就绪？** 没有该声明；Phase 5-8 的完整观测、恢复、审批和治理未授权。
- **知识检索准确率是多少？** 没有该指标。当前 13 题固定 acceptance set 全部满足其
  Top-K/no-evidence 预期，只证明冻结语料与配置下的演示问题可重复，不等于准确率。
- **真实模型成本和延迟是多少？** 没有可公开的可复现测量；离线 cost `0.0` 和
  `latency=n/a` 只描述 deterministic mock。
- **为什么保留 fixture demo？** 它提供不依赖凭据和外部状态的合同复现，真实 smoke
  单独证明受控集成，两者承担不同失败模式。
- **为什么任务失败仍可能是 `task_completed`？** Showcase 将来源/Agent 局部失败转为
  结构化 limitation 并交付可解释结果；`task_failed` 保留给生命周期本身无法完成的异常。
