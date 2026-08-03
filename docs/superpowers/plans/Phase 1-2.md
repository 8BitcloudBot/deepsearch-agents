# Phase 1-2 SkillsMiddleware 真实加载与证据修复实施计划

> **Historical remediation plan:** archived context for the accepted Phase 1 release.

> **For agentic workers:** 必须逐项执行本计划。推荐使用 `superpowers:executing-plans`；每个步骤使用复选框跟踪。不得自行扩展需求、创建 Phase 1 tag 或开始 Phase 2。

**目标：** 将 Phase 1-1 中基于 `Path.iterdir()` 的伪 Skills 发现替换为 DeepAgents 0.6.12 `SkillsMiddleware.before_agent()` 的真实加载链路，并以行为测试证明 YAML frontmatter 解析、校验、一次加载和系统提示注入。

**架构：** 保留现有 `FilesystemBackend` 与 `SkillsMiddleware` 工厂，通过公开中间件生命周期加载 `SkillMetadata`；示例和测试只消费中间件返回的结构化元数据，不直接扫描目录。所有测试离线运行，不调用模型和网络。

**技术栈：** Python 3.12、deepagents 0.6.12、langgraph 1.2.9、langchain 1.3.14、langchain-core 1.5.1、pytest、ruff、pre-commit、detect-secrets。

## 0. 执行前基线与前提

本计划的执行起点是：Phase 1-1 的 `RecordingMiddleware`、interrupt/resume、FilesystemBackend、InMemoryStore 和 MemoryMiddleware 行为已通过其既定验收；本阶段不得重复重构这些能力。当时仓库中的 Skills 示例仍通过目录存在性判断来输出名称，且教学 `SKILL.md` 缺少 DeepAgents 所需的 YAML frontmatter，因此不能把“发现文件”当成“middleware 成功加载”。

执行者必须先核对当前工作树和 `git log`，以实际代码为准；若 Phase 1-1 尚未完成、存在用户未提交改动冲突，或 DeepAgents 版本/API 与本文不一致，应记录 blocker 并停止，不得擅自升级依赖或扩大范围。

---

## 1. 修复背景与结论

Phase 1-1 的验收摘要声称已经使用真实 `SkillsMiddleware` 加载教学 skill，但当前实现并未完成该行为：

```python
def list_loaded_skill_names(middleware: SkillsMiddleware) -> list[str]:
    names: list[str] = []
    for src_path in middleware.sources:
        skill_dir = Path(src_path)
        if skill_dir.is_dir():
            for entry in skill_dir.iterdir():
                if (entry / "SKILL.md").exists():
                    names.append(entry.name)
    return sorted(set(names))
```

这段代码只证明文件存在，没有证明 DeepAgents 能解析或接受该 skill。当前 `examples/phase1/skills/source-review/SKILL.md` 也缺少 DeepAgents 0.6.12 要求的 YAML frontmatter，真实加载会跳过它。

Phase 1-2 是 Phase 1 的第二次窄范围修复，只处理 SkillsMiddleware 及相关证据。完成后仍处于 `awaiting_user_acceptance`，不得创建 `v0.0-deepagents-examples`，不得开始 Phase 2。

## 2. 固定范围

### 2.1 必须修改

```text
examples/phase1/_07_middleware_skills.py
examples/phase1/07_middleware_skills.py
examples/phase1/skills/source-review/SKILL.md
tests/examples/phase1/test_middleware_skills.py
examples/phase1/README.md
docs/phase-status.md
docs/verification/phase-1-evidence.md
docs/adr/0002-deepagents-version-and-api-surface.md
CHANGELOG.md
```

### 2.2 仅在内容确实受影响时修改

```text
README.md
.secrets.baseline
```

`.secrets.baseline` 只允许由合法 hook 结果更新。若 `detect-secrets scan --baseline` 仅改变 `generated_at` 时间戳，则恢复该无意义变更，不得提交。

### 2.3 禁止修改

