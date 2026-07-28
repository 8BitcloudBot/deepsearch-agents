# Phase 1-1 能力行为与验收证据修复计划

> 本阶段只修复 Phase 1 验收发现的实现与证据缺口。不得新增 Phase 2 业务能力；用户验收前不得创建 `v0.0-deepagents-examples`。

## 1. 修复目标

Phase 1 当前已有依赖锁定、七个示例文件和基础测试，但部分能力只有导入或说明文字，没有完成原计划要求的行为级证明。Phase 1-1 必须完成：

1. 为 interrupt、approve/reject、resume、thread 隔离和幂等副作用建立离线行为测试；
2. 使用 DeepAgents 0.6.12 的真实 `FilesystemBackend`、`InMemoryStore` 和 `MemoryMiddleware` 展示 backend/store/memory；
3. 使用真实 `AgentMiddleware.wrap_model_call` 实现结构化、可测试、脱敏的调用观测；
4. 使用真实 `SkillsMiddleware` 加载教学 skill，而不是只扫描目录；
5. 完整重写 Phase 1 evidence，并将 Task 8 状态与真实提交同步；
6. 保持无 Key 离线测试可重复，真实模型 smoke 继续诚实 skip；
7. 最终等待用户验收，不创建 Phase 1 tag，不开始 Phase 2。

## 2. 当前验收缺口

| 缺口 | 当前状态 | Phase 1-1 完成条件 |
|---|---|---|
| Phase 1 evidence | 仅 31 行，只记录 Task 0 | 记录 Task 0-8、全部命令、退出码、测试/skip、版本和限制 |
| Task 8 状态 | `in_progress`，无 commit | 完成后标记 `completed` 并写入真实 SHA |
| interrupt/resume | 只有实现，缺少行为测试 | 首次 interrupt、approve、reject、隔离、幂等全部通过 |
| backend | 直接使用 pathlib | 使用 `deepagents.backends.FilesystemBackend` |
| store | 有演示，无隔离测试 | 使用 `InMemoryStore` 并验证 namespace 隔离 |
| memory | 只返回说明文字 | 使用 `MemoryMiddleware` 和文件型 memory source，验证隔离与可见性 |
| middleware | hook 为空实现 | 真实记录 request_id、model、消息数、duration、error_type |
| skills | 仅手工目录扫描 | 构造并验证 `SkillsMiddleware` 真实加载 skill 元数据 |

## 3. 固定版本与真实 API

不得修改以下已锁定版本，除非当前 API 无法运行并经用户批准：

- deepagents 0.6.12；
- langgraph 1.2.9；
- langchain-core 1.5.1；
- langchain-openai 1.4.1；
- langgraph-checkpoint 4.1.1。

必须使用已经 introspect 的公开接口：

### FilesystemBackend

    FilesystemBackend(
        root_dir: str | Path | None = None,
        virtual_mode: bool | None = None,
        max_file_size_mb: int = 10,
    )

行为入口：

    backend.write(file_path: str, content: str)
    backend.read(file_path: str, offset: int = 0, limit: int = 2000)
    backend.ls_info(path: str)

### InMemoryStore

    InMemoryStore()
    store.put(namespace: tuple[str, ...], key: str, value: dict)
    store.get(namespace: tuple[str, ...], key: str)
    store.search(namespace_prefix: tuple[str, ...])

### MemoryMiddleware

    MemoryMiddleware(
        backend=backend,
        sources=[source_path],
        add_cache_control=False,
    )

Memory 在本示例中定义为：存储在受限 backend 中、能由 `MemoryMiddleware` 注入模型上下文的文件内容。不得用 UUID 或普通字符串冒充 memory。

### AgentMiddleware

使用：

    AgentMiddleware.wrap_model_call(request, handler)

其中 request 为当前版本 `ModelRequest`，handler 返回 `ModelResponse`。不得只实现空的 before/after hook。

### SkillsMiddleware

    SkillsMiddleware(
        backend=backend,
        sources=[skills_source],
    )

必须通过 middleware 的实际能力确认 `source-review/SKILL.md` 被发现；手工 `os.listdir` 只能作为辅助断言，不得作为唯一实现。

## 4. 允许修改文件

