# Phase 2-n Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans. Execute tasks in order. Do not begin Phase 3 or Task 3 until the final gate is green.

**Goal:** 完成 Phase 2 Tasks 0-2 remediation 的剩余合同缺口，并用真实 RED/GREEN 证据重新验收。

**Architecture:** 保持现有 InMemoryEventBus、工具工厂、MySQL provider 和 subagent builder 的模块边界，不引入新的事件抽象或运行时。工具在应用事件循环中读取 LangChain 注入的 RunnableConfig.configurable.thread_id；provider worker 只执行阻塞调用；事件 payload 使用递归 JSON 类型；所有安全上限集中为明确常量。

**Tech Stack:** Python 3.12, LangChain Core 1.5.1, Pydantic 2, pytest/pytest-asyncio, sqlglot 29, Ruff, pre-commit, Docker Compose/MySQL 8.0.

## Global Constraints

- 本计划只修复 Tasks 0-2；不得创建或修改 Task 3-7 的运行时代码、前端、FastAPI、WebSocket、workspace 或 report 模块。
- 工具合同覆盖七个工具：internet_search、list_sql_tables、describe_table、preview_table、execute_readonly_query、list_knowledge_assistants、ask_knowledge_assistant。
- 每次工具调用必须在应用 event loop 发出一对 tool_started/tool_completed 事件；thread_id 只能来自 RunnableConfig.configurable.thread_id，禁止 UNKNOWN 或默认线程。
- provider 阻塞方法只能通过 asyncio.to_thread 调用；worker thread 不得调用 event bus。
- TutorialEvent.data 和 InMemoryEventBus.emit 的 data 参数必须使用递归 JsonValue，拒绝任意对象、bytes、set、tuple、非字符串 dict key 和嵌套非法值。
- preview_table 与 execute_readonly 的 limit 均钳制到 1..100；不得出现 1000。
- MySQL provider 仍只能使用 tutorial_reader；不得放宽 root 或其他账号。
- 不得运行 detect-secrets scan --baseline，不得重生成 .secrets.baseline。新增假密钥使用现有 allowlist 注释。
- 不得把未执行的测试写入 GREEN 证据。每个任务先写失败测试，再写最小实现，再运行测试；每个任务提交一个小 Conventional Commit。

---

### Task 0: Freeze Remediation Scope and Evidence Baseline

**Files**

- Modify: docs/phase-status.md
- Modify: docs/verification/phase-2-evidence.md
- Restore without regeneration: .secrets.baseline

**Interfaces**

- Consumes: current rejection at c5f32ca, fixed point c6c0fa8, this plan.
- Produces: status that marks R2-n in progress and evidence that removes unsupported GREEN claims.

- [ ] Add a status row after F2:

~~~markdown
| R2-n | RED: tool/event/limit/evidence gaps | in_progress | — | Acceptance rejected at c5f32ca; Task 3 blocked |
~~~

Change Blockers from None to the exact five blockers: tool thread/event contract, recursive JsonValue, real overflow test, execute limit 100, and evidence/baseline correction.

- [ ] Replace the Round 2 GREEN summary with:

~~~markdown
Round 2 provider fixes pass their current tests, but acceptance is rejected:
tool event routing, recursive JsonValue validation, overflow isolation, and
execute limit 1..100 are not yet proven. Task 3 remains blocked.
~~~

Do not call the current 149-test result a Phase 2 acceptance.

- [ ] Restore .secrets.baseline to the accepted pre-remediation content by comparing it with the fixed point. Do not run any baseline scan.

~~~bash
git diff -- .secrets.baseline
~~~

Expected: no baseline diff before implementation commits.

- [ ] Commit:

~~~bash
git add docs/phase-status.md docs/verification/phase-2-evidence.md .secrets.baseline
git commit -m "docs: record phase two remediation rejection"
~~~

---

### Task 1: Thread-Aware Paired Events for All Seven Tools

**Files**

- Modify: app/tools/web.py
- Modify: app/tools/catalog.py
- Modify: app/tools/knowledge.py
- Create: tests/unit/phase2/test_tool_events.py

**Interfaces**

- Consumes: InMemoryEventBus.emit, provider Protocols, LangChain @tool wrappers.
- Produces: three factories whose async tools accept LangChain-injected RunnableConfig.

- [ ] Write async RED tests with deterministic fake providers. Invoke every returned tool with config={"configurable": {"thread_id": "thread-42"}}. Subscribe to thread-42 and assert exactly one start and one completion event per call, both carrying thread-42. Subscribe to other-thread and assert it receives no event.