```text
pyproject.toml
uv.lock
examples/phase1/runner.py
examples/phase1/settings.py
examples/phase1/_05_interrupt_resume.py
examples/phase1/_06_backend_store_memory.py
tests/examples/phase1/test_interrupt_resume.py
tests/examples/phase1/test_backend_store_memory.py
tests/integration/phase1/
app/
frontend/
docker-compose.yml
```

如真实 API 与本计划记录不一致，先记录准确 introspection 输出和 blocker，停止实现并等待用户决定；不得升级依赖、重写框架能力或自造兼容层。

## 3. 全局执行约束

- [ ] 严格按 Task 0 到 Task 5 顺序执行。
- [ ] 先写失败测试并记录 RED，再写最小实现并记录 GREEN。
- [ ] 不得删除、放宽、skip 或 xfail 现有测试来换取通过。
- [ ] 不得 mock、monkeypatch 或替换 `SkillsMiddleware.before_agent()`。
- [ ] 不得调用 DeepAgents 的私有 `_list_skills*` 或 `_parse_skill_metadata` 作为项目实现。
- [ ] 不得使用 `Path.iterdir()`、`Path.glob()`、`Path.rglob()`、`os.listdir()`、`glob.glob()` 或类似直接扫描作为 skill 加载证明。
- [ ] 测试 fixture 可以用 `tmp_path` 创建目录和写入 `SKILL.md`，但加载和发现必须经过 `SkillsMiddleware`。
- [ ] 示例、测试和证据不得要求 `MODEL_API_KEY`，不得访问模型、网络、MySQL、RAGFlow 或 Tavily。
- [ ] 输出只包含 skill 的安全字段 `name`、`description`，不得打印完整 skill 正文、Prompt、Key 或环境变量。
- [ ] 每个任务使用独立 Conventional Commit；禁止 `git add .`、`git add -A` 和通配符暂存。
- [ ] 每次提交前检查 `git diff --check` 与暂存文件清单。
- [ ] 文档只记录真实执行结果、真实退出码和真实 SHA，不得预填“通过”。
- [ ] 用户验收前不得创建或移动 `v0.0-deepagents-examples` tag。
- [ ] 不得编写或执行 Phase 2。

## 4. 已确认的 DeepAgents 0.6.12 公开 API

执行者仍须在本机重新 introspect，并将输出记录到 ADR/evidence；预期接口为：

```python
from deepagents.middleware.skills import SkillMetadata, SkillsMiddleware
from langgraph.runtime import Runtime

Runtime(
    *,
    context=None,
    store=None,
    stream_writer=...,
    heartbeat=...,
    previous=None,
    execution_info=None,
    server_info=None,
    control=None,
)

SkillsMiddleware.before_agent(
    self,
    state,
    runtime: Runtime,
    config,
) -> SkillsStateUpdate | None

SkillsMiddleware.modify_request(self, request: ModelRequest) -> ModelRequest
```

已确认行为：

1. `before_agent({}, Runtime(), {})` 通过配置的 backend/source 读取并解析 `SKILL.md`；
2. 成功结果位于 `update["skills_metadata"]`；
3. state 已存在 `skills_metadata` 键时返回 `None`，包括空列表；
4. YAML frontmatter 无效或缺失时，该 skill 被跳过并记录 warning；`name` 与父目录不匹配时，DeepAgents 0.6.12 会记录 warning 但仍加载该 skill，测试必须忠实验证这一实际行为；
5. source 本身不可读取时才可能返回 `skills_load_errors`；不得断言每个无效 skill 都一定出现在该字段；
6. `modify_request()` 读取 request state 的 `skills_metadata`，将名称、描述和路径注入 system message；不需要调用真实模型。

## 5. 固定目标接口

在 `examples/phase1/_07_middleware_skills.py` 保留现有 middleware 观测接口，只删除 `list_loaded_skill_names()`，新增：

```python
from deepagents.middleware.skills import SkillMetadata, SkillsMiddleware
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime


def load_skills_metadata(
    middleware: SkillsMiddleware,
    *,
    runtime: Runtime,
    config: RunnableConfig | None = None,
) -> list[SkillMetadata]:
    """Load parsed skill metadata through the public middleware lifecycle."""
    update = middleware.before_agent({}, runtime, config or {})
    if update is None:
        return []
    return list(update.get("skills_metadata", []))
```

