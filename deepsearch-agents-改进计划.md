# deepsearch-agents 智能化改进与去冗余执行计划（交接文档）

> **项目根目录**：`/Users/wxhu/Documents/zcode/deepsearch-z`
> **交接日期**：2026-08-27
> **阅读对象**：负责实施的新会话。本文档自包含，无需其他上下文。所有行号基于交接当日的代码状态，若行号漂移请按函数/标识符名定位。

---

## 0. 执行须知

### 0.1 业务定位

多轮对话研究助手：用户每轮提一个问题，系统从三类证据源——本地知识库（Qdrant）、实时网络（Tavily，逐轮开关）、会话上传文件——检索材料，综合出带引用编号的回答。核心竞争力指标 = 回答的信息量、可信度、多轮连贯性。

### 0.2 现状一句话诊断

固定 DAG 流水线（plan → retrieve → review → 补充检索 ≤1 轮 → synthesize），每回合 LLM 最多调用 3 次；DeepAgents 外壳被显式掏空成单次调用；证据选取不看相关性分数、截断激进；综合器拿不到对话历史；关键词 if-else 决定产品能力开关。工程面（fail-closed、测试、存储）质量高，智能层被过度夹具化。

### 0.3 技术栈与运行方式

- Python + FastAPI(WebSocket) + SQLite 后端，React/Vite 前端；`langgraph` + `langchain-openai`（OpenAI 兼容协议）；`qdrant-client[fastembed]`、`tavily-python`
- 默认模型 `openai:gpt-4.1-mini`（`app/conversation/settings.py`，可经 MODEL_NAME/MODEL_BASE_URL/MODEL_API_KEY 换任意兼容端点）
- 测试：`pytest`（48 个测试文件，tests/unit + tests/integration 分层标记），lint 用 `ruff`，仓库有 pre-commit
- 改动总原则：**保留现有技术架构**（LangGraph 图形状、FastAPI+WS、SQLite 存储合同不变）；响应合同向后兼容；每个任务都要补配套测试；新增行为默认保守（失败降级到旧行为）

---

## 1. 不许破坏的骨架（实施红线）

以下内容是本项目的合格资产，任何任务不得削弱：

1. **fail-closed 安全姿态**：web 开关关闭时强制 web_queries 为空（runtime.py 规划器提示词中已有该约束）；上传附件按 user/conversation 双重隔离索引（SessionFileIndex）；敏感信息脱敏。
2. **回合状态机与幂等**（app/conversation/store.py）：SQLite 里 users/auth_sessions/conversations/attachments/turns/reports 的存储合同不得变更语义。
3. **错误脱敏文案体系**（model.py `_MODEL_MESSAGES`）：用户可见错误必须继续走稳定枚举文案；本文档 B 组改的是内部参数与流程，不是放松这个边界。
4. **既有测试风格**：契约式测试 + 少而准的断言。新功能在 tests/unit 下按现有模式增测；integration 测试保持分层标记。
5. **app/citations 包不在删除之列**（见 A2 的分界说明）。

---

## 2. 第一部分：去冗余任务

### A1 【替换】移除 DeepAgents 外壳，规划器改为直连模型调用

**现状**
- 全库只有一处真实使用 deepagents：`app/conversation/runtime.py:75-161` 的 `DeepAgentsPlannerAdapter`。
- 它注册 HarnessProfile 排除全部工具并禁用子代理（runtime.py:84-100），然后 `create_deep_agent(model=..., tools=[], subagents=[], system_prompt=...)`（runtime.py:111-122），实际等于一次带模板的消息包装调用；recursion_limit=6 只是防御值。
- pyproject.toml 主依赖含 `deepagents>=0.6.12`（项目本就直依赖 langgraph 与 langchain-core，deepagents 纯增量黑盒）。

**动作与步骤**
1. 重写 `DeepAgentsPlannerAdapter.plan()` 为直接调用：
   ```python
   response = await self._model.ainvoke([
       {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
       {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
   ])
   ```
   - system prompt 文本原样保留（B8 会再重写）；user payload 结构（question/use_web/recent_history）保留；
   - DeepSeek 分支处理原样搬迁：extra_body `thinking={"type":"disabled"}` + response_format json_object（runtime.py:103-110）；注意 openai-compat 场景下 `thinking` 字段对非 DeepSeek 提供方是否安全，建议仅在模型名含 "deepseek" 时注入（现有条件即是如此，保持）。
