# Phase 0 — Foundation and Execution Discipline

**Status:** Accepted
**Release:** `v0.0-foundation`

## Goal

建立可重复的 Python、React、Docker、MySQL、测试、CI、环境变量与密钥扫描基础，
让后续 Agent 功能在受控工程环境中开发。

## Delivered

- Python 3.12 与 uv 项目骨架；
- React/Vite 前端骨架；
- Docker Compose MySQL 与环境检查；
- pytest、Vitest、lint、format、pre-commit 和 secrets gate；
- README、ADR、状态与验收证据体系。

## Non-goals

本阶段不实现业务 Agent、真实 Provider、RAG、报告、WebSocket 或复杂 UI。

## Acceptance

环境可安装、后端和前端可测试与构建、MySQL health check 可运行、密钥不进入 Git。
该阶段已经验收，不再作为当前开发范围。