约束：

- 函数名、参数名与返回类型必须保持一致；
- helper 不接受路径，不读取文件，不访问 `middleware.sources`；
- helper 只调用公开 `before_agent()`；
- `create_skills_middleware(root: Path) -> SkillsMiddleware` 保留；
- 示例与测试使用 `Runtime()` 的真实实例；
- 测试如需同时检查 `skills_load_errors`，直接调用 `before_agent()` 并断言完整 update，不要让 helper 隐藏该字段。

## 6. 固定 Skill fixture

将 `examples/phase1/skills/source-review/SKILL.md` 的开头改为以下精确 frontmatter；父目录名必须继续是 `source-review`：

```markdown
---
name: source-review
description: Reviews source materials for credibility and consistency when validating technical claims.
---

# Source Review
```

保留现有规则的有效内容，但统一标题大小写。不得添加 license、compatibility、metadata 或 allowed-tools，因为本阶段不需要验证这些可选字段。

测试中创建的合法 fixture 必须使用同样的 frontmatter 结构。写入文件时显式指定：

```python
skill_md.write_text(content, encoding="utf-8")
```

## 7. Task 0：建立 Phase 1-2 修复状态并重新确认 API

### 文件

- Modify: `docs/phase-status.md`
- Modify: `docs/verification/phase-1-evidence.md`
- Modify: `docs/adr/0002-deepagents-version-and-api-surface.md`

### 步骤

- [ ] **Step 1：确认起始状态**

运行：

```bash
git status --short
git tag --list v0.0-deepagents-examples
git show --no-patch --oneline v0.0-foundation
git log -8 --oneline
```

预期：工作树除本计划文档外为 clean；Phase 1 tag 不存在；foundation tag 仍存在。若存在其他改动，不得覆盖，先判断是否与本阶段冲突。

- [ ] **Step 2：重新 introspect 真实 API**

运行：

```bash
.venv/bin/python - <<'PY'
import inspect
from deepagents.middleware.skills import SkillsMiddleware
from langgraph.runtime import Runtime

print("Runtime", inspect.signature(Runtime))
print("before_agent", inspect.signature(SkillsMiddleware.before_agent))
print("modify_request", inspect.signature(SkillsMiddleware.modify_request))
PY
```

预期：签名与第 4 节兼容，且 `Runtime()` 可无参构造。

- [ ] **Step 3：更新状态与起始证据**

`docs/phase-status.md` 必须改为：

```text
Phase: 1-2 — SkillsMiddleware Loading Remediation
Status: in_progress
Target Tag: v0.0-deepagents-examples（用户验收通过后创建）
Next Step: Task 1 — add RED behavior tests
```

新增 Phase 1-2 Task 0-5 表，Task 0 完成，其余 pending。将 Phase 1-1 的 Skills 偏差明确改为“未完成真实加载，Phase 1-2 修复中”，不得继续写成“需要完整 LangGraph runtime”。

ADR 新增“Phase 1-2 API clarification”：记录 `Runtime()`、`before_agent()`、`modify_request()` 的真实签名和同步加载入口。Evidence 新增起始快照，不改写为最终通过。

- [ ] **Step 4：验证并提交**

```bash
git diff --check
git add docs/phase-status.md docs/verification/phase-1-evidence.md docs/adr/0002-deepagents-version-and-api-surface.md
git diff --cached --name-only
git commit -m "docs: start phase one skills remediation"
```

预期暂存清单只有上述 3 个文件。将真实 SHA 写入本地执行记录，后续在 Task 5 同步状态表。

## 8. Task 1：先建立会失败的真实加载行为测试

### 文件

- Modify: `tests/examples/phase1/test_middleware_skills.py`
- Test: `tests/examples/phase1/test_middleware_skills.py`

### 必须新增或替换的测试

保留现有 `TestRecordingMiddleware` 测试不变。用以下行为测试替换当前只调用 `list_loaded_skill_names()` 的 Skills 测试：