2. 删除 harness profile 注册代码（runtime.py:84-99）与 `create_deep_agent` import。
3. `pyproject.toml` 移除 `deepagents>=0.6.12`；全库 grep `deepagents`：
   - 已知残留：`app/citations/fixtures.py` 中有匹配字样——先查看是 import 还是注释文本；若是注释/字符串则顺手清理，若为真实依赖则该处一并改造（citations 是评测侧，不影响运行时）。
4. 相关测试中对 planner graph 的 mock/stub 改为对 `ainvoke` 的 stub（返回结构与现有 messages[-1] 对齐即可复用 `_strict_json` 解析路径直至 B2 替换）。

**影响面**：planner 行为零变化（同模型同 prompt 同 payload）；仅调用链变直。
**验收标准**：`deepagents` 在 grep 全库零命中；plan 失败仍抛 `ValueError("model response is invalid")` 语义不变；现有 planner 单测改造后全绿。

### A2 【搬家】归档 app/evaluation 到 benchmarks/（明确不含 app/citations）

**现状**
- `app/evaluation/` 共约 4500 行（strategies/s0_single_agent.py 154 行、s1_orchestrator_workers.py 493 行、runner/datasets/source_corpus 等），加上 `app/citations/` 合计 5094 行。
- 运行时代码（app/conversation、main、api/server）对这两个包的 import 为 **零**；触达方仅 scripts/evaluate*.py（evaluate.py、evaluate_citations.py、evaluate_showcase_knowledge.py）和约 20 个测试文件。
- s0/s1 策略为确定性 mock（model_id="mock:deterministic"），从不调用真实模型，也不反哺线上行为。

**动作与步骤**
1. `git mv app/evaluation benchmarks/evaluation`（顶层新建 benchmarks/ 目录，保持在同一仓库、git history 可追溯）。
2. 全量修正引用：scripts/evaluate*.py 及 tests 下 20 个文件的 `from app.evaluation...` → `from benchmarks.evaluation...`（机械 find-replace）。
3. **分界线（重要）**：`app/citations/` 本次不搬家——它是 B9 引用校验接入的材料来源（r0-r6 规则引擎 + 语义支撑判定）。若 evaluation 内部存在对 app.citations 的 import，允许 benchmarks 反向引用 app.citations（测试包外引用本项目包属正常），不要把 citations 连带走。
4. 若 s0/s1 两套策略确无继续使用价值，可在搬家后的 PR 里注明"候选下架"，但不急于删除——让下一个维护者决定。

**影响面**：纯移动，零行为变化；CI 若有路径断言需同步。
**验收标准**：app/ 仅剩生产链路模块；`pytest` 全绿；`python -c "import app.conversation"` 等入口不受影响。

### A3 【合并】_is_deep_request 双份实现收敛

**现状**：`turn.py:520-525` 与 `runtime.py:408-413` 是逐字重复的同一函数（相同的 5 个关键词元组："深入/详细/全面分析/深度/完整分析"）。turn.py 内 3 处调用（:239、:332、:430），runtime.py 内 1 处（:250）。

**动作**：把函数移到 contracts.py 或新建 app/conversation/heuristics.py 作单一来源，两处 import；函数体先不动（B8 会把它降级为回退逻辑）。
**验收标准**：grep 仅剩一个定义点；测试全绿。

### A4 【清理】httpx 移入 dev 依赖

**现状**：pyproject.toml 主依赖列了 `httpx>=0.28,<1`，但 app/ 非测试代码零使用（fastapi[standard] 自带传递满足）。dev 组还重复声明了一次。
**动作**：主 dependencies 中删除 httpx；dev 组保留（pytest httpx 客户端要用）。
**验收标准**：`pip install -e .[dev]` 后 `pytest` 全绿；uv.lock/poetry 锁文件同步刷新。

---

## 3. 第二部分：优化任务（P0 → P1 → P2）

> P0 = 直接决定回答质量的封锁解除；P1 = 智能上限提升；P2 = 打磨。每项标注：【现状】→【方案】→【验收标准】→【回归风险】。

### B1 (P0) 模型参数治理：temperature、max_retries

