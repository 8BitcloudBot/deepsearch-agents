# Phase 0-2 最终验收一致性修复实施计划

> 本阶段只处理 Phase 0-1 验收后的文档一致性和最终交接事项，不新增任何业务能力。完成后等待用户确认，再由用户决定是否创建 v0.0-foundation。

## 1. 目标

修复当前剩余的文档事实不一致，并形成可审计的最终验收包：

1. 将验收证据中的旧 Git 状态改为当前真实状态。
2. 将 Phase 0-1 Task 6 的 commit 从 TBD 改为真实 SHA。
3. 核对 evidence、phase-status、CHANGELOG、Git log、Git status 的一致性。
4. 明确 MySQL doctor 必须等待 Compose healthcheck healthy 后执行。
5. 重新运行必要门禁并记录真实退出码。
6. 保持工作树 clean。
7. 不创建 v0.0-foundation，不开始 Phase 1。

## 2. 当前已知问题

### 2.1 验收证据中的 Git 状态过期

文件：

docs/verification/phase-0-evidence.md

当前旧内容类似：

    M docs/phase-status.md
    Worktree clean except for in-progress status update.

实际状态已经是：

    git status --short
    # 无输出

必须改为：

    git status --short
    # clean; no untracked or unstaged files

不得保留任何暗示存在未提交修改的旧描述。

### 2.2 phase-status 的 Task 6 commit 仍为 TBD

文件：

docs/phase-status.md

Task 6 当前为：

    | 6 | Rewrite Evidence & Final Gate | completed | TBD | 14 gate items all pass |

必须改为真实提交：

    | 6 | Rewrite Evidence & Final Gate | completed | 6a8a611 | 14 gate items all pass |

如果 DeepSeek 在本次修订中产生新的文档 commit，不得覆盖历史 Task 6 SHA；新 commit 只能作为 Phase 0-2 修正文档的提交记录。

### 2.3 Docker healthcheck 等待语义需要写清楚

MySQL 容器刚启动时可能处于 health: starting，此时 doctor --mysql 可能暂时返回连接失败。最终证据必须使用以下顺序：

    docker compose up -d mysql
    for i in $(seq 1 24); do
      health_state=$(docker inspect --format '{{.State.Health.Status}}' research-copilot-mysql 2>/dev/null || true)
      printf 'health_attempt=%s health_state=%s\n' "$i" "$health_state"
      test "$health_state" = healthy && break
      sleep 5
    done
    test "$health_state" = healthy
    .venv/bin/python scripts/doctor.py --mysql

通过条件：

- health_state 最终为 healthy；
- doctor --mysql 返回 0；
- 输出 phase_0_health table contains 'ok'；
- 停止服务后 doctor --mysql 返回非 0；
- 记录启动等待过程，不能只记录一条刚启动时的失败。

## 3. 允许修改文件

本阶段只允许修改：

- docs/phase-status.md
- docs/verification/phase-0-evidence.md
- CHANGELOG.md
- README.md（仅在运行说明需要补充 healthcheck 等待时修改）
- docs/superpowers/plans/Phase 0-2.md（本计划本身如需修订）

禁止修改：

- app/、frontend/、tests/ 中的实现代码
- scripts/doctor.py
- docker-compose.yml
- pyproject.toml、uv.lock、前端锁文件
- Phase 1 计划或任何后续实现
- .env、数据库 volume、生成产物

## 4. 执行任务

### Task 0: 建立 Phase 0-2 状态

在开始修订前，将 docs/phase-status.md 更新为：

- Phase: 0-2 — Final Acceptance Consistency
- Status: in_progress
- Blockers: stale evidence and Task 6 commit metadata
- Next Steps: 修正文档并重新执行最终门禁，随后等待用户确认

记录本次修订尚未创建 tag。

### Task 1: 修正 phase-status

必须保留完整历史，不删除 Phase 0 和 Phase 0-1 记录。

修正内容：

1. Phase 0-1 Task 6 commit 改为 6a8a611。
2. Blockers 不再写 None，改为当前文档修复事项，直到 Task 4 完成。
3. Deviations 保留真实内容：
   - pnpm 通过 npx pnpm；
   - Node 22 通过 standalone binary；
   - Docker doctor 需要等待 healthcheck。
4. Next Steps 明确写：
   - 完成 Phase 0-2 文档修复；
   - 用户确认后创建 v0.0-foundation；
   - 用户授权后才编写 Phase 1 计划。

### Task 2: 修正验收证据

重写 docs/verification/phase-0-evidence.md 中 Final Gate 部分：

- Git status 改为 clean；
- 删除 “only unstaged status update”；
- Task 6 commit 使用 6a8a611；
- 增加 Phase 0-2 修订前后的 commit 对照；
- 明确 pre-commit/detect-secrets 使用 .venv/bin 执行；
- 明确 Node 22 使用 standalone binary，主机默认 Node 25 不作为验收版本；
- 增加 MySQL healthcheck 等待命令和 healthy 结果；
- 保留 stopped doctor exit 3；
- 不将 Docker 刚启动时的 transient failure 写成最终失败；
- 证据中的日期、工具版本和 commit SHA 必须与实际命令一致。

证据中禁止出现：

- 未实际执行命令的“通过”；
- 与当前 git status 不一致的旧状态；
- TBD commit；
- “全部通过”但没有列出退出码的笼统表述。

