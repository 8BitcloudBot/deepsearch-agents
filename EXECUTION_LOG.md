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
- 用户手测项：冒烟三问之③时效题（需真实 key，例："Tavily 最近发布了什么新功能？"）
- 用户决策项：B6 第3点答案压缩机制是否新增

## 阶段 3 收尾（2026-08-27）
- [x] 管线级冒烟①单跳事实题：证据按分数排序（web:0.9 → web:0.8 → knowledge:0.4）、引用编号正常附加
- [x] 管线级冒烟③追问承接：2 轮 recent_history 端到端到达综合器（规划器/审阅器 payload 由 B3/B7 单测覆盖）
- 冒烟②时效题留用户手测：需 MODEL_API_KEY + TAVILY_API_KEY 真实凭证，验证"截至…"表述与新近 web 证据排前
- [x] README.md 重写为现状版 (15fb7a5)
- 全部任务状态：A1-A4 ✓、B1-B9 ✓（B6 仅第3点未实施，见用户决策项）、B10 未做（P2，仅在点名时执行）

## 真实凭证端到端验收（2026-08-27，用户提供的 .env）
- [x] 配置兼容性：MODEL_NAME=deepseek-v4-flash（无 openai: 前缀）经 ChatOpenAI 直连 DeepSeek API 兼容；
  planner 的 DeepSeek 分支（thinking disabled + json_object）自动触发；TAVILY_API_KEY 即插即用；
  WEB_PROVIDER/CATALOG_PROVIDER/MYSQL_* 六键当前代码零消费——干净基线未迁移 MySQL catalog 源，属无害冗余可保留
- [x] 知识索引：本工作区只有 sources.json 原始抓取数据，分块清单在原仓库
  .data/knowledge-corpus/beginner-v2/manifest.json（134 chunks）；已用它本地建索引成功
- [x] 三轮真实对话全通（DeepSeek v4-flash + Tavily + Qdrant 本地索引）：
  ① 知识题引用编号 [1]-[5] 正常、limitations 具体；② 时效题"截至2026年1月"+Tavily 官方博客权威来源+
  如实 coverage limitation；③ 追问承接显著（开头直接衔接轮1/轮2 已确立概念）
- [x] 冒烟暴露缺口并修复 (6a25a40)：SearchHit/EvidenceItem 链路此前不透传 published_date，
  B4 平局权重与综合器时效判断无输入；现 provider→检索器→证据全程透传（双单测保证）
- 已知观察项：web 证据按每查询独立衰减打分，多查询同位次合并后分数可能扎堆 1.0，
  全局区分度退化为插入序；如需改进可在合并后统一重排，属后续调优不阻塞

### 最终 flag 清单
| 开关 | 默认 | 说明 |
|---|---|---|
| ENABLE_CITATION_VALIDATION | false | B9 引用校验；开启后未获支持 claim 裁剪+limitation。建议在验证 rules 词法阈值对本业务语料有效后再开 |
| ENABLE_TAVILY / TAVILY_API_KEY | 不设即关 | 原有 fail-closed 语义不变 |
| MODEL_TEMPERATURE / MODEL_TOP_P / MODEL_MAX_RETRIES | 0.2 / None / 2 | B1 参数；显式设回可即时恢复旧行为 |
| MAX_SUPPLEMENTAL_ROUNDS / QUERIES_TOTAL | 3 / 6 | B5 预算常量（代码常量区，调参改 turn.py） |

## 用户决策记录
- 2026-08-27 移除 deepagents 后顶层 examples/ 处置 => 删除 examples/（推荐选项）

## 最终测试状态：692 passed / 4 skipped / ruff 全通过（baseline 为 735+6 examples 演示测试）
