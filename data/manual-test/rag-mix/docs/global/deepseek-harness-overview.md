# DeepSeek Harness 概览

> 来源：DeepSeek 官方博客 deepseek.com/harness/en/（Developer Preview 公告）、GitHub deepseek-ai/deepseek-harness。整理日期 2026-08-30。

## 定位

DeepSeek Harness 在 **Developer Preview** 阶段面向全球 agent harness 开发者开放，源码同步发布。核心口号："**Everything is a plugin. Every run is traceable.**"（一切皆插件，每次运行皆可追溯。）

## 插件架构

每项能力都是可替换/可重组的插件：models、tools、skills、sessions、sandboxes、storage、loops、scheduling、UI。开发者通过配置即可选择、替换或扩展任何能力，无需修改 Harness 源码。

## Cordis 内核

底层内核为 **Cordis**（github.com/cordiverse/cordis）：负责插件的挂载、卸载与依赖管理；Cordis services 与 events 机制让插件协同工作。

## 四种运行模式

1. **Standard**：完整工具集——文件编辑、shell、文件与网页搜索、skills、planning、goals、subagents、workflows
2. **Code**：Standard 全部能力，但工具经 Code Mode SDK 暴露，模型可在单个 TypeScript 程序中编排多轮工具调用
3. **Minimal**：仅两个工具（persistent bash + str_replace_editor），用于在最小环境下对模型做 benchmark
4. **Creator**：面向自定义 agent preset 的创建，含 Standard 全部能力 + 运行时检查、在内存中测试 Cordis 插件、preset 编写指导

## 可追溯性

append-only 的 session log 记录模型看到的一切——system prompts、reasoning、tool calls 与结果、subagent 调度、每次 context injection。Trajectory 视图可按来源检查条目；resume、fork、search、replay 均基于同一事件流实现。

## 安装与生态

- 快速开始（需 Node.js）：`npx @deepseek-ai/dsh web`
- 源码：`git clone https://github.com/deepseek-ai/deepseek-harness`
- 许可证：MIT；版权 "© 2026 DeepSeek"
- 社区插件：GitHub topic `dsh-plugin`
- 开发者文档：deepseek-harness.github.io/deepseek-harness/en/guide/quickstart
- 相关论文：arxiv.org/abs/2608.25512（Cordis paper）