**现状**：`app/conversation/model.py:48-69` 构造 ChatOpenAI 时硬编码 `max_retries=0`（:60），temperature/top_p 完全未设（OpenAI 新版默认 temperature≈1，高温跑 JSON-only 研究任务导致输出不稳定）。settings 无对应字段。

**方案**
1. `ConversationSettings`（app/conversation/settings.py）增加三个可选字段，均给保守默认值：
   ```python
   model_temperature: float | None = 0.2      # None 时沿用 provider 默认
   model_max_retries: int = 2
   model_top_p: float | None = None
   ```
2. `build_agent_model()` 组装 kwargs 时消费它们：
   ```python
   kwargs = {
       ...,
       "max_retries": settings.model_max_retries,
       ...
   }
   if settings.model_temperature is not None:
       kwargs["temperature"] = settings.model_temperature
   ```
3. `.env.example` 同步补充示例键名。
4. 单测：构造 settings 断言 kwargs 正确传入（可用 fake transport 或 patch ChatOpenAI 构造器捕获参数）。

**验收标准**：默认温度 0.2、重试 2 次生效；环境变量可覆盖；现有错误码映射行为不变。
**回归风险**：低。max_retries 从 0→2 只会减少瞬时抖动导致的整轮失败。

### B2 (P0) structured output 替代手写 JSON 兜底

**现状**：三处解析都靠提示词约束 + 手工兜底：`_strict_json`（runtime.py:55-72：剥 code fence 后 `json.loads`，失败抛 ValueError）；除 DeepSeek 分支的 response_format=json_object 外未用结构化输出。`classify_model_error`（model.py:72-86）甚至靠 `"401" in text` 这类字符串匹配分类异常。

**方案**
1. 在 contracts.py 旁边定义三组 Pydantic 输出 schema（与现有 dataclass 字段一一对齐，因为 TurnResearchPlan/CoverageDecision/SynthesisDraft 可能已是受限 dataclass——如已是 Pydantic 则直接用）：
   ```python
   class PlanOutput(BaseModel):
       objective: str
       subquestions: list[str]
       knowledge_queries: list[str]
       web_queries: list[str]
   class ReviewOutput(BaseModel):
       uncovered_questions: list[str]
       knowledge_queries: list[str]
       web_queries: list[str]
   class SynthesisOutput(BaseModel):
       answer_sections: list[dict]   # {text, claim_indexes}
       claims: list[dict]            # {statement, evidence_ids}
       limitations: list[str]
   ```
2. 三次调用优先走 OpenAI 结构化输出通道（json_schema response_format 或 provider 支持 with_structured_output）；不支持 JSON-schema 的兼容端点退化为 json_object + `_strict_json` + Pydantic 校验双保险。
3. 顺带收紧 B1 的地址错误分类：能在异常类型/status_code 层面判断的先走类型判断，字符串匹配只作最后兜底（可选小改，不强求一次完成）。

**验收标准**：正常端点上不再出现 `model-response-invalid` 因裸 markdown 围栏引起的整轮失败（模拟围栏/前后缀噪声的对抗单测通过）。
**回归风险**：中。某些 OpenAI 兼容实现对 json_schema 支持不佳——必须保留退化路径，且退化路径要有测试。

### B3 (P0) 把对话历史注入覆盖审阅器与综合器（纯接线）

**现状**：recent_history（最近 6 回合、12000 字符预算，application.py:95-107 与 :203-218 收集）**只传给了规划器**（runtime.py:125-146）。审阅器 payload（runtime.py:197-207）和综合器 payload（runtime.py:269-278）都没有 history 字段——写出最终答案的组件不知道上一轮聊了什么，这是多轮追问场景"感觉笨"的最直接原因之一。

**方案**
1. runtime.py 审阅器 user payload 增加 `"recent_history": [...]`（同 planner 的 QA 列表格式）。
2. 综合器 user payload 同样增加该字段；两个角色的 system prompt 相应加一句中文说明（"recent_history 为此前数轮问答摘录；回答需自然衔接其中已确立的概念与结论，避免重复解释"——完整提示词以 B7 草案为准）。
3. 无历史时字段传空列表，prompt 句子写成条件无关（空列表也合法）。

