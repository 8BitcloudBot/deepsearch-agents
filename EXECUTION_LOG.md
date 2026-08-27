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
- [x] B4 调优：web 证据多查询合并后全局重编衰减分 (4ad2267)，真实时效题复验通过
- [x] 修复 limitations 对象形状被 str() 成原始字典串 (7c54c4b)：Mapping 提取 detail 等可读字段，未知形状退化 ensure_ascii=False JSON
- [x] B1 模型参数治理 (671a7fd)：model_temperature=0.2 / model_top_p=None / model_max_retries=2，环境变量可覆盖越界报错
- [x] B3 历史接线 (f2c520c)：审阅器/综合器 payload 增加 recent_history + 提示词使用说明；无历史传空列表
- [x] B4 评分贯通与全局排序 (9a3043c)：EvidenceItem.score、knowledge 融合分批级归一、web/session rank 衰减分、全局排序+每来源保底+locator 聚合+published_at 平局权重
- [x] B6 材料供给量放开 (a0439ab)：quote 1500/2000、tavily 预截 8000、top2 段落摘录、总字符预算 24000 整条剔除。**第3点（答案压缩+句子边界硬切）未实施**——核实无现存 answer 硬切逻辑（计划书所引 application.py:214 实为历史预算裁剪），待用户决策
- [x] B5 补充检索多轮循环 (700be85)：supplemental→review 回边、轮次≤3/查询总预算≤6 跨轮记账、recursion_limit=14 兜底、耗尽记 limitation 不死循环
- [x] B7 提示词重写+分支收编+日期注入 (75805b5)：三 prompt 用草案全文；_current_date_line 注入三角色；research_intensity/search_hints 字段优先回退关键词；runtime.py E501 per-file-ignores（中文提示词原文不缩写）
- [x] B8 审阅跳过捷径删除 (c810eb9)：每次都审阅；伪覆盖单测补齐
- [x] B9 引用校验上线 (e6ab15f)：app/citations/runtime_adapter.py 适配层；ENABLE_CITATION_VALIDATION 默认关、开启裁剪未支持 claim 记 limitation、全失败回退旧行为、关闭态对齐测试

## 进行中

### 后续优化轮（2026-08-27，按盘点优先级推进）
- [x] 合并决策：opt/deepsearch 全部本地 commit 以 fast-forward 合入 main（此后新任务继续在 opt/deepsearch 上做）
- [x] published_at 复查：结论"无需改动"——关键词回退路径已对时效词自动补 topic=news+time_range=month，hints 优先路径有单测；剩余缺失纯属 Tavily API 响应是否携带该字段
- [x] Citation 真实开箱 (ENABLE_CITATION_VALIDATION=true + DeepSeek/Tavily 实测)：flag 裁剪降级路径端到端可靠、主回答引用完好；但 rules.py 词法引擎为英文冻结语料设计（ASCII tokenizer + 英文否定词表），真实中文混合语料系统性误杀（本轮即有一条 claim 被 r6 'without' 触发裁剪）→ **结论：flag 维持默认关；正式启用需先给 citations 补中文 tokenizer，触碰规则语义红线，须单独拍板**
- [x] limitations 文案收敛 (ea69f3b)：未覆盖问题文案仅保留最新一轮，缺口解决后陈旧文案消失
- [x] web 单查询交付上限常量化 _MAX_WEB_HITS_PER_QUERY (68d859b)，行为零变化
- [x] B2 结构化输出 (d286f84)：output_schemas.py 三组 Pydantic 合同桥（失败原样透传旧行为）；_strict_json 噪声窗口剥离（JSON 前后夹带说明文字不再整轮失败）；MODEL_STRUCTURED_OUTPUT flag → 全角色 bind json_object；classify_model_error 类型/status_code 判断优先、字符串匹配降为兜底。真实 DeepSeek 验证通道开启链路正常
- [x] AGENTS.md 同步现状代码地图与开关清单
- [x] 前端 pnpm build 验证通过（vite build ✓ built in 902ms）

## 会话附件 → 个人知识库（RAG）改造轮（2026-08-27）
- [x] T1 移除旧附件会话路径 (4bd53d6)：前端 UI/API 三端点/引擎 session_file 支流/
  SessionFileIndex/EvidenceRetriever/tools 解析器全链路摘除；store.py attachments 表与
  source_kind 枚举冻结保留（红线2 与历史数据兼容）
- [x] T2 后端入库服务 (3378cd5/86c62b4)：uploads.py per-user Qdrant collection
 （uploads-{user_id} 物理隔离）、增量 upsert 同名覆盖、heading-section-v1 切块、
  readers.py 恢复 pdf/docx/xlsx 解析器与 zip/宏防护；引擎 run(user_knowledge=) 注入，
  结果并入 knowledge 分支统一评分；库间并行库内串行
- [x] T3 API (4879e20)：POST/GET/DELETE /api/library/documents，unavailable→503
- [x] T4 前端子页面 (7bf47ff)：侧边栏"研究/知识库"切换 + LibraryPage 上传管理页
- [x] T5 真实验证：私有手册 md 入库→检索 top1 score=1.0→DeepSeek 准确引用
  "48小时报销制/600元住宿标准" 回答，evidence 标题=company-handbook.md、kind=knowledge
- 备注：原"附件上传链路真实冒烟"待办由本改造取代并关闭

## 待办队列
- 备选池：B10 各项（会话标题模型化 / 滚动记忆 / 优雅降级 / 前端过程展示）；
  citations 中文 tokenizer 立项（若要正式启用引用校验）；README 补个人知识库使用说明

## 用户决策记录
- 2026-08-27 移除 deepagents 后顶层 examples/ 处置 => 删除 examples/（推荐选项）
- 2026-08-27 冒烟②时效题 => 改由执行会话用用户提供凭证实测，通过
- 2026-08-27 B6 第3点（答案超预算压缩+句子边界硬切）=> **不实施**。理由：现行代码无 answer 硬切逻辑（计划书前提不成立），长度控制已由综合器提示词 budget 承担，三轮真实测试无超长失控；如未来观测到普遍超长，优先收紧 budget 参数而非加文本截断

## 阶段 3 收尾（2026-08-27）
- [x] 管线级冒烟①单跳事实题：证据按分数排序（web:0.9 → web:0.8 → knowledge:0.4）、引用编号正常附加
- [x] 管线级冒烟③追问承接：2 轮 recent_history 端到端到达综合器（规划器/审阅器 payload 由 B3/B7 单测覆盖）
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