只允许修改或创建：

    examples/phase1/05_interrupt_resume.py
    examples/phase1/06_backend_store_memory.py
    examples/phase1/07_middleware_skills.py
    examples/phase1/README.md
    examples/phase1/skills/source-review/SKILL.md
    tests/examples/phase1/test_interrupt_resume.py
    tests/examples/phase1/test_backend_store_memory.py
    tests/examples/phase1/test_middleware_skills.py
    tests/examples/phase1/test_examples_import.py
    docs/phase-status.md
    docs/verification/phase-1-evidence.md
    docs/adr/0002-deepagents-version-and-api-surface.md
    README.md
    CHANGELOG.md
    .secrets.baseline

只有测试证明公共 runner 或配置存在缺陷时，才允许修改：

    examples/phase1/runner.py
    examples/phase1/settings.py
    tests/examples/phase1/test_runner.py
    pyproject.toml
    uv.lock

原则上不得修改依赖文件。任何额外文件或依赖必须先记录 blocker 并请求用户决策。

## 5. 全局执行规则

- 严格按 Task 0 到 Task 5 顺序；
- 每项实现先写失败测试并记录 RED 输出，再做最小实现；
- 不得删除已有测试来换取通过；
- 不得使用 import success、`hasattr(main)` 或说明文字替代行为断言；
- 离线测试不得访问模型、网络、MySQL、RAGFlow 或 Tavily；
- 临时 backend 必须使用 pytest `tmp_path`，测试后自动清理；
- 测试不得写入用户目录、仓库 output 或真实 memory；
- 所有日志不得包含 API Key、完整 Prompt 或完整模型输出；
- 每个 Task 使用独立 Conventional Commit，禁止 `git add .`；
- 每次任务同步 `docs/phase-status.md`，证据只记录真实运行结果；
- 遇到 API 与本计划不一致时，先重新 introspect，记录 ADR 后停止，不自造兼容层。

## 6. Task 0：建立 Phase 1-1 修复状态

### 修改

将 `docs/phase-status.md` 更新为：

- Phase: `1-1 — Phase 1 Behavioral Remediation`；
- Status: `in_progress`；
- Target Tag: `v0.0-deepagents-examples`，用户验收后创建；
- Phase 1 Task 8 保持 `in_progress`，不得提前 completed；
- Blockers 列出 evidence、interrupt、backend/store/memory、middleware/skills；
- Next Step 指向 Task 1。

在 `docs/verification/phase-1-evidence.md` 中保留已有真实 Task 0 内容，新增“Phase 1-1 remediation started”段落。不得先写最终通过。

### 验证

    git status --short
    git tag --list v0.0-deepagents-examples
    git show --no-patch --oneline v0.0-foundation

预期：

- 工作树只包含当前计划文档或本任务文档修改；
- Phase 1 tag 不存在；
- foundation tag 仍指向 `9715255`。

### 提交

    git add docs/phase-status.md docs/verification/phase-1-evidence.md
    git commit -m "docs: start phase one behavioral remediation"

## 7. Task 1：补全 interrupt、审批和恢复行为

### 7.1 目标接口

保留：

    build_graph_with_interrupt()

重构运行入口为可测试接口：

    def start_interrupt_flow(
        graph,
        *,
        thread_id: str,
        side_effects: list[str],
    ) -> dict:
        ...

    def resume_interrupt_flow(
        graph,
        *,
        thread_id: str,
        approved: bool,
    ) -> dict:
        ...

    def run_interrupt_flow(
        approve: bool,
        *,
        thread_id: str | None = None,
    ) -> dict:
        ...

允许根据 LangGraph真实返回结构轻微调整返回类型，但必须在函数 docstring 和测试中固定。

### 7.2 副作用模型

风险动作不得删除真实文件。使用注入的 `side_effects: list[str]` 作为可观测副作用记录；批准时只能追加一次：

    execute:delete_old_checkpoints

拒绝时不得追加。

### 7.3 必须先写的失败测试

创建 `tests/examples/phase1/test_interrupt_resume.py`：

1. `test_first_run_exposes_interrupt_payload`：断言 action、reason、risk_level；
2. `test_approve_executes_risk_action_once`；
3. `test_reject_does_not_execute_risk_action`；
4. `test_different_thread_ids_are_isolated`；
5. `test_repeated_resume_does_not_duplicate_side_effect`；
6. `test_flow_runs_without_model_api_key`。