~~~python
@pytest.mark.asyncio
async def test_all_tools_emit_paired_events_with_config_thread_id():
    # Build fake providers and all seven tools.
    # Invoke each tool with the RunnableConfig above.
    # Assert event types, thread ids, and cross-thread isolation.
    ...
~~~

- [ ] Run RED:

~~~bash
.venv/bin/python -m pytest tests/unit/phase2/test_tool_events.py -q
~~~

Expected: failure because web uses UNKNOWN, catalog emits nothing, and knowledge does not accept events.

- [ ] Implement the minimal contract. Use a LangChain-compatible parameter:

~~~python
from langchain_core.runnables import RunnableConfig

def _thread_id(config: RunnableConfig) -> str:
    thread_id = config.get("configurable", {}).get("thread_id")
    if not isinstance(thread_id, str) or not thread_id:
        raise ValueError("RunnableConfig.configurable.thread_id is required")
    return thread_id
~~~

Each @tool function includes config: RunnableConfig, calls _thread_id(config), emits start before asyncio.to_thread, and emits completion after the provider returns. Event data contains only stable metadata such as {"tool_name": "..."}. Never include query text, result rows, credentials, or exception bodies. Event bus calls remain on the event-loop side of the to_thread boundary.

- [ ] Run GREEN:

~~~bash
.venv/bin/python -m pytest tests/unit/phase2/test_tool_events.py tests/unit/phase2/test_events.py -q
~~~

- [ ] Commit:

~~~bash
git add app/tools tests/unit/phase2/test_tool_events.py
git commit -m "fix: route phase two tool events by runnable thread"
~~~

---

### Task 2: Enforce Recursive JsonValue at the Event Boundary

**Files**

- Modify: app/api/events.py
- Modify: tests/unit/phase2/test_events.py
- Modify: tests/unit/phase2/test_remediation_2.py

**Interfaces**

- Consumes: TutorialEvent and InMemoryEventBus.emit.
- Produces: recursive JSON-only validation at model/emit time.

- [ ] Add RED parametrized cases for object(), bytes, set, tuple, a dict with a non-string key, and nested invalid values. Also assert valid None, booleans, integers, floats, strings, lists, and nested string-keyed dictionaries.

~~~python
@pytest.mark.parametrize("bad", [object(), b"x", {"x"}, ("x",), {1: "bad"}])
def test_event_data_rejects_non_json_values(bad):
    bus = InMemoryEventBus()
    with pytest.raises((TypeError, ValueError, ValidationError)):
        bus.emit("thread-42", "task_started", "start", {"bad": bad})
~~~

- [ ] Run RED:

~~~bash
.venv/bin/python -m pytest tests/unit/phase2/test_events.py tests/unit/phase2/test_remediation_2.py -q
~~~

- [ ] Replace dict[str, Any] with one recursive JsonValue alias used by TutorialEvent.data and InMemoryEventBus.emit. Use strict validation where Pydantic would coerce tuples, sets, or arbitrary objects. Preserve the existing event schema and sequence behavior.

- [ ] Run GREEN:

~~~bash
.venv/bin/python -m pytest tests/unit/phase2/test_events.py tests/unit/phase2/test_remediation_2.py -q
~~~

- [ ] Commit:

~~~bash
git add app/api/events.py tests/unit/phase2/test_events.py tests/unit/phase2/test_remediation_2.py
git commit -m "fix: enforce recursive json event payloads"
~~~

---

### Task 3: Prove Subscriber Overflow Isolation

**Files**

- Modify: app/api/events.py only if the test exposes a bug
- Modify: tests/unit/phase2/test_events.py
- Modify: tests/unit/phase2/test_remediation_2.py

- [ ] Replace the placeholder overflow test. Subscribe two consumers to one thread, emit exactly 257 events without draining either queue, assert only the full subscription is marked overflowed and removed, assert the second remains live and receives its events, then subscribe a fresh consumer and assert it receives only future events.

- [ ] Run:

~~~bash
.venv/bin/python -m pytest tests/unit/phase2/test_events.py::test_overflow_isolates_single_subscriber -q
~~~

Expected: RED if isolation is wrong; otherwise GREEN with explicit queue, removal, and overflow assertions.

- [ ] Commit:

~~~bash
git add tests/unit/phase2/test_events.py tests/unit/phase2/test_remediation_2.py app/api/events.py
git commit -m "test: prove event subscriber overflow isolation"
~~~

---

### Task 4: Clamp Every SQL Result to 100

**Files**

- Modify: app/providers/mysql.py
- Modify: tests/unit/phase2/test_sql_policy.py
- Modify: tests/unit/phase2/test_remediation_2.py

