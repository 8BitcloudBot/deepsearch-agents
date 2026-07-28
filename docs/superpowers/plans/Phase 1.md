# Phase 1 DeepAgents 能力示例精确实施计划

> 本阶段对应教程前置章节，只建立 DeepAgents 能力示例和学习证据。禁止提前实现 Phase 2 的一主三从业务系统、Web/MySQL/RAGFlow 工具、WebSocket、报告生成和业务前端。

## 1. 阶段目标

完成以下九类能力的最小、独立、可运行示例：

1. invoke；
2. stream；
3. chunk 解析；
4. 字典式子智能体；
5. LangGraph/Runnable 兼容子智能体；
6. interrupt、人工审批和 resume；
7. backend、store 和 memory；
8. middleware；
9. skills。

每类能力必须具备：

- 独立示例文件；
- 离线单元测试；
- 可选真实模型 smoke test；
- 运行命令；
- 预期输出；
- 用途、限制和 failure case 学习记录。

## 2. 阶段边界

### 允许

- DeepAgents、LangGraph、LangChain Core 和 OpenAI-compatible 模型适配依赖；
- examples/phase1 下的教学示例；
- tests/examples/phase1 下的离线测试；
- tests/integration/phase1 下的可选真实模型测试；
- Prompt、事件解析、测试替身和示例 skill；
- ADR、README、阶段状态和验收证据。

### 禁止

- app/ 中的正式 Agent 主链路；
- Tavily、RAGFlow 和 MySQL Agent；
- 一主三从教程业务架构；
- FastAPI/WebSocket 接入；
- React 功能页面；
- 报告生成、文件上传和 PDF；
- Phase 3 领域数据和评测集；
- 持久化数据库、生产 checkpoint、成本治理和人工审批 UI；
- 未锁定版本的依赖；
- 在测试中调用真实付费模型；
- 把 integration skip 写成真实通过。

## 3. 前置门禁

Phase 1 开始前必须：

1. git status --short 无输出；
2. Phase 0 已由用户明确验收；
3. 当前 HEAD 包含 MySQL 端口隔离提交 9715255；
4. v0.0-foundation 不存在时，在 Phase 1 代码变更前创建 annotated tag；
5. tag 必须指向 Phase 0 最终代码，而不是包含 Phase 1 代码的 commit。

执行：

    git status --short
    git log -1 --oneline
    git tag --list v0.0-foundation
    git tag -a v0.0-foundation -m "Phase 0 foundation accepted"
    git show --stat --oneline v0.0-foundation

若 tag 已存在，验证它指向预期 Phase 0 HEAD，不得删除、移动或重建。

## 4. 固定目录与文件

Phase 1 只允许新增或修改：

    pyproject.toml
    uv.lock
    .env.example
    README.md
    CHANGELOG.md
    docs/phase-status.md
    docs/adr/0002-deepagents-version-and-api-surface.md
    docs/verification/phase-1-evidence.md
    examples/__init__.py
    examples/phase1/__init__.py
    examples/phase1/README.md
    examples/phase1/settings.py
    examples/phase1/events.py
    examples/phase1/runner.py
    examples/phase1/01_invoke.py
    examples/phase1/02_stream_chunks.py
    examples/phase1/03_dictionary_subagents.py
    examples/phase1/04_runnable_subagent.py
    examples/phase1/05_interrupt_resume.py
    examples/phase1/06_backend_store_memory.py
    examples/phase1/07_middleware_skills.py
    examples/phase1/skills/source-review/SKILL.md
    tests/examples/phase1/test_settings.py
    tests/examples/phase1/test_events.py
    tests/examples/phase1/test_runner.py
    tests/examples/phase1/test_examples_import.py
    tests/integration/phase1/test_real_model_smoke.py

不得自行更改文件名或把示例放入 app/。

## 5. 公共接口契约

所有示例共用以下本地接口，禁止各文件重复读取环境变量或自行格式化事件。

### settings.py

必须提供：

    @dataclass(frozen=True)
    class Phase1Settings:
        model_name: str
        base_url: str | None
        api_key: str | None
        timeout_seconds: float

    def load_settings() -> Phase1Settings
    def require_api_key(settings: Phase1Settings) -> str

环境变量固定：

    MODEL_NAME
    MODEL_BASE_URL
    MODEL_API_KEY
    MODEL_TIMEOUT_SECONDS

默认值：

- MODEL_NAME=openai:gpt-4.1-mini；
- MODEL_BASE_URL 为空；
- MODEL_API_KEY 为空；
- MODEL_TIMEOUT_SECONDS=60。

