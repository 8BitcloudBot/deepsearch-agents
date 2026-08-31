# Golden Cases（真实 LLM 评测用例集 v1）

> 固化日期 2026-09-01。用例来源：Dify 五轮 UI 实测、ragmix 18 回合剧本、
> 三场景回归（deepseek-v4-flash 真机执行）。
> 覆盖维度：单跳事实 / 多跳时间线 / 跨库对比 / 个人知识库 / 时效动态 /
> 追问承接 / 零编造（证据不足如实声明）/ Web 开关。
> 每条判据 = 必含事实词（宽松匹配）+ 证据来源预期 + 零编造检查
> （limitations 应声明证据不足而非虚构条目）。

| # | 类别 | 问题 | 必含（宽松） | 预期来源 |
|---|---|---|---|---|
| G1 | 单跳知识 | LangGraph 的图状态是如何管理的？ | 状态/检查点/持久化（任一） | 冻结语料 |
| G2 | 时效动态 | DeepSeek 官方 API 最近有什么新功能？ | 截至表述 + web 证据 | web |
| G3 | 个人知识库 | 我们公司出差返程后多长时间内必须提交报销单？ | 48 小时 | company-handbook |
| G4 | 零编造（反向） | Dify 支持接入 DeepSeek 吗？（语料无该文档时） | 无编造 + limitations 声明证据不足 | — |
| G5 | 枚举零编造 | DeepSeek Harness 的四种运行模式分别是什么？（语料含四模式节时） | Standard/Code/Minimal/Creator（部分+如实声明即可） | dsh 语料 |
| G6 | 追问承接 | 它的 RAG Pipeline 具体支持什么？Agent 能力呢？ | 承接主语 + RAG/Agent | dify 语料 |
| G7 | 跨库对比 | Dify 的 RAG Pipeline 和 RagFlow 的模板化分块分别怎么处理文档？ | 两文档来源并存 | dify+ragflow |
| G8 | 跨库模型管理 | Dify 和 RagFlow 都支持接入 LLM——模型管理上各自怎么设计的？ | 双方来源并存或单侧+声明 | dify+ragflow |
| G9 | 会话管理 | Pi 的树状 session 管理和 steering 机制是怎么工作的？ | 树/分支/排队（任一） | pi 语料 |
| G10 | Web 关闭 | （G1 关闭 use_web 复跑） | 无 web 证据出现 | 冻结语料 |

## 指标定义

- **source coverage**：证据列表中预期来源文档的占比；
- **groundedness**：回答中事实句有 claim 挂接的比例（turns 表 result JSON 可复核）；
- **unsupported-claim rate**：citation 校验判定 UNSUPPORTED 的比例
  （B9/R1 防线触发次数，limitations 可见）；
- **零编造**：G4 类问题不出现虚构条目，且 limitations 如实声明证据不足；
- **首字延迟**：提交到首个 answer.delta(partial) 的 wall clock。
