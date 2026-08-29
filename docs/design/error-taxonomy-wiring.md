# 设计评审稿：错误分类体系接线（G9）

状态：**已随 G9 实施**（用户 2026-08-29 批准治理轮编排，含本项"评审稿先行 + RED-first"）。

## 现状问题

`app/conversation/model.py` 的 `classify_model_error` / `ModelUnavailable` /
`_MODEL_MESSAGES` 在执行链路上零消费：turn.py 把一切异常统一包装为
`TurnExecutionError("model-response-invalid")`，application.py 再统一为
"本轮研究未能完成"。用户无法区分"超时重试即可"与"API Key 配置错误"。
红线3（错误脱敏走 model.py 稳定枚举文案）实际未接到用户可见路径。

## 方案

1. `TurnExecutionError` 增加 `code` 属性（构造参数即 code，默认
   `model-response-invalid`，现有构造点零改动兼容）。
2. `_plan` / `_synthesize` 的底层异常经 `classify_model_error` 映射为
   稳定枚举 code（timeout/authentication/rate-limit/unavailable/…）。
3. `model.py` 新增公共 `safe_message_for(code)`（`_MODEL_MESSAGES` 不暴露）。
4. application 失败路径：`TurnExecutionError` → 枚举文案入库 +
   `turn.failed` 事件 `data.error_kind` 携带类别；其他异常维持现状文案、
   不带新字段。

## 红线核对

- 错误脱敏文案仍全部来自 model.py 稳定枚举（红线3 ✓）
- store.py 状态机与合同零变更（fail_turn 签名与 result_json 形状不变，
  仅调用方传入的文案换为分类文案）（红线2 ✓）
- WS/API 合同只新增 `error_kind` 字段，向后兼容（红线5 ✓）
- citations 包不触碰（红线4 ✓）

## 敌意用例（RED-first）

- planner 抛 `TimeoutError` → 引擎抛出的 `TurnExecutionError.code == "model-timeout"`
- engine 抛 `TurnExecutionError("model-timeout")` → turn.result.error 为
  "研究模型请求超时，请稍后重试"，`turn.failed` 事件 data 带
  `error_kind == "model-timeout"`
- 非 TurnExecutionError 异常 → 文案与事件形状与现状完全一致
