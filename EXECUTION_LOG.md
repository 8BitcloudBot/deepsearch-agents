# 执行日志

> **阶段封版：2026-08-27（freeze/post-rag）** —— 本文件自此为只读快照。封版时点 main 与 opt/deepsearch 同点，测试 608 passed / 4 skipped / ruff 全绿 / 前端 vite build + vitest 通过；后续工作从新周期开始。

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


## 治理改进轮（2026-08-29，分支 opt/deepsearch）

九视角治理审阅（LLM/数据/前端/多轮对话/上下文/文档入库/配置/技术栈/文档）后，
与首轮改进清单合并排序执行，一次一任务一 commit：

- [x] G1 CI 修复 (4daf2f2)：删除无 compose 文件的 docker config 步骤（实测必挂）；lint 路径
  去掉已删除的 examples；移除 format --check（11 文件不合规且 format 非质量门）
- [x] G2 日志层：app/logging_setup.py（DEEPSEARCH_TRACE 开关、brief 异常安全摘要、
  log_model_usage usage 计量）；装配降级全程可观测；embedder 独立构造解除主库
  隐式耦合；DAG 节点 trace 与回合失败诊断日志
- [x] G3 数据完整性：admin 清数据级联清个人知识库（uploads.delete_user）与报告文件
  （report.discard）；删会话清报告目录；reports 记相对路径；turn 锁改弱值字典自动回收
- [x] G4 僵尸 running 回合回收：store.fail_stale_running_turns（阈值
  TURN_STALE_SECONDS 默认 1800）；submit 前自动回收
- [x] G5 文档入库治理：xlsx 每工作表入库上限 20→200 行并显式标注截断；
  文档解析错误文案中文化（直达 422 detail 的用户面消息）
- [x] G6 补充检索轮接入个人知识库：主库与 uploads 库"库间并行、库内串行"
  发同一组补充查询，与首轮结构一致
- [x] G7 runtime 治理：日期注入改服务器本地时区（UTC 在 UTC+8 会差一天）；
  综合器长度预算采纳规划器 research_intensity 优先；删除 Tavily
  include_raw_content 请求（响应体无消费白白放大流量）
- [x] G8 上传并发治理：uploads ingest/remove/delete_user 加 per-user 互斥锁；
  HTTP 端点转 asyncio.to_thread，入库不再阻塞事件循环
- [x] G9 错误分类接线（评审稿 docs/design/error-taxonomy-wiring.md，RED-first）：
  TurnExecutionError 携带稳定枚举 code；plan/synthesize 异常经
  classify_model_error 映射；turn.failed 事件新增 error_kind（向后兼容）；
  用户面文案回归 model.py 稳定枚举（红线3 落地）
- [x] G10 会话列表瘦身：新增 GET /api/conversations/lite（仅元数据），
  完整端点合同原样保留（向后兼容）
- [x] G11 过程与连接治理：G11a 后端 review/supplemental 回环节点向 WS 发真实
  进度（含轮次），事件队列溢出后服务端主动断开 1013 触发重连；G11b 前端
  指数退避重连 + sequence 跳号告警 + 回合事件单会话增量刷新 + 401 统一拦截
- [x] G12 历史注入按句子边界截断：_bounded_history 不再拦腰硬切
- [x] G13 SQLite 最小迁移机制：schema_state 版本表 + 幂等迁移；v2 补
  conversations/turns/attachments/auth_sessions 查询索引，存量库自动演进

最终测试状态：583 passed（unit）/ integration 11 passed / ruff 全绿 /
前端 tsc + vitest 9 passed + vite build 通过。

## 治理轮暂缓池（仅在点名时执行）
- 前后端合同代码生成（openapi-typescript）；CORS/cookie secure 可配置化；
  提示词外置 prompts.py；证据注入定界（防提示词注入）；Tavily score 保留；
  dev 依赖双通道合并；requires-python 解封 3.13；会话并行回合语义评审；
  uploads meta 单点自愈对账工具；个人库容量/文件数上限；readers 死代码
  （SessionWorkspace/save_uploaded_file，T1 遗留，与既有"勿清理"豁免不是
  同一批项）处置确认；前端 useConversationApp 的 WS 逻辑单测


## 备选池执行轮：B10 小/中项 + 暂缓池小/中项（2026-08-29，分支 opt/deepsearch）

用户圈定"全部 小/中 优化"一次性开启（26 项归并 19 任务，编号 H；3 个中-大/大项
排除：citations 中文 tokenizer、回合取消机制、sparse 通道重构）：

- [x] H1 技术栈/配置小修包：dev 依赖双通道合并（httpx-ws 入 optional dev）；
  requires-python 解封 <3.14；doctor 版本放宽 3.12+ 并新增 .env 键对账；
  模块级 app.main:app 修正 README 启动命令
- [x] H2 数据小修包：SQLite busy_timeout 5s；create_session 顺带清理过期
  auth_sessions；ConversationReport.purge_orphans 启动回收孤儿报告目录
- [x] H3 配置小修包：tavily 交付上限提常量 + 双真源对齐断言测试；
  CORS/cookie secure 环境可配置（默认行为不变）