1. `test_before_agent_parses_source_review_metadata`
   - 创建合法 YAML frontmatter；
   - 使用真实 `SkillsMiddleware` 和真实 `Runtime()`；
   - 断言 `source-review` 被加载；
   - 断言 description 精确等于 frontmatter；
   - 断言 path 以 `/source-review/SKILL.md` 结尾。
2. `test_missing_frontmatter_skill_is_omitted_with_warning`
   - fixture 只有 Markdown 标题、没有 frontmatter；
   - 使用 `caplog.at_level(logging.WARNING)`；
   - 断言 metadata 为空；
   - 断言 warning 包含 `SKILL.md` 和 parse/validation/skip 语义之一。
3. `test_directory_name_mismatch_is_omitted_with_warning`
   - 父目录为 `source-review`，frontmatter name 为 `other-review`；
   - 断言 metadata 为空并产生 warning。
4. `test_empty_source_returns_empty_metadata`
   - 空目录；
   - 断言返回 `[]`，不得构造虚假名称。
5. `test_existing_skills_metadata_skips_reload`
   - 直接调用 `middleware.before_agent({"skills_metadata": []}, Runtime(), {})`；
   - 断言返回 `None`。
6. `test_modify_request_injects_loaded_skill_metadata`
   - 先真实加载 metadata；
   - 构造真实 `ModelRequest`，state 包含 metadata；
   - 使用 `SystemMessage(content="Base system prompt")`；
   - 调用 `modify_request()`；
   - 断言新 system message 同时包含 `source-review` 和精确 description；
   - 不调用 handler 或真实模型。
7. `test_project_skill_fixture_is_parseable`
   - 直接以项目 `examples/phase1/skills` 为 source 构造 middleware；
   - 断言仓库内真实 fixture 被解析，而不是只测试临时复制品。

测试辅助函数可以创建 fixture，例如：

```python
def write_skill(root, *, directory: str, name: str, description: str) -> None:
    skill_dir = root / directory
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        "---\n\n"
        "# Test Skill\n",
        encoding="utf-8",
    )
```

该辅助函数只负责构造测试输入，不得承担发现或解析。

### RED 验证

- [ ] **Step 1：只修改测试，不修改实现或 fixture**

- [ ] **Step 2：运行定向测试并保留失败摘要**

```bash
.venv/bin/python -m pytest tests/examples/phase1/test_middleware_skills.py -q
```

预期：至少因 `load_skills_metadata` 不存在、项目 fixture 不可解析或手工扫描无法提供 description/path 而失败。失败必须是预期行为缺失，不能是语法错误、错误 import 或测试本身异常。把失败测试名、退出码和一段最小错误摘要记录到 evidence 的 RED 区域。

- [ ] **Step 3：提交 RED 测试**

```bash
git add tests/examples/phase1/test_middleware_skills.py docs/verification/phase-1-evidence.md
git diff --cached --name-only
git commit -m "test: require real skills middleware loading"
```

预期暂存清单只有上述 2 个文件。允许该提交处于测试失败状态，因为它是明确记录的 TDD RED commit。

## 9. Task 2：实现真实生命周期加载与合法 fixture

### 文件

- Modify: `examples/phase1/_07_middleware_skills.py`
- Modify: `examples/phase1/skills/source-review/SKILL.md`
- Test: `tests/examples/phase1/test_middleware_skills.py`

### 步骤

- [ ] **Step 1：修正项目 Skill fixture**

严格按第 6 节添加 YAML frontmatter。父目录名与 `name` 必须一致。

- [ ] **Step 2：删除伪加载接口**

彻底删除 `list_loaded_skill_names()` 及其直接目录扫描逻辑，同时删除仅为该逻辑存在的 import。不得保留为 fallback。

- [ ] **Step 3：实现固定 helper**

按第 5 节精确实现 `load_skills_metadata()`。不得访问 `middleware.sources`，不得捕获并吞掉解析 warning，不得把目录名拼成元数据。

- [ ] **Step 4：运行定向 GREEN**

```bash
.venv/bin/python -m pytest tests/examples/phase1/test_middleware_skills.py -q
.venv/bin/ruff check examples/phase1/_07_middleware_skills.py tests/examples/phase1/test_middleware_skills.py
.venv/bin/ruff format --check examples/phase1/_07_middleware_skills.py tests/examples/phase1/test_middleware_skills.py
```