**验收标准**：新增契约测试断言两个 payload 含 recent_history 且内容与输入一致；集成层回归一轮追问场景。
**回归风险**：低——payload 变大受 12000 字符预算钳制，不会撑爆上下文。

### B4 (P0) 证据评分贯通与全局排序

**现状（三层饥饿的第一层）**
- `EvidenceItem` 合同没有 score 字段（contracts.py:52-59，仅有 evidence_id/source_kind/title/quote/locator 等；published_at 字段存在于 :60 但全库无排序使用）。
- Qdrant RRF 分数明明存在（app/knowledge/contracts.py:198 有 score 字段；qdrant_local.py:350-385 计算 dense/sparse rank 与融合分），却在 `KnowledgeEvidenceRetriever.search_sync`（runtime.py:315-335）构造 EvidenceItem 时被丢弃。
- 因此 `_select_evidence`（turn.py:465-495）只能按 knowledge→session_file→web 固定次序轮流凑满 6/8 条配额——低相关知识库命中可以挤掉 web 高相关命中。

**方案**
1. contracts.py 给 `EvidenceItem` 加可选字段 `score: float | None = None`（as_dict/from_payload 同步序列化，参照 published_at 的既有写法）。
2. KnowledgeEvidenceRetriever 把融合分透传到 score。分数口径统一：knowledge 分数如果 >1（rank 型），先归一到 [0,1]（例如按本批 max 归一）；若实现麻烦，最低限度透传 dense 归一分。
3. Web/Tavily 检索器给出 rank 衰减分：第 i 条命中 score = 1/(i+1)；session_file 检索同理用其内部相似度或衰减分。
4. `_select_evidence`（turn.py:465-495）重写选择算法：
   - 先按 URL/locator 聚合（同一 locator 的多条 quote 合并为一条更长证据，仍受 quote 截断上限约束）；
   - 再全局按 score 降序取满 limit，同时做"每来源保底"：只要某来源非空且尚未入选，为其保底至少 1 条（防止任一来源被剃光头，保留现有多源融合的产品语义）；
   - published_at 作为 web 证据的同分平局权重（越新越前），并在传给综合器的 payload 中带上它供模型判断新旧。
5. turn.py:332/:430 与 :339-341 的证据条目选取同步改调新版 `_select_evidence`。
6. 测试：构造已知分数的三来源集合，断言入选顺序 = 分数序且各来源保底生效；URL 聚合单测。

**验收标准**：分数全链路可追踪（evidence payload 可见 score）；排序测试通过；历史 round-robin 语义完全移除。
**回归风险**：中低。answer 质量应上升；若某些集成测试固化了旧选取顺序，需更新期望（这属于合理断言修订，在 PR 说明中点名）。

### B5 (P0/P1) 补充检索从"一轮 ≤2 条"放开为带预算的多轮循环

**现状**
- 图边写死：review 之后要么 supplemental 要么 synthesize，**补充检索只允许一轮**，注释明说 "One supplementary round only"（turn.py:367-369）。
- 数量极限压缩：每个未覆盖问题每来源 ≤1 条查询、整轮 ≤2 条（turn.py:369-384 的 candidates[:2]/bounded[:2]）。
- 效果：需要连续追查 3 步以上的多跳问题必然覆盖不足，只能记一条 limitation 了事（turn.py:387-388）。

**方案**
1. LangGraph 图上增加回边：supplemental → retrieve（复用并行检索节点），state 增加计数器字段 `supplemental_rounds: int = 0`。
2. 路由条件改造（coverage decision 之后）：
   - `uncovered_questions` 为空 → synthesize（现有）；
   - 有未覆盖问题且 `supplemental_rounds < MAX_SUPPLEMENTAL_ROUNDS` 且本轮产出了新查询 → retrieve + rounds+=1；
   - 否则 → synthesize 并追加 limitation（现状文案保持）。
3. 总预算常量化：`MAX_SUPPLEMENTAL_ROUNDS = 3`、`MAX_SUPPLEMENTAL_QUERIES_TOTAL = 6`（跨轮累计记账，放在 state 一个 frozenset/tuple 里延续现有 `_new_queries` 去重语义，turn.py:365-366）。
4. coverage reviewer 的输出放宽一点点：允许每个未覆盖问题每来源至多 1 条保持不变（其自身夹具），但允许跨轮累计多次进料。
5. 所有规模常量集中到一个模块顶部常量区，便于后续调参。
6. 新测试：3 个未覆盖子问题的模拟场景断言进行了 3 轮补充后正确收敛退出；预算耗尽场景记 limitation 而非死循环（LangGraph recursion_limit 同步上调，跟 B6 循环次数联动）。

