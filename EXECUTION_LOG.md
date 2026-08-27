# 执行日志

## 基线：2026-08-27
- 测试入口：`uv run --extra dev python -m pytest -q`（pytest 在 `[project.optional-dependencies].dev`，需 `--extra dev`；另有 `[dependency-groups].dev` 仅含 httpx-ws）
- 单测（-m "not integration"）：735 passed / 1 skipped / 9 deselected
- 全量含 integration：741 passed / 4 skipped——**integration 本机可直接跑通**，无 qdrant/tavily 外部依赖阻塞
- ruff check app：通过
- 分支：已从 main 切出 `opt/deepsearch`
- 备注：基线中 pyproject 主依赖仍含 deepagents / httpx（对应 A1/A4 待办）

## 已完成任务
- [x] B1 模型参数治理：ConversationSettings 新增 model_temperature=0.2 / model_top_p=None / model_max_retries=2（MODEL_TEMPERATURE/MODEL_TOP_P/MODEL_MAX_RETRIES 可覆盖），build_agent_model 消费；.env.example 同步 (671a7fd)
- [x] B3 历史接线：审阅器/综合器 payload 增加 recent_history（复用 _history_records，与 planner 同构），system prompt 各加使用说明；无历史传空列表
- [x] 阶段1：A4 httpx 移入 dev (6d6502b)；A3 _is_deep_request 收敛 heuristics.py (db4f405)；A1 deepagents 外壳移除+examples 删除（用户确认）(185715e)；A2 evaluation→benchmarks (b3b6067)；文档清扫+ruff 死配置清理 (6895dae)
- [x] A4 httpx 移入 dev 依赖，uv.lock 刷新 (6d6502b)
- [x] A3 _is_deep_request 收敛到 app/conversation/heuristics.py 单一定义
- [x] A1 移除 deepagents 外壳：ModelPlannerAdapter 直连 ainvoke（system prompt/payload/DeepSeek 分支原样保留）；删除 deepagents 依赖；经用户确认删除纯 DeepAgents 演示代码 examples/ 与 tests/examples/
  - 备注：app/citations/fixtures.py 及 phase4 测试中的 "DeepAgents" 样本文案保留——它们是引用规则引擎的语料内容，改写将连带修改 20+ 处既有断言且触碰 citations 红线，非 A1 本意
- [x] B4+B6 评分贯通与材料放开 (9a3043c, a0439ab)；B6 第3点（答案压缩+句子边界硬切）未实施——核实无现存 answer 硬切（计划书 application.py:214 实为历史裁剪），待用户决策
- [x] B5 补充检索多轮循环 (700be85)：回边 supplemental→review、轮次/总预算记账、recursion_limit 兜底
## 进行中

## 待办队列
- 阶段 1：A4 → A3 → A1 → A2 → 文档清扫兜底
- 阶段 2：B1 → B3 → B4+B6 → B5 → B7 → B8 → B9
- 阶段 3：冒烟三问 + README 重写 + 最终报告

## 用户决策记录