预期：全部通过。warning 断言必须与 DeepAgents 0.6.12 的真实日志语义一致，不得为了匹配测试 monkeypatch 框架日志。

- [ ] **Step 5：静态检查不存在手工扫描证明**

```bash
rg -n "iterdir|os\.listdir|glob|rglob" examples/phase1/_07_middleware_skills.py tests/examples/phase1/test_middleware_skills.py
```

预期：无输出，`rg` 退出码为 1。该退出码表示“未匹配”，是本门禁的通过结果。

- [ ] **Step 6：提交实现**

```bash
git add examples/phase1/_07_middleware_skills.py examples/phase1/skills/source-review/SKILL.md
git diff --cached --name-only
git commit -m "fix: load phase one skill metadata through middleware"
```

预期暂存清单只有上述 2 个文件。

## 10. Task 3：让编号示例展示真实解析结果

### 文件

- Modify: `examples/phase1/07_middleware_skills.py`
- Modify: `examples/phase1/README.md`
- Test: `tests/examples/phase1/test_middleware_skills.py`

### 固定行为

编号示例不得再动态创建无 frontmatter 的临时 skill。改为加载仓库内：

```python
skills_root = Path(__file__).resolve().parent / "skills"
skills_mw = create_skills_middleware(skills_root)
metadata = load_skills_metadata(skills_mw, runtime=Runtime())
```

安全输出格式固定为每个 skill 一行：

```text
  - source-review: Reviews source materials for credibility and consistency when validating technical claims.
```

输出不得包含完整正文、完整 system prompt、绝对临时目录、Key 或任意环境变量。若 metadata 为空，打印明确错误到 stderr 并返回非零，不得伪装成功。

`examples/phase1/README.md` 必须明确：

- `middleware-skills` 无 Key 可运行；
- skill 使用 Agent Skills YAML frontmatter；
- metadata 由 `SkillsMiddleware.before_agent()` 加载；
- `modify_request()` 注入仅在离线测试中验证，不调用模型。

### 步骤

- [ ] **Step 1：为 CLI 输出添加失败测试**

在同一测试文件中通过现有 runner 测试习惯或直接调用 `main()`，断言退出码 0，stdout 包含合法 name/description，不包含 skill 规则正文和敏感标记。

- [ ] **Step 2：运行测试确认 RED**

```bash
.venv/bin/python -m pytest tests/examples/phase1/test_middleware_skills.py -q
```

预期：新增 CLI 断言因旧输出或旧实现失败。记录简短 RED 结果。

- [ ] **Step 3：最小修改示例和 README**

只实现上述固定行为，不修改 RecordingMiddleware 功能。

- [ ] **Step 4：验证 GREEN 与无 Key 运行**

```bash
env -u MODEL_API_KEY .venv/bin/python -m examples.phase1.runner middleware-skills
.venv/bin/python -m pytest tests/examples/phase1/test_middleware_skills.py -q
```

预期：命令退出 0；真实解析的 name/description 出现在输出中。

- [ ] **Step 5：提交示例**

```bash
git add examples/phase1/07_middleware_skills.py examples/phase1/README.md tests/examples/phase1/test_middleware_skills.py
git diff --cached --name-only
git commit -m "feat: demonstrate parsed phase one skill metadata"
```

## 11. Task 4：纠正 ADR、状态、证据和变更记录

### 文件

- Modify: `docs/phase-status.md`
- Modify: `docs/verification/phase-1-evidence.md`
- Modify: `docs/adr/0002-deepagents-version-and-api-surface.md`
- Modify: `CHANGELOG.md`
- Modify only if needed: `README.md`

### 必须记录的事实

