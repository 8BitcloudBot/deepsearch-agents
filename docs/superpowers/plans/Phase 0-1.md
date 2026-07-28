# Phase 0-1 验收阻塞修复实施计划

> 本文档只修复 Phase 0 验收阻塞，不新增 Phase 1 能力。完成后仍需用户确认，才能创建 v0.0-foundation。

## 1. 修复目标

将当前状态推进到证据完整、命令可复现、可正式验收：

1. 修复 scripts/doctor.py 的 Ruff 格式问题。
2. 安装并验证 mysql-connector-python，使 MySQL 正常运行时 doctor --mysql 返回 0。
3. 完成 pre-commit 和 detect-secrets 的真实执行。
4. 固定 Node.js 22，并使用与 .nvmrc 一致的版本复验前端。
5. 处理未跟踪的 docs/superpowers/ 文档，消除工作树歧义。
6. 修正 docs/phase-status.md 的过期 Next Steps、阻塞项和偏差记录。
7. 清理并重写 Phase 0 验收证据，只保留真实执行结果。
8. 验收未通过前禁止创建 v0.0-foundation，禁止开始 Phase 1。

## 2. 当前问题与根因

| 问题 | 当前证据 | 根因 | 修复判定 |
|---|---|---|---|
| Ruff format 失败 | scripts/doctor.py 会被重新格式化 | 只执行 lint，没有执行格式化修复 | ruff format --check 返回 0 |
| MySQL doctor 非 0 | 缺少 mysql-connector-python，返回 2 | 依赖安装受 PyPI 网络限制 | MySQL 启动时返回 0，停止时返回非 0 |
| pre-commit 未运行 | pre-commit 未安装 | PyPI 网络限制 | pre-commit run --all-files 返回 0 |
| detect-secrets 未运行 | 仅使用手工正则扫描 | 正式 hook 未安装 | 正式扫描返回 0 |
| Node 版本不一致 | .nvmrc=22，记录使用 Node 25 | 未切换到项目锁定版本 | node --version 为 22.x |
| 工作树有未跟踪文档 | ?? docs/superpowers/ | 设计文档未纳入提交策略 | 明确提交，最终状态可解释 |
| 状态文档过期 | Next Steps 仍是 Task 0 | 完成后未同步文案 | Next Steps 指向用户验收 |
| 证据夸大 | 记录未执行 checks 为通过 | 证据更新不严谨 | 只保留真实命令和限制 |

## 3. 允许修改范围

默认只允许修改：