**验收标准**：多跳样例（手工场景 + 集成测试）能完成 ≥2 轮补充检索并在预算内退出；无任何无限循环路径（recursion_limit 兜底仍有）。
**回归风险**：中。延迟与 token 成本上升是设计意图——用常量控制上限；用例超时相关的集成测试设置需检查。

### B6 (P1) 材料供给量放开：quote 截断、web 摘录策略、超预算淘汰

**现状**
- quote 上限 480 字符（普通）/800（深入）（turn.py:339-341、:437-439 和 runtime.py:243 的 `_MAX_QUOTE/_MAX_COVERAGE_QUOTE` 多套常量并存）。
- Web 每个命中只取一个段落（runtime.py:416-436 的 `_relevant_excerpt`），页面正文先被整体截到 2048 字符（providers/tavily.py:51）、每查询仅前 5 条命中交付。
- 超字数预算的最终回答用 `answer[:available]` 硬切（application.py:214），可能断句。

**方案**
1. 常量治理：所有 quote/摘要上限集中定义，普通轮 480→1500、深入轮 800→2000；tavily 页面预截 2048→8000（正文字节成本可控）；`_relevant_excerpt` 从取 1 段改为取 top2 段落（按查询词密度排序拼接，中间用省略号分隔）。
2. 选择顺序：先用 B4 的 score 做证据间取舍；超过总字符预算（新增总预算常量，建议 ~24000 字符）时，从低分证据整体剔除，而不是把每条截得更碎。
3. 综合答案超预算时：优先调用一次便宜模型做压缩（同一端点，prompt 见 B7 草案附注）；若模型不可用才退回硬切，硬切从句子边界回退查找最近的 `。！？\n` 截断点。
4. deep-mode 判定此后只读 `_is_deep_request`（A3 已收敛），深入轮用大额常量档位。

**验收标准**：字符预算单测 + 硬切句子边界单测；正常问答的字数合规测试维持。
**回归风险**：低。主要成本是每轮输入 token 增长，均在可控常量内。

### B7 (P1) 系统提示词全面重写（附可直接粘贴草案）

**现状**：三条 system prompt 各 3-5 行、内联硬编码——规划器 runtime.py:115-121、审阅器 runtime.py:189-193、综合器 runtime.py:258-265；无角色纵深、无方法论、无 few-shot、无 CoT 引导（反而要求"不复述内部结构"）、**没有注入当前日期**（时效性问题失灵的根因）；深入模式判定靠关键词元组在两处重复实现，且 Tavily search_depth/topic/time_range 也由关键词表驱动（runtime.py:384-405）。

**方案分两步**

*第一步：分支收编*
- 规划器 JSON schema 增加可选字段：
  ```python
  class PlanOutput(...):
      ...                       # 既有四字段
      research_intensity: Literal["standard", "deep"] | None = None
      search_hints: dict | None = None   # {"search_depth": ..., "topic": ..., "time_range": ...}
  ```
- 规划器提示词中给两个字段的判定指导（何时算 deep、什么话题该搜 news）；下游 `_is_deep_request` 与 Tavily 参数代码改为：规划器字段缺失/解析失败时才回退到现有关键词启发（即 A3 收敛后的唯一实现）。这样旧测试仍可通过回退路径验证。

*第二步：提示词替换草稿（当前日期由 application.py 在组装时注入 system prompt 头部，格式 `今天是{ISO日期}（星期X）`）*

规划器（替换 runtime.py:115-121）：

```
你是一名严谨的研究规划器。给定用户问题与近几轮对话，输出一份研究计划。

方法要求：
1. 先判断问题的类型（事实查证 / 定义解释 / 多实体对比 / 时效动态 / 步骤教程），据此决定搜索侧重；
2. 将问题拆解为回答所必需的子问题，去掉可有可无的枝节；每轮至多 3 个子问题、2 个知识库查询、3 个网络查询；
3. 网络查询要具体、可命中（避免过宽的单词查询），时效类信息加年份或"最新"；权威事实类优先官方文档/规范；
4. 注意 recent_history：已经确立的事实不要再列入子问题；
5. 当本轮关闭 Web 时，web_queries 必须为空；research_intensity 取 standard 或 deep——涉及多步论证、比较多个主体或用户明示要深入分析时取 deep。

只返回 JSON 对象，字段：objective、subquestions、knowledge_queries、web_queries、research_intensity、search_hints（可选）。不调用任何工具，不委派任务，不输出 JSON 以外的内容。
```

