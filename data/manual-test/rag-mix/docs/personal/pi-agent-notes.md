# PI Agent 进阶笔记（个人）

> 来源：pi.dev、GitHub earendil-works/pi。整理日期 2026-08-30。本文件为个人笔记库内容。

## 树状 Session 管理

Pi 的 session 以**树结构**存储于单个文件内：

- `/tree` 可导航到任意历史节点并从该点分叉继续（fork）
- 支持按消息类型过滤、标记 bookmark
- `/export` 导出为 HTML
- `/share` 上传到 GitHub gist 生成可分享 URL

## Steering（转向控制）

- **Enter**：立即插入引导消息，打断剩余工具调用的执行
- **Alt+Enter**：排队 follow-up 消息，等 agent 完成当前工作后送达

这套机制让用户在 agent 跑偏时实时纠偏，而不需要等整轮结束。

## 系统提示词与压缩

- `SYSTEM.md` 可按项目替换或追加系统提示词（加载顺序：`~/.pi/agent/`、父目录、当前目录）
- **自定义 Compaction**：自动摘要旧消息的机制可整体替换，适配长任务
- 系统提示词本身极简——这是 pi token 效率高的直接原因

## 第三方扩展示例

- Ben Vinegar 的 `@termdraw/pi`：在终端内画图
- `pi-doom`：在 pi 里运行 DOOM（`pi install git:github.com/badlogic/pi-doom`）
- 社区扩展生态位于 GitHub topic `pi-extension`（示例覆盖 subagent、plan-mode、permission-gate、protected-paths、ssh、sandbox 等 50+ 官方示例）

## 与 OpenClaw 的关系

OpenClaw 项目基于 Pi 的 SDK 模式构建（嵌入式运行模式），pi 是 OpenClaw 的底层 harness。
