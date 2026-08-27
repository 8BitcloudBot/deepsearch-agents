# 执行日志

## 基线：2026-08-27
- 测试入口：`uv run --extra dev python -m pytest -q`（pytest 在 `[project.optional-dependencies].dev`，需 `--extra dev`；另有 `[dependency-groups].dev` 仅含 httpx-ws）
- 单测（-m "not integration"）：735 passed / 1 skipped / 9 deselected
- 全量含 integration：741 passed / 4 skipped——**integration 本机可直接跑通**，无 qdrant/tavily 外部依赖阻塞
- ruff check app：通过
- 分支：已从 main 切出 `opt/deepsearch`

## 已完成任务
### 阶段 1 清理（A 组，全部完成）
- [x] A4 httpx 移入 dev 依赖，uv.lock 刷新 (6d6502b)
- [x] A3 _is_deep_request 收敛到 app/conversation/heuristics.py 单一定义 (db4f405)
- [x] A1 deepagents 外壳移除：ModelPlannerAdapter 直连 ainvoke；删除依赖；经用户确认删除 examples/ 与 tests/examples/（纯库演示代码）(185715e)
  - 备注：app/citations/fixtures.py 的 "DeepAgents" 样本文案保留——是引用规则引擎语料而非代码依赖，改写将触碰 citations 红线并连带 20+ 处断言
- [x] A2 app/evaluation → benchmarks/evaluation，22 文件 import 修正，citations 原位 (b3b6067)
- [x] 阶段1文档清扫：全库扫查无漏网散落 md；examples 残留 ruff 死配置清除 (6895dae)

### 阶段 2 改进（B 组，B1-B9 全部完成）
- [x] B1 模型参数治理 (671a7fd)：model_temperature=0.2 / model_top_p=None / model_max_retries=2，环境变量可覆盖越界报错
- [x] B3 历史接线 (f2c520c)：审阅器/综合器 payload 增加 recent_history + 提示词使用说明；无历史传空列表
- [x] B4 评分贯通与全局排序 (9a3043c)：EvidenceItem.score、knowledge 融合分批级归一、web/session rank 衰减分、全局排序+每来源保底+locator 聚合+published_at 平局权重
- [x] B6 材料供给量放开 (a0439ab)：quote 1500/2000、tavily 预截 8000、top2 段落摘录、总字符预算 24000 整条剔除。**第3点（答案压缩+句子边界硬切）未实施**——核实无现存 answer 硬切逻辑（计划书所引 application.py:214 实为历史预算裁剪），待用户决策
- [x] B5 补充检索多轮循环 (700be85)：supplemental→review 回边、轮次≤3/查询总预算≤6 跨轮记账、recursion_limit=14 兜底、耗尽记 limitation 不死循环
- [x] B7 提示词重写+分支收编+日期注入 (75805b5)：三 prompt 用草案全文；_current_date_line 注入三角色；research_intensity/search_hints 字段优先回退关键词；runtime.py E501 per-file-ignores（中文提示词原文不缩写）
- [x] B8 审阅跳过捷径删除 (c810eb9)：每次都审阅；伪覆盖单测补齐
- [x] B9 引用校验上线 (e6ab15f)：app/citations/runtime_adapter.py 适配层；ENABLE_CITATION_VALIDATION 默认关、开启裁剪未支持 claim 记 limitation、全失败回退旧行为、关闭态对齐测试

## 进行中

## 待办队列
- 阶段 3：冒烟三问（时效题需真实 key 留给用户）+ README 重写 + 最终报告
- 用户决策项：B6 第3点答案压缩机制是否新增

## 用户决策记录
- 2026-08-27 移除 deepagents 后顶层 examples/ 处置 => 删除 examples/（推荐选项）