- [x] H4 LLM 小修包：三角色 system prompt 外置 app/conversation/prompts.py；
  综合器新增注入定界条款（evidence 为不可信外部材料）
- [x] H5 readers 死代码处置：删 SessionWorkspace/save_uploaded_file/原子写助手
  与 _validate_file_content（-199 行，T1 遗留，经用户开启确认）
- [x] H6 个人库容量上限：每用户文档数 50（构造可调），同名覆盖不占名额
- [x] H7 回合耗时可见：execute 完成/失败日志带 elapsed
- [x] H8 会话轮次软上限：MAX_TURNS_PER_CONVERSATION（默认 0 不限制）
- [x] H9 B10-1 会话标题模型化：ModelTitleAdapter 一次便宜调用，
  rename_if_untitled 保持占位标题语义，失败回退正则
- [x] H10 三角色独立温度通道：MODEL_TEMPERATURE_PLANNER/SYNTHESIZER/REVIEWER
- [x] H11 token 级历史预算：HISTORY_TOKEN_BUDGET（默认 12000 对齐旧字符语义），
  CJK 1:1 其余 4 字符/token，英文容量×4
- [x] H12 审阅器历史瘦身：coverage reviewer 只喂问答摘要（200/300 字符）
- [x] H13 同会话回合排队：执行锁粒度收紧为会话级，并行提交串行执行
- [x] H14 uploads 对账工具：uploads.audit 比对 meta↔索引（meta_only/index_only）
- [x] H15 B10-2 滚动记忆：窗口外轮次确定性结论卡（问题+答案首句）注入综合器
- [x] H16 B10-3 优雅降级（评审稿 docs/design/graceful-degradation.md，RED-first）：
  综合失败但证据在手 → 确定性证据快照（claims 空+降级说明），走既有
  turn.completed 流合同零扩展；引用幻觉场景同样降级（旧显式失败契约更新）
- [x] H17 B10-4 plan 子问题展示：planning 事件携带 subquestions，前端 stage 线渲染
- [x] H18 合同防漂移基建：scripts/export_openapi.py + 契约测试锁定 lite 字段集
  与完整端点兼容字段（openapi-typescript 全量生成仍留暂缓池）
- [x] H19 前端 WS 逻辑单测：401 静默登出 / failed 事件 / 重连行为（12 tests）

最终测试状态：unit 606 passed；全量 658 passed / 4 skipped；ruff 全绿；
前端 tsc + vitest 12 passed + vite build 通过。


## 真机效果验证轮（2026-08-29，G/H 改动实测）

测试数据包 `data/manual-test-v1/`（三文档三场景，README 含问题与预期）：
team-ai-policy.md（数字型制度）、device-inventory.xlsx（25 行台账）、
bluewhale-project.md（多轮记忆素材）。服务四能力全 ready，DEEPSEARCH_TRACE 开启。

- [x] T1 个人库精确检索（3 问）：token 预算数字全对（200 万/80 万/150 万/6000 万）
  且引用指向上传文档；"带出客户数据"如实区分"文档只禁输入环节"并拒绝越界发挥；
  "谁负责执行"文档未记载 → 明确无法回答并记 limitations（fail-closed）。
- [x] T2 表格入库（2 问）：第 23 行数据（旧 20 行截断上限会丢）准确命中——H5 生效；
  25 台统计与维修中 5 台（DEV-002/007/012/017/022）全对，且识别了表头行口径差异。
- [x] T3 多轮滚动记忆（9 连问）：第 8 轮仍准确答出第 1 轮建立的"蓝鲸"代号
  （已出 6 轮窗口，H15 结论卡生效）；第 9 问跨三文档汇总全部准确（6 条引用命中）。
- [x] H 轮功能实测观察：H9 标题生成全程工作（13 次调用，如"设备DEV-023负责人位置"
  "蓝鲸项目概述"）；H16 优雅降级真机首秀一次（综合输出无效 → 证据快照 + 降级
  limitation + 脱敏摘要，status=completed 前端可正常渲染）；G6 补充回环全程活跃
  （40 次 supplemental 节点）；G2 装配/usage/trace 日志完整可读。
- [x] 暴露并修正：真机测试数据包 README 首版预期值口算错误，已按生成脚本真值修正。
- 观察项（不入池，留档）：个别回合 90-290s 偏慢，主因补充回环轮次 + 模型输出
  啰嗦（title 调用曾出现 2442 completion token）；审阅器对已答对的问题仍可能记
  "未覆盖问题" limitations，文案略有噪声。

最终测试状态：与收尾基线一致（本轮无代码变更，仅新增数据文档）。


## 剩余问题修复轮（2026-08-29，9 项规划 → I1-I6）

- [x] I1+I2 漏网小项包：start_turn 关闭死附件流水线（新回合恒空、历史行读取
  兼容、冻结语义测试更新）；embedding 版本/维度入 settings（EMBEDDING_VERSION/
  DIMENSION）；前端请求 AbortSignal.timeout 兜底（30s/上传 120s）