先运行：

    .venv/bin/python -m pytest tests/examples/phase1/test_interrupt_resume.py -q

必须看到因缺少接口或行为而失败，而不是语法/导入错误。

### 7.4 实现约束

- 使用 `MemorySaver`；
- 首次执行必须实际生成 LangGraph interrupt；
- 使用 `Command(resume={"approved": ...})` 恢复；
- thread_id 由调用者传入，测试不得依赖随机 UUID；
- 相同 thread 的重复 resume 必须返回已完成状态或 no-op，不能再次产生副作用；
- 此示例不需要 MODEL_API_KEY，因为没有模型调用；`main()` 不得人为要求 Key。

### 7.5 验证与提交

    .venv/bin/python -m pytest tests/examples/phase1/test_interrupt_resume.py -q
    .venv/bin/ruff check examples/phase1/05_interrupt_resume.py tests/examples/phase1/test_interrupt_resume.py

提交：

    git commit -m "test: verify phase one interrupt behavior"

## 8. Task 2：真实 Backend、Store 和 Memory

### 8.1 目标接口

在 `06_backend_store_memory.py` 中提供：

    def create_filesystem_backend(root: Path) -> FilesystemBackend
    def write_research_note(backend: FilesystemBackend, path: str, content: str) -> None
    def read_research_note(backend: FilesystemBackend, path: str) -> str
    def create_store() -> InMemoryStore
    def put_thread_memory(store, *, thread_id: str, key: str, value: dict) -> None
    def get_thread_memory(store, *, thread_id: str, key: str) -> dict | None
    def create_memory_middleware(backend, *, source: str) -> MemoryMiddleware

函数名必须保持一致，方便 DeepSeek 之外的验收者直接测试。

### 8.2 Backend 行为

使用：

    FilesystemBackend(root_dir=root, virtual_mode=True)

所有示例路径使用虚拟绝对路径，例如：

    /notes/research.md
    /memory/thread-a/AGENTS.md

禁止直接用 pathlib 完成示例读写。pathlib 只允许创建 tmp root 和准备测试 fixture。

### 8.3 Store 与 Memory 边界

Store namespace 固定：

    ("phase1", "threads", thread_id)

Memory source 固定在每个 thread 的虚拟路径：

    /memory/{thread_id}/AGENTS.md

同一 thread 的第二次读取必须看到第一次写入；thread-a 不得读取 thread-b 的 store value 或 memory 文件。

### 8.4 必须先写的失败测试

创建 `tests/examples/phase1/test_backend_store_memory.py`：

1. backend 使用真实 `FilesystemBackend`；
2. 写入和读取受限 root 内文件；
3. `../outside.txt`、虚拟根逃逸或等价路径被拒绝；
4. 两个 store namespace 不串数据；
5. 同 thread 的 memory 内容连续可见；
6. 不同 thread 的 memory 内容隔离；
7. `create_memory_middleware` 返回真实 `MemoryMiddleware`；
8. tmp_path 生命周期结束后不留下仓库文件；
9. 所有行为无需 MODEL_API_KEY。

先运行并记录 RED：

    .venv/bin/python -m pytest tests/examples/phase1/test_backend_store_memory.py -q

### 8.5 main 行为

`main()` 使用 `TemporaryDirectory` 执行一次 backend/store/memory 演示并输出结构化摘要。它不调用模型，因此不得要求 MODEL_API_KEY。Runner 可以为此类离线示例增加“无需 Key”的明确 allowlist，但不得改变 invoke/stream 的 exit 3 契约。

### 8.6 验证与提交

    .venv/bin/python -m pytest tests/examples/phase1/test_backend_store_memory.py -q
    .venv/bin/python -m examples.phase1.runner backend-store-memory

预期 runner exit 0，无 Key 也可运行。

提交：

    git commit -m "feat: implement real backend store and memory examples"

## 9. Task 3：可观测 Middleware 与真实 Skills 加载

### 9.1 结构化事件

