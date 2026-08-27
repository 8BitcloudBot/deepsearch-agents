# 执行日志

## 基线：2026-08-27
- 测试入口：`uv run --extra dev python -m pytest -q`（pytest 在 `[project.optional-dependencies].dev`，需 `--extra dev`；另有 `[dependency-groups].dev` 仅含 httpx-ws）
- 单测（-m "not integration"）：735 passed / 1 skipped / 9 deselected
- 全量含 integration：741 passed / 4 skipped——**integration 本机可直接跑通**，无 qdrant/tavily 外部依赖阻塞
- ruff check app：通过
- 分支：已从 main 切出 `opt/deepsearch`
- 备注：基线中 pyproject 主依赖仍含 deepagents / httpx（对应 A1/A4 待办）

## 已完成任务
- [x] A4 httpx 移入 dev 依赖，uv.lock 刷新 (6d6502b)
- [x] A3 _is_deep_request 收敛到 app/conversation/heuristics.py 单一定义
## 进行中

## 待办队列
- 阶段 1：A4 → A3 → A1 → A2 → 文档清扫兜底
- 阶段 2：B1 → B3 → B4+B6 → B5 → B7 → B8 → B9
- 阶段 3：冒烟三问 + README 重写 + 最终报告

## 用户决策记录
