# Phase 2-n2 Residual Remediation Plan

> **Historical remediation plan:** archived context for earlier Phase 2 review.

> Read completely before editing. Execute tasks in order with RED -> GREEN evidence. This plan does not authorize Task 3.

**Goal:** 修复 Phase 2-n 验收剩余的类型、假绿测试、subagent 合同和证据缺口。

**Scope:** 只修改事件类型、Phase 2 测试和 Phase 2 证据文档。禁止修改 Task 3-7 运行时代码、前端、FastAPI、WebSocket、workspace、report 或发布 tag。

## Task 1: Recursive Event Type

Files:

- Modify: app/api/events.py
- Modify: tests/unit/phase2/test_events.py

Requirements:

- Keep one recursive JsonValue alias:

~~~python
JsonValue = (
    None
    | bool
    | int
    | float
    | str
    | list["JsonValue"]
    | dict[str, "JsonValue"]
)
~~~

- Type TutorialEvent.data as dict[str, JsonValue].
- Type InMemoryEventBus.emit data as dict[str, JsonValue] | None.
- Keep the runtime validator so invalid values fail before event construction.
- Do not leave dict[str, Any] in either public event data declaration.
- Add an annotation regression test using typing.get_type_hints; assert the public annotations reference JsonValue and are not dict[str, Any].
- Keep negative tests for object(), bytes, set, tuple, non-string dict keys, and nested invalid values.

Run RED before implementation and GREEN after:

~~~bash
.venv/bin/python -m pytest tests/unit/phase2/test_events.py -q
.venv/bin/ruff check app/api/events.py tests/unit/phase2/test_events.py
.venv/bin/ruff format --check app/api/events.py tests/unit/phase2/test_events.py
~~~

Commit:

~~~bash
git add app/api/events.py tests/unit/phase2/test_events.py
git commit -m "fix: expose recursive json event annotations"
~~~

## Task 2: Delete False-Green Tests and Strengthen Real Tests

Files:

- Modify: tests/unit/phase2/test_remediation_2.py
- Modify: tests/unit/phase2/test_events.py
- Modify: tests/unit/phase2/test_sql_policy.py

Delete these obsolete methods from test_remediation_2.py:

- TestToolsUseConfigThreadId.test_tool_uses_config_thread_id
- TestEventBusOverflow.test_overflow_isolates_single_subscriber
- TestExecuteReadonlyLimits.test_limit_clamped_to_max_100

Do not leave pass, will-be-implemented comments, or tests that only inspect an initial overflow flag.

Strengthen the real overflow test in test_events.py:

- subscribe sub_a and sub_b to one thread;
- drain sub_a on every emission;
- emit 257 events;
- assert sub_a is not overflowed;
- assert sub_b is overflowed and removed from the bus subscription list;
- subscribe sub_c and assert it receives only a future event.

Add a provider-level SQL capture test:

- call MySQLCatalogProvider.execute_readonly with limit=999 and assert generated SQL contains LIMIT 100;
- call it with limit=0 and assert generated SQL contains LIMIT 1;
- use a fake connection/cursor; do not test only validate_readonly_query.

Run:

~~~bash
.venv/bin/python -m pytest tests/unit/phase2/test_remediation_2.py tests/unit/phase2/test_events.py tests/unit/phase2/test_tool_events.py tests/unit/phase2/test_sql_policy.py -q
rg -n "pass  # will be implemented|Actually the queue is fixed|test_limit_clamped_to_max_100" tests/unit/phase2
~~~

Expected: tests pass and the scan returns no matches.

Commit:

~~~bash
git add tests/unit/phase2/test_remediation_2.py tests/unit/phase2/test_events.py tests/unit/phase2/test_tool_events.py tests/unit/phase2/test_sql_policy.py
git commit -m "test: remove phase two false green remediation cases"
~~~

## Task 3: Exact Subagent Contracts

Files:

- Modify: tests/unit/phase2/test_subagents.py
- Modify: tests/unit/phase2/test_remediation_2.py only for duplicate weak assertions
- Modify: app/agent/subagents.py only if tests fail

Pass seven uniquely named fake tools and assert:

- exact ordered names: web-research, structured-data, knowledge-base;
- exact descriptions and system prompts;
- web tools only in web-research;
- four catalog tools only in structured-data;
- two knowledge tools only in knowledge-base;
- every item is callable or a LangChain BaseTool;
- no tool appears in another domain.

Explicitly assert the prompt contains internet_search, execute_readonly_query, and ask_knowledge_assistant respectively.

Run and commit:

~~~bash
.venv/bin/python -m pytest tests/unit/phase2/test_subagents.py tests/unit/phase2/test_remediation_2.py -q
git add tests/unit/phase2/test_subagents.py tests/unit/phase2/test_remediation_2.py app/agent/subagents.py
git commit -m "test: assert exact tutorial subagent contracts"
~~~

## Task 4: Honest Evidence

Files:

- Modify: docs/phase-status.md
- Modify: docs/verification/phase-2-evidence.md
- Do not modify: .secrets.baseline

Remove every claim that the baseline was regenerated. Record only:

~~~markdown
- .secrets.baseline unchanged from the accepted fixed point.
- .venv/bin/pre-commit run --all-files passed without mutating the baseline.
~~~

Replace the stale Round 2 GREEN prose with a table containing the exact observed command, exit status, and counts for:

- full pytest;
- Phase 2 pytest;
- MySQL integration;
- Ruff and format;
- pre-commit;
- Docker Compose config;
- git diff --check.

Keep Task 3 blocked until all gates and scans are green. Do not create v0.1-tutorial-parity.

Final scans:

~~~bash
rg -n "dict\\[str, Any\\]|pass  # will be implemented|Actually the queue is fixed|baseline regenerated|1000" app tests docs
git diff -- .secrets.baseline
git status --short --branch
~~~

Expected: no forbidden matches, no baseline diff, and only intended plan files untracked.

Commit:

~~~bash
git add docs/phase-status.md docs/verification/phase-2-evidence.md
git commit -m "docs: reconcile phase two remediation evidence"
~~~

## Final Gate

~~~bash
.venv/bin/python -m pytest tests/ -q
.venv/bin/ruff check app tests docker
.venv/bin/ruff format --check app tests
.venv/bin/pre-commit run --all-files
docker compose config
git diff --check
PHASE2_MYSQL_INTEGRATION=1 .venv/bin/python -m pytest tests/integration/phase2/test_mysql_provider.py -q
~~~

Acceptance requires every command to exit 0, the scans to be clean, evidence to match output, and no Task 3 code or tag to exist.