require_api_key 缺少 Key 时必须抛出带操作提示的 RuntimeError，不得打印 Key。

### events.py

必须提供：

    @dataclass(frozen=True)
    class NormalizedChunk:
        event_type: str
        agent_name: str | None
        text: str
        tool_name: str | None
        raw_type: str

    def normalize_chunk(chunk: object) -> list[NormalizedChunk]
    def render_chunk(chunk: NormalizedChunk) -> str

normalize_chunk 必须安全处理：

- AIMessage；
- AIMessageChunk；
- ToolMessage；
- 字典事件；
- tuple/list 包装；
- None；
- 未知对象。

未知对象不得抛异常，必须生成 event_type=unknown。不得通过字符串切片解析结构化对象。

### runner.py

必须提供：

    EXAMPLES: dict[str, str]

    def list_examples() -> list[str]
    def resolve_example(name: str) -> Path
    def run_example(name: str) -> int
    def main() -> int

允许的 example name 固定：

    invoke
    stream
    dictionary-subagents
    runnable-subagent
    interrupt-resume
    backend-store-memory
    middleware-skills

CLI：

    python -m examples.phase1.runner --list
    python -m examples.phase1.runner invoke

未知示例返回 exit 2；缺少模型 Key 返回 exit 3；示例执行异常返回 exit 1；成功返回 0。

## 6. Task 0：Phase 0 Tag 与 Phase 1 状态

1. 执行前置门禁并创建 v0.0-foundation。
2. docs/phase-status.md 更新为：
   - Phase: 1 — DeepAgents Capability Examples；
   - Status: in_progress；
   - Target Tag: v0.0-deepagents-examples；
   - Blockers: dependency/API surface not yet locked；
   - Next Step: Task 1 API inventory。
3. docs/verification/phase-1-evidence.md 建立环境、命令、结果、失败记录表。
4. CHANGELOG 增加 Phase 1 in progress，不写尚未实现能力。
5. 提交：
   docs: start phase one capability examples

## 7. Task 1：锁定依赖与 API Surface

### 7.1 依赖规则

在 pyproject.toml 增加 Phase 1 运行依赖：

- deepagents；
- langgraph；
- langchain-core；
- langchain-openai。

首次解析可以使用兼容版本范围，但 uv.lock 生成后必须记录实际精确版本。不得添加 Tavily、RAGFlow、数据库或前端依赖。

运行：

    uv add deepagents langgraph langchain-core langchain-openai
    uv lock
    uv sync --extra dev --frozen

### 7.2 必须进行 API introspection

不得凭记忆编写 DeepAgents API。必须执行并保存摘要：

    .venv/bin/python -c "import deepagents, langgraph, langchain_core; print(deepagents.__file__); print(langgraph.__file__); print(langchain_core.__file__)"
    .venv/bin/python -c "from deepagents import create_deep_agent; import inspect; print(inspect.signature(create_deep_agent))"
    .venv/bin/python -c "import deepagents; print(sorted(name for name in dir(deepagents) if not name.startswith('_')))"

继续 introspect 教程所需对象：

- create_deep_agent；
- subagents 参数或等价公开入口；
- backend/store/memory 公开类型；
- middleware 入口；
- skills 入口；
- LangGraph interrupt、Command、checkpointer；
- Runnable 类型要求。

### 7.3 ADR

docs/adr/0002-deepagents-version-and-api-surface.md 必须记录：

- 精确包版本；
- create_deep_agent 完整 signature；
- 本阶段使用的公开 API；
- 教程名称与当前包名称的映射；
- 已弃用或不存在的 API；
- 选择 mock/offline 与真实模型 smoke test 的原因；
- Phase 2 允许复用的部分和禁止复用的教学代码。

如果当前版本不存在某教程 API，不得自行造同名实现；记录阻塞并停止请求决策。

提交：

    chore: lock deepagents phase one api surface

## 8. Task 2：Settings、事件标准化和 Runner

严格使用 TDD。

### 8.1 Settings tests

测试：

- 默认 model name；
-空 base URL；
- 缺少 Key 时 require_api_key 抛 RuntimeError；
- timeout 非数字、零或负数时拒绝；
-错误信息不包含任何 Key。

### 8.2 Event tests

为 AIMessage、AIMessageChunk、ToolMessage、字典、tuple/list、None、unknown 建立固定 fixture。断言 NormalizedChunk 字段，不只断言字符串包含关系。

### 8.3 Runner tests