### Task 3: 重新执行最终门禁

从当前工作树执行：

    git status --short
    git log --oneline --decorate -12
    git diff --check
    .venv/bin/python -m pytest tests/ -q
    .venv/bin/ruff check app tests scripts
    .venv/bin/ruff format --check app tests scripts
    .venv/bin/pre-commit run --all-files
    .venv/bin/detect-secrets scan --baseline .secrets.baseline
    ./node_modules/.bin/vitest run
    ./node_modules/.bin/eslint src --ext .ts,.tsx
    ./node_modules/.bin/tsc -b
    ./node_modules/.bin/vite build
    docker compose config

前端命令必须在 frontend 目录执行。不要使用会进入 watch 模式的 pnpm test 作为唯一证据。

### Task 4: 重新执行 MySQL 双状态验证

启动：

    docker compose up -d mysql

等待：

    health_state=starting
    for i in $(seq 1 24); do
      health_state=$(docker inspect --format '{{.State.Health.Status}}' research-copilot-mysql 2>/dev/null || true)
      printf 'health_attempt=%s health_state=%s\n' "$i" "$health_state"
      test "$health_state" = healthy && break
      sleep 5
    done
    test "$health_state" = healthy

运行：

    .venv/bin/python scripts/doctor.py --mysql

记录 running exit 0。然后：

    docker compose down
    .venv/bin/python scripts/doctor.py --mysql

记录 stopped exit 3 或其他明确非 0，并记录 actionable error。

### Task 5: 文档自洽检查与提交

执行：

    git status --short
    rg -n 'TBD|M docs/phase-status|in-progress status update|Complete Task 0' docs/phase-status.md docs/verification/phase-0-evidence.md README.md CHANGELOG.md || true

预期：不得出现 TBD、旧 Git 状态或过期 Next Steps。

检查历史：

    git show --stat --oneline 6a8a611
    git log --oneline -- docs/phase-status.md docs/verification/phase-0-evidence.md

更新 CHANGELOG 仅在确有必要时记录 Phase 0-2 文档一致性修复。

提交：

    git add docs/phase-status.md docs/verification/phase-0-evidence.md CHANGELOG.md README.md
    git commit -m "docs: reconcile phase zero acceptance evidence"

禁止使用 git add .。

提交后将 phase-status 状态改回 awaiting_user_acceptance，并使用第二个显式文档 commit；或者在同一文档提交中完成状态更新，但必须保证最终 evidence 与 status 描述一致。

## 5. 最终验收条件

只有同时满足以下条件，Phase 0-2 才算完成：

- git status --short 无输出；
- phase-status Task 6 commit 不再是 TBD；
- evidence 不再声称存在未提交修改；
- Python 6 tests pass；
- Ruff check 和 format check 均返回 0；
- pre-commit 返回 0；
- detect-secrets 返回 0；
- 前端 vitest、eslint、tsc、vite build 均返回 0；
- docker compose config 返回 0；
- MySQL healthy 后 doctor --mysql 返回 0；
- MySQL 停止后 doctor --mysql 返回非 0；
- 禁止范围检查无 Phase 1+ 实现；
- 未创建 v0.0-foundation；
- 未编写或执行 Phase 1。

## 6. 不得做的事情

- 不得为了让 evidence 通过而修改历史 commit SHA；
- 不得把新文档 commit 填入旧 Task 6；
- 不得删除已知限制；
- 不得在 MySQL health: starting 时直接判定功能失败；
- 不得创建 v0.0-foundation；
- 不得开始 Phase 1；
- 不得添加新的业务依赖、Agent、工具或数据。

## 7. 可直接交给 DeepSeek 的指令

请在 /Users/wxhu/Documents/reasonix/deepsearch-agents 执行：

docs/superpowers/plans/Phase 0-2.md

本任务只处理 Phase 0-1 验收后的文档事实一致性和最终交接，不新增任何业务能力。严格按 Task 0 到 Task 5 执行，直接开始。

必须完成：

1. 修正 docs/verification/phase-0-evidence.md 中旧的 Git 状态描述，当前真实状态应为 clean。
2. 将 docs/phase-status.md 的 Phase 0-1 Task 6 commit 从 TBD 改为 6a8a611。
3. 记录 MySQL doctor 必须等待 Docker healthcheck 进入 healthy 后再执行；running 时必须 exit 0，stopped 时必须 exit 非 0。
4. 使用 .venv/bin/python、.venv/bin/ruff、.venv/bin/pre-commit、.venv/bin/detect-secrets 记录真实命令和结果。
5. 重新执行 Python、Ruff、pre-commit、detect-secrets、前端测试/lint/build、Docker Compose config 和 MySQL 双状态验证。
6. 检查 evidence、phase-status、CHANGELOG、git log、git status 的一致性。
7. 只修改本计划允许的文档文件，禁止修改代码、依赖、Agent、工具、RAGFlow、Tavily、WebSocket、报告、业务数据或 Phase 1。
8. 使用显式文件路径提交，禁止 git add .。
9. 最终将 phase-status 设置为 awaiting_user_acceptance。
10. 不要创建 v0.0-foundation tag，不要编写或执行 Phase 1。

遇到环境或网络问题时记录真实错误，不得伪造通过结果。完成后输出修改文件、commit SHA、全部门禁退出码、最终 git status 和剩余阻塞。