在 `07_middleware_skills.py` 中提供：

    @dataclass(frozen=True)
    class MiddlewareEvent:
        request_id: str
        phase: str
        model_name: str
        input_message_count: int
        output_message_count: int | None
        duration_ms: float | None
        error_type: str | None

    class RecordingMiddleware(AgentMiddleware):
        ...

    def build_recording_middleware(
        *,
        events: list[MiddlewareEvent],
        clock: Callable[[], float],
        request_id_factory: Callable[[], str],
    ) -> RecordingMiddleware:
        ...

### 9.2 wrap_model_call 行为

使用 `wrap_model_call(request, handler)`：

1. 调用 handler 前记录起始时间；
2. 调用 handler；
3. 成功后追加一条 phase=completed 事件；
4. 异常时追加一条 phase=failed 事件，然后原样重新抛出；
5. duration_ms = (end - start) * 1000；
6. model_name 只取安全模型标识；
7. 不在事件中存 messages 内容、system prompt、API Key、response 文本。

### 9.3 Skills 加载

提供：

    def create_skills_middleware(root: Path) -> SkillsMiddleware
    def list_loaded_skill_names(middleware: SkillsMiddleware) -> list[str]

使用真实 `FilesystemBackend` 和 `SkillsMiddleware`。skill source 路径必须与当前 API 所需格式一致，必须从 middleware 的已加载元数据或实际 before_model 结果证明 `source-review` 可用。

若 0.6.12 没有公开的直接列表方法：

1. introspect middleware 实例；
2. 通过其真实 `before_model` 输出或系统提示中的技能清单断言；
3. 在 ADR 记录采用的公开/稳定程度；
4. 不得退化为仅 `os.listdir`。

### 9.4 必须先写的失败测试

创建 `tests/examples/phase1/test_middleware_skills.py`：

1. 成功调用记录 request_id、model、输入/输出数量和 duration；
2. deterministic clock 得到精确 duration；
3. handler 异常记录 error_type 并重新抛出；
4. Prompt、Key、完整响应不出现在事件 `repr` 或日志；
5. request_id_factory 的值被使用；
6. `source-review` 由真实 SkillsMiddleware 加载；
7. 缺失或非法 SKILL.md 产生明确错误/警告；
8. 示例无需真实模型和 API Key。

先运行 RED：

    .venv/bin/python -m pytest tests/examples/phase1/test_middleware_skills.py -q

### 9.5 main 与提交

`main()` 使用 fake handler/fixture 演示 middleware，不调用真实模型，不要求 Key。输出只能包含安全元数据和已发现 skill 名称。

提交：

    git commit -m "feat: add observable middleware and real skills loading"

## 10. Task 4：补强导入与 Runner 测试

修正已有弱测试：

- 删除 `path.exists() or True`，必须真实存在；
- 删除空的 `test_runner_import_does_not_connect: pass`；
- 使用 monkeypatch/socket guard 或等价方式证明 import 不发起连接；
- 离线示例 `interrupt-resume`、`backend-store-memory`、`middleware-skills` 在无 Key 时 exit 0；
- 模型示例 `invoke`、`stream` 在无 Key时仍 exit 3；
- 字典式/Runnable 示例是否需要 Key以实际调用为准，不得伪造离线成功。

运行：

    .venv/bin/python -m pytest tests/examples/phase1 -q
    .venv/bin/python -m examples.phase1.runner interrupt-resume
    .venv/bin/python -m examples.phase1.runner backend-store-memory
    .venv/bin/python -m examples.phase1.runner middleware-skills

提交：

    git commit -m "test: strengthen phase one example contracts"

## 11. Task 5：完整证据、状态和最终门禁

### 11.1 Evidence 必须包含

完整重写 `docs/verification/phase-1-evidence.md`，至少包含：

1. OS、Python、uv 和日期；
2. foundation tag 和当前 HEAD；
3. 精确依赖版本；
4. `create_deep_agent` 和相关 API introspection 摘要；
5. Task 0-8 及 Phase 1-1 Task 0-5 的 commit SHA；
6. 七个示例的离线/真实模型状态；
7. interrupt 六项行为结果；
8. backend/store/memory 九项行为结果；
9. middleware/skills 八项行为结果；
10. 完整测试通过数和 skip 数；
11. integration skip 原因；
12. runner exit code；
13. Ruff、format、pre-commit、detect-secrets；
14. Phase 2 禁止范围扫描；
15. git status；
16. 已知限制和未执行项。