1. Phase 1-1 的“SkillsMiddleware skills_metadata 需要完整 LangGraph runtime”结论错误；`Runtime()` 足以离线调用公开 `before_agent()`；
2. 旧 `list_loaded_skill_names()` 是直接文件扫描，只证明文件存在，不证明 middleware 接受 skill；
3. Phase 1-2 使用真实 `before_agent()` 得到 `SkillMetadata`；
4. `modify_request()` 注入在无模型条件下通过行为测试；
5. 无效单个 skill 主要通过框架 warning 暴露，`skills_load_errors` 面向 source 级加载错误，证据不得混淆；
6. helper 文件 `_05_interrupt_resume.py`、`_06_backend_store_memory.py`、`_07_middleware_skills.py` 曾超出 Phase 1-1 原允许清单；它们是为保持编号示例短小、可运行和可测试而引入的聚焦 helper。记录该偏差，不新增第四个 helper；
7. 此次未执行真实模型 smoke；integration 在无 Key 时保持诚实 skip；
8. Phase 1 仍未获用户最终验收，tag 不存在。

### 文档状态

在 Task 4 完成后，`docs/phase-status.md` 中 Task 0-4 标为 completed，Task 5 保持 in_progress；总状态仍是 `in_progress`，不得提前写 `awaiting_user_acceptance`。

### 提交

```bash
git add docs/phase-status.md docs/verification/phase-1-evidence.md docs/adr/0002-deepagents-version-and-api-surface.md CHANGELOG.md
git diff --cached --name-only
git commit -m "docs: finalize phase one skills evidence"
```

若 root `README.md` 确实修改，必须显式追加到 `git add` 并在 evidence 解释必要性。

## 12. Task 5：全量验收、回填 SHA 和停止

### 12.1 依赖与测试门禁

按顺序执行，并在 `docs/verification/phase-1-evidence.md` 记录命令、退出码、关键摘要和执行日期：

```bash
git status --short
uv sync --extra dev --frozen
.venv/bin/python -m pytest tests/examples/phase1/test_middleware_skills.py -q
.venv/bin/python -m pytest tests/ -q
.venv/bin/python -m pytest tests/integration/phase1 -q
.venv/bin/ruff check app examples tests scripts
.venv/bin/ruff format --check app examples tests scripts
.venv/bin/pre-commit run --all-files
.venv/bin/detect-secrets scan --baseline .secrets.baseline
env -u MODEL_API_KEY .venv/bin/python -m examples.phase1.runner middleware-skills
rg -n "iterdir|os\.listdir|glob|rglob" examples/phase1/_07_middleware_skills.py tests/examples/phase1/test_middleware_skills.py
git diff --check
git status --short
```

预期：

- `uv sync --frozen` 不修改 lock；
- Skills 定向测试全部通过；
- 全量 unit tests 全部通过，数量以真实输出为准，不预填；
- integration 在没有 `MODEL_API_KEY` 时仍为 2 skipped，退出码 0；如实际数量变化，记录真实值并解释；
- Ruff、pre-commit、detect-secrets 全部退出 0；
- `middleware-skills` 无 Key 退出 0，并输出真实 name/description；
- 直接扫描 `rg` 无匹配并退出 1，此处退出 1 是通过；
- 最终 `git diff --check` 退出 0；
- 最终工作树 clean。

若 detect-secrets 造成 `.secrets.baseline` 仅时间戳变化：

```bash
git diff -- .secrets.baseline
git restore .secrets.baseline
```

只允许在确认差异仅为工具生成时间戳后恢复；若发现真实 baseline 内容变化，必须分析、记录并显式提交。

### 12.2 最终状态回填

所有门禁通过后：

- `docs/phase-status.md`：Phase 1-2 Task 0-5 全部 completed；
- Phase 总状态：`awaiting_user_acceptance`；
- Target Tag：仍写“用户验收通过后创建”；
- Next Step：用户独立验收 Phase 1-2；
- 回填 Task 0-4 的真实 commit SHA；
- Task 5 的 commit 先写 `pending final evidence commit`，提交后再用单独提交回填真实 SHA；
- Evidence 包含 RED/GREEN、最终门禁、测试/skip、已知限制和 commit 表；
- 不得把未运行真实模型 smoke 写成通过。

### 12.3 最终两次文档提交

第一次提交最终门禁证据：

