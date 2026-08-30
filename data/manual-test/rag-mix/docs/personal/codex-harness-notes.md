# Codex CLI 进阶笔记（个人）

> 来源：GitHub openai/codex（docs/ 目录、README）。整理日期 2026-08-30。本文件为个人笔记库内容。

## 沙箱与审批

Codex 的沙箱与审批文档在仓库 `docs/sandbox.md` 中以外链形式指向官方 security 文档；权限相关的交互入口是 `/permissions` 命令（"choose when Codex can edit files or run commands without asking"），执行前可 "inspect the active sandbox and writable roots"。Windows 有独立的 Windows sandbox 文档。

## 配置分层

配置文档分为三级：Config Basics、Advanced Config、Config Reference（`docs/config.md` 概述 + 外链）。管理员可在 `requirements.toml` 顶层设置 `allow_managed_hooks_only = true`，忽略用户/项目/会话级 hook 配置而仅保留 managed hooks——**该键只支持 requirements.toml，放在 config.toml 中不生效**（管理分层语义）。

## 文档目录速查

`docs/` 下实际存在的文件：`agents_md.md`、`authentication.md`、`config.md`、`contributing.md`、`exec.md`、`execpolicy.md`、`getting-started.md`、`install.md`、`skills.md`、`slash_commands.md`、`sandbox.md`、`example-config.md`、`license.md`。

## 下载源控制

安装器默认从 `releases.openai.com/codex` 下载，失败回退 GitHub Releases；设环境变量 `CODEX_INSTALLER_USE_RELEASES_OPENAI_COM=false` 可强制走 GitHub Releases——网络受控环境下的关键开关。

## 开发者入口

- 开发文档：developers.openai.com/codex（已迁移至 learn.chatgpt.com 域名下的 /docs/codex 路径，存在 308 重定向）
- 贡献指南：`docs/contributing.md`；安全策略：`SECURITY.md`
- `.devcontainer/` 与 `patches/`、`third_party/`、`tools/` 支撑源码开发