测试：

- list_examples 返回固定七项；
- resolve_example 不能越过 examples/phase1；
- 未知名称 exit 2；
-缺少 Key exit 3；
- runner 不读取 .env 文件中的秘密；
-导入 runner 不触发模型连接。

验证：

    .venv/bin/python -m pytest tests/examples/phase1/test_settings.py tests/examples/phase1/test_events.py tests/examples/phase1/test_runner.py -q
    .venv/bin/ruff check examples tests
    .venv/bin/ruff format --check examples tests

提交：

    feat: add phase one example runtime

## 9. Task 3：invoke、stream 和 chunk

### 9.1 01_invoke.py

必须：

- 通过 load_settings 获取配置；
- 使用锁定版本的 create_deep_agent；
- 使用固定 system prompt：You are a concise research assistant. Answer with one sentence.；
- 固定输入：Explain why checkpointing matters for long-running agents.；
- 只输出最终 assistant 文本；
- main 返回 int；
- 导入模块不执行网络请求。

### 9.2 02_stream_chunks.py

必须：

- 对同一输入调用公开 stream API；
- 使用 events.normalize_chunk；
- 输出 event_type、agent/tool 和 text；
- 不直接 print 原始对象；
- 保存至少一个未知 chunk fixture 的离线测试；
-记录 stream_mode 或当前版本等价参数。

### 9.3 验收

离线导入测试必须通过。真实模型 smoke test仅在 MODEL_API_KEY 存在时执行，否则 pytest skip，并明确显示 skip reason。

运行：

    .venv/bin/python -m pytest tests/examples/phase1 -q
    MODEL_API_KEY=... .venv/bin/python -m examples.phase1.runner invoke
    MODEL_API_KEY=... .venv/bin/python -m examples.phase1.runner stream

不得把没有 Key 的 skip 记为真实 smoke pass。

提交：

    feat: add invoke and stream examples

## 10. Task 4：字典式与 Runnable 子智能体

### 10.1 03_dictionary_subagents.py

固定两个教学子智能体：

- framework-researcher：只总结框架能力；
- risk-reviewer：只列出实现风险。

每个字典必须显式包含当前 DeepAgents 版本要求的 name、description、system_prompt 或等价公开字段。主输入固定为：

    Compare checkpointing and human approval as reliability mechanisms.

验收输出必须能区分主智能体和两个子智能体事件，但不要求模型一定调用全部子智能体；测试验证配置结构和事件归属。

### 10.2 04_runnable_subagent.py

实现一个最小 LangGraph/Runnable 子智能体：

- 输入契约与当前 API introspection 一致；
- 输出必须转换为 DeepAgents 接受的 message/state 契约；
- 不访问文件、数据库或网络工具；
-测试分别覆盖合法输入和缺少 messages/state 的错误；
-记录 Runnable 与字典式子智能体的适用差异。

提交：

    feat: add phase one subagent examples

## 11. Task 5：interrupt、审批和恢复

05_interrupt_resume.py 必须使用 LangGraph 当前公开 API：

- MemorySaver 或当前版本等价的内存 checkpointer；
-固定 thread_id；
- 一个风险动作节点；
- interrupt payload 至少包含 action、reason、risk_level；
- Command(resume=...) 或当前等价公开恢复 API；
- approve 和 reject 两条路径；
-恢复后不重复 interrupt 前已经完成的节点。

测试必须离线覆盖：

1. 首次执行进入 interrupt；
2. approve 后完成；
3. reject 后结束且不执行风险动作；
4.不同 thread_id 状态隔离；
5.相同 resume 不产生重复副作用。

本阶段只证明内存恢复，不实现数据库持久化和审批 UI。

提交：

    feat: add interrupt and resume example

## 12. Task 6：backend、store 和 memory

06_backend_store_memory.py 必须展示三个概念边界：

- backend：Agent 文件或工作空间访问接口；
- store：跨调用的键值/命名空间状态；
- memory：模型可消费的对话或长期信息。

使用临时目录和内存 store，不写用户目录，不写真实数据库。

测试必须覆盖：

-临时 backend 的读写作用域；
-路径不能逃逸临时根目录；
-两个 namespace 不串数据；
-同 thread memory 连续可见；
-不同 thread memory 隔离；
-测试结束临时数据清理。

如果 DeepAgents 当前版本对 backend/store/memory 命名不同，以 ADR 记录的公开 API 为准，不得伪造不存在的类型。

提交：

    feat: add backend store and memory example

## 13. Task 7：middleware 与 skills