不得声称真实 smoke 已通过。`2 skipped` 必须明确归因于没有 `MODEL_API_KEY`。

### 11.2 最终命令

    git status --short
    uv sync --extra dev --frozen
    .venv/bin/python -m pytest tests/ -q
    .venv/bin/python -m pytest tests/integration/phase1 -q
    .venv/bin/ruff check app examples tests scripts
    .venv/bin/ruff format --check app examples tests scripts
    .venv/bin/pre-commit run --all-files
    .venv/bin/detect-secrets scan --baseline .secrets.baseline
    .venv/bin/python -m examples.phase1.runner --list
    env -u MODEL_API_KEY .venv/bin/python -m examples.phase1.runner invoke
    env -u MODEL_API_KEY .venv/bin/python -m examples.phase1.runner interrupt-resume
    env -u MODEL_API_KEY .venv/bin/python -m examples.phase1.runner backend-store-memory
    env -u MODEL_API_KEY .venv/bin/python -m examples.phase1.runner middleware-skills
    rg -n "Tavily|RAGFlow|WebSocket|drug|medicine" app examples tests
    git diff --check

预期：

- 全套测试 exit 0；
- integration 为 2 skipped，exit 0；
- invoke 无 Key exit 3；
- 三个离线示例无 Key exit 0；
- forbidden scope 无业务实现；文档中的术语说明不算实现，但必须人工复核；
- pre-commit 第二次运行 exit 0；
- detect-secrets 不留下 baseline 时间戳脏改动；
- 最终 Git clean。

### 11.3 Phase status

最终才允许：

- Phase 1 Task 8 = completed；
- commit 填写本任务最终 evidence 提交 SHA；
- Current Phase = 1；
- Status = awaiting_user_acceptance；
- Blockers = None；
- Next Steps = 用户验收后创建 tag；未授权不得 Phase 2。

注意：如果同一个 commit 无法在提交前写入自身 SHA，可先提交 evidence，再使用第二个文档 commit 回填真实 SHA。不得写 TBD 或错误 SHA。

### 11.4 提交

    git commit -m "docs: finalize phase one behavioral evidence"

如需回填 SHA：

    git commit -m "docs: record phase one final task sha"

不得创建 `v0.0-deepagents-examples`。

## 12. Phase 1-1 验收清单

- [ ] evidence 不再只有 Task 0；
- [ ] phase-status Task 8 completed 且 SHA 真实；
- [ ] interrupt 首次暂停 payload 正确；
- [ ] approve 只执行一次副作用；
- [ ] reject 不执行副作用；
- [ ] thread 隔离通过；
- [ ] 重复 resume 幂等；
- [ ] 使用真实 FilesystemBackend；
- [ ] backend 路径逃逸被拒绝；
- [ ] store namespace 隔离；
- [ ] MemoryMiddleware 真实构造并使用文件 source；
- [ ] memory thread 隔离；
- [ ] RecordingMiddleware 记录安全元数据；
- [ ] duration 使用 deterministic clock 验证；
- [ ] handler error 被记录并重新抛出；
- [ ] Prompt/Key/response 不泄露；
- [ ] SkillsMiddleware 实际加载 source-review；
- [ ] 弱测试已替换为有效断言；
- [ ] 真实模型 smoke 诚实记录为 skip；
- [ ] Phase 2 禁止范围未实现；
- [ ] git status clean；
- [ ] 未创建 Phase 1 tag；
- [ ] 未开始 Phase 2。

## 13. DeepSeek 停止条件

出现以下任一情况立即停止并记录 blocker：

- DeepAgents 0.6.12 API 与本计划的 introspection 结果不一致；
- 需要升级依赖才能实现；
- SkillsMiddleware 无法通过任何真实公开行为证明 skill 被加载；
- backend 路径逃逸行为与预期不同且需要更改安全边界；
- 幂等 resume 无法在不新增生产持久化的情况下实现；
- 需要修改 app、前端、数据库或 Phase 2 目录；
- 测试需要真实模型才能运行；
- pre-commit 或 secrets scan 无法通过。