```bash
git add docs/phase-status.md docs/verification/phase-1-evidence.md
git diff --cached --name-only
git commit -m "docs: verify phase one skills remediation"
```

获取真实 SHA 后只回填 Task 5：

```bash
git rev-parse --short HEAD
git add docs/phase-status.md docs/verification/phase-1-evidence.md
git diff --cached --name-only
git commit -m "docs: record phase one-two final task sha"
```

最后重新运行：

```bash
git status --short
git diff --check
git tag --list v0.0-deepagents-examples
```

预期：工作树 clean；diff check 退出 0；tag 无输出。

## 13. 预期提交序列

除最终 SHA 回填外，每个提交都必须具有可独立审查的单一目的：

```text
docs: start phase one skills remediation
test: require real skills middleware loading
fix: load phase one skill metadata through middleware
feat: demonstrate parsed phase one skill metadata
docs: finalize phase one skills evidence
docs: verify phase one skills remediation
docs: record phase one-two final task sha
```

不得 squash、amend 已有 Phase 1/1-1 提交，不得 rebase 或 force push。

## 14. 最终验收清单

- [ ] 项目 skill 具有合法 YAML frontmatter。
- [ ] 父目录名与 frontmatter `name` 一致。
- [ ] 使用真实 `SkillsMiddleware` 实例。
- [ ] 使用真实 `Runtime()` 和公开 `before_agent()`。
- [ ] 返回 metadata 包含精确 name、description、path。
- [ ] 无 frontmatter skill 被跳过并产生 warning。
- [ ] 目录/name 不匹配被跳过并产生 warning。
- [ ] 空 source 返回空 metadata，不伪造名称。
- [ ] 已存在 `skills_metadata` 时返回 `None`。
- [ ] `modify_request()` 将 name/description 注入 system message。
- [ ] 实现和验证测试不存在直接目录扫描。
- [ ] 编号示例无 Key 退出 0，并只输出安全 metadata。
- [ ] 现有 RecordingMiddleware 行为测试继续通过。
- [ ] 全量测试、lint、format、hooks、secret scan 通过。
- [ ] integration 无 Key 时诚实 skip。
- [ ] Evidence 包含真实 RED/GREEN 和最终退出码。
- [ ] ADR 修正“需要完整 LangGraph runtime”的错误说法。
- [ ] helper 文件范围偏差已记录，未新增 helper。
- [ ] Git 工作树 clean。
- [ ] `v0.0-deepagents-examples` 不存在。
- [ ] 未开始 Phase 2。

## 15. 遇到失败时的停止规则

出现以下任一情况，停止当前 Task，记录命令、退出码、最小错误摘要和已尝试动作，不得自行扩展范围：

1. 已安装 API 签名与第 4 节不兼容；
2. 必须升级依赖或修改 `uv.lock` 才能继续；
3. 必须修改禁止范围文件；
4. 真实 middleware 生命周期必须访问网络或模型；
5. 原有非 Skills 测试因本阶段修改发生回归；
6. 发现与用户改动冲突；
7. 需要删除、重写历史或移动 tag。

报告 blocker 后等待用户决定。不得把 blocker 写成 known limitation 后继续宣布完成。

## 16. DeepSeek 完成时的固定汇报格式

```text
Phase 1-2 完成 — 等待用户验收

1. 修改文件清单
   - 路径：职责与变更摘要

2. 全部 commit SHA
   - SHA message

3. RED 证据
   - 命令、退出码、失败测试名、失败原因

4. GREEN 与最终门禁
   - 每条命令、退出码、测试 passed/skipped 数量
   - `rg` 无匹配时明确说明 exit 1 是预期通过

5. Skills 真实行为证据
   - 解析出的 name、description、path 后缀
   - 无效 frontmatter 与 name mismatch 的 warning 结果
   - load-once 与 modify_request 结果

6. Git 状态
   - `git status --short` 原始结果
   - Phase 1 tag 查询结果

7. 剩余限制或 blocker
   - 没有则写“无”

8. 当前状态
   - awaiting_user_acceptance
   - 未创建 v0.0-deepagents-examples
   - 未开始 Phase 2
```

完成汇报后立即停止，等待用户独立验收。
