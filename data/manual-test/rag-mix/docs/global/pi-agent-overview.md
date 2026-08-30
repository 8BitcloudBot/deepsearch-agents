# PI Agent（pi coding agent）概览

> 来源：pi.dev 官网、GitHub earendil-works/pi（原 badlogic/pi-mono）、Mario Zechner 设计文章（2025-11-30）。整理日期 2026-08-30。

## 定位与设计哲学

Pi 是一个**极简 agent harness**（官方表述："Pi is a minimal agent harness"），理念是"Adapt Pi to your workflows, not the other way around"——让工具适配工作流，而非反过来。由 Earendil Inc. 开发，MIT 许可证。

Pi 刻意**不内置**以下常见能力：MCP、sub-agents、权限弹窗、plan mode、内置 to-dos、后台 bash——全部可以通过扩展机制自建（例如用 tmux 扩展替代后台 bash 和 sub-agents）。系统提示词极简，因此 token 效率高；项目内可用 SYSTEM.md 按项目替换或追加系统提示词。

## 包结构

Pi 是一个 monorepo（pi-mono），核心包包括：

- `@earendil-works/pi-coding-agent`：交互式 coding agent CLI（源码位于仓库 `packages/coding-agent` 目录）
- `pi-ai`：统一的 LLM API 层，agent loop 在此处理完整编排——处理用户消息、执行工具调用、把结果回喂给模型
- `pi-web-ui`：Web UI 组件

## 扩展机制

- **Extensions**：TypeScript 模块，可访问 tools、commands、快捷键、events 和完整 TUI；官方提供 50+ 示例扩展（subagent、plan-mode、permission-gate、protected-paths、ssh、sandbox 等）
- **Skills**：按需加载的能力包（含指令与工具），实现渐进式披露（progressive disclosure）；无 MCP 时可用带 README 的 CLI 工具替代
- **Prompt templates**：Markdown 文件，输入 `/name` 展开
- **Themes** 与 AGENTS.md 支持（从 `~/.pi/agent/`、父目录、当前目录三级加载）
- **自定义 Compaction**：可替换的自动摘要机制（压缩旧消息）
- 修改后用 `/reload` 热重载；第三方扩展示例：Ben Vinegar 的 `@termdraw/pi`（在终端画图），社区甚至有跑 DOOM 的扩展

## LLM 支持

支持 **15+ LLM 提供商**：Anthropic、OpenAI、Google、Azure、Bedrock、Mistral、Groq、Cerebras、xAI、Hugging Face、Kimi For Coding、MiniMax、NVIDIA、OpenRouter、Ollama 等；支持 API key 或 OAuth 认证。会话内用 `/model` 或 Ctrl+L 切换模型，Ctrl+P 循环收藏模型；可通过 `models.json` 或扩展添加自定义 provider。

## 安装

- Linux/macOS：`curl -fsSL https://pi.dev/install.sh | sh`
- Windows：`powershell -c "irm https://pi.dev/install.ps1 | iex"`
- npm：`npm install -g --ignore-scripts @earendil-works/pi-coding-agent`（pnpm/bun 同理）

## 四种运行模式

1. **Interactive**：完整 TUI 交互
2. **Print/JSON**：`pi -p "query"` 单发查询、`--mode json` 结构化输出
3. **RPC**：stdin/stdout 上的 JSON 协议，供宿主程序驱动
4. **SDK**：嵌入式使用（OpenClaw 项目即基于 Pi SDK）

## Pi packages 分发

extensions、skills、prompts、themes 可打包为 Pi packages，通过 npm 或 git 分发：

- `pi install npm:@foo/pi-tools`
- `pi install git:github.com/badlogic/pi-doom`