- scripts/doctor.py
- docs/phase-status.md
- docs/verification/phase-0-evidence.md
- README.md
- CHANGELOG.md
- .nvmrc
- docs/superpowers/specs/*
- docs/superpowers/plans/*

如需修改 pyproject.toml，只能确认或修正已有 mysql-connector-python dev 依赖，不得引入业务依赖。

禁止修改 app/业务代码、前端功能代码、docker-compose.yml 业务配置、Agent、工具、RAG、WebSocket、报告、数据目录和 Phase 1 计划。

## 4. 执行步骤

### Task 0: 建立修复状态

开始前将 docs/phase-status.md 更新为：

- Phase: 0-1 — Acceptance Blocker Remediation
- Status: in_progress
- Blockers: mysql connector, pre-commit/detect-secrets, ruff format, Node version, untracked docs

Next Steps 改为：完成 Phase 0-1 修复，重新执行完整验收；通过后等待用户确认并创建 v0.0-foundation。

### Task 1: 修复 Ruff 格式

先执行失败复核：

    .venv/bin/ruff format --check app tests scripts

对 scripts/doctor.py 执行最小格式化：

    .venv/bin/ruff format scripts/doctor.py
    .venv/bin/ruff format --check app tests scripts
    .venv/bin/ruff check app tests scripts

验收：format check 和 lint 均返回 0，不改变 doctor 行为、退出码或接口。提交：
style: format phase zero doctor

### Task 2: 完成 MySQL doctor 验证

确认 pyproject.toml 的 dev extra 包含：

    mysql-connector-python>=9.2,<10

安装依赖：

    uv sync --extra dev
    .venv/bin/python -c "import mysql.connector; print(mysql.connector.__version__)"

启动并检查 MySQL：

    docker compose up -d mysql
    docker compose ps mysql
    docker compose exec -T mysql mysql -uroot -proot -e "SELECT status FROM research_copilot.phase_0_health;"

运行：

    .venv/bin/python scripts/doctor.py --offline
    .venv/bin/python scripts/doctor.py --mysql

预期 offline exit 0，mysql running exit 0，并输出 phase_0_health table contains 'ok'。停止服务后再次运行 doctor --mysql，必须返回非 0，并输出可操作的连接失败提示。提交：
fix: verify mysql doctor against health table

### Task 3: 真实执行 pre-commit 与 detect-secrets

运行：

    pre-commit --version
    detect-secrets --version
    pre-commit install
    pre-commit run --all-files
    pre-commit run --all-files
    detect-secrets scan --baseline .secrets.baseline

若第一次 hook 自动修改文件，查看修改并再次运行，第二次必须返回 0。用临时文件测试假密钥发现能力，随后删除临时文件，不得提交 fixture。提交：
ci: complete phase zero local hooks

### Task 4: 固定 Node.js 版本并复验前端

使用 .nvmrc 指定的 Node 22.x，确认：

    node --version
    pnpm --version

然后运行：

    pnpm --dir frontend install --frozen-lockfile
    pnpm --dir frontend exec vitest run
    pnpm --dir frontend lint
    pnpm --dir frontend build

不要使用会进入 watch 模式的 pnpm test -- --run 作为唯一证据。提交：
chore: verify frontend with pinned node

### Task 5: 处理 docs/superpowers 未跟踪文档

查看：

    git status --short
    find docs/superpowers -type f -maxdepth 4 -print

这些文档是项目设计基线和实施计划，应作为明确 Git 文档提交：

    git add docs/superpowers
    git commit -m "docs: add project design and implementation plans"

禁止使用 git add .。最终 git status --short 应为空。

### Task 6: 重写证据并完成最终门禁

更新 docs/verification/phase-0-evidence.md：

- 删除未实际执行的“通过”表述；
- 分开记录通过、失败和环境阻塞；
- 记录所有工具版本、commit SHA、时间和退出码；
- 记录 MySQL running/stopped 两条 doctor 结果；
- 记录第二次 pre-commit 结果；
- 记录 Node 22 下的前端结果；
- 记录最终工作树状态；
- 保留真实限制，不隐藏网络问题。

最终命令：

    git status --short
    .venv/bin/python -m pytest tests/ -q
    .venv/bin/ruff check app tests scripts
    .venv/bin/ruff format --check app tests scripts
    pnpm --dir frontend exec vitest run
    pnpm --dir frontend lint
    pnpm --dir frontend build
    docker compose config
    .venv/bin/python scripts/doctor.py --offline
    docker compose up -d mysql
    .venv/bin/python scripts/doctor.py --mysql
    docker compose down
    pre-commit run --all-files
    detect-secrets scan --baseline .secrets.baseline

只有全部必要命令返回 0，且停止 MySQL 的 doctor 明确返回非 0，才能把状态改为 awaiting_user_acceptance。此时提交：
docs: finalize phase zero acceptance evidence

## 5. 不通过条件

出现任一条件就不能创建 tag：

- MySQL 正常运行时 doctor --mysql 非 0；
- Ruff format check 非 0；
- pre-commit 未执行或第二次仍失败；
- detect-secrets baseline 扫描非 0；
- Node 版本不是 22.x；
- 工作树存在未解释的未跟踪文件；
- 证据中包含未执行命令的“通过”；
- phase-status.md 存在过期 Next Steps；
- 引入 Phase 1+ 代码或依赖。

## 6. 可直接交给 DeepSeek 的指令

请在 /Users/wxhu/Documents/reasonix/deepsearch-agents 执行 docs/superpowers/plans/Phase 0-1.md。

本任务只修复 Phase 0 验收阻塞，不实现 Phase 1 或任何 Agent 业务能力。严格按 Task 0 到 Task 6 顺序执行，直接开始，不要等待再次确认。只能修改 Phase 0-1 文档允许的文件，禁止新增 Agent、工具、RAGFlow、Tavily、WebSocket、报告、业务数据或复杂 UI。

必须完成：
1. ruff format scripts/doctor.py，并确保 format check 返回 0。
2. 安装 mysql-connector-python；MySQL 运行时 doctor --mysql 必须返回 0；MySQL 停止时必须返回非 0。
3. 真实运行 pre-commit run --all-files，第二次也必须返回 0。
4. 真实运行 detect-secrets scan --baseline .secrets.baseline。
5. 使用 .nvmrc 指定的 Node 22.x，重新运行前端 vitest、lint、build。
6. 将 docs/superpowers 下文档作为明确 Git 文档提交，禁止 git add .。
7. 修正 phase-status.md 的过期 Next Steps、Blockers、Deviations 和当前状态。
8. 重写 verification evidence，只记录真实命令和结果。
9. 每个 Task 开始前更新 phase-status，每个 Task 完成后更新证据、README、CHANGELOG（确有变化才修改）。
10. 每个 Task 使用独立 Conventional Commit。

遇到网络或环境阻塞时，记录真实错误并停止，不伪造结果。最终不要创建 v0.0-foundation tag；完成后输出所有 commit SHA、测试结果、git status 和剩余阻塞。只有用户确认验收后才允许创建 tag 和进入 Phase 1。