审阅器（替换 runtime.py:189-193）：

```
你是证据覆盖审阅器。对照研究计划的子问题和已有证据，判断哪些部分仍未被证据支撑，并生成少量补充查询。

规则：
1. 逐一核对每个子问题：covered（有直接支撑）/ partial（只有间接或片面支撑）/ uncovered（没有证据触及）；
2. uncovered_questions 只收录 partial 与 uncovered 的子问题，至多 3 个，按重要性排序；
3. 每个未覆盖子问题对每类来源至多生成一条查询，查询不得与研究计划和已有记录重复；
4. 如果证据总体充分（关键主张均有出处），uncovered_questions 返回空数组。

仅返回 JSON：uncovered_questions、knowledge_queries、web_queries。
```

综合器（替换 runtime.py:258-265）：

```
你是研究综合撰写人。根据证据集与既定计划撰写回答。

要求：
1. 用自然、连贯的中文段落直接回答用户的问题；开头给出结论，再展开论据；不复述内部结构；
2. 每个事实性陈述都必须挂接 claims，claims.statement 对应答案中的一句话要点，evidence_ids 只能来自给出的证据 ID；一段 text 通过 claim_indexes 关联若干 claim；
3. 结合 recent_history 自然承接前文，不重复解释已确立的概念；
4. 证据之间冲突时如实呈现分歧而不是擅自裁决，并把冲突写入 limitations；
5. 信息可能因时间而变化的部分，利用证据中的时间信息谨慎表述（"截至…"）；
6. 涉及权限或安全限制的话题统一表述为"仅按允许列表执行"，不使用其他同义措辞；
7. 回答长度控制在约 {answer_budget} 个中文字符。

仅返回 JSON：answer_sections、claims、limitations。
```

（超预算压缩用的辅助 prompt，供 B6 第 3 点使用：）

```
将下面的研究报告压缩到不超过 {budget} 字，保留结论、关键数字与矛盾点，语言连贯可直接发布，输出纯文本。
```

**验收标准**：注入当前日期的单测（日期进入 system prompt）；research_intensity/search_hints 的取值-回退两条路径都有测试；全部既有 JSON 合同不被破坏（字段增加均为可选）。
**回归风险**：提示词行为变化属于预期收益，但要跑一轮整体手测/集成测试确认引用编号纪律没有被破坏（claim 的 evidence_ids 仍全部合法）。

### B8 (P1) 覆盖审阅跳过条件修订

**现状**：`_coverage_is_sufficient`（turn.py:528-548）在每个来源 hit_count≥1 且证据≥4 条时跳过审阅——命中数≠真答了问题，导致反思在最需要的场景恰好失效。

**方案**
- 简单可靠的版本：删除跳过捷径，每次都执行审阅（B2 之后审阅只是一次便宜的调用）；原"跳过"语义等价于审阅器返回空 uncovered_questions，新提示词（B7）已给了它的判据。
- 若想保留短路省成本的形态：只在「全部子问题仅 1 个 且 证据≥N 且 检索得分普遍高于阈值」时跳过，阈值随 B4 的 score 语义一起定。
- 同步处理与图路由的条件耦合点。

**验收标准**：构造"首轮命中的伪覆盖"单测：证据虽多但与子问题无关时不再跳过审阅。
**回归风险**：低-中（成本小幅上升，收益是反思真正起效）。

### B9 (P1/P2) 引用校验能力上线（接线 app/citations）

**现状**：app/citations 有一整套成品校验设施——rules.py 的 `RuleSupportChecker`(:210)/`SupportJudgment`(:198)、contracts 的 validate_claim/validate_evidence/fingerprint_sha256——但只消费冻结的 SEED_10 fixtures（fixtures.py），运行时的"引用校验"只是 `_finalize_draft`（turn.py:562-587）里的 evidence_id 集合交运算；claim 全部丢光时整轮报 `model-response-invalid`，不做降级重试。

