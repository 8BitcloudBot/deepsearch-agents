# 设计评审稿：部分失败优雅降级（B10-3，H16）

状态：**已批准实施**（用户 2026-08-29 开启全部小/中优化，含本项）。

## 现状

综合器两次重试耗尽后，整轮 `fail_turn`（G9 后带分类文案）——即使本轮
知识库/网络证据已经检索到位。复合故障（证据在手、模型整理失败）下
用户一无所获，重试也拿不回证据。

## 方案（保守形态）

`_synthesize` 重试耗尽时：

- `evidence_items` 非空 → 返回**确定性证据快照** `TurnResult`：
  - `answer` = 固定头部说明 + 每条证据的标题与原文摘录（≤300 字符/条，≤8 条）；
  - `claims = ()`（无模型整理即无事实声明，前端已有空 claims 渲染）；
  - `evidence` = 全部入选证据（前端证据卡照常展示）；
  - `limitations` 追加"模型服务异常，本轮以证据快照降级呈现"与错误安全摘要。
- `evidence_items` 为空 → 维持旧行为（`TurnExecutionError`，分类 code）。

## 红线核对

- 不新增 WS 事件类型：降级结果走既有 `answer.delta`/`turn.completed`
  流，前端零改动即可渲染（红线5 向后兼容 ✓，比计划书"新事件类型"更保守）。
- `store.py` 语义零变更（红线2 ✓）；错误文案仍走安全摘要、不泄漏 provider
  细节（红线3 ✓）；citations 不触碰（红线4 ✓）。
- 降级属可见行为变化：回合状态为 completed 而非 failed，limitations
  明确告知降级原因。

## 敌意用例（RED-first）

- synthesizer 恒抛 + 证据在手 → `engine.run` 正常返回，answer 含证据
  标题与原文，limitations 含降级说明，claims 为空。
- synthesizer 恒抛 + 无证据 → 仍抛 `TurnExecutionError`（分类 code）。