### 13.1 Skill fixture

examples/phase1/skills/source-review/SKILL.md 必须包含：

- name: source-review；
- description；
-触发条件；
-输入/输出；
-三条来源审查规则；
-禁止编造引用；
-一个最小示例。

它只用于教学，不得复制为最终 Phase 4 引用验证器。

### 13.2 Middleware

07_middleware_skills.py 必须实现最小 middleware：

-调用前记录 request_id、model name、message count；
-调用后记录 duration_ms、output message count；
-错误时记录 error_type，不记录 Prompt、Key 或完整模型输出；
-支持注入 deterministic clock 进行离线测试；
-展示 skill 目录如何被当前 DeepAgents 版本加载。

测试覆盖成功、异常、脱敏和 skill 发现。禁止引入完整 trace 系统；全链路 trace 属于 Phase 6。

提交：

    feat: add middleware and skills examples

## 14. Task 8：集成 Smoke、文档和最终验收

### 14.1 Integration marker

pyproject.toml 注册 integration marker。tests/integration/phase1/test_real_model_smoke.py：

- MODEL_API_KEY 为空时 skip；
- Key 存在时只执行 invoke 和 stream 两个最小 smoke；
-每个测试 timeout 60 秒；
-不执行全部七个示例，避免不可控成本；
-不在日志打印 Key；
-失败记录 provider、model、错误类型，不记录秘密。

### 14.2 README

examples/phase1/README.md 必须包含：

-七个示例映射；
-逐条运行命令；
-离线测试命令；
-真实 smoke 命令；
-预期输出摘要；
-概念边界；
-已知限制；
-与 Phase 2 的边界。

根 README 只增加 Phase 1 示例入口，不宣称教程基线完成。

### 14.3 最终命令

    git status --short
    uv sync --extra dev --frozen
    .venv/bin/python -m pytest tests/ -q
    .venv/bin/python -m pytest tests/integration/phase1 -q
    .venv/bin/ruff check app examples tests scripts
    .venv/bin/ruff format --check app examples tests scripts
    .venv/bin/pre-commit run --all-files
    .venv/bin/detect-secrets scan --baseline .secrets.baseline
    .venv/bin/python -m examples.phase1.runner --list
    rg -n "Tavily|RAGFlow|WebSocket|report|drug|medicine" app examples tests

无 MODEL_API_KEY 时 integration 必须显示 skip，不能记为 pass。若用户提供 Key，再执行 invoke/stream smoke 并记录 Token/费用未知，不伪造成本。

### 14.4 完成状态

docs/verification/phase-1-evidence.md 记录：

-依赖精确版本；
- API introspection；
-每个示例命令和 exit code；
-测试总数、skip 数；
-真实 smoke 是否执行；
-失败和限制；
-commit SHA；
-禁止范围检查；
-最终 git status。

docs/phase-status.md 设置 awaiting_user_acceptance。不得创建 v0.0-deepagents-examples，等待用户验收后再创建。

提交：

    docs: finalize phase one capability evidence

## 15. Phase 1 验收标准

- v0.0-foundation 指向 Phase 0 最终 commit；
- DeepAgents/LangGraph 版本和 API surface 已锁定；
-七个示例全部存在且可独立导入；
-invoke、stream、chunk、两类 subagent、interrupt/resume、backend/store/memory、middleware/skills 均有证据；
-离线测试不依赖 Key 和外部网络；
-真实 smoke 执行状态诚实记录；
-中断 approve/reject 和 thread 隔离测试通过；
-backend 路径隔离和 store namespace 隔离通过；
-middleware 不泄露 Prompt/Key；
-没有 Phase 2 业务 Agent、工具、API 或页面；
-README、ADR、phase-status、evidence、CHANGELOG 一致；
-git status clean；
-用户验收前未创建 v0.0-deepagents-examples。

## 16. DeepSeek 执行约束

-先阅读 v3、实施大纲、本计划、当前 phase-status 和 Phase 0 evidence；
-严格按 Task 0 到 Task 8 顺序；
-先写失败测试，再写最小实现；
-不得凭记忆猜 DeepAgents API，Task 1 必须 introspect；
-不得修改固定目录、接口、示例名称和退出码；
-不得新增计划外依赖；
-遇到教程 API 与当前版本不一致时停止并记录，不自行造兼容层；
-每个 Task 一个独立 Conventional Commit；
-每次任务同步 phase-status 和 evidence；
-禁止 git add .；
-禁止 Phase 2+ 实现；
-完成后停止等待用户验收。