- [ ] Write a provider-level RED test with a fake connection/cursor. Call execute_readonly("SELECT * FROM drugs", limit=999) and assert captured SQL contains LIMIT 100. Add limit=0 coverage for LIMIT 1.

- [ ] Run RED:

~~~bash
.venv/bin/python -m pytest tests/unit/phase2/test_sql_policy.py tests/unit/phase2/test_remediation_2.py -q
~~~

- [ ] Implement one helper and reuse its result:

~~~python
def _clamp_limit(limit: int) -> int:
    return max(1, min(limit, 100))
~~~

Remove duplicated max/min expressions and every 1000 literal. Use the clamped value in SQL and truncated calculation.

- [ ] Run GREEN and commit:

~~~bash
.venv/bin/python -m pytest tests/unit/phase2/test_sql_policy.py tests/unit/phase2/test_remediation_2.py -q
git add app/providers/mysql.py tests/unit/phase2/test_sql_policy.py tests/unit/phase2/test_remediation_2.py
git commit -m "fix: cap phase two sql results at one hundred"
~~~

---

### Task 5: Assert Exact Subagent Tool Sets

**Files**

- Modify: app/agent/subagents.py only if tests expose a defect
- Modify: tests/unit/phase2/test_subagents.py
- Modify: tests/unit/phase2/test_remediation_2.py

- [ ] Pass uniquely named fake callables for all seven tools. Assert ordered names web-research, structured-data, knowledge-base; exact descriptions and system prompts; exact domain-specific tool lists; no cross-domain tool; every item callable or a LangChain BaseTool.

- [ ] Run and commit:

~~~bash
.venv/bin/python -m pytest tests/unit/phase2/test_subagents.py tests/unit/phase2/test_remediation_2.py -q
git add app/agent/subagents.py tests/unit/phase2/test_subagents.py tests/unit/phase2/test_remediation_2.py
git commit -m "test: lock tutorial subagent tool sets"
~~~

---

### Task 6: Full Acceptance Gate and Honest Evidence

**Files**

- Modify: docs/phase-status.md
- Modify: docs/verification/phase-2-evidence.md
- Do not modify: Phase 3 files or frontend files

- [ ] Run every gate:

~~~bash
.venv/bin/python -m pytest tests/ -q
.venv/bin/python -m pytest tests/unit/phase2 tests/integration/phase2 -q
.venv/bin/ruff check app tests docker
.venv/bin/ruff format --check app tests
.venv/bin/pre-commit run --all-files
docker compose config
git diff --check
PHASE2_MYSQL_INTEGRATION=1 .venv/bin/python -m pytest tests/integration/phase2/test_mysql_provider.py -q
~~~

Run the MySQL command outside the sandbox if local port 3307 is inaccessible inside the sandbox. Record that fact, not a fake skip.

- [ ] Direct contract scan:

~~~bash
rg -n "UNKNOWN|1000|dict\\[str, Any\\]|pass  # will be implemented|detect-secrets scan" app tests docs .secrets.baseline
git status --short --branch
~~~

Expected: no production UNKNOWN, no 1000 SQL cap, no dict[str, Any] event payload, no placeholder test, and no regenerated-baseline claim.

- [ ] Update evidence only from observed output. Mark R2-n accepted only if every command exits 0 and the direct scan is clean. Otherwise keep Task 3 blocked and record the exact failure. Never create a Phase 2 release tag.

- [ ] Commit:

~~~bash
git add docs/phase-status.md docs/verification/phase-2-evidence.md
git commit -m "docs: close phase two remediation evidence"
~~~

## Acceptance Checklist

- [ ] All seven tools use RunnableConfig.configurable.thread_id.
- [ ] All seven tools emit paired events on the application loop.
- [ ] Cross-thread event isolation is tested.
- [ ] Recursive JSON validation rejects invalid values before serialization.
- [ ] Overflow test fills the 256 queue and proves single-subscriber isolation.
- [ ] Preview and execute limits are exactly 1..100.
- [ ] Subagent names, prompts, and exact tool sets are tested.
- [ ] .secrets.baseline was not regenerated.
- [ ] Full tests, targeted tests, Ruff, format, pre-commit, Compose, MySQL integration, and diff checks are green.
- [ ] Evidence matches observed output.
- [ ] Task 3 remains blocked until this checklist is complete.

## Handoff

Read this file completely before editing. Execute Tasks 0-6 in order and report each commit SHA plus exact command output. Stop immediately on any contract or infrastructure failure. This document does not authorize Task 3; Task 3 requires a separate acceptance.