- [x] I3 uploads 对账修复：repair() 双向修复（index_only 从 payload 恢复 meta、
  meta_only 清死条目），修复后 audit 归零；qdrant_local 增加 list_documents_summary
- [x] I4 真机观察项治理：title/planner/reviewer 设 max_tokens（200/600/800，
  synthesizer 不限）；reviewer 提示词强化 covered 判定
- [x] I5 回合取消机制（评审稿 docs/design/turn-cancellation.md，RED-first）：
  DELETE /turns/{tid}（404/409/僵尸分支）+ WS 新事件 turn.cancelled（向后兼容）
  + task 注册表按键定位；前端停止按钮；单测/integration/前端三层覆盖
- [x] I6 citations 中文 tokenizer：**两拍板点已决**（红线4 解读接受=tokenizer 属
  输入处理层、默认值保持关）；实现 app/citations/chinese.py 并行中文路径
  （rules.py 零改动）+ runtime_adapter 双 flag 串联 + 敌意套件 11 例 +
  真机 A/B（零误杀；一次裁剪为推断性陈述符合设计）；评审稿状态已更新
  （docs/design/citations-chinese-tokenizer.md）。观察项：真机一次 drop_reason
  截为 ": t"（本地不可复现），已加 DEBUG 诊断日志待复跑定位
- [x] ": t" 展示 bug 已定位并修复：根因是 chinese.py 各分支 reasons=("…")
  缺尾逗号实为 str，adapter 迭代字符串被逐字符展开成 "…: t/o/k…"；单测只
  断言 verdict 未查 reasons 类型形成盲区。修复：全分支尾逗号 tuple + 数字
  锚点按数值归一（023≡23）+ reasons 类型回归测试 2 例；真机复跑 drop_reason
  完整可读（"token 重叠率 0.13 低于 0.65 阈值（r2 词法重叠，中文路径）"）
- [x] I6 真机观察轮（.env 双 flag 开）：Q1 数字题 4 claims 零误杀 15s；Q2
  推断题裁剪 2 条且 drop_reason 完整（重叠率 0.13/0.06 低于阈值，fail-closed
  正确）；Q3 数字锚点对汇总类陈述从严（"共 25 台"引用单 chunk 证据不足被裁，
  符合设计）；定位中顺带发现 Qdrant local 文件锁被残留服务器进程占用导致
  主库不可用（pkill 重启即恢复）
- [x] sparse 检索重构：**决策不实施**——H6 容量上限已把最坏规模锁死在
  ~250 点，全库扫描无实际痛点；容量上限放开时再立项

最终测试状态：全量 667 passed / 4 skipped；ruff 全绿；前端 tsc + vitest
13 passed + vite build 通过。

## 剩余问题最新状态（本轮后）

- 待拍板：citations 中文 tokenizer（I6 评审稿就绪，2 个拍板点见评审稿）
- 暂缓观察：sparse 检索重构（触发条件未达成）
- 已全部收口：真机观察项（慢回合输出约束/审阅器文案）、4 项漏网小项、
  回合取消机制；留档决策项（单机假设、B6-3、主库冻结等）不变


## 前端展示审阅轮（2026-08-30，浏览器真机逐屏截图审阅）

真机审阅发现并修复三个功能性缺陷 + 一批展示优化：

### 功能缺陷（审阅实测暴露）
- [x] 跨站 cookie 401：页面 localhost:5173 与 API 默认 127.0.0.1:8000 属跨站，
  SameSite=Lax 会话 cookie 不随 fetch 发送 → 登录后会话列表静默为空、事件
  收不到。修复：vite dev 代理 /api → 127.0.0.1:8000（ws 支持），前端默认
  同源（VITE_API_BASE_URL 覆盖保留）；顺带发现 vite 仅绑定 ::1 时 IPv4
  客户端（内嵌浏览器）连接失败，server.host 双栈监听。
- [x] lite 摘要形状崩溃：hook 将 lite 列表直接断言为 Conversation 形状
  （无 turns 字段），组件 fallback 读 active.turns.length 白屏。修复：
  lite 结果补空 turns/attachments + 组件 activeDetail 守卫（双保险）。
- [x] eventSocketUrl 对空 baseUrl 构造 URL 抛 Invalid URL（同源模式），
  React 崩溃卸载。修复：退回 location.origin。

### 展示优化
- [x] "本轮限制"黄色大块从回答上方移除：流程性说明折叠为回答后方的
  "本轮限制与说明（N）"面板（默认收起）；内部诊断条目（ev- 前缀、
  token 重叠率）过滤不展示。
- [x] 主题统一：知识库页与工作区切换按钮的蓝色（#1a73e8）全部收敛到
  全站绿色系；证据卡裸露的 chunk locator 技术串对用户隐藏。
- [x] 侧栏身份成组（绿点+用户名），退出靠右；证据卡标题 13→14px；
  清理 T1 后死附件样式与重复的 .visually-hidden 弱化定义；补
  cancel-turn/stage-subquestions 新元素样式与窄屏缩进。

最终测试状态：前端 tsc + vitest 13 passed + vite build 通过；后端无改动
（626 unit passed 基线不变）。
