# Codex CLI（codex harness）概览

> 来源：GitHub openai/codex（README）、OpenAI Codex CLI 文档站。整理日期 2026-08-30。

## 定位

Codex 是 OpenAI 官方的**终端编码 agent**（官方表述："Lightweight coding agent that runs in your terminal"），本地运行于用户计算机。仓库 `openai/codex` 拥有约 **120k stars**、18.3k forks、10,016 commits，Apache-2.0 许可。

## 架构

- 核心实现为 **Rust**：`codex-rs/` 目录；另有 `codex-cli/` 与 `sdk/`（SDK 层）
- 构建体系：Bazel（`MODULE.bazel`、`BUILD.bazel`）、Nix flake、pnpm workspace、`justfile`
- 仓库自带 `AGENTS.md`（agent 指引文件约定——repo 内即用即验证）
- 相关文档：`docs/install.md`、`docs/sandbox.md`（外链到官方 security 文档）、`docs/skills.md`、`docs/exec.md`、`docs/config.md`

## 安装

- macOS/Linux：`curl -fsSL https://chatgpt.com/codex/install.sh | sh`
- Windows：`powershell -ExecutionPolicy ByPass -c "irm https://chatgpt.com/codex/install.ps1 | iex"`
- 包管理器：`npm install -g @openai/codex` 或 `brew install --cask codex`
- 预编译二进制：`codex-aarch64-apple-darwin.tar.gz`（Apple Silicon）、`codex-x86_64-unknown-linux-musl.tar.gz` 等
- 下载源默认 `releases.openai.com/codex`，失败回退 GitHub Releases

## 认证与模型

- 推荐 "Sign in with ChatGPT"（Plus/Pro/Business/Edu/Enterprise 计划），也可用 API key
- CLI 内 `/model` 命令选择模型与 reasoning effort（文档截图默认显示 `model: gpt-5.6-sol medium`）

## 扩展与集成

- **MCP**：`codex mcp` 命令添加本地或远程 MCP server 并按需认证；Codex 自身也可作为 MCP server 暴露
- IDE：VS Code、Cursor、Windsurf；桌面应用 `codex app`；云端版 Codex Web（chatgpt.com/codex）
- 自动化：`codex exec` 用于可重复的工作流与流水线
- 常用斜杠命令：`/init`（创建 AGENTS.md）、`/status`（会话配置）、`/review`（审查变更）、`/permissions`（选择 Codex 可自动执行的操作）
