# 执行日志

## 基线：2026-08-27
- 测试入口：`uv run --extra dev python -m pytest -q`（pytest 在 `[project.optional-dependencies].dev`，需 `--extra dev`；另有 `[dependency-groups].dev` 仅含 httpx-ws）
- 单测（-m "not integration"）：735 passed / 1 skipped / 9 deselected
- 全量含 integration：741 passed / 4 skipped——**integration 本机可直接跑通**，无 qdrant/tavily 外部依赖阻塞
- ruff check app：通过
- 分支：已从 main 切出 `opt/deepsearch`
- 备注：基线中 pyproject 主依赖仍含 deepagents / httpx（对应 A1/A4 待办）

## 已完成任务
- [x] A2 app/evaluation → benchmarks/evaluation，22 文件 import 修正，citations 原位 (b3b6067)
- [x] 阶段1文档清扫：全库扫查无漏网散落 md；随 A1 删除的 examples 留下的 ruff per-file-ignores 死配置一并清除；updated//output/ 为运行时输出空目录保留
- [x] A4 httpx 移入 dev 依赖，uv.lock 刷新 (6d6502b)
- [x] A3 _is_deep_request 收敛到 app/conversation/heuristics.py 单一定义
- [x] A1 移除 deepagents 外壳：ModelPlannerAdapter 直连 ainvoke（system prompt/payload/DeepSeek 分支原样保留）；删除 deepagents 依赖；经用户确认删除纯 DeepAgents 演示代码 examples/ 与 tests/examples/
  - 备注：app/citations/fixtures.py 及 phase4 测试中的 "DeepAgents" 样本文案保留——它们是引用规则引擎的语料内容，改写将连带修改 20+ 处既有断言且触碰 citations 红线，非 A1 本意
## 进行中

## 待办队列
- 阶段 1：A4 → A3 → A1 → A2 → 文档清扫兜底
- 阶段 2：B1 → B3 → B4+B6 → B5 → B7 → B8 → B9
- 阶段 3：冒烟三问 + README 重写 + 最终报告

## 用户决策记录