**方案（分级推进，做成 feature flag）**
1. 设置增加 `ENABLE_CITATION_VALIDATION: bool = False`（默认关，开启后才改变行为——风险隔离）。
2. 写适配层 app/citations/runtime_adapter.py：
   - 输入：EvidenceItem 序列 + SynthesisDraft；
   - 输出：逐 claim 的 SupportState/ConflictState 判定结果列表；
   - 内部把 EvidenceItem 映射为 rules 期望的 source/claim 记录格式（先读懂 contracts.CITATION_FIELDS/SOURCE_FIELDS 再动手；fixture 依赖要通过参数化接口解耦，不允许再把 SEED_10 写死进调用路径）。
3. _finalize_draft 改造：flag 开启时对每个 claim 跑适配层；未获支持的 claim 处置：
   - 第一次尝试：收集失败原因，若存在 ≥1 个失败 claim，携带原因重新综合一次（复用 synthesize 循环但这次提示词附失败清单：哪些陈述缺证据支持）；
   - 第二次仍失败：丢弃失败 claim 并把差额记入 limitations（现行为是丢光即报错——保留报错路径作最后兜底）。
4. flag 关闭时行为与现状逐字节一致（保证随时可回滚）。

**验收标准**：flag 开启后的伪案例测试（模型编造无证据陈述→触发重综合或按 limitation 呈现）；关闭状态下全量测试与主线一致；异常情况下永远降级回旧路径而不是引入新的崩溃面。
**回归风险**：中。rules 依赖的具体字段格式需仔细适配；务必让该功能整体处于 flag 后面独立演进。

### B10 (P2) 记忆与体验打磨（顺手任务池，逐项独立提交）

1. 会话标题：store.py:312-335 目前纯正则剥前缀（"请问/我想了解"），换成一次便宜模型调用生成（失败回退现有正则）；同样可以做个开关或在无 key 时自动回退。
2. 滚动记忆：超出 6 轮/12000 字符的部分定期摘要成"结论卡"（哪些概念已定义、哪些事实已确认），注入 planner/synthesizer；实现放 application.py._bounded_history 旁，成为可选增强。
3. 部分失败优雅降级（外部评审吸收项）：知识库成功而 web 失败/模型超时这类复合故障下，考虑把已取得的知识库证据以"临时快照"形式呈现给用户而非整轮失败——注意必须维持现有错误码合同向后兼容（可作为新的事件类型扩展 WS 协议）。
4. 前端过程可观测（外部评审吸收项）：WebSocket 事件里已具备节点粒度事件的前提下，前端展示研究计划子问题与每条引用的来源分解（URL/知识库/附件文件名）。改动限于 React 层。

---

## 4. 建议实施顺序与 PR 切分

| # | 内容 | 任务 | 体感 |
|---|---|---|---|
| PR1 | 小清理 | A3 + A4 + A1 | 半天内 |
| PR2 | 参数修正 | B1 | 小 |
| PR3 | 历史接线 | B3 | 小 |
| PR4 | 评分贯通 + 材料放开 | B4 + B6 | 核心收益主力 |
| PR5 | 迭代检索 | B5 | 中 |
| PR6 | 提示词与分支收编 | B7 | 中 |
| PR7 | 反思门槛修正 | B8 | 小 |
| PR8 | 引用校验上线 | B9 | 大，flag 隔离 |
| backlog | 打磨 | B10 逐项 | 各自独立 |

## 5. 完成定义（DoD）与回滚

- 每个 PR：`pytest`（unit 必须全绿；integration 若有本地资源依赖按 marker 分层）、`ruff` 通过；新增行为均有对应新测试；PR 描述里列出更新的既有断言及理由。
- 主观验收基线（人工冒烟三问）：① 单跳事实题——正常引用；② 一道含最新进展的时效题——回答中有"截至…"+ 时间较新的 web 证据排前；③ 第三轮追问指代之前话题——回答承接到前文。
- 回滚开关：B9 由 ENABLE_CITATION_VALIDATION 控制；B5/B6/B7 的行为差异本质是常量与提示词，git revert 即回滚；B1 参数通过环境变量可即时恢复旧行为（显式设回未设置的组合）。
